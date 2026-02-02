"""
GIF Estimator v4 - Self-Contained Class-Based Estimator
Optimizes GIF animations for target file size using palette-based compression.
Uses preset combinations of FPS, colors, dither, and scale.

CHANGELOG:
- v4: Expanded preset list (20 presets) for finer size targeting
- Improved binary search to select highest quality preset under target
- v3: Full class-based architecture with integrated execution
- Processes FULL video for estimation (no sampling) to fix size accuracy issues
- Interruptible encoding with proper error capture
"""
import os
import time
import tempfile
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional, Callable
from client.core.target_size._estimator_protocol import EstimatorProtocol


class Estimator(EstimatorProtocol):
    """
    GIF Estimator v4 - Self-Contained Estimator
    Strategy: Binary search on quality presets with full-video testing.
    """
    
    # GIF Presets: (fps, colors, dither, scale)
    # Ordered from highest quality to lowest
    # v4: Expanded from 7 to 20 presets for finer size targeting
    GIF_PRESETS = [
        (30, 256, "floyd_steinberg", 1.0),
        (25, 256, "floyd_steinberg", 1.0),
        (24, 256, "bayer:bayer_scale=4", 1.0),
        (20, 256, "bayer:bayer_scale=3", 1.0),
        (18, 256, "bayer:bayer_scale=3", 1.0),
        (15, 256, "bayer:bayer_scale=2", 1.0),
        (15, 192, "bayer:bayer_scale=2", 1.0),
        (15, 128, "bayer:bayer_scale=2", 1.0),
        (12, 128, "bayer:bayer_scale=2", 1.0),
        (15, 128, "bayer:bayer_scale=1", 0.90),
        (12, 128, "bayer:bayer_scale=1", 0.85),
        (12, 96, "bayer:bayer_scale=1", 0.85),
        (12, 64, "bayer:bayer_scale=1", 0.85),
        (10, 64, "bayer:bayer_scale=1", 0.80),
        (10, 64, "none", 0.70),
        (8, 64, "none", 0.70),
        (8, 48, "none", 0.60),
        (8, 32, "none", 0.50),
        (6, 32, "none", 0.50),
        (6, 24, "none", 0.40),
    ]
    
    def get_output_extension(self) -> str:
        return 'gif'
    
    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            fmt = probe['format']
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            duration = float(fmt.get('duration', 0))
            if duration == 0 and video:
                duration = float(video.get('duration', 0))
            return {
                'duration': duration,
                'width': int(video['width']),
                'height': int(video['height'])
            }
        except:
            return {'duration': 0, 'width': 0, 'height': 0}
    
    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """
        Calculate optimal GIF parameters using binary search on presets.
        Processes the FULL video to ensure accurate file size estimation.
        """
        allow_downscale = options.get('allow_downscale', False)
        
        print(f"[ESTIMATOR] Using loop_estimators/gif_estimator_v4.py")
        print(f"[GIF_v4] Optimizing for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0:
            return {
                'fps': 15,
                'colors': 128,
                'dither': 'bayer:bayer_scale=2',
                'resolution_scale': 1.0,
                'width': meta.get('width', 0),
                'height': meta.get('height', 0)
            }
        
        # Check for overrides
        meta['width'] = options.get('override_width', meta['width'])
        meta['height'] = options.get('override_height', meta['height'])
        
        # Filter presets based on downscale permission
        valid = [p for p in self.GIF_PRESETS if allow_downscale or p[3] == 1.0]
        
        # Binary search for optimal preset
        # Start with best=0 (highest quality). If all presets fit, we want the best one.
        left, right, best = 0, len(valid) - 1, 0
        
        while left <= right:
            mid = (left + right) // 2
            fps, colors, dither, scale = valid[mid]
            w, h = int(meta['width'] * scale), int(meta['height'] * scale)
            tmp = self._get_temp_filename()
            
            try:
                # Parse dither parameters
                dither_args = self._parse_dither(dither)
                
                # Build FFmpeg graph - USE FULL VIDEO
                in_stream = ffmpeg.input(input_path)
                scaled = (
                    in_stream
                    .filter('fps', fps)
                    .filter('scale', w, h)
                )
                split = scaled.filter('split')
                palette = split[0].filter('palettegen', max_colors=colors)
                
                out = ffmpeg.filter([split[1], palette], 'paletteuse', **dither_args)
                
                # Run encoding on FULL video
                out.output(tmp).run(quiet=True, overwrite_output=True)
                
                if os.path.exists(tmp) and os.path.getsize(tmp) <= target_size_bytes:
                    best = mid
                    right = mid - 1  # Try higher quality
                else:
                    left = mid + 1  # File too big, reduce quality
            except:
                left = mid + 1
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        
        p = valid[best]
        print(f"[GIF_v4] Result: {p[0]}fps, {p[1]} colors, scale {int(p[3]*100)}%")
        
        return {
            'fps': p[0],
            'colors': p[1],
            'dither': p[2],
            'resolution_scale': p[3],
            'width': int(meta['width'] * p[3]),
            'height': int(meta['height'] * p[3])
        }
    
    def execute(
        self,
        input_path: str,
        output_path: str,
        target_size_bytes: int,
        status_callback: Optional[Callable[[str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        **options
    ) -> bool:
        """
        Execute GIF encoding with palette generation.
        """
        def emit(msg: str):
            if status_callback:
                status_callback(msg)
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
        # Get optimal parameters
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params:
            emit("Estimation failed")
            return False
        
        fps = params['fps']
        colors = params['colors']
        dither = params['dither']
        scale = params['resolution_scale']
        
        emit(f"Encoding GIF: {fps}fps, {colors} colors, scale {int(scale * 100)}%")
        
        # Get metadata for scaling
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0:
            emit("✗ No video stream found")
            return False
        
        target_w = int(meta['width'] * scale)
        target_h = int(meta['height'] * scale)
        
        # Parse dither parameters
        dither_args = self._parse_dither(dither)
        dither_type = dither.split(':')[0] if ':' in dither else dither
        
        # Get transform filters
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        vf_filters = list(transform_filters.get('vf_filters', []))
        
        # Build filter_complex chain with transforms
        # Order: transforms → fps → scale → palette generation → paletteuse
        filter_parts = []
        
        # Start with input
        current_label = "0:v"
        
        # Apply transform filters first
        if vf_filters:
            transform_chain = ','.join(vf_filters)
            filter_parts.append(f"[{current_label}]{transform_chain}[transformed]")
            current_label = "transformed"
        
        # Then apply GIF-specific filters (fps, scale, palette)
        filter_parts.append(
            f"[{current_label}]fps={fps},scale={target_w}:{target_h}[v];"
            f"[v]split[a][b];"
            f"[a]palettegen=max_colors={colors}[p];"
            f"[b][p]paletteuse=dither={dither_type}"
        )
        
        filter_complex = ';'.join(filter_parts)
        
        input_stream = ffmpeg.input(input_path, **input_args)
        output_stream = ffmpeg.output(
            input_stream,
            output_path,
            filter_complex=filter_complex
        )
        
        # Run with interruptibility
        if not self._run_ffmpeg_process("Encoding GIF...", output_stream, emit, should_stop):
            return False
        
        # Verify output
        if os.path.exists(output_path):
            actual_size = os.path.getsize(output_path)
            emit(f"✓ Complete: {actual_size / 1024:.1f} KB")
            return True
        else:
            emit("✗ Output file not created")
            return False
    
    def _get_temp_filename(self, ext='gif'):
        f = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
        f.close()
        return f.name
    
    def _parse_dither(self, dither: str) -> dict:
        """Parse dither string into FFmpeg arguments."""
        dither_args = {}
        if ':' in dither:
            base, params = dither.split(':', 1)
            dither_args['dither'] = base
            for p in params.split(':'):
                k, v = p.split('=')
                dither_args[k] = v
        else:
            dither_args['dither'] = dither
        return dither_args
    
    def _run_ffmpeg_process(self, description: str, stream_obj, emit, should_stop) -> bool:
        """Run FFmpeg process with interruptibility."""
        def drain_pipe(pipe, collected):
            try:
                while True:
                    chunk = pipe.read(4096)
                    if not chunk:
                        break
                    collected.append(chunk)
            except:
                pass
        
        cmd = ffmpeg.compile(stream_obj, overwrite_output=True)
        print(f"[GIF_v4 DEBUG] Command: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        stderr_chunks = []
        drain_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
        drain_thread.daemon = True
        drain_thread.start()
        
        while process.poll() is None:
            if should_stop():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except:
                    process.kill()
                emit("Stopped by user")
                return False
            time.sleep(0.1)
        
        drain_thread.join(timeout=1)
        
        if process.returncode != 0:
            error_msg = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
            print(f"[GIF_v4 ERROR] FFmpeg failed. Command: {' '.join(cmd)}\nError Output:\n{error_msg}")
            emit(f"FFmpeg Error: {error_msg[-300:]}")
            return False
        
        return True


# Legacy function wrapper for backward compatibility
def optimize_gif_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    """Legacy wrapper - delegates to Estimator class."""
    estimator = Estimator()
    return estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
