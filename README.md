# 🏷️ Brand Extractor API

A robust Vercel Cloud Function (Python) that parses PDFs, extracts images, tags them semantically, and uses **Gemini 1.5 Pro** to categorize brand assets without memory exhaustion.

----------

## 🚀 Getting Started

### 1. Local Setup

Bash

```
# Clone and enter directory
cd brand-extractor

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

```

### 2. Environment Variables

Create a `.env` file or export these in your terminal:

Bash

```
export JWT_SECRET="your_shared_backend_secret"
export OPENROUTER_API_KEY="your_openrouter_key"
export BLOB_READ_WRITE_TOKEN="your_vercel_blob_token"
export CRON_SECRET="your_cleanup_job_password"

```


## 🧪 Testing the Extraction API

### Option A: Using cURL`enter code here`

Since the API uses HS256 JWT, you first need a test token. Use this one-liner to generate a token valid for 1 hour (requires `python-jose` installed):

Bash

```
# Generate Token
TOKEN=$(python3 -c "from jose import jwt; import datetime; print(jwt.encode({'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, '$JWT_SECRET', algorithm='HS256'))")

# Call the API
curl -X GET "http://127.0.0.1:5000/api/extract-brand?pdf_url=https://your-pdf-link.pdf" \
  -H "Authorization: Bearer $TOKEN"

```

### Option B: Using Postman

1.  **Method**: `GET`
    
2.  **URL**: `{{BASE_URL}}/api/extract-brand`
    
3.  **Params**:
    
    -   Key: `pdf_url`, Value: `https://link-to-your-brand-guide.pdf`
        
4.  **Authorization**:
    
    -   **Type**: `Bearer Token`
        
    -   **Token**: (Paste the token generated from the script above)
        
5.  **Headers**:
    
    -   `Content-Type`: `application/json`
        

----------

## 🧹 Testing the Cleanup Job

The cleanup job deletes images older than 24 hours. You can trigger it manually to ensure the `CRON_SECRET` logic is working.

### Using cURL

Bash

```
curl -i -X GET "http://127.0.0.1:5000/api/cleanup" \
  -H "Authorization: Bearer $CRON_SECRET"

```

----------

## 🛠️ Project Structure

**File**

**Description**

`api/index.py`

Main logic: PDF parsing -> Image tagging -> Gemini analysis.

`api/cleanup.py`

Cron job handler to wipe Vercel Blob storage of expired files.

`vercel.json`

Defines the API routes and the hourly cron schedule.

`requirements.txt`

Required: `pymupdf`, `vercel-blob`, `python-jose`, `requests`, `flask`.

----------

## 📡 Deployment

1.  **Push** this code to a GitHub Repository.
    
2.  **Import** to Vercel.
    
3.  **Connect Storage**: Go to the **Storage** tab in Vercel and create/connect a **Blob** store.
    
4.  **Add Envs**: Add `JWT_SECRET`, `OPENROUTER_API_KEY`, and `CRON_SECRET` in Vercel Settings.
    
5.  **Deploy**: Vercel will automatically detect the `crons` in `vercel.json`.
