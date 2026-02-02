import os
import time
import subprocess
import threading
import ffmpeg
from typing import Dict, Optional
from client.core.target_size._estimator_protocol import EstimatorProtocol

class Estimator(EstimatorProtocol):
    """
    AV1 Video Estimator v5 (SVT-AV1)
    Strategy: 2-Pass ABR (Average Bitrate) using libsvtav1.
    - Pass 1: Preset 8 (Fast analysis)
    - Pass 2: Preset 5 (Balanced Quality/Speed)
    """

    def get_output_extension(self) -> str:
        """Return output file extension."""
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
            
            # Parse frame rate
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
            return {
                'duration': 0, 'width': 0, 'height': 0, 'fps': 30, 'has_audio': False
            }

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """
        Calculate optimal encoding parameters for SVT-AV1.
        """
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0:
            return {}
        
        allow_downscale = options.get('allow_downscale', False)
        
        # 1. Calculate bitrate budget
        # WebM/AV1 has slightly higher container overhead than raw streams
        container_overhead = 0.93  # 7% overhead safety buffer
        total_bits = target_size_bytes * 8 * container_overhead
        
        # 2. Audio budget (Opus is efficient)
        # Use 48k for small files (<5MB), 96k for larger
        audio_kbps = 0
        if meta['has_audio']:
            audio_kbps = 48 if target_size_bytes < 5 * 1024 * 1024 else 96
            
        audio_bits = (audio_kbps * 1000) * meta['duration']
        
        # 3. Video budget
        video_bits = total_bits - audio_bits
        
        # Safety: If video gets < 50% of bits, reduce audio to 32k
        if video_bits < (total_bits * 0.5) and meta['has_audio']:
            audio_kbps = 32
            audio_bits = (audio_kbps * 1000) * meta['duration']
            video_bits = total_bits - audio_bits

        video_bps = max(video_bits / meta['duration'], 10000)  # Floor at 10kbps
        
        # 4. Resolution optimization (BPP)
        width = meta['width']
        height = meta['height']
        
        if allow_downscale:
            # SVT-AV1 is very efficient, can tolerate lower BPP than H264
            target_bpp = 0.04 
            
            def get_bpp(w, h):
                pixels = w * h
                return video_bps / (pixels * meta['fps'])
            
            # Scale down if BPP is too low
            while get_bpp(width, height) < target_bpp and width > 426:
                width = int(width * 0.85)
                height = int(height * 0.85)
                # Ensure even dimensions
                width = width - (width % 2)
                height = height - (height % 2)
        
        return {
            'video_bitrate_kbps': int(video_bps / 1000),
            'audio_bitrate_kbps': int(audio_kbps),
            'resolution_w': width,
            'resolution_h': height,
            'codec': 'libsvtav1'
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int, 
                status_callback=None, stop_check=None, **options) -> bool:
        """
        Execute 2-Pass SVT-AV1 conversion with interruptible execution.
        """
        
        # Helper to emit status
        def emit(msg: str):
            if status_callback: status_callback(msg)

        # Helper to check stop
        def should_stop() -> bool:
            return stop_check() if stop_check else False

        # --- INTERNAL HELPER FOR SUBPROCESS EXECUTION ---
        def run_ffmpeg_process(description, stream_obj):
            """Runs a single FFmpeg pass using subprocess to allow stopping."""
            
            def drain_pipe(pipe, collected):
                try:
                    while True:
                        chunk = pipe.read(4096)
                        if not chunk: break
                        collected.append(chunk)
                except: pass

            cmd = ffmpeg.compile(stream_obj, overwrite_output=True)
            emit(description)

            # Create process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Drain stderr in background (prevent deadlock)
            stderr_chunks = []
            drain_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
            drain_thread.daemon = True
            drain_thread.start()

            # Monitor loop
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
                # Filter out common benign FFmpeg warnings if needed
                emit(f"FFmpeg Error: {error_msg[-300:]}")
                return False
            
            return True

        # --- MAIN EXECUTION FLOW ---

        # 1. Get Parameters
        params = self.estimate(input_path, target_size_bytes, **options)
        if not params:
            emit("Estimation failed (invalid duration?)")
            return False

        # 2. Common Arguments
        bitrate = f"{params['video_bitrate_kbps']}k"
        
        # Scaling Filter
        vf_args = {}
        if params['resolution_w'] != params.get('original_width', params['resolution_w']):
            vf_args['vf'] = f"scale={params['resolution_w']}:{params['resolution_h']}"

        # 3. PASS 1: Analysis
        # preset=8 is fast, sufficient for 2-pass stats
        # -an: No audio, -f null: No output file
        null_output = "NUL" if os.name == 'nt' else "/dev/null"
        
        pass1_args = {
            'vcodec': 'libsvtav1',
            'b': bitrate,
            'preset': 8,
            'pass': 1,
            'f': 'null',
            'an': None
        }
        pass1_args.update(vf_args)

        pass1_stream = (
            ffmpeg.input(input_path)
            .output(null_output, **pass1_args)
        )

        if not run_ffmpeg_process("Pass 1/2: Analysis...", pass1_stream):
            return False

        # 4. PASS 2: Export
        # preset=5 is the quality sweet spot for SVT-AV1 VOD
        audio_args = {}
        if params['audio_bitrate_kbps'] > 0:
            audio_args['c:a'] = 'libopus'
            audio_args['b:a'] = f"{params['audio_bitrate_kbps']}k"
        
        pass2_args = {
            'vcodec': 'libsvtav1',
            'b': bitrate,
            'preset': 5,
            'pass': 2,
        }
        pass2_args.update(audio_args)
        pass2_args.update(vf_args)

        pass2_stream = (
            ffmpeg.input(input_path)
            .output(output_path, **pass2_args)
        )

        if not run_ffmpeg_process("Pass 2/2: Encoding...", pass2_stream):
            return False

        # 5. Verification
        if os.path.exists(output_path):
            actual_mb = os.path.getsize(output_path) / (1024 * 1024)
            emit(f"✓ Complete: {actual_mb:.2f} MB")
            
            # Clean up ffmpeg pass log files (ffmpeg2pass-0.log)
            # They usually generate in the current working directory
            try:
                log_file = "ffmpeg2pass-0.log"
                if os.path.exists(log_file):
                    os.remove(log_file)
            except:
                pass
                
            return True
        else:
            emit("Output file missing")
            return False