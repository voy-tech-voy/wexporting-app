import os
import time
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional
from client.core.target_size._estimator_protocol import EstimatorProtocol

class Estimator(EstimatorProtocol):
    """
    VP9 Loop Estimator v6 (VP9 for Loopable WebM)
    Strategy: 2-Pass VBR with constrained VBV Buffering.
    
    Based on AV1 loop estimator v6, adapted for VP9 codec:
    - No audio processing (loops are video-only)
    - WebM container output
    - Optimized for loopable content
    - Uses libvpx-vp9 instead of libsvtav1
    """

    def get_output_extension(self) -> str:
        return 'webm'

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
                'has_audio': False  # Loops never have audio
            }
        except:
            return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30, 'has_audio': False}

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """
        Calculates strict parameters to force VP9 into the target box (no audio for loops).
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
        
        # --- 2. NO AUDIO FOR LOOPS ---
        # Loops are video-only, so all bits go to video
        video_bits = total_bits
        video_bps = max(video_bits / meta['duration'], 5000) # Floor 5kbps
        
        print(f"[VP9_LOOP_v6] target_size_bytes={target_size_bytes}, duration={meta['duration']}, video_bps={video_bps}, bitrate_kbps={int(video_bps/1000)}")
        
        # --- 3. RESOLUTION & BPP OPTIMIZATION ---
        # Check for overrides (e.g. from user transforms)
        width = options.get('override_width', meta['width'])
        height = options.get('override_height', meta['height'])
        
        # VP9 target BPP (slightly higher than AV1 since VP9 is less efficient)
        target_bpp = 0.08  # VP9 needs more bits per pixel than AV1
        
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
            
        return {
            'video_bitrate_kbps': int(video_bps / 1000),
            'resolution_w': width,
            'resolution_h': height,
            'codec': 'libvpx-vp9',
            # Derived Params for Execute (VBV Constraints)
            'maxrate_kbps': int((video_bps / 1000) * 1.2), 
            'bufsize_kbps': int((video_bps / 1000) * 2.0),
            'original_width': meta['width'],
            'original_height': meta['height']
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options) -> bool:
        """
        Execute 2-Pass VP9 conversion with VBV Constraints.
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
            
            # Replace cmd[0] with actual FFMPEG_BINARY path (ffmpeg.compile returns just 'ffmpeg')
            ffmpeg_bin = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
            cmd[0] = ffmpeg_bin
            
            print(f"[VP9_LOOP_v6 DEBUG] Command: {cmd}")
            
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
                print(f"[VP9_LOOP_v6 ERROR] FFmpeg failed. Command: {cmd}\nError Output:\n{error_msg}")
                emit(f"FFmpeg Error: {error_msg[-300:]}")
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

        emit(f"Target: {params['resolution_w']}x{params['resolution_h']} @ {bitrate} (Loop, no audio)")

        # PASS 1
        null_output = "NUL" if os.name == 'nt' else "/dev/null"
        
        pass1_args = {
            'vcodec': 'libvpx-vp9',
            'b:v': bitrate,
            'cpu-used': 4,  # VP9 speed preset (0-5, higher=faster)
            'pass': 1,
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

        # PASS 2 - No audio for loops
        pass2_args = {
            'vcodec': 'libvpx-vp9',
            'b:v': bitrate,
            'cpu-used': 1,  # Slower for better quality in pass 2
            'pass': 2,
            'an': None  # No audio in loops
        }
        pass2_args.update(vf_args)

        pass2_stream = (
            ffmpeg.input(input_path, **input_args)
            .output(output_path, **pass2_args)
        )

        if not run_ffmpeg_process("Pass 2/2: Encoding...", pass2_stream):
            return False

        if os.path.exists(output_path):
            actual_mb = os.path.getsize(output_path) / (1024 * 1024)
            emit(f"✓ Complete: {actual_mb:.2f} MB")
            try:
                if os.path.exists("ffmpeg2pass-0.log"): os.remove("ffmpeg2pass-0.log")
            except: pass
            return True
        else:
            emit("Output file missing")
            return False
