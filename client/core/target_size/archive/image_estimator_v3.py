import os
import tempfile
import ffmpeg
from typing import Dict

def get_temp_filename(ext): 
    f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
    f.close()
    return f.name

def get_media_metadata(file_path: str):
    try:
        probe = ffmpeg.probe(file_path)
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        return {'width': int(video['width']), 'height': int(video['height'])}
    except: return {'width': 0, 'height': 0}

def optimize_image_params(file_path: str, output_format: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    print(f"[ImageEstimatorV2] optimize_image_params: target={target_size_bytes} bytes, downscale_allowed={allow_downscale}")
    
    meta = get_media_metadata(file_path)
    
    # 1. Determine Initial Strategy
    # If allow_downscale is True: We proactively step down resolution to maintain higher Quality (e.g. Q50).
    # If allow_downscale is False: We force Scale 1.0 initially.
    scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
    
    best_res = None
    
    def get_args(q, fmt):
        if 'webp' in fmt: return {'quality': q}
        if 'jpg' in fmt or 'jpeg' in fmt: return {'qscale:v': int(31 - (q/100)*30)}
        return {'compression_level': 6}

    # --- PHASE 1: Standard Search ---
    for scale in scales:
        target_w = max(1, int(meta['width'] * scale))
        target_h = max(1, int(meta['height'] * scale))
        
        low, high, valid_q = 1, 100, 0
        current_best_q_size = 0
        
        # Binary Search 1-100
        for _ in range(6): 
            mid = (low + high) // 2
            tmp = get_temp_filename(output_format)
            try:
                (ffmpeg.input(file_path).filter('scale', target_w, target_h)
                 .output(tmp, **get_args(mid, output_format)).run(quiet=True, overwrite_output=True))
                
                if os.path.exists(tmp):
                    size = os.path.getsize(tmp)
                    if size < target_size_bytes:
                        valid_q = mid
                        current_best_q_size = size
                        best_res = {
                            'quality': mid, 
                            'scale_factor': scale, 
                            'resolution_w': target_w, 
                            'resolution_h': target_h, 
                            'estimated_size': size
                        }
                        low = mid + 1 # Try for better quality
                    else: 
                        high = mid - 1 # Too big, reduce quality
                else: high = mid - 1
            except: high = mid - 1
            finally: 
                if os.path.exists(tmp): os.remove(tmp)
        
        # If we found a good quality (>=50) at this scale, stop looking
        if valid_q >= 50: break

    # --- PHASE 2: Emergency Fallback (Force Size) ---
    # If we haven't found a valid result yet (meaning Q=1 @ Scale 1.0 was still too big),
    # AND the user requested a strict file size, we MUST downscale, 
    # even if allow_downscale was False (because physics says so).
    
    if best_res is None:
        print("[ImageEstimatorV3] ⚠ Target size impossible at requested resolution. Engaging Emergency Downscaling.")
        
        # Start from where we left off (e.g. 1.0 or 0.55)
        current_scale = scales[-1]
        current_w = int(meta['width'] * current_scale)
        current_h = int(meta['height'] * current_scale)
        
        # Force Q=1 (Max compression) and shrink dimensions until it fits
        max_iterations = 20  # Prevent infinite loop
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Reduce resolution by 10% each step
            current_scale *= 0.90
            current_w = max(1, int(meta['width'] * current_scale))
            current_h = max(1, int(meta['height'] * current_scale))
            
            tmp = get_temp_filename(output_format)
            try:
                # Test at Quality 5 (Give it a tiny bit of breathing room, or strictly 1)
                test_q = 5 
                (ffmpeg.input(file_path).filter('scale', current_w, current_h)
                 .output(tmp, **get_args(test_q, output_format)).run(quiet=True, overwrite_output=True))
                
                size = os.path.getsize(tmp)
                
                # If we fit, or if image is becoming ridiculous (<16px)
                if size < target_size_bytes or current_w < 16:
                    best_res = {
                        'quality': test_q,
                        'scale_factor': current_scale,
                        'resolution_w': current_w,
                        'resolution_h': current_h,
                        'estimated_size': size
                    }
                    print(f"[ImageEstimatorV3] Emergency fit found at {current_w}x{current_h} ({size} bytes)")
                    if os.path.exists(tmp): os.remove(tmp)
                    break
            except Exception as e:
                print(f"[ImageEstimatorV3] Emergency loop error: {e}")
            finally: 
                if os.path.exists(tmp): os.remove(tmp)
    
    # SAFETY NET: If we still have None (shouldn't happen, but just in case)
    if best_res is None:
        print("[ImageEstimatorV3] ⚠⚠⚠ CRITICAL: Could not find ANY valid compression. Using absolute minimum fallback.")
        fallback_scale = 0.25  # 25% of original size
        best_res = {
            'quality': 1,
            'scale_factor': fallback_scale,
            'resolution_w': max(1, int(meta['width'] * fallback_scale)),
            'resolution_h': max(1, int(meta['height'] * fallback_scale)),
            'estimated_size': 0
        }
    
    print(f"[ImageEstimatorV3] Returning: {best_res}")
    return best_res
