import os
import tempfile
import ffmpeg
from typing import Dict

def get_temp_filename(ext): f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False); f.close(); return f.name

def get_media_metadata(file_path: str):
    try:
        probe = ffmpeg.probe(file_path)
        video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        return {'width': int(video['width']), 'height': int(video['height'])}
    except: return {'width': 0, 'height': 0}

def optimize_image_params(file_path: str, output_format: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    print(f"[ImageEstimatorV2] optimize_image_params called: file={file_path}, format={output_format}, target={target_size_bytes}, downscale={allow_downscale}")
    
    meta = get_media_metadata(file_path)
    print(f"[ImageEstimatorV2] Metadata: {meta}")
    
    scales = [1.0, 0.85, 0.70, 0.55] if allow_downscale else [1.0]
    
    # Initialize with safest fallback (Smallest scale, lowest quality)
    fallback_scale = scales[-1]
    best_res = {
        'quality': 1, 
        'scale_factor': fallback_scale,
        'resolution_w': int(max(1, meta['width'] * fallback_scale)),
        'resolution_h': int(max(1, meta['height'] * fallback_scale)),
        'estimated_size': 0
    }
    
    def get_args(q, fmt):
        if 'webp' in fmt: return {'quality': q}
        if 'jpg' in fmt or 'jpeg' in fmt: return {'qscale:v': int(31 - (q/100)*30)}
        return {'compression_level': 6}

    for scale in scales:
        target_w = int(meta['width'] * scale)
        target_h = int(meta['height'] * scale)
        target_w, target_h = max(1, target_w), max(1, target_h)
        
        low, high, valid_q = 1, 100, 0
        for _ in range(6): # Binary Search
            mid = (low + high) // 2
            tmp = get_temp_filename(output_format)
            try:
                (ffmpeg.input(file_path).filter('scale', target_w, target_h)
                 .output(tmp, **get_args(mid, output_format)).run(quiet=True, overwrite_output=True))
                
                if os.path.exists(tmp):
                    size = os.path.getsize(tmp)
                    if size < target_size_bytes:
                        valid_q = mid
                        best_res = {'quality': mid, 'scale_factor': scale, 'resolution_w': target_w, 'resolution_h': target_h, 'estimated_size': size}
                        low = mid + 1
                    else: high = mid - 1
                else: high = mid - 1
            except Exception as e:
                print(f"[ImageEstimatorV2] FFmpeg error at quality {mid}: {e}")
                high = mid - 1
            finally: 
                if os.path.exists(tmp): os.remove(tmp)
        if valid_q >= 50: break
    
    print(f"[ImageEstimatorV2] Final result: {best_res}")        
    return best_res
