import os
import json
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from jose import jwt
from vercel_blob import put

app = Flask(__name__)

# Config
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")

def verify_jwt(token):
    try:
        token = token.split(" ")[1] if " " in token else token
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except: return None

def extract_and_tag_images(pdf_content):
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
                # Upload to 'extracted/' folder for the 24h cleanup job
                blob = put(f"extracted/{tag}.{base_image['ext']}", base_image["image"], {"access": "public"})
                tag_map[tag] = blob['url']
                img_counter += 1
            except: pass
            
            if img_counter > 50: break # Absolute safety limit
    return tag_map

@app.route('/api/extract-brand', methods=['GET'])
def handler():
    # 1. Security
    auth = request.headers.get('Authorization')
    if not auth or not verify_jwt(auth): return jsonify({"error": "Unauthorized"}), 401

    pdf_url = request.args.get('pdf_url')
    if not pdf_url: return jsonify({"error": "Missing pdf_url"}), 400

    try:
        # 2. Tag & Upload Images
        pdf_data = requests.get(pdf_url).content
        tag_map = extract_and_tag_images(pdf_data)
        
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
                "response_format": { "type": "json_object" }
            }
        )
        
        data = json.loads(response.json()['choices'][0]['message']['content'])

        # 4. Map Tags back to URLs
        data['logo'] = tag_map.get(data.get('logo'), "")
        data['productimages'] = [tag_map[t] for t in data.get('productimages', []) if t in tag_map]
        data['bannerimages'] = [tag_map[t] for t in data.get('bannerimages', []) if t in tag_map]

        return jsonify(data), 200

    except Exception as e:
        return jsonify({"error": str(e), "brandname": "", "colors": [], "logo": "", "productimages": [], "bannerimages": []}), 200

def handler_adapter(request): return app(request)