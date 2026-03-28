"""
Invoice Intelligence: FastAPI Backend for Invoice Field Extraction

Accepts invoice image uploads, processes them via AI,
and returns structured JSON with extracted fields.
"""

import json
import os
import re
import time
import glob
import base64
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from google import genai
from google.genai import types
from google.oauth2 import service_account

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
RESULTS_DIR = PROJECT_ROOT / "results_vertex"
PROJECT_ID = "project-ai-api-keys"
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash"

EXTRACTION_PROMPT = """You are an expert document AI agent analyzing Indian tractor invoice/quotation images.

Extract ALL of the following fields from this invoice image. Return ONLY valid JSON, nothing else.

Fields to extract:
1. dealer_name: The dealer/seller company name (e.g. "SHRI RAM TRACTORS", "SAPNA Motors", "Aradhya Tractors").
   - This is NOT a bank or financial institution. Banks like IDFC, ICICI, HDFC are financiers, not dealers.
   - Look for words like: Motors, Tractors, Dealers, Auto, Services, M/s.

2. model_name: The tractor model name/number (e.g. "PowerTrac 434", "Mahindra 575 DI", "John Deere 5050D", "Sonalika DI 60")

3. horse_power: The engine horsepower rating as an integer (typically 25-150 HP for tractors).
   - This is the ENGINE HP, NOT the model number. "PowerTrac 434" has ~42 HP, not 434 HP.
   - Look for "HP", "Horse Power", "BHP" mentions in the document.

4. asset_cost: The total invoice/quotation amount in Indian Rupees as an integer.
   - Look for "Total", "Grand Total", "Net Amount", "Ex-Showroom Price".
   - This is typically a 5-7 digit number.

5. signature: Whether a handwritten signature is present in the image.
   - present: true/false
   - bbox: [x1_pct, y1_pct, x2_pct, y2_pct] as PERCENTAGE of image dimensions (0-100), or empty [] if not found.

6. stamp: Whether an official stamp/seal is present in the image.
   - present: true/false
   - bbox: [x1_pct, y1_pct, x2_pct, y2_pct] as PERCENTAGE of image dimensions (0-100), or empty [] if not found.

Return EXACTLY this JSON structure:
{
  "dealer_name": "actual dealer name or empty string",
  "model_name": "actual model name or empty string",
  "horse_power": integer_or_0,
  "asset_cost": integer_or_0,
  "signature": {"present": true_or_false, "bbox": [x1_pct,y1_pct,x2_pct,y2_pct] or []},
  "stamp": {"present": true_or_false, "bbox": [x1_pct,y1_pct,x2_pct,y2_pct] or []}
}

NOTE: All bbox values MUST be percentages (0-100) of the image width/height, NOT pixel values.

IMPORTANT: Return ONLY the JSON object. No markdown, no explanation, no code fences."""


app = FastAPI(title="Invoice Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gemini_client = None


@app.on_event("startup")
def startup():
    global gemini_client
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(f"Credentials not found at {CREDENTIALS_PATH}")

    credentials = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    gemini_client = genai.Client(
        vertexai=True,
        credentials=credentials,
        project=PROJECT_ID,
        location=LOCATION,
    )
    print(f"Vertex AI client ready (project={PROJECT_ID}, model={MODEL_NAME})")


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "project": PROJECT_ID}


@app.post("/api/extract")
async def extract_fields(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (PNG, JPG)")

    image_bytes = await file.read()
    filename = file.filename or "upload.png"
    doc_id = os.path.splitext(filename)[0]

    mime = file.content_type or "image/png"
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime)

    start_time = time.time()
    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=[EXTRACTION_PROMPT, image_part],
        )
        raw_text = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI extraction error: {e}")

    processing_time = round(time.time() - start_time, 2)
    parsed = _parse_response(raw_text)

    result = {
        "doc_id": doc_id,
        "fields": {
            "dealer_name": parsed.get("dealer_name", ""),
            "model_name": parsed.get("model_name", ""),
            "horse_power": parsed.get("horse_power", 0),
            "asset_cost": parsed.get("asset_cost", 0),
            "signature": parsed.get("signature", {"present": False, "bbox": []}),
            "stamp": parsed.get("stamp", {"present": False, "bbox": []}),
        },
        "confidence": _calculate_confidence(parsed),
        "processing_time_sec": processing_time,
        "cost_estimate_usd": 0.002,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    result_path = RESULTS_DIR / f"{doc_id}.json"
    with open(result_path, "w", encoding="utf-8") as f:
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


def _parse_response(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not json_match:
        return {}

    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError:
        json_text = json_match.group()
        if not json_text.rstrip().endswith("}"):
            json_text = json_text.rstrip() + "}"
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            return {}

    if "horse_power" in parsed:
        hp = parsed["horse_power"]
        if isinstance(hp, (int, float)):
            parsed["horse_power"] = int(hp)
        else:
            hp_match = re.search(r"(\d+)", str(hp))
            parsed["horse_power"] = int(hp_match.group(1)) if hp_match else 0

    if "asset_cost" in parsed:
        cost = parsed["asset_cost"]
        if isinstance(cost, float):
            parsed["asset_cost"] = int(cost)
        elif isinstance(cost, str):
            cost_clean = cost.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
            try:
                parsed["asset_cost"] = int(float(cost_clean))
            except ValueError:
                parsed["asset_cost"] = 0

    return parsed


def _calculate_confidence(parsed: dict) -> float:
    if not parsed:
        return 0.0
    filled = 0
    if parsed.get("dealer_name"):
        filled += 1
    if parsed.get("model_name"):
        filled += 1
    if parsed.get("horse_power", 0) > 0:
        filled += 1
    if parsed.get("asset_cost", 0) > 0:
        filled += 1
    sig = parsed.get("signature", {})
    if isinstance(sig, dict) and sig.get("present"):
        filled += 1
    stamp = parsed.get("stamp", {})
    if isinstance(stamp, dict) and stamp.get("present"):
        filled += 1
    return round(min(filled / 6 * 0.98, 0.98), 2)
