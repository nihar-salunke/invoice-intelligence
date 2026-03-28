"""
Clean Image Processing Pipeline for Invoice Signature/Stamp Detection
Includes scaling normalization, manual thresholding, clustering, and CLIP validation
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import clip
import torch
import random
import glob
import os

# Global CLIP setup
device = "cpu"
clip_model = None
preprocess = None

# Global pipeline configuration
TARGET_WIDTH = 1200
TARGET_HEIGHT = 1600
BOTTOM_PCT = 0.4           # Search bottom 60% of image
MANUAL_THRESHOLD = 75      # B&W threshold for noisy images
ITERATIONS = 2             # Clustering iterations
DISTANCE_FACTOR = None     # None = adaptive, number = manual distance
RIGHT_BIAS = 0.05          # Confidence boost for right-side boxes
HIDE_OUTPUT_IMAGE = False  # Hide visualization for cloud/production

def configure_pipeline(target_width=1200, target_height=1600, bottom_pct=0.4, 
                      manual_threshold=75, iterations=2, distance_factor=None, 
                      right_bias=0.05, hide_output_image=False):
    """Configure global pipeline parameters"""
    global TARGET_WIDTH, TARGET_HEIGHT, BOTTOM_PCT, MANUAL_THRESHOLD
    global ITERATIONS, DISTANCE_FACTOR, RIGHT_BIAS, HIDE_OUTPUT_IMAGE
    
    TARGET_WIDTH = target_width
    TARGET_HEIGHT = target_height
    BOTTOM_PCT = bottom_pct
    MANUAL_THRESHOLD = manual_threshold
    ITERATIONS = iterations
    DISTANCE_FACTOR = distance_factor
    RIGHT_BIAS = right_bias
    HIDE_OUTPUT_IMAGE = hide_output_image
    
    search_area_pct = (1 - bottom_pct) * 100
    print(f"Pipeline configured:")
    print(f"  Target size: {target_width}x{target_height}")
    print(f"  Search area: bottom {search_area_pct:.0f}%")
    print(f"  Threshold: {manual_threshold}")
    print(f"  Distance: {'adaptive' if distance_factor is None else distance_factor}")
    print(f"  Right bias: +{right_bias:.2f}")
    print(f"  Hide images: {hide_output_image}")

def initialize_clip():
    """Initialize CLIP model (call once)"""
    global clip_model, preprocess
    if clip_model is None:
        print("Initializing CLIP model...")
        clip_model, preprocess = clip.load("ViT-B/32", device=device)
        print("CLIP loaded successfully")

def adaptive_image_scaling(image_path, target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT):
    """Scale image to target dimensions while preserving aspect ratio"""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")
        
    height, width = img.shape
    original_area = width * height
    target_area = target_width * target_height
    
    # Calculate scaling factor to match target area
    scale_factor = (target_area / original_area) ** 0.5
    
    # Calculate new dimensions
    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)
    
    # Ensure we don't exceed target dimensions
    if new_width > target_width:
        scale_factor = target_width / width
        new_width = target_width
        new_height = int(height * scale_factor)
    
    if new_height > target_height:
        scale_factor = target_height / height  
        new_height = target_height
        new_width = int(width * scale_factor)
    
    # Apply scaling if needed
    if abs(scale_factor - 1.0) > 0.05:  # Only scale if significant difference
        scaled_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
        print(f"  Scaled: {width}x{height} -> {new_width}x{new_height} (factor: {scale_factor:.2f})")
    else:
        scaled_img = img
        print(f"  No scaling needed: {width}x{height}")
    
    return scaled_img, scale_factor

def get_adaptive_clustering_distance(img_width, img_height, base_distance_pct=0.05):
    """Calculate clustering distance as percentage of image width"""
    adaptive_distance = int(img_width * base_distance_pct)
    adaptive_distance = max(20, min(200, adaptive_distance))
    return adaptive_distance

def get_opencv_contours_from_image(scaled_img, bottom_pct=BOTTOM_PCT, manual_threshold=MANUAL_THRESHOLD):
    """Get contours from already-loaded scaled image"""
    height, width = scaled_img.shape
    
    # Apply manual threshold
    manual_thresh = np.where(scaled_img >= manual_threshold, 255, 0).astype(np.uint8)
    contour_ready = cv2.bitwise_not(manual_thresh)
    
    # Find contours
    contours, _ = cv2.findContours(contour_ready, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Adaptive filtering based on scaled image size
    search_threshold = height * bottom_pct
    min_area = int(width * height * 0.0001)  # 0.01% of image
    max_area = int(width * height * 0.3)     # 30% of image
    
    all_boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        
        if (area > min_area and area < max_area and 
            y > search_threshold and w > 5 and h > 5):
            all_boxes.append([x, y, x + w, y + h])
    
    search_area_pct = (1 - bottom_pct) * 100
    print(f"  Found {len(all_boxes)} contours in bottom {search_area_pct:.0f}%")
    
    return all_boxes, (width, height), search_threshold

def simple_cluster_boxes(boxes, distance_factor=50):
    """Simple distance-based clustering"""
    if len(boxes) < 2:
        return boxes
    
    clustered = []
    used = set()
    
    for i, box1 in enumerate(boxes):
        if i in used:
            continue
            
        cluster = [box1]
        used.add(i)
        
        for j, box2 in enumerate(boxes):
            if j in used or i == j:
                continue
                
            center1 = ((box1[0] + box1[2])/2, (box1[1] + box1[3])/2)
            center2 = ((box2[0] + box2[2])/2, (box2[1] + box2[3])/2)
            
            distance = ((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)**0.5
            
            if distance <= distance_factor:
                cluster.append(box2)
                used.add(j)
        
        combined = combine_boxes(cluster)
        if combined:
            clustered.append(combined)
    
    return clustered

def iterative_cluster_contours(boxes, adaptive_distance, iterations=2):
    """Apply iterative clustering with adaptive distance"""
    if not boxes:
        return []
        
    current_boxes = boxes[:]
    print(f"  Starting clustering: {len(current_boxes)} boxes, distance: {adaptive_distance}px")
    
    for iteration in range(iterations):
        current_distance = adaptive_distance * (iteration + 1)
        new_boxes = simple_cluster_boxes(current_boxes, current_distance)
        
        print(f"  Iteration {iteration + 1} (d={current_distance}): {len(current_boxes)} -> {len(new_boxes)} clusters")
        
        if len(new_boxes) == len(current_boxes) or len(new_boxes) == 0:
            break
            
        current_boxes = new_boxes
    
    return current_boxes

def combine_boxes(boxes):
    """Combine multiple boxes into one encompassing box"""
    if not boxes:
        return None
    
    x1_min = min(box[0] for box in boxes)
    y1_min = min(box[1] for box in boxes)
    x2_max = max(box[2] for box in boxes)
    y2_max = max(box[3] for box in boxes)
    
    return [x1_min, y1_min, x2_max, y2_max]

def classify_cluster_for_both(original_image, bbox, right_bias=RIGHT_BIAS):
    """Check each cluster independently for BOTH signature AND stamp"""
    global clip_model, preprocess
    
    if clip_model is None:
        initialize_clip()
    
    cluster_crop = original_image.crop(bbox)
    image_tensor = preprocess(cluster_crop).unsqueeze(0).to(device)
    
    results = {"signature": False, "stamp": False, "sig_conf": 0.0, "stamp_conf": 0.0}
    
    # Check if bbox is in right 50% of image
    img_width = original_image.size[0]
    bbox_center_x = (bbox[0] + bbox[2]) / 2
    is_right_side = bbox_center_x > img_width * 0.5
    
    # Check for signature
    text_tokens = clip.tokenize(["no signature", "handwritten signature"]).to(device)
    with torch.no_grad():
        logits, _ = clip_model(image_tensor, text_tokens)
        sig_probs = logits.softmax(dim=-1)[0]
        signature_confidence = sig_probs[1].item()
    
    # Check for stamp
    text_tokens = clip.tokenize(["no stamp", "official stamp or seal"]).to(device)
    with torch.no_grad():
        logits, _ = clip_model(image_tensor, text_tokens)
        stamp_probs = logits.softmax(dim=-1)[0]
        stamp_confidence = stamp_probs[1].item()
    
    # Apply right-side bias
    if is_right_side and right_bias > 0:
        signature_confidence = min(1.0, signature_confidence + right_bias)
        stamp_confidence = min(1.0, stamp_confidence + right_bias)
    
    if signature_confidence > 0.4:
        results["signature"] = True
        results["sig_conf"] = signature_confidence
    
    if stamp_confidence > 0.4:
        results["stamp"] = True
        results["stamp_conf"] = stamp_confidence
    
    return results

def select_best_detections(signature_detections, stamp_detections):
    """Select best signature and stamp, apply fallback logic if one is missing"""
    result = {
        "signature": {"present": False, "bbox": [], "confidence": 0.0},
        "stamp": {"present": False, "bbox": [], "confidence": 0.0}
    }
    
    # Find best signature (highest confidence)
    if signature_detections:
        best_signature = max(signature_detections, key=lambda x: x["confidence"])
        result["signature"] = {
            "present": True,
            "bbox": best_signature["bbox"],
            "confidence": best_signature["confidence"]
        }
    
    # Find best stamp (highest confidence)
    if stamp_detections:
        best_stamp = max(stamp_detections, key=lambda x: x["confidence"])
        result["stamp"] = {
            "present": True,
            "bbox": best_stamp["bbox"],
            "confidence": best_stamp["confidence"]
        }
    
    # Apply fallback logic
    if result["signature"]["present"] and not result["stamp"]["present"]:
        result["stamp"] = {
            "present": True,
            "bbox": result["signature"]["bbox"][:],
            "confidence": 0.1,
            "fallback": "from_signature"
        }
        print("  Fallback: Using signature bbox for stamp")
    
    elif result["stamp"]["present"] and not result["signature"]["present"]:
        result["signature"] = {
            "present": True, 
            "bbox": result["stamp"]["bbox"][:],
            "confidence": 0.1,
            "fallback": "from_stamp"
        }
        print("  Fallback: Using stamp bbox for signature")
    
    return result

def visualize_best_results(original_image, best_results, scale_factor, clustering_distance, 
                          manual_threshold, bottom_pct):
    """Visualize only the best signature and stamp detections"""
    
    if HIDE_OUTPUT_IMAGE:
        print("  Visualization hidden (cloud mode)")
        return
    
    fig, ax = plt.subplots(1, 1, figsize=(15, 10))
    ax.imshow(original_image)
    
    # Draw only the best signature and stamp
    if best_results["signature"]["present"]:
        sig_bbox = best_results["signature"]["bbox"]
        sig_conf = best_results["signature"]["confidence"]
        is_fallback = "fallback" in best_results["signature"]
        
        color = 'orange' if is_fallback else 'blue'
        label = f'SIGNATURE\n{sig_conf:.2f}' + ('\n(fallback)' if is_fallback else '')
        
        rect = patches.Rectangle((sig_bbox[0], sig_bbox[1]), sig_bbox[2]-sig_bbox[0], sig_bbox[3]-sig_bbox[1],
                               linewidth=5, edgecolor=color, facecolor='none', alpha=0.9)
        ax.add_patch(rect)
        
        ax.text(sig_bbox[0], sig_bbox[1]-10, label, fontsize=12, color=color, weight='bold',
               bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=color, alpha=0.9))
    
    if best_results["stamp"]["present"]:
        stamp_bbox = best_results["stamp"]["bbox"]
        stamp_conf = best_results["stamp"]["confidence"]
        is_fallback = "fallback" in best_results["stamp"]
        
        color = 'orange' if is_fallback else 'red'
        label = f'STAMP\n{stamp_conf:.2f}' + ('\n(fallback)' if is_fallback else '')
        
        # Handle same bbox case
        if (best_results["signature"]["present"] and 
            stamp_bbox == best_results["signature"]["bbox"]):
            rect = patches.Rectangle((stamp_bbox[0]+5, stamp_bbox[1]+5), 
                                   stamp_bbox[2]-stamp_bbox[0]-10, stamp_bbox[3]-stamp_bbox[1]-10,
                                   linewidth=3, edgecolor=color, facecolor='none', 
                                   alpha=0.7, linestyle='--')
            ax.add_patch(rect)
            ax.text(stamp_bbox[2]-120, stamp_bbox[1]-10, label, fontsize=12, color=color, weight='bold',
                   bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=color, alpha=0.9))
        else:
            rect = patches.Rectangle((stamp_bbox[0], stamp_bbox[1]), stamp_bbox[2]-stamp_bbox[0], stamp_bbox[3]-stamp_bbox[1],
                                   linewidth=5, edgecolor=color, facecolor='none', alpha=0.9)
            ax.add_patch(rect)
            ax.text(stamp_bbox[0], stamp_bbox[1]-10, label, fontsize=12, color=color, weight='bold',
                   bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=color, alpha=0.9))
    
    # Add search area reference
    orig_search_line = int(original_image.size[1] * bottom_pct)
    ax.axhline(y=orig_search_line, color='yellow', linewidth=2, linestyle='--', alpha=0.8)
    
    search_area_pct = (1 - bottom_pct) * 100
    ax.text(10, orig_search_line-25, f'Search Area (Bottom {search_area_pct:.0f}%)', 
           color='yellow', fontsize=12, weight='bold')
    
    # Create title
    sig_status = "Found" if best_results["signature"]["present"] else "Missing"
    stamp_status = "Found" if best_results["stamp"]["present"] else "Missing"
    
    ax.set_title(f'Best Detections: Signature {sig_status} | Stamp {stamp_status}\n'
                f'Scale: {scale_factor:.2f}x, Threshold: {manual_threshold}, Distance: {clustering_distance}px', 
                fontsize=14)
    ax.axis('off')
    plt.tight_layout()
    plt.show()

def process_image(image_path, target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT,
                 bottom_pct=BOTTOM_PCT, manual_threshold=MANUAL_THRESHOLD, iterations=ITERATIONS,
                 distance_factor=DISTANCE_FACTOR, right_bias=RIGHT_BIAS, hide_output_image=HIDE_OUTPUT_IMAGE):
    """Complete pipeline: Scaling -> Manual Threshold -> Clustering -> CLIP"""
    
    print(f"Processing: {image_path.split('/')[-1]}")
    
    # Step 1: Adaptive scaling
    scaled_img, scale_factor = adaptive_image_scaling(image_path, target_width, target_height)
    height, width = scaled_img.shape
    
    # Step 2: Get clustering distance
    if distance_factor is not None:
        clustering_distance = distance_factor
        print(f"  Manual distance: {clustering_distance}px")
    else:
        clustering_distance = get_adaptive_clustering_distance(width, height)
        print(f"  Adaptive distance: {clustering_distance}px")
    
    # Step 3: Contour detection
    all_boxes, (scaled_width, scaled_height), search_threshold = get_opencv_contours_from_image(
        scaled_img, bottom_pct, manual_threshold
    )
    
    if not all_boxes:
        print("  No contours found")
        return {
            "signature": {"present": False, "bbox": [], "confidence": 0.0},
            "stamp": {"present": False, "bbox": [], "confidence": 0.0},
            "scale_factor": scale_factor,
            "clustering_distance": clustering_distance,
            "processing_method": "Scaling_Threshold_Clustering_CLIP"
        }
    
    # Step 4: Apply clustering
    clustered_boxes = iterative_cluster_contours(all_boxes, clustering_distance, iterations)
    
    if not clustered_boxes:
        print("  No clusters found")
        return {
            "signature": {"present": False, "bbox": [], "confidence": 0.0},
            "stamp": {"present": False, "bbox": [], "confidence": 0.0},
            "scale_factor": scale_factor,
            "clustering_distance": clustering_distance,
            "processing_method": "Scaling_Threshold_Clustering_CLIP"
        }
    
    # Step 5: Convert back to original coordinates
    original_boxes = []
    if scale_factor != 1.0:
        for box in clustered_boxes:
            orig_box = [int(coord / scale_factor) for coord in box]
            original_boxes.append(orig_box)
    else:
        original_boxes = clustered_boxes
    
    # Step 6: Load original image and classify
    original_image = Image.open(image_path)
    original_width, original_height = original_image.size
    
    signature_detections = []
    stamp_detections = []
    
    print(f"  CLIP classification of {len(original_boxes)} clusters:")
    
    for i, bbox in enumerate(original_boxes):
        # Ensure bbox is within bounds
        bbox[0] = max(0, min(bbox[0], original_width-1))
        bbox[1] = max(0, min(bbox[1], original_height-1))  
        bbox[2] = max(bbox[0]+1, min(bbox[2], original_width))
        bbox[3] = max(bbox[1]+1, min(bbox[3], original_height))
        
        classification = classify_cluster_for_both(original_image, bbox, right_bias)
        
        if classification["signature"]:
            signature_detections.append({"bbox": bbox, "confidence": classification["sig_conf"]})
            
        if classification["stamp"]:
            stamp_detections.append({"bbox": bbox, "confidence": classification["stamp_conf"]})
    
    # Step 7: Select best detections
    best_results = select_best_detections(signature_detections, stamp_detections)
    
    # Step 8: Visualization (only if not hidden)
    if not hide_output_image:
        visualize_best_results(original_image, best_results, scale_factor, 
                               clustering_distance, manual_threshold, bottom_pct)
    
    # Return results
    final_result = {
        "signature": best_results["signature"],
        "stamp": best_results["stamp"],
        "scale_factor": scale_factor,
        "clustering_distance": clustering_distance,
        "processing_method": "Scaling_Threshold_Clustering_CLIP"
    }
    
    print(f"  RESULTS: Signature {'Found' if best_results['signature']['present'] else 'Missing'}, "
          f"Stamp {'Found' if best_results['stamp']['present'] else 'Missing'}")
    
    return final_result

def test_image(use_specific=False, specific_image=None, images_folder="input_images",
              target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT, bottom_pct=BOTTOM_PCT, 
              manual_threshold=MANUAL_THRESHOLD, iterations=ITERATIONS,
              distance_factor=DISTANCE_FACTOR, right_bias=RIGHT_BIAS, hide_output_image=HIDE_OUTPUT_IMAGE):
    """Test the complete pipeline (uses global defaults)"""
    
    initialize_clip()
    
    # Select image
    if use_specific and specific_image:
        # Check if it's already a full path
        if os.path.exists(specific_image):
            sample_image = specific_image
        else:
            # Construct path using the provided folder
            sample_image = os.path.join(images_folder, specific_image)
            
        if not os.path.exists(sample_image):
            print(f"Image not found: {sample_image}")
            return None
    else:
        # Use the provided folder for random selection
        all_images = glob.glob(os.path.join(images_folder, "*.png"))
        if not all_images:
            print(f"No images found in {images_folder}/ folder")
            return None
        sample_image = random.choice(all_images)
        print(f"Random selection: {sample_image.split('/')[-1]}")
    
    # Run pipeline
    results = process_image(
        sample_image, 
        target_width=target_width,
        target_height=target_height,
        bottom_pct=bottom_pct,
        manual_threshold=manual_threshold,
        iterations=iterations,
        distance_factor=distance_factor,
        right_bias=right_bias,
        hide_output_image=hide_output_image
    )
    
    return results