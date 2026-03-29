"""
Invoice Intelligence: FastAPI Backend with Agentic Pipeline

Accepts invoice image uploads, runs them through a 5-agent verification
pipeline, and returns a full report with audit trail.
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from google import genai

from orchestrator import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-ai-api-keys")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

# Cloud Run provides K_SERVICE env var; use /tmp for ephemeral storage there
if os.environ.get("K_SERVICE"):
    RESULTS_DIR = Path("/tmp/results_vertex")
    PROCESSED_DIR = Path("/tmp/processed_images")
else:
    RESULTS_DIR = PROJECT_ROOT / "results_vertex"
    PROCESSED_DIR = PROJECT_ROOT / "processed_images"

app = FastAPI(title="Invoice Intelligence API")

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gemini_client = None


@app.on_event("startup")
def startup():
    global gemini_client
    # On Cloud Run, Application Default Credentials are provided automatically
    # by the service account. For local dev, set GOOGLE_APPLICATION_CREDENTIALS
    # to a service account key file path.
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        gemini_client = genai.Client(
            vertexai=True,
            credentials=credentials,
            project=PROJECT_ID,
            location=LOCATION,
        )
    else:
        gemini_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION,
        )
    print(f"Vertex AI client ready (project={PROJECT_ID})")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/extract")
async def extract_fields(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (PNG, JPG)")

    image_bytes = await file.read()
    filename = file.filename or "upload.png"
    mime = file.content_type or "image/png"

    result = run_pipeline(image_bytes, filename, mime, gemini_client)

    doc_id = result["doc_id"]

    # Save preprocessed image
    processed_bytes = result.pop("_processed_bytes", None)
    if processed_bytes:
        PROCESSED_DIR.mkdir(exist_ok=True)
        with open(PROCESSED_DIR / f"{doc_id}.jpg", "wb") as f:
            f.write(processed_bytes)
        result["processed_image_url"] = f"/api/processed/{doc_id}"

    RESULTS_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / f"{doc_id}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


@app.get("/api/results")
def list_results():
    RESULTS_DIR.mkdir(exist_ok=True)
    files = sorted(RESULTS_DIR.glob("*.json"))
    results = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            results.append(json.load(f))
    return results


@app.get("/api/results/{doc_id}")
def get_result(doc_id: str):
    fp = RESULTS_DIR / f"{doc_id}.json"
    if not fp.exists():
        raise HTTPException(status_code=404, detail=f"Result not found: {doc_id}")
    with open(fp, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/processed/{doc_id}")
def get_processed_image(doc_id: str):
    fp = PROCESSED_DIR / f"{doc_id}.jpg"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Processed image not found")
    return Response(content=fp.read_bytes(), media_type="image/jpeg")
