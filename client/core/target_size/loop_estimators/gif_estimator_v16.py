import os
import math
import time
import tempfile
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional, Callable
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary

class Estimator(EstimatorProtocol):
    """
    GIF Estimator v17 - "The Visual Analyzer"
    
    Logic:
    1. Pre-Analysis: Analyzes frames for color variance (gradients vs flat).
    2. Dynamic Dither: Disables dither for flat content to save massive space.
    3. Tier Search: O(log n) search for FPS/Color combo (Max 24fps).
    4. Size Safety: Uses a 0.90 safety multiplier to prevent overshooting.
    """

    # Removed 30 and 25 FPS tiers
    SORTED_TIERS = [
        {'id': 0,  'fps': 24, 'colors': 256},
        {'id': 1,  'fps': 20, 'colors': 256},
        {'id': 2,  'fps': 15, 'colors': 256},
        {'id': 3,  'fps': 15, 'colors': 128},
        {'id': 4,  'fps': 12, 'colors': 256},
        {'id': 5,  'fps': 12, 'colors': 128},
        {'id': 6,  'fps': 10, 'colors': 128},
        {'id': 7,  'fps': 10, 'colors': 64},
        {'id': 8,  'fps': 8,  'colors': 64},
        {'id': 9,  'fps': 6,  'colors': 32},
        {'id': 10, 'fps': 5,  'colors': 16},
    ]

    def get_output_extension(self) -> str:
        return 'gif'

    def _analyze_visual_complexity(self, input_path: str, start: float) -> dict:
        """
        Analyzes the video to detect if it's flat-colored or contains gradients.
        Uses signalstats filter to check standard deviation of pixel values.
        """
        try:
            ffmpeg_bin = get_ffmpeg_binary()
            # Analyze 1 second of video
            cmd = [
                ffmpeg_bin, '-y', '-ss', str(start), '-t', '1', '-i', input_path,
                '-vf', 'signalstats', '-f', 'null', '-'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            # Look for 'VAV' (Value Average Variance). 
            # High VAV = Gradients/Noise. Low VAV = Flat colors.
            # We look for the 'mean' variance in the output.
            import re
            vav_values = re.findall(r"VAV=(\d+)", result.stderr)
            if not vav_values:
                return {'has_gradients': True, 'score': 100} # Default to safe
            
            avg_vav = sum(int(v) for v in vav_values) / len(vav_values)
            
            # Threshold: < 15 usually indicates flat UI or simple animation
            return {
                'has_gradients': avg_vav > 15,
                'score': avg_vav
            }
        except:
            return {'has_gradients': True, 'score': 100}

    def _run_sample_encode(self, input_path, start, duration, w, h, fps, colors, dither, transform_filters) -> int:
        tmp = tempfile.NamedTemporaryFile(suffix='.gif', delete=False).name
        try:
            d_parts = dither.split(':')
            dither_type = d_parts[0]
            d_opts = f":{d_parts[1]}" if len(d_parts) > 1 else ""
            
            # Palette options: Disable transparency reservation for very low colors
            p_opts = f"max_colors={colors}:stats_mode=diff"
            if colors <= 4: p_opts += ":reserve_transparent=0"

            vf = transform_filters.get('vf_filters', [])
            chain = []
            curr = "0:v"
            if vf:
                chain.append(f"[0:v]{','.join(vf)}[t]")
                curr = "t"
            
            chain.append(
                f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];"
                f"[v]split[a][b];"
                f"[a]palettegen={p_opts}[p];"
                f"[b][p]paletteuse=dither={dither_type}{d_opts}:diff_mode=rectangle"
            )
            
            cmd = [get_ffmpeg_binary(), '-y', '-hide_banner', '-loglevel', 'error']
            # Pass input args (hwaccel, etc)
            for k, v in transform_filters.get('input_args', {}).items():
                cmd.extend([f'-{k.lstrip("-")}', str(v)])
                
            cmd.extend(['-ss', str(start), '-t', str(duration), '-i', input_path,
                        '-filter_complex', ";".join(chain), tmp])
            
            subprocess.run(cmd, capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0)
            return os.path.getsize(tmp) if os.path.exists(tmp) else 999999999
        finally:
            if os.path.exists(tmp): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        meta = ffmpeg.probe(input_path)
        video = next(s for s in meta['streams'] if s['codec_type'] == 'video')
        duration = float(meta['format'].get('duration', video.get('duration', 0)))
        orig_w, orig_h = int(video['width']), int(video['height'])
        
        # Get options
        allow_downscale = options.get('allow_downscale', False)  # Default FALSE - don't resize unless explicitly enabled
        transform_filters = options.get('transform_filters', {})
        
        print(f"[GIF v16] Target: {target_size_bytes} bytes, Duration: {duration}s")
        print(f"[GIF v16] allow_downscale: {allow_downscale}")
        print(f"[GIF v16] transform_filters: {transform_filters}")
        
        # 1. Visual Analysis
        start_sample = duration * 0.2
        analysis = self._analyze_visual_complexity(input_path, start_sample)
        
        # Initial Dither Choice: If flat, no dither. If gradients, start with Bayer 3.
        base_dither = "bayer:bayer_scale=3" if analysis['has_gradients'] else "none"
        
        sample_len = min(2.0, duration)
        sample_target = (target_size_bytes / duration) * sample_len * 0.90 # 10% safety
        
        # 2. Tier Selection
        ref_w = min(480, orig_w)
        ref_h = int(orig_h * (ref_w / orig_w)) & ~1
        
        low, high = 0, len(self.SORTED_TIERS) - 1
        best_tier_idx = high
        
        while low <= high:
            mid = (low + high) // 2
            tier = self.SORTED_TIERS[mid]
            sz = self._run_sample_encode(input_path, start_sample, sample_len, ref_w, ref_h,
                                         tier['fps'], tier['colors'], base_dither, transform_filters)
            if sz <= sample_target:
                best_tier_idx, high = mid, mid - 1
            else:
                low = mid + 1
        
        selected_tier = self.SORTED_TIERS[best_tier_idx]
        print(f"[GIF v16] Selected tier: fps={selected_tier['fps']}, colors={selected_tier['colors']}")
        
        # 3. Resolution Solver - only if allow_downscale is True
        if allow_downscale:
            print(f"[GIF v16] Downscaling enabled - searching for optimal resolution")
            low_scale, high_scale = 0.1, 1.0
            final_scale = 0.1
            current_full_est = 0
            
            for iteration in range(4):
                mid_scale = (low_scale + high_scale) / 2
                w, h = (int(orig_w * mid_scale) & ~1), (int(orig_h * mid_scale) & ~1)
                sz = self._run_sample_encode(input_path, start_sample, sample_len, w, h,
                                             selected_tier['fps'], selected_tier['colors'], base_dither, transform_filters)
                current_full_est = (sz / sample_len) * duration
                
                if current_full_est <= target_size_bytes * 0.95:
                    final_scale, low_scale = mid_scale, mid_scale
                else:
                    high_scale = mid_scale
        else:
            # No downscaling - use original resolution
            print(f"[GIF v16] Downscaling disabled - using original resolution {orig_w}x{orig_h}")
            final_scale = 1.0
            w, h = orig_w, orig_h
            # Estimate size at native resolution
            sz = self._run_sample_encode(input_path, start_sample, sample_len, w, h,
                                         selected_tier['fps'], selected_tier['colors'], base_dither, transform_filters)
            current_full_est = (sz / sample_len) * duration

        # 4. Final Dither Refinement
        # Calculate how much space we have left
        final_w, final_h = (int(orig_w * final_scale) & ~1), (int(orig_h * final_scale) & ~1)
        buffer_percent = (target_size_bytes - current_full_est) / target_size_bytes
        
        final_dither = base_dither
        if analysis['has_gradients']:
            if buffer_percent < 0.07: 
                final_dither = "bayer:bayer_scale=5" # Tight budget, use most efficient dither
            elif buffer_percent > 0.18:
                final_dither = "floyd_steinberg" # High budget, use best quality dither

        return {
            'fps': selected_tier['fps'],
            'colors': selected_tier['colors'],
            'dither': final_dither,
            'resolution_scale': round(final_scale, 3),
            'resolution_w': final_w,
            'resolution_h': final_h,
            # Extra analytical data
            'estimated_size_bytes': int(current_full_est),
            'has_gradients': analysis['has_gradients'],
            'complexity_score': round(analysis['score'], 1),
            'size_buffer_percent': round(buffer_percent * 100, 1)
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options):
        
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params: return False

        if status_callback:
            status_callback(f"Encoding GIF ({params['resolution_w']}x{params['resolution_h']}, {params['dither']} dither)")

        # Prepare Filter
        d_parts = params['dither'].split(':')
        d_type = d_parts[0]
        d_opts = f":{d_parts[1]}" if len(d_parts) > 1 else ""
        
        p_opts = f"max_colors={params['colors']}:stats_mode=diff"
        if params['colors'] <= 4: p_opts += ":reserve_transparent=0"

        vf = options.get('transform_filters', {}).get('vf_filters', [])
        chain = []
        curr = "0:v"
        if vf:
            chain.append(f"[0:v]{','.join(vf)}[t]")
            curr = "t"
        
        chain.append(
            f"[{curr}]fps={params['fps']},scale={params['resolution_w']}:{params['resolution_h']}:flags=lanczos[v];"
            f"[v]split[a][b];"
            f"[a]palettegen={p_opts}[p];"
            f"[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle"
        )

        cmd = [get_ffmpeg_binary(), '-y', '-i', input_path]
        in_args = options.get('transform_filters', {}).get('input_args', {})
        for k, v in in_args.items():
            cmd.extend([f'-{k.lstrip("-")}', str(v)])
            
        cmd.extend(['-filter_complex', ";".join(chain), output_path])
        
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, creationflags=0x08000000 if os.name == 'nt' else 0)
        
        while proc.poll() is None:
            if stop_check and stop_check():
                proc.terminate()
                return False
            time.sleep(0.2)
            
        return proc.returncode == 0