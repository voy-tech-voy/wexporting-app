"""
MP4 H.264 Video Estimator v6
Optimizes H.264/MP4 videos for target file size using adaptive encoding.
- Hardware Encoders (NVENC/QSV/AMF): 1-pass VBR/CBR (stable)
- Software Encoders (CPU): 2-pass CBR (accurate)

Codec efficiency: 1.0x (baseline)

Improvements in v6:
- Better overhead calculation (85% efficiency vs 92% in v5)
- Hardware encoder safety margin to account for less predictable bitrate
- More conservative audio bitrate allocation

Features: 
- Interruptible encoding with proper error capture
- Transform filter support (resize, rotate, retime, time trim)
- Accurate resolution tracking including auto-resize
- Hardware acceleration support
"""
import os
import time
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata
from client.utils.gpu_detector import get_gpu_detector, EncoderType
from client.core.tool_registry import get_ffmpeg_path


class Estimator(EstimatorProtocol):
    """
    MP4 H.264 Adaptive encoding estimator.
    """
    
    @property
    def version(self) -> str:
        return "v6"
    
    @property
    def description(self) -> str:
        return "H.264 Adaptive (Hardware 1-pass / Software 2-pass)"
    
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
        print(f"[H264_v6] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        meta = get_media_metadata(input_path)
        
        # Resolve Encoder
        try:
            ffmpeg_path = get_ffmpeg_path()
            detector = get_gpu_detector(ffmpeg_path)
            codec, encoder_type = detector.get_best_encoder('MP4 (H.264)', prefer_gpu=True)
            print(f"[H264_v6] Resolved encoder: {codec} ({encoder_type})")
        except Exception as e:
            print(f"[H264_v6] GPU detection failed, using libopenh264: {e}")
            codec = "libopenh264"
            encoder_type = EncoderType.CPU

        if meta['duration'] == 0:
            return {
                'video_bitrate_kbps': 1000,
                'audio_bitrate_kbps': 64,
                'encoding_mode': '1-pass' if encoder_type != EncoderType.CPU else '2-pass',
                'codec': codec,
                'resolution_scale': 1.0,
                'encoder_type': encoder_type.value
            }
        
        # 1. Bitrate Budget Calculation
        # v6: More conservative overhead to prevent overshooting
        # MP4 container + muxing overhead + encoder variance = ~15% overhead
        total_bits = target_size_bytes * 8 * 0.85  # 85% efficiency (15% overhead)
        
        # More conservative audio bitrate allocation
        audio_kbps = 64 if target_size_bytes < 5*1024*1024 else 96
        vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'] if meta['has_audio'] else 0)
        
        # If video budget is too small, reduce audio
        if vid_bits < total_bits * 0.5:
            audio_kbps = 32
            vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'])
        
        vid_bps = max(vid_bits / meta['duration'], 50000)  # Minimum 50kbps
        
        # 2. H.264 Specific Settings
        # Hardware encoders are less predictable, apply safety margin
        if encoder_type != EncoderType.CPU:
             # Hardware encoders often overshoot slightly, reduce target by 5%
             vid_bps = vid_bps * 0.95
             print(f"[H264_v6] Applied hardware encoder safety margin: {int(vid_bps/1000)}kbps")
        
        # 3. Resolution Scaling Based on BPP
        curr_w = options.get('override_width', meta['width'])
        curr_h = options.get('override_height', meta['height'])
        
        if allow_downscale:
            target_bpp = 0.08 / efficiency
            
            h_for_calc = curr_h if curr_h else (curr_w * meta['height'] / meta['width'])
            
            while (vid_bps / (curr_w * h_for_calc * meta['fps'])) < target_bpp and curr_w > 480:
                curr_w = int(curr_w * 0.85)
                curr_w -= (curr_w % 2)
                h_for_calc = curr_w * (curr_h / curr_w) if curr_h else (curr_w * meta['height'] / meta['width'])
        
        final_h = int(curr_h * (curr_w / options.get('override_width', meta['width']))) if options.get('override_width') else int(meta['height'] * (curr_w / meta['width']))
        final_h = final_h & ~1
        
        print(f"[H264_v6] Estimated: {int(vid_bps/1000)}kbps, {curr_w}x{final_h}")
        
        return {
            'video_bitrate_kbps': int(vid_bps / 1000),
            'audio_bitrate_kbps': audio_kbps,
            'resolution_scale': curr_w / meta['width'],
            'resolution_w': curr_w,
            'resolution_h': int(meta['height'] * (curr_w / meta['width'])) & ~1,
            'estimated_size': target_size_bytes,
            'codec': codec,
            'encoding_mode': '1-pass' if encoder_type != EncoderType.CPU else '2-pass',
            'has_audio': meta['has_audio'],
            'estimator_version': self.version,
            'original_width': meta['width'],
            'original_height': meta['height'],
            'encoder_type': encoder_type.value
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
        """Execute encoding (1-pass for HW, 2-pass for SW)."""
        import threading
        import subprocess
        import re
        
        def emit(msg: str):
            if status_callback:
                status_callback(msg)
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
        def emit_progress(progress: float):
            if progress_callback:
                progress_callback(min(max(progress, 0.0), 1.0))
        
        def drain_pipe(pipe, collected: list):
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
        codec = params['codec']
        has_audio = params.get('has_audio', True)
        is_hardware = params.get('encoder_type') != 'cpu'
        
        # Get duration for progress tracking
        meta = get_media_metadata(input_path)
        duration = meta.get('duration', 0)
        
        # Get transform filters
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        vf_filters = list(transform_filters.get('vf_filters', []))
        
        # Resolution scaling
        # Resolution scaling
        target_dims = transform_filters.get('target_dimensions')
        if target_dims:
            effective_input_w = target_dims[0]
        else:
            effective_input_w = params.get('original_width', 0)
            
        if effective_input_w > 0 and params['resolution_w'] < effective_input_w:
             vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
        elif params.get('resolution_scale', 1.0) < 1.0 and not target_dims:
             vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
        
        vf_args = {'vf': ','.join(vf_filters)} if vf_filters else {}
        
        emit(f"Using {codec} ({'Hardware 1-pass' if is_hardware else 'Software 2-pass'}), {video_bitrate}kbps")
        emit_progress(0.0)
        
        try:
            # Base encoding args
            encode_args = {
                'vcodec': codec,
                'b:v': f'{video_bitrate}k',
                'maxrate': f'{int(video_bitrate * 1.5)}k',
                'bufsize': f'{int(video_bitrate * 2)}k',
                'pix_fmt': 'yuv420p',
            }
            encode_args.update(vf_args)
            
            if has_audio:
                encode_args['acodec'] = 'aac'
                encode_args['b:a'] = f'{audio_bitrate}k'
            
            # --- HARDWARE PATH: 1-PASS ---
            if is_hardware:
                emit("Encoding with hardware acceleration...")
                
                encode_args.update({
                    'progress': 'pipe:1',
                    'nostats': None
                })
                
                stream = ffmpeg.input(input_path, **input_args)
                if has_audio:
                    stream = ffmpeg.output(stream.video, stream.audio, output_path, **encode_args)
                else:
                    stream = ffmpeg.output(stream.video, output_path, **encode_args)
                
                stream = ffmpeg.overwrite_output(stream)
                cmd = ffmpeg.compile(stream)
                
                # DEBUG: Print the command
                emit(f"[DEBUG] Command: {cmd}")
                
                # Run single pass
                success = self._run_process(cmd, duration, emit, should_stop, emit_progress, drain_pipe)
                
                # Verify output
                if success and os.path.exists(output_path):
                    actual_mb = os.path.getsize(output_path) / (1024 * 1024)
                    emit(f"[OK] Complete: {actual_mb:.2f} MB")
                    emit_progress(1.0)
                    return True
                elif success:
                    emit("[X] Output file not created")
                    return False
                return False

            # --- SOFTWARE PATH: 2-PASS (Legacy) ---
            else:
                passlogfile = os.path.join(tempfile.gettempdir(), f'ffmpeg2pass_{os.getpid()}_{id(self)}')
                encode_args['passlogfile'] = passlogfile
                
                # Pass 1
                emit("Pass 1/2: Analyzing video...")
                pass1_args = encode_args.copy()
                pass1_args['f'] = 'null'
                pass1_args['pass'] = 1
                pass1_args['an'] = None
                
                null_output = 'NUL' if os.name == 'nt' else '/dev/null'
                stream1 = ffmpeg.input(input_path, **input_args).output(null_output, **pass1_args)
                stream1 = ffmpeg.overwrite_output(stream1)
                
                if not self._run_process(ffmpeg.compile(stream1), duration, emit, should_stop, lambda p: emit_progress(p*0.5), drain_pipe, is_pass1=True):
                    return False
                
                # Pass 2
                emit("Pass 2/2: Encoding final video...")
                pass2_args = encode_args.copy()
                pass2_args['pass'] = 2
                pass2_args.update({'progress': 'pipe:1', 'nostats': None})
                
                stream2 = ffmpeg.input(input_path, **input_args)
                if has_audio:
                    stream2 = ffmpeg.output(stream2, output_path, **pass2_args)
                else:
                    stream2 = ffmpeg.output(stream2.video, output_path, **pass2_args)
                
                stream2 = ffmpeg.overwrite_output(stream2)
                
                success = self._run_process(ffmpeg.compile(stream2), duration, emit, should_stop, lambda p: emit_progress(0.5 + p*0.5), drain_pipe)
                
                # Cleanup
                self._cleanup_passlog(passlogfile)
                
                # Verify output
                if success and os.path.exists(output_path):
                    actual_mb = os.path.getsize(output_path) / (1024 * 1024)
                    emit(f"[OK] Complete: {actual_mb:.2f} MB")
                    emit_progress(1.0)
                    return True
                elif success:
                    emit("[X] Output file not created")
                    return False
                return False

        except Exception as e:
            emit(f"Error: {str(e)}")
            from client.utils.error_reporter import log_error
            log_error(e, context="mp4_h264_estimator_v6 / execute")
            return False

    def _run_process(self, cmd, duration, emit, should_stop, update_progress, drain_pipe, is_pass1=False):
        import subprocess
        import threading
        import re

        ffmpeg_bin = get_ffmpeg_path()
        cmd[0] = ffmpeg_bin
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        stderr_chunks = []
        stderr_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
        stderr_thread.daemon = True
        stderr_thread.start()
        
        # Progress parsing
        time_pattern = re.compile(r'out_time_ms=(\d+)')
        
        def read_stdout():
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line_str = line if isinstance(line, str) else line.decode('utf-8', errors='ignore')
                    
                    if duration > 0:
                        time_match = time_pattern.search(line_str)
                        if time_match:
                            current_time_s = int(time_match.group(1)) / 1000000.0
                            progress = min(0.99, current_time_s / duration)
                            update_progress(progress)
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
            emit(f"{'Pass 1' if is_pass1 else 'Encoding'} failed: {error_msg[-200:]}")
            from client.utils.error_reporter import log_error
            log_error(
                Exception(f"FFmpeg mp4_h264 failed (returncode={process.returncode})"),
                context="mp4_h264_estimator_v6",
                additional_info={"command": cmd, "stderr_tail": error_msg[-2000:]}
            )
            return False

        if not is_pass1:
            update_progress(1.0)

        return True

    def _cleanup_passlog(self, passlogfile: str):
        try:
            for suffix in ['-0.log', '-0.log.mbtree']:
                log_path = passlogfile + suffix
                if os.path.exists(log_path):
                    os.remove(log_path)
        except Exception:
            pass

# Backward compatibility
_estimator = Estimator()

def optimize_video_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
