import os
import json
from pathlib import Path

import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_from_directory
from jose import jwt

app = Flask(__name__)

# Config
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")

# Store files in: brand-extractor/local-dump/extracted/
BASE_DIR = Path(__file__).resolve().parents[1]
LOCAL_DUMP_DIR = BASE_DIR / "local-dump"
EXTRACTED_DIR = LOCAL_DUMP_DIR / "extracted"


def verify_jwt(token: str):
    """
    Local testing convenience:
    - If JWT_SECRET is unset, auth is skipped.
    - If JWT_SECRET is set, behaves like production and verifies HS256 token.
    """
    if not JWT_SECRET:
        return {"local": True}
    try:
        token = token.split(" ")[1] if " " in token else token
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


@app.get("/local-dump/<path:filename>")
def serve_local_dump(filename: str):
    # Serves files written to brand-extractor/local-dump/
    return send_from_directory(LOCAL_DUMP_DIR, filename)


def _safe_write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def extract_and_tag_images(pdf_content: bytes, base_url: str):
    """
    Extracts images from PDF and stores them under local-dump/extracted/.
    Returns mapping of fig.X -> http(s)://<host>/local-dump/extracted/fig.X.<ext>
    """
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(stream=pdf_content, filetype="pdf")
    tag_map = {}
    img_counter = 1

    for page_index in range(len(doc)):
        for img_info in doc[page_index].get_images(full=True):
            xref = img_info[0]
            base_image = doc.extract_image(xref)

            # Filter: ignore icons/spacers smaller than 60px
            if base_image["width"] < 60 or base_image["height"] < 60:
                continue

            tag = f"fig.{img_counter}"
            try:
                ext = base_image.get("ext") or "bin"
                filename = f"{tag}.{ext}"
                file_path = EXTRACTED_DIR / filename
                _safe_write_file(file_path, base_image["image"])

                # Important: keep URLs consistent with local route
                tag_map[tag] = f"{base_url.rstrip('/')}/local-dump/extracted/{filename}"
                img_counter += 1
            except Exception:
                pass

            if img_counter > 50:  # Absolute safety limit
                break

    return tag_map


@app.route("/api/extract-brand", methods=["GET"])
def handler():
    # 1. Security (optional locally)
    auth = request.headers.get("Authorization")
    if JWT_SECRET:
        if not auth or not verify_jwt(auth):
            return jsonify({"error": "Unauthorized"}), 401

    pdf_url = request.args.get("pdf_url")
    if not pdf_url:
        return jsonify({"error": "Missing pdf_url"}), 400

    if not OPENROUTER_API_KEY:
        return (
            jsonify(
                {
                    "error": "Missing OPENROUTER_API_KEY",
                    "brandname": "",
                    "colors": [],
                    "tagline": "",
                    "description": "",
                    "logo": "",
                    "productimages": [],
                    "bannerimages": [],
                }
            ),
            400,
        )

    try:
        # 2. Tag & Store Images Locally
        pdf_data = requests.get(pdf_url, timeout=60).content
        base_url = request.host_url
        tag_map = extract_and_tag_images(pdf_data, base_url=base_url)

        # 3. Request Gemini to categorize the tags
        available_tags = list(tag_map.keys())
        prompt = f"""
        Analyze the brand document at {pdf_url}.
        Reference the pre-extracted images: {available_tags}

        INSTRUCTIONS:
        - Extract 'brandname', 'tagline', and 'description'.
        - COLORS: Identify primary brand colors and return them ONLY as HEX CODES (e.g., #FFFFFF).
        - LOGO: Find the single cleanest logo. Once one high-quality logo is detected, move on.
        - ASSETS: Categorize remaining tags into 'productimages' or 'bannerimages'.
        - If an item is missing, return an empty string "" or empty array [].

        RETURN FORMAT:
        {{
            "brandname": "",
            "colors": ["#HEX1", "#HEX2"],
            "tagline": "",
            "description": "",
            "logo": "tag_id",
            "productimages": ["tag_id"],
            "bannerimages": ["tag_id"]
        }}
        """

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": "google/gemini-pro-1.5",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )

        data = json.loads(response.json()["choices"][0]["message"]["content"])

        # 4. Map Tags back to URLs
        data["logo"] = tag_map.get(data.get("logo"), "")
        data["productimages"] = [
            tag_map[t] for t in data.get("productimages", []) if t in tag_map
        ]
        data["bannerimages"] = [
            tag_map[t] for t in data.get("bannerimages", []) if t in tag_map
        ]

        return jsonify(data), 200

    except Exception as e:
        return (
            jsonify(
                {
                    "error": str(e),
                    "brandname": "",
                    "colors": [],
                    "tagline": "",
                    "description": "",
                    "logo": "",
                    "productimages": [],
                    "bannerimages": [],
                }
            ),
            200,
        )


if __name__ == "__main__":
    # Local dev server
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)


