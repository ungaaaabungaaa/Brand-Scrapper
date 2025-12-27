import os
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from vercel_blob import list, delete

app = Flask(__name__)
CRON_SECRET = os.environ.get("CRON_SECRET")

@app.route('/api/cleanup')
def cleanup():
    if request.headers.get('Authorization') != f"Bearer {CRON_SECRET}":
        return "Unauthorized", 401

    now = datetime.now(timezone.utc)
    blobs = list({"prefix": "extracted/"}).get('blobs', [])
    deleted = 0
    
    for b in blobs:
        uploaded = datetime.fromisoformat(b['uploadedAt'].replace('Z', '+00:00'))
        if now - uploaded > timedelta(hours=24):
            delete(b['url'])
            deleted += 1
            
    return f"Cleaned {deleted} files", 200