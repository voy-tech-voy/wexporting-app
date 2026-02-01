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
                        best_res = {
                            'quality': mid, 
                            'scale_factor': scale, 
                            'resolution_w': target_w, 
                            'resolution_h': target_h, 
                            'estimated_size': size
                        }
                        low = mid + 1 
                    else: 
                        high = mid - 1 
                else: high = mid - 1
            except: high = mid - 1
            finally: 
                if os.path.exists(tmp): os.remove(tmp)
        
        if valid_q >= 50: break

    # --- HANDLING NO MATCH ---
    if best_res is None:
        if not allow_downscale:
            # FIX: If downscaling is OFF, return Max Compression at 100% scale.
            # Do NOT enter emergency loop.
            print("[ImageEstimatorV2] ⚠ Target size too small for native resolution. Returning Max Compression (Q1).")
            return {
                'quality': 1,
                'scale_factor': 1.0,
                'resolution_w': meta['width'],
                'resolution_h': meta['height'],
                'estimated_size': 0 # Unknown, will be larger than target
            }

        # --- PHASE 2: Emergency Fallback (Only if downscale allowed) ---
        print("[ImageEstimatorV2] ⚠ Target size impossible at requested resolution. Engaging Emergency Downscaling.")
        current_scale = scales[-1]
        current_w = int(meta['width'] * current_scale)
        current_h = int(meta['height'] * current_scale)
        
        iteration = 0
        while iteration < 20:
            iteration += 1
            current_scale *= 0.90
            current_w = max(1, int(meta['width'] * current_scale))
            current_h = max(1, int(meta['height'] * current_scale))
            
            tmp = get_temp_filename(output_format)
            try:
                test_q = 5 
                (ffmpeg.input(file_path).filter('scale', current_w, current_h)
                 .output(tmp, **get_args(test_q, output_format)).run(quiet=True, overwrite_output=True))
                
                size = os.path.getsize(tmp)
                if size < target_size_bytes or current_w < 16:
                    best_res = {
                        'quality': test_q,
                        'scale_factor': current_scale,
                        'resolution_w': current_w,
                        'resolution_h': current_h,
                        'estimated_size': size
                    }
                    if os.path.exists(tmp): os.remove(tmp)
                    break
            except: pass
            finally: 
                if os.path.exists(tmp): os.remove(tmp)

    return best_res