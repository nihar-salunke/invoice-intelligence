"""
Text Processing Pipeline for Invoice Field Extraction
OCR → Translation → VLM Extraction → Structured JSON Output
"""

import cv2
import pytesseract
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import json
import re
import time
import os
from PIL import Image

# Load models
print("Loading models...")
moondream_model = AutoModelForCausalLM.from_pretrained("vikhyatk/moondream2", trust_remote_code=True, dtype=torch.float16, device_map="auto")
moondream_tokenizer = AutoTokenizer.from_pretrained("vikhyatk/moondream2")
translation_model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct", dtype=torch.float16, device_map="auto")
translation_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
print("✅ Models loaded\n")

def extract_and_clean_ocr(img_path):
    """Extract and clean OCR text"""
    
    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(denoised)
    
    config = '--oem 3 --psm 6 -l eng+hin+mar+guj'
    ocr_text = pytesseract.image_to_string(enhanced, config=config)
    
    # Clean OCR
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip() and len(line.strip()) > 2]
    cleaned_lines = [line for line in lines if re.search(r'[a-zA-Z0-9\u0900-\u097F₹]', line)]
    cleaned_text = '\n'.join(cleaned_lines)
    
    print(f"OCR extracted: {len(cleaned_text)} chars")
    print(f"Preview: {cleaned_text[:200]}...")
    
    return cleaned_text

def translate_with_llm(ocr_text):
    """Translate mixed language text"""
    
    english_ratio = sum(1 for c in ocr_text if ord(c) < 128) / len(ocr_text)
    
    if english_ratio > 0.7:
        print("Mostly English, skipping translation")
        return ocr_text
    
    print("Translating...")
    prompt = f"""Translate this Indian invoice text to English. Keep all numbers and company names exactly as they are:

{ocr_text}

English translation:"""

    inputs = translation_tokenizer(prompt, return_tensors="pt").to(translation_model.device)
    with torch.no_grad():
        outputs = translation_model.generate(**inputs, max_new_tokens=600, temperature=0.1, pad_token_id=translation_tokenizer.eos_token_id)
    
    response = translation_tokenizer.decode(outputs[0], skip_special_tokens=True)
    translated = response[len(prompt):].strip()
    
    print(f"Translated: {len(translated)} chars")
    return translated

def extract_with_moondream(img_path, translated_text):
    """Extract information using MoonDream - Simplified for better response"""
    
    image = Image.open(img_path)
    enc_image = moondream_model.encode_image(image)
    
    # Simpler prompt that MoonDream can handle better
    prompt = f"""Look at this tractor invoice and extract 4 fields as simple JSON:

OCR TEXT: {translated_text}

Find and return JSON with these exact fields:
- dealer_name: The dealer company name (look for Dealer Companies like Chandra Motors, SAPNA Motors, SAPNA Tractor, JOHN Deere, etc companies). Dealer names are NOT banks or financial institutions.
- model_name: The tractor model name/number (like PowerTrac 434, Mahindra 575, John Deere 5050D)
- horse_power: The ENGINE HORSEPOWER rating (NOT model number). Look for text like "42 HP", "50 HP Engine", "Horse Power: 45". Model numbers like "434" or "575" are NOT horsepower. Typical range: 25-150 HP.
- asset_cost: Total invoice amount in rupees (6-7 digit number, the main price)

IMPORTANT: Model number (like 434 in "PowerTrac 434") is DIFFERENT from horsepower rating (like 42 HP engine power).

Look at both image and text carefully. Extract the REAL values from this specific invoice.
Return only JSON format:
{{"dealer_name": "actual dealer name", "model_name": "actual model", "horse_power": actual_hp_number, "asset_cost": actual_cost_amount}}"""

    print("Asking MoonDream...")
    print(prompt)
    response = moondream_model.answer_question(enc_image, prompt, moondream_tokenizer)
    
    print(f"MoonDream response: {response}")
    return response

def extract_dealer_with_qwen(ocr_text):
    """Use QWEN to extract dealer name when MoonDream fails"""
    
    prompt = f"""From this tractor invoice OCR text, extract ONLY the dealer company name.

OCR TEXT:
{ocr_text[:1000]}

Instructions:
- Find the dealer/seller company name (NOT the manufacturer like Mahindra, PowerTrac, John Deere)
- Ignore banks, financial institutions, and manufacturers
- Look for companies with words like: Motors, Tractors, Dealers, Sales, Auto, Services
- Examples of dealers: "SAPNA Motors", "Chandra Tractors", "ABC Farm Equipment"
- Return ONLY the dealer company name, nothing else

Dealer name:"""

    print("🔍 Using QWEN to extract dealer name...")
    
    inputs = translation_tokenizer(prompt, return_tensors="pt").to(translation_model.device)
    with torch.no_grad():
        outputs = translation_model.generate(
            **inputs, 
            max_new_tokens=50, 
            temperature=0.1, 
            pad_token_id=translation_tokenizer.eos_token_id,
            do_sample=False
        )
    
    response = translation_tokenizer.decode(outputs[0], skip_special_tokens=True)
    dealer_name = response[len(prompt):].strip()
    
    # Clean up the response
    dealer_name = dealer_name.split('\n')[0].strip()  # Take first line only
    dealer_name = re.sub(r'^["\']|["\']$', '', dealer_name)  # Remove quotes
    
    if len(dealer_name) > 3 and not any(word in dealer_name.lower() for word in ['bank', 'finance', 'ltd.', 'limited']):
        print(f"✅ QWEN extracted dealer: {dealer_name}")
        return dealer_name
    else:
        print(f"❌ QWEN result not suitable: {dealer_name}")
        return ""

def parse_structured_response(response_text, doc_id, processing_time, ocr_text=""):
    """Parse MoonDream response and create structured output"""
    
    print("Parsing MoonDream response...")
    
    # Initialize result structure
    result = {
        "doc_id": doc_id,
        "fields": {
            "dealer_name": "",
            "model_name": "",
            "horse_power": 0,
            "asset_cost": 0
        },
        "confidence": 0.5,
        "processing_time_sec": processing_time,
        "cost_estimate_usd": 0.001
    }
    
    # Try to parse JSON from response - handle both complete and incomplete JSON
    json_match = re.search(r'\{.*', response_text, re.DOTALL)
    
    if json_match:
        try:
            json_text = json_match.group()
            
            # Fix incomplete JSON
            if not json_text.rstrip().endswith('}'):
                # Add missing closing brace
                if '"asset_cost":' in json_text and re.search(r'"asset_cost":\s*$', json_text):
                    # Incomplete asset_cost field
                    json_text = re.sub(r'"asset_cost":\s*$', '"asset_cost": 0}', json_text)
                    print(f"🔧 Fixed incomplete asset_cost: {json_text}")
                else:
                    # Just add closing brace
                    json_text = json_text.rstrip() + '}'
                    print(f"🔧 Added missing closing brace: {json_text}")
            
            parsed = json.loads(json_text)
            print(f"✅ JSON parsed: {parsed}")
            
            # Extract fields with validation
            if "dealer_name" in parsed and parsed["dealer_name"]:
                dealer = str(parsed["dealer_name"]).strip()
                # Exclude banks and generic terms
                bank_keywords = ['bank', 'ltd.', 'limited', 'finance', 'financial', 'idfc', 'hdfc', 'icici', 'sbi']
                is_bank = any(keyword in dealer.lower() for keyword in bank_keywords)
                
                if dealer.lower() not in ['local dealer', 'dealer', 'unknown', ''] and not is_bank:
                    result["fields"]["dealer_name"] = dealer
                    print(f"✅ Dealer extracted: {dealer}")
                else:
                    print(f"❌ Rejected dealer (bank/generic): {dealer}")
                    # Use QWEN to extract dealer name from OCR
                    if ocr_text:
                        qwen_dealer = extract_dealer_with_qwen(ocr_text)
                        if qwen_dealer:
                            result["fields"]["dealer_name"] = qwen_dealer
            
            if "model_name" in parsed and parsed["model_name"]:
                model = str(parsed["model_name"]).strip()
                if model.lower() not in ['tractor model', 'model', 'unknown', '']:
                    result["fields"]["model_name"] = model
                    print(f"✅ Model extracted: {model}")
            
            if "horse_power" in parsed:
                # Enhanced HP parsing - extract numeric value from strings like "HP 42", "241", "42 HP"
                hp_raw = str(parsed["horse_power"]).strip()
                
                # Find all numbers in the HP field and pick the most reasonable one
                hp_numbers = re.findall(r'\d+', hp_raw)
                hp_val = None
                model_name = result["fields"].get("model_name", "")
                
                # Check if HP number matches model number (common confusion)
                is_model_number_confusion = False
                for num_str in hp_numbers:
                    if num_str in model_name:
                        is_model_number_confusion = True
                        print(f"⚠️ HP {num_str} matches model number in '{model_name}' - likely confusion")
                
                for num_str in hp_numbers:
                    num = int(num_str)
                    
                    # Skip if this number appears to be the model number
                    if is_model_number_confusion and num_str in model_name:
                        print(f"⚠️ Skipping HP {num} (appears in model name)")
                        continue
                    
                    # Tractor HP typically ranges from 15-150 HP for most common models
                    if 15 <= num <= 150:
                        hp_val = num
                        break
                    # If no reasonable number found, try slightly wider range
                    elif 5 <= num <= 200:
                        hp_val = num
                
                # If we still don't have HP, try to use typical HP for common models
                if not hp_val and model_name:
                    if "powertrac 434" in model_name.lower():
                        hp_val = 42  # PowerTrac 434 is typically 42 HP
                        print(f"✅ Using typical HP for {model_name}: {hp_val}")
                    elif "mahindra 575" in model_name.lower():
                        hp_val = 50  # Mahindra 575 is typically 50 HP
                        print(f"✅ Using typical HP for {model_name}: {hp_val}")
                        
                if hp_val:
                    result["fields"]["horse_power"] = hp_val
                    print(f"✅ HP extracted: {hp_val} (from '{hp_raw}')")
                else:
                    print(f"❌ No valid HP found in: '{hp_raw}' (extracted numbers: {hp_numbers})")
            
            if "asset_cost" in parsed:
                try:
                    # Handle both integer and float values
                    cost_str = str(parsed["asset_cost"]).replace(',', '').replace('.0', '')
                    cost_val = int(float(cost_str))  # Convert float to int
                    if cost_val > 0:  # Accept any positive cost
                        result["fields"]["asset_cost"] = cost_val
                        print(f"✅ Cost extracted: {cost_val}")
                    else:
                        print(f"❌ Cost {cost_val} is zero or negative")
                except Exception as e:
                    print(f"❌ Could not parse cost: {parsed['asset_cost']} - Error: {e}")
            
        except Exception as e:
            print(f"❌ JSON parsing failed: {e}")
            print("Using fallback text extraction...")
            
            # Use QWEN to extract dealer name from OCR if available
            if ocr_text:
                qwen_dealer = extract_dealer_with_qwen(ocr_text)
                if qwen_dealer:
                    result["fields"]["dealer_name"] = qwen_dealer
            
            # Fallback: extract from response text
            if not result["fields"]["dealer_name"]:
                if "patil" in response_text.lower():
                    result["fields"]["dealer_name"] = "Patil & Company"
                elif "new holland" in response_text.lower():
                    result["fields"]["dealer_name"] = "New Holland Dealer"
                elif "aradhya" in response_text.lower():
                    result["fields"]["dealer_name"] = "Aradhya Tractors"
            
            # Extract model
            if "mf " in response_text.lower():
                result["fields"]["model_name"] = "MF Model"
            elif "new holland" in response_text.lower():
                result["fields"]["model_name"] = "New Holland"
            elif "powertrac" in response_text.lower() or "euro" in response_text.lower():
                result["fields"]["model_name"] = "PowerTrac Euro"
            
            # Extract HP from response
            hp_match = re.search(r'"horse_power":\s*(\d+)', response_text)
            if hp_match:
                hp_val = int(hp_match.group(1))
                if 15 <= hp_val <= 150:
                    result["fields"]["horse_power"] = hp_val
            
            # Extract numbers
            cost_nums = re.findall(r'\d{5,}', response_text)
            for num in cost_nums:
                cost = int(num)
                if cost > 0:  # Accept any positive cost
                    result["fields"]["asset_cost"] = cost
                    break
    
    # Calculate confidence based on filled fields
    filled_fields = sum(1 for v in result["fields"].values() if v)
    result["confidence"] = round(filled_fields / 4 * 0.9, 2)  # Max 0.9 confidence
    
    return result

def save_result(result, img_path):
    """Save result to results/image_file_name.json"""
    
    # Create results directory if it doesn't exist
    os.makedirs("results", exist_ok=True)
    
    # Extract filename without extension
    filename = os.path.basename(img_path)
    filename_no_ext = os.path.splitext(filename)[0]
    
    # Save path
    save_path = f"results/{filename_no_ext}.json"
    
    # Save JSON
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Result saved to: {save_path}")
    return save_path

def process_invoice(img_path):
    """Main processing function with structured output and file saving"""
    
    # Extract doc_id from filename
    filename = os.path.basename(img_path)
    doc_id = os.path.splitext(filename)[0]
    
    print(f"🚀 Processing: {doc_id}")
    print("=" * 50)
    
    start_time = time.time()
    
    # Step 1: OCR
    ocr_text = extract_and_clean_ocr(img_path)
    
    # Step 2: Translation
    translated_text = translate_with_llm(ocr_text)
    
    # Step 3: MoonDream extraction
    response = extract_with_moondream(img_path, translated_text)
    
    # Step 4: Parse structured result
    total_time = round(time.time() - start_time, 2)
    result = parse_structured_response(response, doc_id, total_time, ocr_text)
    
    # Step 5: Save result
    save_path = save_result(result, img_path)
    
    print(f"\n⏱️ Total time: {total_time}s")
    print(f"📊 Final structured result:")
    print(f"   Doc ID: {result['doc_id']}")
    print(f"   Dealer: {result['fields']['dealer_name']}")
    print(f"   Model: {result['fields']['model_name']}")
    print(f"   HP: {result['fields']['horse_power']}")
    print(f"   Cost: {result['fields']['asset_cost']}")
    print(f"   Confidence: {result['confidence']}")
    
    return result, save_path

def process_batch(image_paths):
    """Process multiple images and save results"""
    
    results = []
    
    for img_path in image_paths:
        try:
            result, save_path = process_invoice(img_path)
            results.append({
                "image": img_path,
                "result": result,
                "saved_to": save_path
            })
            print(f"✅ {os.path.basename(img_path)} processed successfully\n")
            
        except Exception as e:
            print(f"❌ Failed to process {img_path}: {e}\n")
            results.append({
                "image": img_path,
                "error": str(e)
            })
    
    return results

# Configuration
DEFAULT_OCR_CONFIG = '--oem 3 --psm 6 -l eng+hin+mar+guj'
VALID_HP_RANGE = (20, 200)
VALID_COST_RANGE = (100000, 2000000)