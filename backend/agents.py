"""
Agent definitions for the Invoice Verification Pipeline.

5 agents:
  1. IntakeAgent     - validates image format/size (pure Python)
  2. ExtractionAgent - extracts fields + enrichment via Gemini (1 API call)
  3. ResearchAgent   - verifies model HP and dealer via Gemini + Google Search (1 API call)
  4. ValidationAgent - cross-checks extracted vs researched data (pure Python)
  5. ScoringAgent    - computes authenticity score and compliance status (pure Python)
"""

import io
import json
import re
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"

EXTRACTION_PROMPT = """You are an expert document AI agent analyzing Indian tractor invoice/quotation images.

Extract ALL of the following fields from this invoice image. Return ONLY valid JSON, nothing else.

Fields to extract:
1. dealer_name: The dealer/seller company name (e.g. "SHRI RAM TRACTORS", "SAPNA Motors").
   - NOT a bank or financial institution.
   - Look for: Motors, Tractors, Dealers, Auto, Services, M/s.

2. model_name: The tractor model name/number (e.g. "PowerTrac 434", "Mahindra 575 DI")

3. horse_power: Engine horsepower as integer (typically 25-150 HP).
   - ENGINE HP, not the model number. "PowerTrac 434" has ~42 HP, not 434.

4. asset_cost: Total invoice amount in Rupees as integer.

5. signature: Handwritten signature presence.
   - present: true/false
   - bbox: [x1_pct, y1_pct, x2_pct, y2_pct] as % of image (0-100), or []

6. stamp: Official stamp/seal presence.
   - present: true/false
   - bbox: [x1_pct, y1_pct, x2_pct, y2_pct] as % of image (0-100), or []

7. language_detected: Primary language of the document (English, Hindi, Gujarati, Marathi, Kannada, Tamil, Telugu, Punjabi, etc.)

8. state_detected: Indian state based on address, dealer location, pin code (e.g. "Haryana", "Maharashtra", "Gujarat")

9. document_type: Type of document - "invoice", "quotation", "proforma", or "receipt"

Return EXACTLY this JSON:
{
  "dealer_name": "",
  "model_name": "",
  "horse_power": 0,
  "asset_cost": 0,
  "signature": {"present": false, "bbox": []},
  "stamp": {"present": false, "bbox": []},
  "language_detected": "",
  "state_detected": "",
  "document_type": ""
}

NOTE: bbox values MUST be percentages (0-100). Return ONLY JSON, no markdown."""


@dataclass
class AgentResult:
    agent: str
    status: str  # "pass", "warn", "fail"
    time_sec: float
    decision: str
    data: dict = field(default_factory=dict)


def parse_json_response(raw_text: str) -> dict:
    """Shared JSON parser with repair logic."""
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
        text = json_match.group()
        if not text.rstrip().endswith("}"):
            text = text.rstrip() + "}"
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}

    if "horse_power" in parsed:
        hp = parsed["horse_power"]
        if isinstance(hp, (int, float)):
            parsed["horse_power"] = int(hp)
        else:
            m = re.search(r"(\d+)", str(hp))
            parsed["horse_power"] = int(m.group(1)) if m else 0

    if "asset_cost" in parsed:
        cost = parsed["asset_cost"]
        if isinstance(cost, float):
            parsed["asset_cost"] = int(cost)
        elif isinstance(cost, str):
            c = cost.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
            try:
                parsed["asset_cost"] = int(float(c))
            except ValueError:
                parsed["asset_cost"] = 0

    return parsed


# ---------------------------------------------------------------------------
# Agent 1: Intake (validate + smart preprocessing)
# ---------------------------------------------------------------------------

MAX_LONG_EDGE = 1600
JPEG_QUALITY = 90

class IntakeAgent:
    name = "intake"

    def run(self, image_bytes: bytes, filename: str) -> AgentResult:
        start = time.time()
        steps = []

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("png", "jpg", "jpeg", "webp", "heic", "heif"):
            return AgentResult(
                agent=self.name, status="fail",
                time_sec=round(time.time() - start, 2),
                decision=f"Unsupported format: .{ext}",
            )

        orig_mb = len(image_bytes) / (1024 * 1024)

        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            orig_w, orig_h = pil_img.size
        except Exception as e:
            return AgentResult(
                agent=self.name, status="fail",
                time_sec=round(time.time() - start, 2),
                decision=f"Cannot read image: {e}",
            )

        steps.append(f"{ext.upper()} {orig_w}x{orig_h} ({orig_mb:.1f}MB)")

        # Strip EXIF — removes GPS, camera metadata, embedded thumbnails
        pil_img = _strip_exif(pil_img)
        steps.append("EXIF stripped")

        # Convert to OpenCV for processing
        cv_img = cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)

        # Denoise
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # CLAHE contrast enhancement (boosts text readability)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Merge enhanced luminance back into color image
        lab = cv2.cvtColor(cv_img, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = enhanced
        cv_img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        steps.append("denoised + contrast enhanced")

        # Adaptive resize — cap longest edge at MAX_LONG_EDGE, preserve aspect ratio
        h, w = cv_img.shape[:2]
        long_edge = max(w, h)
        if long_edge > MAX_LONG_EDGE:
            scale = MAX_LONG_EDGE / long_edge
            new_w = int(w * scale)
            new_h = int(h * scale)
            cv_img = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            steps.append(f"resized {w}x{h} -> {new_w}x{new_h}")
        else:
            new_w, new_h = w, h

        # Encode to JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        _, jpeg_buf = cv2.imencode(".jpg", cv_img, encode_params)
        processed_bytes = jpeg_buf.tobytes()
        final_mb = len(processed_bytes) / (1024 * 1024)
        steps.append(f"JPEG {JPEG_QUALITY}% ({final_mb:.2f}MB)")

        reduction = ((orig_mb - final_mb) / orig_mb * 100) if orig_mb > 0 else 0

        return AgentResult(
            agent=self.name, status="pass",
            time_sec=round(time.time() - start, 2),
            decision=f"{orig_w}x{orig_h} -> {new_w}x{new_h}, {orig_mb:.1f}MB -> {final_mb:.2f}MB ({reduction:.0f}% smaller)",
            data={
                "processed_bytes": processed_bytes,
                "mime_type": "image/jpeg",
                "orig_size": {"w": orig_w, "h": orig_h, "mb": round(orig_mb, 2)},
                "new_size": {"w": new_w, "h": new_h, "mb": round(final_mb, 2)},
                "steps": steps,
            },
        )


def _strip_exif(img: Image.Image) -> Image.Image:
    """Return a copy of the image without EXIF data, handling rotation."""
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img)
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    return clean


# ---------------------------------------------------------------------------
# Agent 2: Extraction (Gemini call - fields + enrichment)
# ---------------------------------------------------------------------------

class ExtractionAgent:
    name = "extraction"

    def run(self, image_bytes: bytes, mime_type: str, client) -> AgentResult:
        start = time.time()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[EXTRACTION_PROMPT, image_part],
                )
                raw = response.text.strip()
                parsed = parse_json_response(raw)

                if not parsed or not parsed.get("dealer_name"):
                    if attempt == 0:
                        continue
                    return AgentResult(
                        agent=self.name, status="fail",
                        time_sec=round(time.time() - start, 2),
                        decision="Extraction returned empty after 2 attempts",
                    )

                fields = {
                    "dealer_name": parsed.get("dealer_name", ""),
                    "model_name": parsed.get("model_name", ""),
                    "horse_power": parsed.get("horse_power", 0),
                    "asset_cost": parsed.get("asset_cost", 0),
                    "signature": parsed.get("signature", {"present": False, "bbox": []}),
                    "stamp": parsed.get("stamp", {"present": False, "bbox": []}),
                }
                enrichment = {
                    "language_detected": parsed.get("language_detected", ""),
                    "state_detected": parsed.get("state_detected", ""),
                    "document_type": parsed.get("document_type", ""),
                }

                filled = sum(1 for k in ["dealer_name", "model_name", "horse_power", "asset_cost"]
                             if fields.get(k))
                retry_note = " (retry)" if attempt == 1 else ""

                return AgentResult(
                    agent=self.name, status="pass",
                    time_sec=round(time.time() - start, 2),
                    decision=f"Extracted {filled}/4 fields + {enrichment['language_detected']}, {enrichment['state_detected']}, {enrichment['document_type']}{retry_note}",
                    data={"fields": fields, "enrichment": enrichment},
                )

            except Exception as e:
                if attempt == 0:
                    continue
                return AgentResult(
                    agent=self.name, status="fail",
                    time_sec=round(time.time() - start, 2),
                    decision=f"API error after 2 attempts: {e}",
                )

        return AgentResult(
            agent=self.name, status="fail",
            time_sec=round(time.time() - start, 2),
            decision="Extraction exhausted retries",
        )


# ---------------------------------------------------------------------------
# Agent 3: Research (Gemini + Google Search grounding)
# ---------------------------------------------------------------------------

RESEARCH_PROMPT_TEMPLATE = """You are a research analyst verifying tractor invoice data using web search.

Given the following extracted invoice data:
- Tractor Model: {model_name}
- Claimed HP: {horse_power}
- Dealer Name: {dealer_name}
- State: {state}

Research and verify:
1. What is the ACTUAL horsepower of the "{model_name}" tractor according to manufacturer specs?
2. Is "{dealer_name}" a real, registered tractor dealer? Can you find any online presence?

Return ONLY this JSON:
{{
  "model_hp_verified": true_or_false,
  "expected_hp": integer_or_0,
  "hp_source": "brief explanation of where you found the HP info",
  "dealer_found_online": true_or_false,
  "dealer_search_summary": "brief summary of what you found about the dealer"
}}

Return ONLY JSON, no markdown."""


class ResearchAgent:
    name = "research"

    def run(self, fields: dict, enrichment: dict, client) -> AgentResult:
        start = time.time()

        model_name = fields.get("model_name", "")
        hp = fields.get("horse_power", 0)
        dealer = fields.get("dealer_name", "")
        state = enrichment.get("state_detected", "India")

        if not model_name and not dealer:
            return AgentResult(
                agent=self.name, status="warn",
                time_sec=round(time.time() - start, 2),
                decision="No model or dealer to research",
                data={"model_hp_verified": False, "expected_hp": 0,
                      "hp_source": "", "dealer_found_online": False,
                      "dealer_search_summary": ""},
            )

        prompt = RESEARCH_PROMPT_TEMPLATE.format(
            model_name=model_name, horse_power=hp,
            dealer_name=dealer, state=state,
        )

        search_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[search_tool])

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )
            raw = response.text.strip()
            parsed = parse_json_response(raw)

            if not parsed:
                return AgentResult(
                    agent=self.name, status="warn",
                    time_sec=round(time.time() - start, 2),
                    decision="Research returned unparseable response",
                    data={"model_hp_verified": False, "expected_hp": 0,
                          "hp_source": raw[:200], "dealer_found_online": False,
                          "dealer_search_summary": ""},
                )

            research = {
                "model_hp_verified": bool(parsed.get("model_hp_verified", False)),
                "expected_hp": int(parsed.get("expected_hp", 0)),
                "hp_source": str(parsed.get("hp_source", "")),
                "dealer_found_online": bool(parsed.get("dealer_found_online", False)),
                "dealer_search_summary": str(parsed.get("dealer_search_summary", "")),
            }

            parts = []
            if research["model_hp_verified"]:
                parts.append(f"HP verified ({research['expected_hp']})")
            else:
                parts.append("HP unverified")
            if research["dealer_found_online"]:
                parts.append("dealer found online")
            else:
                parts.append("dealer not found online")

            return AgentResult(
                agent=self.name, status="pass",
                time_sec=round(time.time() - start, 2),
                decision=", ".join(parts),
                data=research,
            )

        except Exception as e:
            return AgentResult(
                agent=self.name, status="warn",
                time_sec=round(time.time() - start, 2),
                decision=f"Research failed: {e}",
                data={"model_hp_verified": False, "expected_hp": 0,
                      "hp_source": "", "dealer_found_online": False,
                      "dealer_search_summary": str(e)},
            )


# ---------------------------------------------------------------------------
# Agent 4: Validation (pure Python)
# ---------------------------------------------------------------------------

class ValidationAgent:
    name = "validation"

    def run(self, fields: dict, enrichment: dict, research: dict) -> AgentResult:
        start = time.time()
        warnings = []
        errors = []

        if not fields.get("dealer_name"):
            errors.append("Dealer name missing")
        if not fields.get("model_name"):
            errors.append("Model name missing")

        hp = fields.get("horse_power", 0)
        if hp == 0:
            warnings.append("Horse power not detected")
        elif hp < 15 or hp > 200:
            warnings.append(f"HP {hp} outside typical range (15-200)")

        cost = fields.get("asset_cost", 0)
        if cost == 0:
            warnings.append("Asset cost not detected")

        sig = fields.get("signature", {})
        if not (isinstance(sig, dict) and sig.get("present")):
            warnings.append("Signature not detected")

        stamp = fields.get("stamp", {})
        if not (isinstance(stamp, dict) and stamp.get("present")):
            warnings.append("Stamp not detected")

        expected_hp = research.get("expected_hp", 0)
        hp_match = True
        if hp > 0 and expected_hp > 0:
            hp_match = abs(hp - expected_hp) <= 5
            if not hp_match:
                warnings.append(f"HP mismatch: invoice says {hp}, web says {expected_hp}")

        if not research.get("dealer_found_online"):
            warnings.append("Dealer not found in web search")

        all_fields_present = (
            bool(fields.get("dealer_name"))
            and bool(fields.get("model_name"))
            and hp > 0
            and cost > 0
            and isinstance(sig, dict) and sig.get("present")
            and isinstance(stamp, dict) and stamp.get("present")
        )

        status = "fail" if errors else ("warn" if warnings else "pass")
        parts = []
        if errors:
            parts.append(f"{len(errors)} error(s)")
        if warnings:
            parts.append(f"{len(warnings)} warning(s)")
        if not parts:
            parts.append("all checks passed")

        return AgentResult(
            agent=self.name, status=status,
            time_sec=round(time.time() - start, 2),
            decision=", ".join(parts),
            data={
                "warnings": warnings, "errors": errors,
                "hp_match": hp_match, "all_fields_present": all_fields_present,
            },
        )


# ---------------------------------------------------------------------------
# Agent 5: Scoring (pure Python)
# ---------------------------------------------------------------------------

class ScoringAgent:
    name = "scoring"

    def run(self, fields: dict, enrichment: dict, research: dict, validation: dict) -> AgentResult:
        start = time.time()
        breakdown = {}

        filled = sum(1 for k in ["dealer_name", "model_name", "horse_power", "asset_cost"]
                     if fields.get(k))
        sig_present = isinstance(fields.get("signature"), dict) and fields["signature"].get("present")
        stamp_present = isinstance(fields.get("stamp"), dict) and fields["stamp"].get("present")
        if sig_present:
            filled += 1
        if stamp_present:
            filled += 1
        breakdown["field_completeness"] = round(filled / 6 * 20)

        if research.get("model_hp_verified"):
            breakdown["hp_verification"] = 20
        elif research.get("expected_hp", 0) > 0:
            breakdown["hp_verification"] = 10
        else:
            breakdown["hp_verification"] = 0

        if research.get("dealer_found_online"):
            breakdown["dealer_verification"] = 20
        else:
            breakdown["dealer_verification"] = 0

        breakdown["signature_present"] = 15 if sig_present else 0
        breakdown["stamp_present"] = 15 if stamp_present else 0

        n_warnings = len(validation.get("warnings", []))
        n_errors = len(validation.get("errors", []))
        if n_errors == 0 and n_warnings == 0:
            breakdown["document_quality"] = 10
        elif n_errors == 0 and n_warnings <= 2:
            breakdown["document_quality"] = 5
        else:
            breakdown["document_quality"] = 0

        score = sum(breakdown.values())

        if score >= 70:
            compliance = "PASS"
        elif score >= 40:
            compliance = "REVIEW"
        else:
            compliance = "FAIL"

        parts = []
        dealer = fields.get("dealer_name", "Unknown dealer")
        state = enrichment.get("state_detected", "")
        model = fields.get("model_name", "")
        hp = fields.get("horse_power", 0)

        if dealer:
            loc = f" in {state}" if state else ""
            parts.append(f"Invoice from {'verified ' if research.get('dealer_found_online') else ''} dealer {dealer}{loc}.")
        if model and research.get("model_hp_verified"):
            parts.append(f"{model} HP confirmed at {research.get('expected_hp', hp)} HP.")
        elif model:
            parts.append(f"{model} HP could not be verified online.")
        if not sig_present and not stamp_present:
            parts.append("Both signature and stamp missing.")
        elif not sig_present:
            parts.append("Signature missing.")
        elif not stamp_present:
            parts.append("Stamp missing.")

        summary = " ".join(parts)

        return AgentResult(
            agent=self.name, status="pass",
            time_sec=round(time.time() - start, 2),
            decision=f"Score: {score}/100 - {compliance}",
            data={
                "authenticity_score": score,
                "compliance_status": compliance,
                "breakdown": breakdown,
                "summary": summary,
            },
        )
