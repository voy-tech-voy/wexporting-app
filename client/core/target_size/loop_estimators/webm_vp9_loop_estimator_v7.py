import os
import time
import subprocess
import threading
import re
import ffmpeg
from typing import Dict, Optional, Callable
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary

class Estimator(EstimatorProtocol):
    """
    VP9 Loop Estimator v7 (VP9 for Loopable WebM)
    Strategy: 2-Pass VBR with constrained VBV Buffering.

    Changes from v6:
    - Added progress_callback support:
      Pass 1 (analysis): 0.0 → 0.50 (real-time from out_time_ms)
      Pass 2 (encode):   0.50 → 1.0  (real-time from out_time_ms)
    """

    def get_output_extension(self) -> str:
        return 'webm'

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
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
                'has_audio': False
            }
        except:
            return {'duration': 0, 'width': 0, 'height': 0, 'fps': 30, 'has_audio': False}

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        """Calculates strict parameters to force VP9 into the target box."""
        meta = self.get_media_metadata(input_path)
        if meta['duration'] == 0:
            return {}

        allow_downscale = options.get('allow_downscale', False)

        if target_size_bytes < 100 * 1024:
            overhead_safety = 0.70
        elif target_size_bytes < 500 * 1024:
            overhead_safety = 0.80
        elif target_size_bytes < 5 * 1024 * 1024:
            overhead_safety = 0.90
        else:
            overhead_safety = 0.95

        total_bits = target_size_bytes * 8 * overhead_safety
        video_bits = total_bits
        video_bps = max(video_bits / meta['duration'], 5000)

        print(f"[VP9_LOOP_v7] target_size_bytes={target_size_bytes}, duration={meta['duration']}, video_bps={video_bps}, bitrate_kbps={int(video_bps/1000)}")

        width = options.get('override_width', meta['width'])
        height = options.get('override_height', meta['height'])

        target_bpp = 0.08

        def get_bpp(w, h):
            pixels = w * h
            return video_bps / (pixels * meta['fps'])

        if allow_downscale:
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
            'maxrate_kbps': int((video_bps / 1000) * 1.2),
            'bufsize_kbps': int((video_bps / 1000) * 2.0),
            'original_width': meta['width'],
            'original_height': meta['height'],
            'duration': meta['duration'],
        }

    def _run_process_with_progress(self, cmd, duration, emit, should_stop, update_progress):
        """
        Run a subprocess with real-time progress from FFmpeg's -progress pipe.
        update_progress receives [0.0, 1.0] fractions.
        Returns True on success, False on failure/stop.
        """
        time_pattern = re.compile(r'out_time_ms=(\d+)')

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        stderr_chunks = []

        def drain_stderr(pipe, collected):
            try:
                while True:
                    chunk = pipe.read(4096)
                    if not chunk:
                        break
                    collected.append(chunk)
            except:
                pass

        stderr_thread = threading.Thread(target=drain_stderr, args=(process.stderr, stderr_chunks), daemon=True)
        stderr_thread.start()

        def read_stdout():
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line_str = line if isinstance(line, str) else line.decode('utf-8', errors='ignore')
                    if duration > 0:
                        m = time_pattern.search(line_str)
                        if m:
                            current_s = int(m.group(1)) / 1_000_000.0
                            update_progress(min(0.99, current_s / duration))
            except:
                pass

        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
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
            print(f"[VP9_LOOP_v7 ERROR] FFmpeg failed.\nError: {error_msg}")
            emit(f"FFmpeg Error: {error_msg[-300:]}")
            return False

        update_progress(1.0)
        return True

    def execute(self, input_path: str, output_path: str, target_size_bytes: int,
                status_callback=None, stop_check=None, progress_callback=None, **options) -> bool:
        """Execute 2-Pass VP9 conversion with VBV Constraints and progress bar."""

        def emit(msg: str):
            if status_callback: status_callback(msg)

        def should_stop() -> bool:
            return stop_check() if stop_check else False

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        emit_progress(0.0)

        params = self.estimate(input_path, target_size_bytes, **options)
        if not params:
            emit("Estimation failed.")
            return False

        duration = params.get('duration', 0)
        bitrate = f"{params['video_bitrate_kbps']}k"

        transform_filters = options.get('transform_filters', {})
        input_args = transform_filters.get('input_args', {})
        vf_filters = list(transform_filters.get('vf_filters', []))

        target_dims = transform_filters.get('target_dimensions')
        effective_input_w = target_dims[0] if target_dims else params.get('original_width', 0)

        if effective_input_w > 0 and params['resolution_w'] < effective_input_w:
            vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")
        elif params['resolution_w'] != params.get('original_width', params['resolution_w']) and not target_dims:
            vf_filters.append(f"scale={params['resolution_w']}:{params['resolution_h']}")

        vf_args = {}
        if vf_filters:
            vf_args['vf'] = ','.join(vf_filters)

        emit(f"Target: {params['resolution_w']}x{params['resolution_h']} @ {bitrate} (Loop, no audio)")

        null_output = "NUL" if os.name == 'nt' else "/dev/null"

        # --- PASS 1 (0 → 0.50) ---
        emit("Pass 1/2: Analyzing...")
        pass1_args = {
            'vcodec': 'libvpx-vp9',
            'b:v': bitrate,
            'cpu-used': 8,  # Pass 1 is null-output analysis only; max speed
            'pass': 1,
            'f': 'null',
            'an': None,
            'progress': 'pipe:1',
            'nostats': None,
        }
        pass1_args.update(vf_args)

        pass1_stream = ffmpeg.input(input_path, **input_args).output(null_output, **pass1_args)
        cmd1 = ffmpeg.compile(pass1_stream, overwrite_output=True)
        cmd1[0] = get_ffmpeg_binary()
        print(f"[VP9_LOOP_v7 DEBUG] Pass 1 cmd: {cmd1}")

        if not self._run_process_with_progress(
            cmd1, duration, emit, should_stop,
            lambda p: emit_progress(p * 0.50)
        ):
            return False

        # --- PASS 2 (0.50 → 1.0) ---
        emit("Pass 2/2: Encoding...")
        pass2_args = {
            'vcodec': 'libvpx-vp9',
            'b:v': bitrate,
            'cpu-used': 6,  # Speed-quality balance; bitrate constraint controls size accuracy
            'pass': 2,
            'an': None,
            'progress': 'pipe:1',
            'nostats': None,
        }
        pass2_args.update(vf_args)

        pass2_stream = ffmpeg.input(input_path, **input_args).output(output_path, **pass2_args)
        cmd2 = ffmpeg.compile(pass2_stream, overwrite_output=True)
        cmd2[0] = get_ffmpeg_binary()
        print(f"[VP9_LOOP_v7 DEBUG] Pass 2 cmd: {cmd2}")

        if not self._run_process_with_progress(
            cmd2, duration, emit, should_stop,
            lambda p: emit_progress(0.50 + p * 0.50)
        ):
            return False

        if os.path.exists(output_path):
            actual_mb = os.path.getsize(output_path) / (1024 * 1024)
            emit(f"[OK] Complete: {actual_mb:.2f} MB")
            emit_progress(1.0)
            try:
                if os.path.exists("ffmpeg2pass-0.log"): os.remove("ffmpeg2pass-0.log")
            except: pass
            return True
        else:
            emit("Output file missing")
            return False
