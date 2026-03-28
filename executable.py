#!/usr/bin/env python3
"""
IDFC Hackathon: Intelligent Document AI for Invoice Field Extraction

DESCRIPTION:
This script processes tractor invoice/quotation images to extract key fields:
- Dealer Name
- Model Name  
- Horse Power
- Asset Cost
- Signature Presence (with bounding box)
- Stamp Presence (with bounding box)

SETUP:
    pip install -r requirements.txt

USAGE:
    python executable.py --images_folder train/

PROCESSING PIPELINE:
1. OCR Extraction with multi-language support (Hindi/Gujarati/English)
2. LLM Translation (if needed)
3. MoonDream VLM field extraction
4. Computer Vision signature/stamp detection
5. Result combination and confidence scoring

OUTPUTS:
- Individual JSON files saved to results/ directory
- Each file named as: results/{image_filename}.json
- JSON format matches hackathon requirements

EXAMPLE OUTPUT:
{
  "doc_id": "invoice_001",
  "fields": {
    "dealer_name": "ABC Tractors Pvt Ltd",
    "model_name": "Mahindra 575 DI", 
    "horse_power": 50,
    "asset_cost": 525000,
    "signature": {"present": true, "bbox": [100, 200, 300, 250]},
    "stamp": {"present": true, "bbox": [400, 500, 500, 550]}
  },
  "confidence": 0.96,
  "processing_time_sec": 3.8,
  "cost_estimate_usd": 0.001
}

RESULTS DIRECTORY:
All processed results are automatically saved to results/ directory.
One JSON file per input image with the same filename.
"""

import argparse
import importlib
import sys
import json
import os
import time
import glob

# Force reload modules to get latest code
if 'utils.text_pipeline_processing' in sys.modules:
    importlib.reload(sys.modules['utils.text_pipeline_processing'])

if 'utils.image_pipeline_clean' in sys.modules:
    importlib.reload(sys.modules['utils.image_pipeline_clean'])

# Import from defined utility files
from utils.text_pipeline_processing import extract_and_clean_ocr, translate_with_llm, extract_with_moondream, parse_structured_response
from utils.image_pipeline_clean import configure_pipeline, test_image, initialize_clip

def setup_pipelines():
    """Setup both text and image processing pipelines"""
    
    print("Setting up combined pipeline...")
    
    configure_pipeline(
        target_width=1200,
        target_height=1600, 
        bottom_pct=0.6,
        manual_threshold=50,
        iterations=3,
        distance_factor=120,
        right_bias=0.1,
        hide_output_image=True
    )
    
    initialize_clip()
    print("Pipeline setup complete\n")

def process_text_fields(img_path):
    """Process text fields using text pipeline"""
    
    filename = os.path.basename(img_path)
    doc_id = os.path.splitext(filename)[0]
    
    start_time = time.time()
    
    ocr_text = extract_and_clean_ocr(img_path)
    translated_text = translate_with_llm(ocr_text)
    moondream_response = extract_with_moondream(img_path, translated_text)
    
    text_processing_time = round(time.time() - start_time, 2)
    text_result = parse_structured_response(moondream_response, doc_id, text_processing_time, ocr_text)
    
    print(f"Text processing completed: {text_processing_time}s")
    
    return text_result

def process_visual_fields(img_path):
    """Process visual fields using image pipeline"""
    
    # Extract folder and filename from full path
    images_folder = os.path.dirname(img_path)
    filename = os.path.basename(img_path)
    
    start_time = time.time()
    
    image_results = test_image(
        use_specific=True, 
        specific_image=img_path,  # Pass full path instead of just filename
        images_folder=images_folder,
        target_width=1200,
        target_height=1600, 
        bottom_pct=0.6,
        manual_threshold=50,
        iterations=3,
        distance_factor=120,
        right_bias=0.1
    )
    
    visual_processing_time = round(time.time() - start_time, 2)
    
    print(f"Visual processing completed: {visual_processing_time}s")
    
    return image_results, visual_processing_time

def combine_results(text_result, image_results, visual_processing_time):
    """Combine text and visual results"""
    
    combined_result = text_result.copy()
    
    # Process signature/stamp data
    signature_data = image_results.get('signature', {})
    stamp_data = image_results.get('stamp', {})
    
    sig_bbox = signature_data.get('bbox', [])
    sig_present = signature_data.get('present', False) and len(sig_bbox) > 0
    sig_confidence = signature_data.get('confidence', 0.0)
    
    stamp_bbox = stamp_data.get('bbox', [])
    stamp_present = stamp_data.get('present', False) and len(stamp_bbox) > 0
    stamp_confidence = stamp_data.get('confidence', 0.0)
    
    # Add visual fields
    combined_result["fields"]["signature"] = {
        "present": sig_present,
        "bbox": sig_bbox if sig_present else []
    }
    
    combined_result["fields"]["stamp"] = {
        "present": stamp_present,
        "bbox": stamp_bbox if stamp_present else []
    }
    
    # Update processing time and confidence
    combined_result["processing_time_sec"] += visual_processing_time
    
    text_confidence = combined_result["confidence"]
    visual_confidence = (sig_confidence + stamp_confidence) / 2 if (sig_confidence or stamp_confidence) else 0
    combined_confidence = (text_confidence * 0.7) + (visual_confidence * 0.3)
    combined_result["confidence"] = round(min(combined_confidence, 0.98), 2)
    
    return combined_result

def save_combined_result(result, img_path):
    """Save combined result to results/image_file_name.json"""
    
    os.makedirs("results", exist_ok=True)
    
    filename = os.path.basename(img_path)
    filename_no_ext = os.path.splitext(filename)[0]
    save_path = f"results/{filename_no_ext}.json"
    
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return save_path

def process_invoice_complete(img_path):
    """Complete processing pipeline: Text + Visual"""
    
    filename = os.path.basename(img_path)
    print(f"Processing: {filename}")
    
    try:
        # Process text fields
        text_result = process_text_fields(img_path)
        
        # Process visual fields
        image_results, visual_time = process_visual_fields(img_path)
        
        # Combine results
        combined_result = combine_results(text_result, image_results, visual_time)
        
        # Save result
        save_path = save_combined_result(combined_result, img_path)
        
        print(f"Completed: {combined_result['processing_time_sec']}s, confidence: {combined_result['confidence']}")
        
        return combined_result, save_path
        
    except Exception as e:
        print(f"Processing failed: {e}")
        return None, None

def process_batch_complete(image_paths):
    """Process multiple images with complete pipeline"""
    
    print(f"Processing {len(image_paths)} images...")
    
    results = []
    
    for i, img_path in enumerate(image_paths, 1):
        print(f"\n[{i}/{len(image_paths)}] {os.path.basename(img_path)}")
        
        try:
            result, save_path = process_invoice_complete(img_path)
            
            if result:
                results.append({
                    "image": img_path,
                    "result": result,
                    "saved_to": save_path,
                    "status": "success"
                })
            else:
                results.append({
                    "image": img_path,
                    "status": "failed",
                    "error": "Processing returned None"
                })
            
        except Exception as e:
            results.append({
                "image": img_path,
                "status": "failed", 
                "error": str(e)
            })
            print(f"Failed: {e}")
    
    return results

def main():
    """Main execution function"""
    
    parser = argparse.ArgumentParser(
        description='IDFC Hackathon: Extract fields from invoice images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    python executable.py --images_folder train/
    python executable.py --images_folder /path/to/invoices/

OUTPUTS:
    Results are saved to results/ directory as JSON files.
    One file per input image: results/{image_name}.json
        """
    )
    
    parser.add_argument('--images_folder', 
                        required=True, 
                        help='Path to folder containing invoice images (PNG format)')
    
    args = parser.parse_args()
    
    # Validate input folder
    if not os.path.exists(args.images_folder):
        print(f"Error: Images folder '{args.images_folder}' does not exist")
        sys.exit(1)
    
    # Get all PNG images from the folder
    image_pattern = os.path.join(args.images_folder, "*.png")
    image_paths = glob.glob(image_pattern)
    image_paths.sort()
    
    if not image_paths:
        print(f"Error: No PNG images found in '{args.images_folder}'")
        sys.exit(1)
    
    print(f"Found {len(image_paths)} PNG images in {args.images_folder}")
    
    # Setup processing pipelines
    setup_pipelines()
    
    # Process all images
    start_time = time.time()
    results = process_batch_complete(image_paths)
    total_time = time.time() - start_time
    
    # Final summary
    successful = len([r for r in results if r.get("status") == "success"])
    failed = len(results) - successful
    
    print(f"\n=== PROCESSING COMPLETE ===")
    print(f"Total time: {total_time:.2f}s")
    print(f"Images processed: {len(image_paths)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success rate: {successful/len(image_paths)*100:.1f}%")
    print(f"Average time per image: {total_time/len(image_paths):.2f}s")
    print(f"Results saved to: results/ directory")
    
    # List some example outputs
    if successful > 0:
        print(f"\nExample result files created:")
        example_results = [r for r in results if r.get("status") == "success"][:3]
        for result_info in example_results:
            print(f"  - {result_info['saved_to']}")

if __name__ == "__main__":
    main()