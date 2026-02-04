"""
MP4 H.264 Video Estimator v4
Optimizes H.264/MP4 videos for target file size using 2-pass CBR encoding.
Codec efficiency: 1.0x (baseline)

Features: 
- Interruptible encoding with proper error capture
- Transform filter support (resize, rotate, retime, time trim)
- Accurate resolution tracking including auto-resize

Changes from v3:
- Added transform_filters support via **options
- Removed legacy _build_stream method
- Apply transforms via filter chain like AV1 v6
"""
import os
import time
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata, get_ffmpeg_binary
from ...ffmpeg_utils import has_audio_stream


class Estimator(EstimatorProtocol):
    """
    MP4 H.264 2-pass CBR encoding estimator with transform filter support.
    
    Strategy:
    - Pass 1: Analyze video with transforms applied
    - Pass 2: Encode with calculated bitrate and transforms
    """
    
    @property
    def version(self) -> str:
        return "v4"
    
    @property
    def description(self) -> str:
        return "H.264 2-pass CBR (transforms + interruptible)"
    
    def get_output_extension(self) -> str:
        return "mp4"
    
    def estimate(
        self, 
        input_path: str, 
        target_size_bytes: int, 
        **options
    ) -> Dict[str, Any]:
        """Calculate optimal encoding parameters for H.264 target size."""
        allow_downscale = options.get('allow_downscale', False)
        print(f"[H264_v4] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        meta = get_media_metadata(input_path)
        if meta['duration'] == 0:
            return {
                'video_bitrate_kbps': 1000,
                'audio_bitrate_kbps': 64,
                'encoding_mode': '2-pass',
                'codec': 'libx264',
                'resolution_scale': 1.0
            }
        
        # 1. Bitrate Budget Calculation
        total_bits = target_size_bytes * 8 * 0.92  # 92% efficiency (8% overhead)
        audio_kbps = 64 if target_size_bytes < 5*1024*1024 else 128
        vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'] if meta['has_audio'] else 0)
        
        # If video budget is too small, reduce audio
        if vid_bits < total_bits * 0.5:
            audio_kbps = 32
            vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'])
        
        vid_bps = max(vid_bits / meta['duration'], 50000)  # Minimum 50kbps
        
        # 2. H.264 Specific Settings
        codec = "libx264"
        efficiency = 1.0  # Baseline efficiency
        
        # 3. Resolution Scaling Based on BPP (Bits Per Pixel)
        # Check for overrides (e.g. from user transforms)
        curr_w = options.get('override_width', meta['width'])
        curr_h = options.get('override_height', meta['height'])
        
        # If we have overrides, use them as the baseline
        if allow_downscale:
            target_bpp = 0.08 / efficiency  # Target 0.08 BPP for H.264
            
            # Use curr_h if available, otherwise calculate from aspect ratio
            h_for_calc = curr_h if curr_h else (curr_w * meta['height'] / meta['width'])
            
            while (vid_bps / (curr_w * h_for_calc * meta['fps'])) < target_bpp and curr_w > 480:
                curr_w = int(curr_w * 0.85)
                curr_w -= (curr_w % 2)  # Ensure even width
                h_for_calc = curr_w * (curr_h / curr_w) if curr_h else (curr_w * meta['height'] / meta['width'])
        
        # Calculate final height
        final_h = int(curr_h * (curr_w / options.get('override_width', meta['width']))) if options.get('override_width') else int(meta['height'] * (curr_w / meta['width']))
        final_h = final_h & ~1
        
        print(f"[H264_v4] Estimated: {int(vid_bps/1000)}kbps, {curr_w}x{final_h}")
        
        return {
            'video_bitrate_kbps': int(vid_bps / 1000),
            'audio_bitrate_kbps': audio_kbps,
            'resolution_scale': curr_w / meta['width'],
            'resolution_w': curr_w,
            'resolution_h': int(meta['height'] * (curr_w / meta['width'])) & ~1,
            'estimated_size': target_size_bytes,
            'codec': codec,
            'encoding_mode': '2-pass',
            'has_audio': meta['has_audio'],
            'estimator_version': self.version,
            'original_width': meta['width'],
            'original_height': meta['height']
        }
    
    def execute(
        self,
        input_path: str,
        output_path: str,
        target_size_bytes: int,
        status_callback: Optional[Callable[[str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        **options
    ) -> bool:
        """Execute 2-pass CBR encoding for H.264 with transform filters."""
        import threading
        import subprocess
        import re
        
        def emit(msg: str):
            if status_callback:
                status_callback(msg)
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
        def emit_progress(progress: float):
            """Emit progress (0.0-1.0) if callback available"""
            if progress_callback:
                progress_callback(min(max(progress, 0.0), 1.0))
        
        def drain_pipe(pipe, collected: list):
            """Drain pipe in background thread to prevent buffer deadlock."""
            try:
                while True:
                    chunk = pipe.read(4096)
                    if not chunk:
                        break
                    collected.append(chunk)
            except:
                pass
        
        # Get parameters
        params = self.estimate(input_path, target_size_bytes, **options)
        
        video_bitrate = params['video_bitrate_kbps']
        audio_bitrate = params['audio_bitrate_kbps']
        resolution_scale = params.get('resolution_scale', 1.0)
        codec = params['codec']
        has_audio = params.get('has_audio', True)
        
        # Get duration for progress tracking
        meta = get_media_metadata(input_path)
        duration = meta.get('duration', 0)
        
        # Get transform filters
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        vf_filters = list(transform_filters.get('vf_filters', []))
        
        # Determine effective input width (user override or original)
        target_dims = transform_filters.get('target_dimensions')
        effective_input_w = target_dims[0] if target_dims else params.get('original_width', 0)
        
        # Add auto-resize scaling filter ONLY if further downscaling occurred
        if effective_input_w > 0 and params['resolution_w'] < effective_input_w:
            vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
        elif resolution_scale < 1.0 and not target_dims:
            vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
        
        # Build vf argument
        vf_args = {}
        if vf_filters:
            vf_args['vf'] = ','.join(vf_filters)
        
        emit(f"Using {codec}, {video_bitrate}kbps video, {audio_bitrate}kbps audio")
        
        # Emit 0% at start
        emit_progress(0.0)
        
        # Generate unique passlogfile
        passlogfile = os.path.join(
            tempfile.gettempdir(), 
            f'ffmpeg2pass_{os.getpid()}_{id(self)}'
        )
        
        try:
            # Base encoding args
            encode_args = {
                'vcodec': codec,
                'b:v': f'{video_bitrate}k',
                'maxrate': f'{int(video_bitrate * 1.5)}k',
                'bufsize': f'{int(video_bitrate * 2)}k',
                'passlogfile': passlogfile,
            }
            encode_args.update(vf_args)
            
            # Audio settings
            if has_audio:
                encode_args['b:a'] = f'{audio_bitrate}k'
                encode_args['acodec'] = 'aac'
            
            # =============================================
            # PASS 1: Analyze
            # =============================================
            emit("Pass 1/2: Analyzing video...")
            
            pass1_args = encode_args.copy()
            pass1_args['f'] = 'null'
            pass1_args['pass'] = 1
            pass1_args['an'] = None  # No audio for pass 1
            
            null_output = 'NUL' if os.name == 'nt' else '/dev/null'
            pass1_stream = ffmpeg.input(input_path, **input_args).output(null_output, **pass1_args)
            pass1_stream = ffmpeg.overwrite_output(pass1_stream)
            
            # Get the command and run with subprocess for proper pipe handling
            cmd = ffmpeg.compile(pass1_stream)
            
            # Replace cmd[0] with actual FFMPEG_BINARY path
            ffmpeg_bin = get_ffmpeg_binary()
            cmd[0] = ffmpeg_bin
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Drain stderr in background thread to prevent deadlock
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
                emit(f"Pass 1 failed: {error_msg[-200:]}")
                return False
            
            # Pass 1 complete - report 50% progress
            emit_progress(0.50)
            
            # =============================================
            # PASS 2: Encode with progress tracking
            # =============================================
            emit("Pass 2/2: Encoding final video...")
            
            pass2_args = encode_args.copy()
            pass2_args['pass'] = 2
            
            input_stream = ffmpeg.input(input_path, **input_args)
            if has_audio:
                pass2_stream = ffmpeg.output(input_stream, output_path, **pass2_args)
            else:
                pass2_stream = ffmpeg.output(input_stream.video, output_path, **pass2_args)
            
            pass2_stream = ffmpeg.overwrite_output(pass2_stream)
            
            cmd2 = ffmpeg.compile(pass2_stream)
            
            # Add progress tracking flags before FFmpeg command
            cmd2_list = list(cmd2)
            cmd2_list.insert(1, '-progress')
            cmd2_list.insert(2, 'pipe:1')
            cmd2_list.insert(3, '-nostats')
            cmd2 = cmd2_list
            
            # Replace cmd[0] with actual FFMPEG_BINARY path
            ffmpeg_bin = get_ffmpeg_binary()
            cmd2[0] = ffmpeg_bin
            
            process = subprocess.Popen(
                cmd2,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stderr_chunks = []
            stderr_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
            stderr_thread.daemon = True
            stderr_thread.start()
            
            # Parse progress from stdout
            time_pattern = re.compile(r'out_time_ms=(\d+)')
            
            def read_stdout():
                try:
                    while True:
                        line = process.stdout.readline()
                        if not line:
                            break
                        line_str = line if isinstance(line, str) else line.decode('utf-8', errors='ignore')
                        
                        # Parse progress
                        if duration > 0:
                            time_match = time_pattern.search(line_str)
                            if time_match:
                                current_time_ms = int(time_match.group(1))
                                current_time_s = current_time_ms / 1000000.0  # microseconds to seconds
                                # Scale progress from 0.50-0.95 (pass 2 is 50-95%, final 5% for cleanup)
                                progress = 0.50 + min(0.45, (current_time_s / duration) * 0.45)
                                emit_progress(progress)
                except:
                    pass
            
            stdout_thread = threading.Thread(target=read_stdout)
            stdout_thread.daemon = True
            stdout_thread.start()
            
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
            
            stderr_thread.join(timeout=1)
            stdout_thread.join(timeout=1)
            
            if process.returncode != 0:
                error_msg = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
                emit(f"Pass 2 failed: {error_msg[-200:]}")
                return False
            
            # Cleanup passlog files
            self._cleanup_passlog(passlogfile)
            
            # Verify output
            if os.path.exists(output_path):
                actual_mb = os.path.getsize(output_path) / (1024 * 1024)
                emit(f"[OK] Complete: {actual_mb:.2f} MB")
                emit_progress(1.0)  # Report 100% on success
                return True
            else:
                emit("[X] Output file not created")
                return False
                
        except Exception as e:
            emit(f"Error: {str(e)}")
            return False
    
    def _cleanup_passlog(self, passlogfile: str):
        """Clean up FFmpeg pass log files."""
        try:
            for suffix in ['-0.log', '-0.log.mbtree']:
                log_path = passlogfile + suffix
                if os.path.exists(log_path):
                    os.remove(log_path)
        except Exception:
            pass


# Backward compatibility: expose optimize_video_params function
_estimator = Estimator()

def optimize_video_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    """Legacy function interface for backward compatibility."""
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
