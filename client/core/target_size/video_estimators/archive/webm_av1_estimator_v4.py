import os
import time
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional
from client.core.target_size._estimator_protocol import EstimatorProtocol

class Estimator(EstimatorProtocol):
    """
    AV1 Video Estimator v4 using libsvtav1 (SVT-AV1).
    Strategy: Single-pass ABR (SVT-AV1 is optimized for single-pass).
    Implements interruptible execution pattern as per INTERRUPTIBLE_EXECUTION_GUIDE.md
    """

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            fmt = probe['format']
            duration = float(fmt.get('duration', 0))
            if duration == 0 and video: duration = float(video.get('duration', 0))
            width = int(video.get('width', 0))
            height = int(video.get('height', 0))
            fps = 30.0
            if video and 'r_frame_rate' in video:
                parts = video['r_frame_rate'].split('/')
                if len(parts) == 2 and int(parts[1]) > 0: fps = int(parts[0]) / int(parts[1])
                else: fps = float(video['r_frame_rate'])
            return {'duration': duration, 'width': width, 'height': height, 'fps': fps, 'has_audio': audio is not None}
        except: return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30, 'has_audio': False}

    def get_output_extension(self) -> str:
        """Return the output file extension for AV1 videos."""
        return 'webm'

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """
        Calculates optimal Bitrate and Resolution for SVT-AV1.
        """
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0: return {}

        allow_downscale = options.get('allow_downscale', False)

        # 1. Calculate Bitrate Budget
        # Reserve 7% for WebM container overhead
        total_bits = target_size_bytes * 8 * 0.93
        
        # Audio Budget (Opus)
        audio_kbps = 48 if target_size_bytes < 5 * 1024 * 1024 else 96
        if not meta['has_audio']: audio_kbps = 0
        
        audio_bits = (audio_kbps * 1000) * meta['duration']
        video_bits = total_bits - audio_bits
        
        # Safety: If video has < 50% of budget, crush audio to 32k
        if video_bits < (total_bits * 0.5) and meta['has_audio']:
            audio_kbps = 32
            audio_bits = (audio_kbps * 1000) * meta['duration']
            video_bits = total_bits - audio_bits

        video_bps = max(video_bits / meta['duration'], 10000)

        # 2. Resolution Optimization (BPP Logic)
        curr_w = meta['width']
        curr_h = meta['height']
        
        if allow_downscale:
            target_bpp = 0.04
            
            def get_bpp(w, h):
                pixels = w * h
                return video_bps / (pixels * meta['fps'])

            while get_bpp(curr_w, curr_h) < target_bpp and curr_w > 426:
                curr_w = int(curr_w * 0.85)
                curr_h = int(curr_h * 0.85)
                curr_w = curr_w - (curr_w % 2)
                curr_h = curr_h - (curr_h % 2)

        return {
            'video_bitrate_kbps': int(video_bps / 1000),
            'audio_bitrate_kbps': int(audio_kbps),
            'resolution_w': curr_w,
            'resolution_h': curr_h,
            'codec': 'libsvtav1'
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, status_callback=None, stop_check=None, **options) -> bool:
        """
        Executes single-pass SVT-AV1 encoding with interruptible execution.
        SVT-AV1 is optimized for single-pass encoding with excellent quality.
        """
        print("[ESTIMATOR] Executing webm_av1_estimator_v4.py")
        
        def emit(msg: str):
            print(f"[V4] {msg}")
            if status_callback:
                status_callback(msg)
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
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
        
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params:
            emit("Estimation failed")
            return False

        video_bitrate = f"{params['video_bitrate_kbps']}k"
        audio_bitrate = f"{params['audio_bitrate_kbps']}k"
        
        emit(f"SVT-AV1 encoding: {video_bitrate} video, {audio_bitrate} audio, {params['resolution_w']}x{params['resolution_h']}")
        
        try:
            # Build encoding args
            encode_args = {
                'vcodec': 'libsvtav1',
                'b:v': video_bitrate,
                'preset': 6,  # Preset 6: Good balance of speed and quality for SVT-AV1
                'c:a': 'libopus',
                'b:a': audio_bitrate
            }
            
            # Add scaling if needed
            if params['resolution_w'] != params.get('original_width', params['resolution_w']):
                encode_args['vf'] = f"scale={params['resolution_w']}:{params['resolution_h']}"
            
            stream = ffmpeg.input(input_path).output(output_path, **encode_args)
            stream = ffmpeg.overwrite_output(stream)
            
            cmd = ffmpeg.compile(stream)
            emit("Encoding with SVT-AV1 (this may take a while)...")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Drain stderr in background thread
            stderr_chunks = []
            drain_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
            drain_thread.daemon = True
            drain_thread.start()
            
            # Monitor for stop signal
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
                emit(f"Encoding failed: {error_msg[-300:]}")
                print(f"[V4 ERROR] Full error:\n{error_msg}")
                return False
            
            if os.path.exists(output_path):
                actual_mb = os.path.getsize(output_path) / (1024 * 1024)
                emit(f"✓ Complete: {actual_mb:.2f} MB")
                return True
            else:
                emit("Output file not created")
                return False
            
        except Exception as e:
            import traceback
            emit(f"Error: {str(e)}")
            print(f"[V4 ERROR] Exception:\n{traceback.format_exc()}")
            return False