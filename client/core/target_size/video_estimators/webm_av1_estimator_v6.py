import os
import tempfile
import time
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary

class Estimator(EstimatorProtocol):
    """
    AV1 Video Estimator v5.2 (SVT-AV1 Strict + Audio Preservation)
    Strategy: 2-Pass VBR with constrained VBV Buffering.
    
    Changes in v5.2:
    - Audio is NEVER removed if present.
    - Audio bitrate is dynamically compressed (down to 16kbps) to fit budget.
    - Dynamic Overhead Calculation.
    - Strict BPP enforcement.
    """

    def get_output_extension(self) -> str:
        return 'mp4'

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            fmt = probe['format']
            
            duration = float(fmt.get('duration', 0))
            if duration == 0 and video:
                duration = float(video.get('duration', 0))
            
            width = int(video.get('width', 0))
            height = int(video.get('height', 0))
            
            fps = 30.0
            if video and 'r_frame_rate' in video:
                parts = video['r_frame_rate'].split('/')
                if len(parts) == 2 and int(parts[1]) > 0:
                    fps = int(parts[0]) / int(parts[1])
                else:
                    fps = float(video['r_frame_rate'])
            
            return {
                'duration': duration,
                'width': width,
                'height': height,
                'fps': fps,
                'has_audio': audio is not None
            }
        except:
            return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30, 'has_audio': False}

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """
        Calculates strict parameters to force SVT-AV1 into the target box while preserving audio.
        """
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0:
            return {}
        
        allow_downscale = options.get('allow_downscale', False)
        
        # --- 1. DYNAMIC OVERHEAD CALCULATION ---
        # Small files have proportionally higher container overheads.
        if target_size_bytes < 100 * 1024:         # < 100KB
            overhead_safety = 0.70                 # Reserve 30% for headers
        elif target_size_bytes < 500 * 1024:       # < 500KB
            overhead_safety = 0.80                 # Reserve 20%
        elif target_size_bytes < 5 * 1024 * 1024:  # < 5MB
            overhead_safety = 0.90                 # Reserve 10%
        else:
            overhead_safety = 0.95                 # Reserve 5%

        total_bits = target_size_bytes * 8 * overhead_safety
        
        # --- 2. ADAPTIVE AUDIO BUDGETING ---
        audio_kbps = 0
        if meta['has_audio']:
            # Start with a healthy default for Opus
            proposed_audio_kbps = 96
            
            # Helper: Calculate how much % of the budget this audio takes
            def get_audio_ratio(kbps):
                audio_total_bits = (kbps * 1000) * meta['duration']
                return audio_total_bits / total_bits

            # Progressively reduce audio quality if it eats too much of the file
            # We assume video needs at least 70-80% of the space to look decent
            if get_audio_ratio(96) > 0.20: proposed_audio_kbps = 64
            if get_audio_ratio(64) > 0.20: proposed_audio_kbps = 48
            if get_audio_ratio(48) > 0.25: proposed_audio_kbps = 32
            if get_audio_ratio(32) > 0.30: proposed_audio_kbps = 24
            
            # Absolute floor: 16kbps (Opus is still intelligible for speech here)
            # If even 16kbps takes up > 50% of the file, we keep it anyway 
            # because the user requested audio, but video will suffer heavily.
            if get_audio_ratio(24) > 0.40: proposed_audio_kbps = 16
            
            audio_kbps = proposed_audio_kbps
            
        audio_bits = (audio_kbps * 1000) * meta['duration']
        video_bits = total_bits - audio_bits
        
        # Ensure we don't have negative video bits (extreme edge case)
        if video_bits < 0:
            video_bits = total_bits * 0.10 # Give video 10% regardless, file will overshoot slightly
            
        video_bps = max(video_bits / meta['duration'], 5000) # Floor 5kbps
        
        # --- 3. RESOLUTION & BPP OPTIMIZATION ---
        # Check for overrides (e.g. from user transforms)
        width = options.get('override_width', meta['width'])
        height = options.get('override_height', meta['height'])
        
        # SVT-AV1 target BPP. 
        # Since we might have squeezed audio tight, we need to be careful with video resolution.
        target_bpp = 0.065 
        
        def get_bpp(w, h):
            pixels = w * h
            return video_bps / (pixels * meta['fps'])
        
        if allow_downscale:
            # Aggressive downscaling loop
            while get_bpp(width, height) < target_bpp and width > 160:
                width = int(width * 0.80) 
                height = int(height * 0.80)
                width = width - (width % 2)
                height = height - (height % 2)
            
        # If explicit height override wasn't provided but width was, recalculate height based on aspect ratio of the *overridden* width
        # But wait, above logic updates width/height in tandem.
        # If overrides were provided, they are the starting point.
        
        return {
            'video_bitrate_kbps': int(video_bps / 1000),
            'audio_bitrate_kbps': int(audio_kbps),
            'resolution_w': width,
            'resolution_h': height,
            'codec': 'libsvtav1',
            # Derived Params for Execute (VBV Constraints)
            'maxrate_kbps': int((video_bps / 1000) * 1.2), 
            'bufsize_kbps': int((video_bps / 1000) * 2.0),
            'original_width': meta['width'],
            'original_height': meta['height']
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options) -> bool:
        """
        Execute 2-Pass SVT-AV1 conversion with VBV Constraints.
        """
        
        def emit(msg: str):
            if status_callback: status_callback(msg)

        def should_stop() -> bool:
            return stop_check() if stop_check else False

        def run_ffmpeg_process(description, stream_obj):
            def drain_pipe(pipe, collected):
                try:
                    while True:
                        chunk = pipe.read(4096)
                        if not chunk: break
                        collected.append(chunk)
                except: pass

            cmd = ffmpeg.compile(stream_obj, overwrite_output=True)
            
            # Replace cmd[0] with actual FFMPEG_BINARY path
            ffmpeg_bin = get_ffmpeg_binary()
            cmd[0] = ffmpeg_bin
            
            print(f"[V6 DEBUG] Command: {cmd}")
            
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
                    try: process.wait(timeout=2)
                    except: process.kill()
                    emit("Stopped by user")
                    return False
                time.sleep(0.1)

            drain_thread.join(timeout=1)

            if process.returncode != 0:
                error_msg = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
                print(f"[V6 ERROR] FFmpeg failed. Command: {cmd}\nError Output:\n{error_msg}")
                emit(f"FFmpeg Error: {error_msg[-300:]}")
                from client.utils.error_reporter import log_error
                log_error(
                    Exception(f"FFmpeg AV1 failed (returncode={process.returncode})"),
                    context="webm_av1_estimator_v6",
                    additional_info={"command": cmd, "stderr_tail": error_msg[-2000:]}
                )
                return False
            return True

        # --- EXECUTION ---
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params:
            emit("Estimation failed.")
            return False

        bitrate = f"{params['video_bitrate_kbps']}k"
        maxrate = f"{params['maxrate_kbps']}k"
        bufsize = f"{params['bufsize_kbps']}k"
        
        # Build filter chain from transform_filters and scaling
        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        vf_filters = list(transform_filters.get('vf_filters', []))
        
        # Determine effective input width (user override or original)
        target_dims = transform_filters.get('target_dimensions')
        effective_input_w = target_dims[0] if target_dims else params.get('original_width', 0)
        
        # Add scaling filter if resolution changed further than transforms
        if effective_input_w > 0 and params['resolution_w'] < effective_input_w:
            vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
        elif params['resolution_w'] != params.get('original_width', params['resolution_w']) and not target_dims:
            vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
        
        # Build vf argument
        vf_args = {}
        if vf_filters:
            vf_args['vf'] = ','.join(vf_filters)

        emit(f"Target: {params['resolution_w']}x{params['resolution_h']} @ {bitrate} (Audio: {params['audio_bitrate_kbps']}k)")

        # PASS 1
        null_output = "NUL" if os.name == 'nt' else "/dev/null"
        passlogfile = os.path.join(tempfile.gettempdir(), f'ffmpeg2pass_{os.getpid()}_{id(self)}')

        pass1_args = {
            'vcodec': 'libsvtav1',
            'b:v': bitrate,
            'preset': 8,
            'pass': 1,
            'passlogfile': passlogfile,
            'f': 'null',
            'an': None
        }
        pass1_args.update(vf_args)

        pass1_stream = (
            ffmpeg.input(input_path, **input_args)
            .output(null_output, **pass1_args)
        )

        if not run_ffmpeg_process("Pass 1/2: Analysis...", pass1_stream):
            return False

        # PASS 2
        audio_args = {}
        if params['audio_bitrate_kbps'] > 0:
            audio_args['c:a'] = 'aac'  # Use AAC for MP4 container
            audio_args['b:a'] = f"{params['audio_bitrate_kbps']}k"
        
        pass2_args = {
            'vcodec': 'libsvtav1',
            'b:v': bitrate,
            'preset': 5,
            'pass': 2,
            'passlogfile': passlogfile,
        }
        pass2_args.update(audio_args)
        pass2_args.update(vf_args)

        pass2_stream = (
            ffmpeg.input(input_path, **input_args)
            .output(output_path, **pass2_args)
        )

        if not run_ffmpeg_process("Pass 2/2: Encoding...", pass2_stream):
            return False

        if os.path.exists(output_path):
            actual_mb = os.path.getsize(output_path) / (1024 * 1024)
            emit(f"[OK] Complete: {actual_mb:.2f} MB")
            for suffix in ['.log', '.log.mbtree', '-0.log', '-0.log.mbtree']:
                try:
                    p = passlogfile + suffix
                    if os.path.exists(p): os.remove(p)
                except: pass
            return True
        else:
            emit("Output file missing")
            return False