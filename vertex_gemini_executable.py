#!/usr/bin/env python3
"""
IDFC Hackathon: Vertex AI Gemini Invoice Field Extraction

Uses Google Vertex AI with service account authentication to process
tractor invoice images via Gemini 2.5 Flash. Single API call per image
handles OCR, field extraction, and signature/stamp detection.

USAGE:
    python vertex_gemini_executable.py --images_folder input_images
    python vertex_gemini_executable.py --images_folder input_images --single 90019675571_OTHERS_v1_pg1.png
    python vertex_gemini_executable.py --images_folder input_images --credentials path/to/key.json
"""

import argparse
import json
import os
import sys
import time
import glob
import re

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: google-genai not installed. Run: pip install google-genai")
    sys.exit(1)

try:
    from google.oauth2 import service_account
except ImportError:
    print("ERROR: google-auth not installed. Run: pip install google-auth")
    sys.exit(1)

DEFAULT_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
DEFAULT_PROJECT_ID = "project-ai-api-keys"
DEFAULT_LOCATION = "us-central1"
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


def init_vertex_client(credentials_path, project_id, location):
    """Initialize the Gemini client via Vertex AI with service account credentials."""

    if not os.path.exists(credentials_path):
        print(f"Error: Credentials file not found: {credentials_path}")
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    client = genai.Client(
        vertexai=True,
        credentials=credentials,
        project=project_id,
        location=location,
    )

    print(f"Vertex AI client initialized")
    print(f"  Project:  {project_id}")
    print(f"  Location: {location}")
    print(f"  Model:    {MODEL_NAME}")
    print(f"  Auth:     Service account ({credentials.service_account_email})")

    return client


def process_image(client, img_path):
    """Send a single image to Vertex AI Gemini and extract all fields."""

    filename = os.path.basename(img_path)
    doc_id = os.path.splitext(filename)[0]

    print(f"  Processing: {filename}")
    start_time = time.time()

    with open(img_path, "rb") as f:
        image_bytes = f.read()

    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[EXTRACTION_PROMPT, image_part],
        )

        raw_text = response.text.strip()
        processing_time = round(time.time() - start_time, 2)

        print(f"  Response in {processing_time}s")
        print(f"  Raw: {raw_text[:200]}...")

        parsed = parse_response(raw_text)

        return {
            "doc_id": doc_id,
            "fields": {
                "dealer_name": parsed.get("dealer_name", ""),
                "model_name": parsed.get("model_name", ""),
                "horse_power": parsed.get("horse_power", 0),
                "asset_cost": parsed.get("asset_cost", 0),
                "signature": parsed.get("signature", {"present": False, "bbox": []}),
                "stamp": parsed.get("stamp", {"present": False, "bbox": []}),
            },
            "confidence": calculate_confidence(parsed),
            "processing_time_sec": processing_time,
            "cost_estimate_usd": 0.002,
        }

    except Exception as e:
        processing_time = round(time.time() - start_time, 2)
        print(f"  ERROR: {e}")
        return {
            "doc_id": doc_id,
            "fields": {
                "dealer_name": "",
                "model_name": "",
                "horse_power": 0,
                "asset_cost": 0,
                "signature": {"present": False, "bbox": []},
                "stamp": {"present": False, "bbox": []},
            },
            "confidence": 0.0,
            "processing_time_sec": processing_time,
            "cost_estimate_usd": 0.002,
            "error": str(e),
        }


def parse_response(raw_text):
    """Parse Gemini's JSON response, handling common formatting issues."""

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not json_match:
        print("  WARNING: No JSON found in response")
        return {}

    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"  WARNING: JSON parse error: {e}")
        json_text = json_match.group()
        if not json_text.rstrip().endswith("}"):
            json_text = json_text.rstrip() + "}"
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            print("  WARNING: Could not repair JSON")
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


def calculate_confidence(parsed):
    """Calculate confidence based on how many fields were extracted."""
    if not parsed:
        return 0.0

    filled = 0
    total = 6

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

    return round(min(filled / total * 0.98, 0.98), 2)


def save_result(result, img_path, output_dir="results_vertex"):
    """Save result JSON to output directory."""
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.basename(img_path)
    filename_no_ext = os.path.splitext(filename)[0]
    save_path = os.path.join(output_dir, f"{filename_no_ext}.json")

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return save_path


def main():
    parser = argparse.ArgumentParser(
        description="IDFC Hackathon: Vertex AI Gemini invoice field extraction",
    )
    parser.add_argument(
        "--images_folder",
        required=True,
        help="Path to folder containing invoice images (PNG format)",
    )
    parser.add_argument(
        "--single",
        default=None,
        help="Process only a single image filename (for testing)",
    )
    parser.add_argument(
        "--output_dir",
        default="results_vertex",
        help="Output directory for results (default: results_vertex)",
    )
    parser.add_argument(
        "--credentials",
        default=DEFAULT_CREDENTIALS_PATH,
        help=f"Path to service account JSON key (default: {DEFAULT_CREDENTIALS_PATH})",
    )
    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT_ID,
        help=f"GCP project ID (default: {DEFAULT_PROJECT_ID})",
    )
    parser.add_argument(
        "--location",
        default=DEFAULT_LOCATION,
        help=f"GCP region (default: {DEFAULT_LOCATION})",
    )

    args = parser.parse_args()

    if not os.path.exists(args.images_folder):
        print(f"Error: Images folder '{args.images_folder}' does not exist")
        sys.exit(1)

    if args.single:
        img_path = os.path.join(args.images_folder, args.single)
        if not os.path.exists(img_path):
            print(f"Error: Image '{img_path}' does not exist")
            sys.exit(1)
        image_paths = [img_path]
    else:
        image_pattern = os.path.join(args.images_folder, "*.png")
        image_paths = sorted(glob.glob(image_pattern))

    if not image_paths:
        print(f"Error: No PNG images found in '{args.images_folder}'")
        sys.exit(1)

    print(f"Found {len(image_paths)} image(s)")
    print(f"Output: {args.output_dir}/")
    print()

    client = init_vertex_client(args.credentials, args.project, args.location)
    print()

    total_start = time.time()
    results = []

    for i, img_path in enumerate(image_paths, 1):
        print(f"[{i}/{len(image_paths)}] {os.path.basename(img_path)}")

        try:
            result = process_image(client, img_path)
            save_path = save_result(result, img_path, args.output_dir)
            results.append({"image": img_path, "result": result, "saved_to": save_path, "status": "success"})

            print(f"  Dealer: {result['fields']['dealer_name']}")
            print(f"  Model:  {result['fields']['model_name']}")
            print(f"  HP:     {result['fields']['horse_power']}")
            print(f"  Cost:   {result['fields']['asset_cost']}")
            sig = result["fields"]["signature"]
            stamp = result["fields"]["stamp"]
            print(f"  Sig:    {'Yes' if sig.get('present') else 'No'} | Stamp: {'Yes' if stamp.get('present') else 'No'}")
            print(f"  Confidence: {result['confidence']}")
            print(f"  Saved: {save_path}")
            print()

        except Exception as e:
            results.append({"image": img_path, "status": "failed", "error": str(e)})
            print(f"  FAILED: {e}\n")

    total_time = time.time() - total_start
    successful = len([r for r in results if r.get("status") == "success"])
    failed = len(results) - successful

    print("=" * 60)
    print("PROCESSING COMPLETE (Vertex AI)")
    print("=" * 60)
    print(f"Total time:    {total_time:.2f}s")
    print(f"Images:        {len(image_paths)}")
    print(f"Successful:    {successful}")
    print(f"Failed:        {failed}")
    print(f"Success rate:  {successful/len(image_paths)*100:.1f}%")
    print(f"Avg per image: {total_time/len(image_paths):.2f}s")
    print(f"Results in:    {args.output_dir}/")


if __name__ == "__main__":
    main()
