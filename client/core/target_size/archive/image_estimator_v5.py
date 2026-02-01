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
    
    # Helper to generate EXACT FFmpeg args
    def get_args(q, fmt):
        if 'webp' in fmt: 
            return {'quality': q}
        if 'jpg' in fmt or 'jpeg' in fmt:
            # Map 0-100 Quality to 31-2 Qscale
            # 0 (Worst) -> 31 (Smallest Size)
            # 100 (Best) -> 2 (Largest Size)
            val = 31 - int((q / 100.0) * 29)
            return {'qscale:v': val}
        return {'compression_level': 6}

    # --- PHASE 1: Standard Search ---
    for scale in scales:
        target_w = max(1, int(meta['width'] * scale))
        target_h = max(1, int(meta['height'] * scale))
        
        # Search 0-100 (Allow 0/Max Compression)
        low, high, valid_q = 0, 100, -1
        
        for _ in range(6): 
            mid = (low + high) // 2
            tmp = get_temp_filename(output_format)
            
            # Generate the specific args for this attempt
            current_args = get_args(mid, output_format)
            
            try:
                (ffmpeg.input(file_path).filter('scale', target_w, target_h)
                 .output(tmp, **current_args).run(quiet=True, overwrite_output=True))
                
                if os.path.exists(tmp):
                    size = os.path.getsize(tmp)
                    if size < target_size_bytes:
                        valid_q = mid
                        best_res = {
                            'quality': mid, 
                            'scale_factor': scale, 
                            'resolution_w': target_w, 
                            'resolution_h': target_h, 
                            'estimated_size': size,
                            'ffmpeg_out_args': current_args # <--- SAVE EXACT ARGS
                        }
                        low = mid + 1 
                    else: high = mid - 1
                else: high = mid - 1
            except: high = mid - 1
            finally: 
                if os.path.exists(tmp): os.remove(tmp)
        
        if valid_q >= 50: break

    # --- PHASE 2: Fallbacks ---
    if best_res is None:
        
        # STRATEGY A: Auto-Resize OFF -> Return Absolute Floor (Q0 / Qscale 31)
        if not allow_downscale:
            print("[ImageEstimatorV2] ⚠ Target size unreachable at native resolution. Forcing Max Compression.")
            floor_args = get_args(0, output_format) # qscale:v 31
            
            # Calculate floor size for reporting
            tmp = get_temp_filename(output_format)
            floor_size = 0
            try:
                (ffmpeg.input(file_path)
                 .output(tmp, **floor_args)
                 .run(quiet=True, overwrite_output=True))
                if os.path.exists(tmp): floor_size = os.path.getsize(tmp)
            except: pass
            finally: 
                if os.path.exists(tmp): os.remove(tmp)

            return {
                'quality': 0,
                'scale_factor': 1.0,
                'resolution_w': meta['width'],
                'resolution_h': meta['height'],
                'estimated_size': floor_size,
                'ffmpeg_out_args': floor_args # <--- THIS IS CRITICAL (qscale:v 31)
            }

        # STRATEGY B: Auto-Resize ON -> Emergency Downscale Loop
        print("[ImageEstimatorV2] ⚠ Engaging Emergency Downscaling.")
        current_scale = scales[-1]
        
        for _ in range(20):
            current_scale *= 0.90
            current_w = max(1, int(meta['width'] * current_scale))
            current_h = max(1, int(meta['height'] * current_scale))
            
            tmp = get_temp_filename(output_format)
            try:
                test_q = 5
                test_args = get_args(test_q, output_format)
                
                (ffmpeg.input(file_path).filter('scale', current_w, current_h)
                 .output(tmp, **test_args).run(quiet=True, overwrite_output=True))
                
                size = os.path.getsize(tmp)
                if size < target_size_bytes or current_w < 16:
                    best_res = {
                        'quality': test_q,
                        'scale_factor': current_scale,
                        'resolution_w': current_w,
                        'resolution_h': current_h,
                        'estimated_size': size,
                        'ffmpeg_out_args': test_args
                    }
                    if os.path.exists(tmp): os.remove(tmp)
                    break
            except: pass
            finally: 
                if os.path.exists(tmp): os.remove(tmp)

    return best_res