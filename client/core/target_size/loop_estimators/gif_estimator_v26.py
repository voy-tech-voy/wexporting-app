import os
import time
import tempfile
import subprocess
import threading
import ffmpeg
import re
from typing import Dict, Optional, Callable
from client.core.target_size._estimator_protocol import EstimatorProtocol
from client.core.target_size._common import get_ffmpeg_binary, run_ffmpeg_skill_standard

class Estimator(EstimatorProtocol):
    """
    GIF Estimator v26 - Progress bar support added.

    Changes from v25:
    - progress_callback now wired throughout estimate() and execute()
      Estimation phase: 0.0 → 0.70 (stepped after each _run_sample call)
      Encode phase:     0.70 → 1.0 (via run_ffmpeg_skill_standard return)
    """

    # For Fixed Resolution: We go as low as needed
    DEEP_QUALITY_STEPS = [256, 128, 64, 32, 16]

    # For Resize Enabled: We stop at this floor before downscaling
    QUALITY_FLOOR = {'fps': 12, 'colors': 128}

    def get_output_extension(self) -> str:
        return 'gif'

    def get_media_metadata(self, file_path: str) -> dict:
        try:
            probe = ffmpeg.probe(file_path)
            v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            return {
                'duration': float(probe['format'].get('duration', v.get('duration', 0))),
                'width': int(v['width']), 'height': int(v['height'])
            }
        except: return {'duration': 0, 'width': 0, 'height': 0}

    def _calculate_effective_duration(self, meta_duration: float, options: dict) -> float:
        duration = meta_duration
        t_filters = options.get('transform_filters', {})
        inp_args = t_filters.get('input_args', {})
        clean_args = {k.lstrip('-'): v for k, v in inp_args.items()}

        if 'to' in clean_args and 'ss' in clean_args:
            try:
                start = float(clean_args['ss'])
                end = float(clean_args['to'])
                duration = max(0.1, end - start)
            except: pass
        elif 't' in clean_args:
            try:
                duration = min(duration, float(clean_args['t']))
            except: pass
        elif 'ss' in clean_args:
            try:
                start = float(clean_args['ss'])
                duration = max(0.1, duration - start)
            except: pass

        vf = t_filters.get('vf_filters', [])
        for f in vf:
            if 'setpts=' in f:
                try:
                    factor = float(f.split('setpts=')[1].split('*')[0])
                    if factor > 0:
                        duration = duration * factor
                except: pass

        return duration

    def _get_transformed_dimensions(self, orig_w: int, orig_h: int, options: dict) -> tuple:
        t_filters = options.get('transform_filters', {})
        vf = t_filters.get('vf_filters', [])

        w, h = orig_w, orig_h

        for f in vf:
            if f.startswith('transpose='):
                transpose_count = sum(1 for flt in vf if flt.startswith('transpose='))
                if transpose_count == 1:
                    w, h = h, w
                break

        target_dims = t_filters.get('target_dimensions')
        if target_dims:
            if w != orig_w:
                return target_dims
            return target_dims

        for f in vf:
            if f.startswith('scale='):
                try:
                    parts = f.replace('scale=', '').split(':')
                    sw = parts[0].split('=')[-1] if '=' in parts[0] else parts[0]
                    sh = parts[1].split(':')[0] if len(parts) > 1 else '-2'

                    scale_w = int(sw) if sw not in ['-2', '-1'] else -2
                    scale_h = int(sh) if sh not in ['-2', '-1'] else -2

                    if scale_w == -2 and scale_h > 0:
                        scale_w = int(w * (scale_h / h)) & ~1
                    elif scale_h == -2 and scale_w > 0:
                        scale_h = int(h * (scale_w / w)) & ~1

                    if scale_w > 0 and scale_h > 0:
                        return (scale_w, scale_h)
                except: pass

        return (w, h)

    def _analyze_gradients(self, input_path: str, start: float) -> bool:
        """Detects if dither is needed. Flat colors (VAV < 18) get dither=none."""
        try:
            cmd = [get_ffmpeg_binary(), '-y', '-ss', str(start), '-t', '1', '-i', input_path,
                   '-vf', 'signalstats', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
            stderr_text = res.stderr.decode('utf-8', errors='replace') if res.stderr else ''
            vavs = re.findall(r"VAV=(\d+)", stderr_text)
            avg_vav = sum(int(v) for v in vavs) / len(vavs) if vavs else 100
            return avg_vav > 18
        except: return True

    def _run_sample(self, input_path, start, dur, w, h, fps, col, dither, filters) -> int:
        tmp = tempfile.NamedTemporaryFile(suffix='.gif', delete=False).name
        try:
            d_parts = dither.split(':')
            d_type, d_opts = d_parts[0], f":{d_parts[1]}" if len(d_parts) > 1 else ""
            p_opts = f"max_colors={col}:stats_mode=diff"

            vf = filters.get('vf_filters', [])
            vf_no_scale = [f for f in vf if not f.startswith('scale=')]

            chain = []
            if vf_no_scale:
                chain.append(f"[0:v]{','.join(vf_no_scale)}[t]")
                curr = "t"
            else:
                curr = "0:v"

            chain.append(f"[{curr}]fps={fps},scale={w}:{h}:flags=lanczos[v];[v]split[a][b];"
                         f"[a]palettegen={p_opts}[p];[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle")

            cmd = [get_ffmpeg_binary(), '-y', '-hide_banner', '-loglevel', 'error']
            for k, v in filters.get('input_args', {}).items(): cmd.extend([f'-{k.lstrip("-")}', str(v)])
            cmd.extend(['-ss', str(start), '-t', str(dur), '-i', input_path, '-filter_complex', ";".join(chain), tmp])

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return os.path.getsize(tmp) if os.path.exists(tmp) else 999999999
        finally:
            if os.path.exists(tmp): os.remove(tmp)

    def estimate(self, input_path: str, target_size_bytes: int, **options) -> Dict:
        meta = self.get_media_metadata(input_path)
        if not meta['duration']: return {}

        allow_downscale = options.get('allow_downscale', False)
        transform_filters = options.get('transform_filters', {})
        stop_check = options.get('stop_check')
        progress_callback = options.get('progress_callback')

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        duration = self._calculate_effective_duration(meta['duration'], options)
        orig_w, orig_h = meta['width'], meta['height']
        base_w, base_h = self._get_transformed_dimensions(orig_w, orig_h, options)

        has_gradients = self._analyze_gradients(input_path, duration * 0.2)
        base_dither = "bayer:bayer_scale=3" if has_gradients else "none"

        usable_budget = target_size_bytes * 0.90
        sample_dur, start_time = min(2.0, duration), duration * 0.2
        sample_target = (usable_budget / duration) * sample_dur

        best_cfg = None

        # --- Progress tracking ---
        # Path A: up to 5 samples (DEEP_QUALITY_STEPS)
        # Path B: up to 4 ladder + 5 binary scale = up to 9 samples
        # We estimate a max of 10 samples for the progress budget.
        total_samples = 10
        completed_samples = 0

        last_sz = None  # Track for fallback
        if not allow_downscale:
            # PATH A: FIXED RESOLUTION
            for col in self.DEEP_QUALITY_STEPS:
                if stop_check and stop_check():
                    break
                ref_fps = 10
                sz = self._run_sample(input_path, start_time, sample_dur, base_w, base_h,
                                      ref_fps, col, base_dither, transform_filters)
                last_sz = sz
                completed_samples += 1
                emit_progress(completed_samples / total_samples * 0.65)

                price_per_frame = sz / (ref_fps * sample_dur)
                max_fps = (usable_budget / duration) / price_per_frame

                if max_fps >= 5.0:
                    final_fps = min(int(max_fps), 24)
                    best_cfg = {'fps': final_fps, 'colors': col, 'dither': base_dither,
                                'w': base_w, 'h': base_h, 'scale': 1.0, 'sz': price_per_frame * final_fps * sample_dur}
                    break
        else:
            # PATH B: AUTO-RESIZE
            ladder = [{'c': 128, 'f': 24}, {'c': 128, 'f': 15}, {'c': 128, 'f': 12}, {'c': 256, 'f': 12}]
            for tier in ladder:
                if stop_check and stop_check():
                    break
                sz = self._run_sample(input_path, start_time, sample_dur, base_w, base_h,
                                      tier['f'], tier['c'], base_dither, transform_filters)
                completed_samples += 1
                emit_progress(completed_samples / total_samples * 0.65)

                if sz <= sample_target:
                    best_cfg = {'fps': tier['f'], 'colors': tier['c'], 'dither': base_dither,
                                'w': base_w, 'h': base_h, 'scale': 1.0, 'sz': sz}
                    break

            if not best_cfg:
                low_s, high_s = 0.1, 1.0
                found_scale = 0.1
                for _ in range(5):
                    if stop_check and stop_check():
                        break
                    mid_s = (low_s + high_s) / 2
                    tw, th = (int(base_w * mid_s) & ~1), (int(base_h * mid_s) & ~1)
                    sz = self._run_sample(input_path, start_time, sample_dur, tw, th,
                                          self.QUALITY_FLOOR['fps'], self.QUALITY_FLOOR['colors'], base_dither, transform_filters)
                    completed_samples += 1
                    emit_progress(completed_samples / total_samples * 0.65)

                    if sz <= sample_target:
                        found_scale, low_s = mid_s, mid_s
                    else:
                        high_s = mid_s
                best_cfg = {'fps': self.QUALITY_FLOOR['fps'], 'colors': self.QUALITY_FLOOR['colors'],
                            'dither': base_dither, 'scale': found_scale, 'sz': sz,
                            'w': int(base_w * found_scale) & ~1, 'h': int(base_h * found_scale) & ~1}

        if not best_cfg:
            # Target unreachable at fixed resolution — best-effort floor rather than hard fail.
            # Output will exceed target, but the user gets a file instead of a silent failure.
            floor_sz = last_sz if last_sz is not None else sample_target
            print(f"[GIF_v26] ⚠ Target unreachable ({target_size_bytes/1024:.0f} KB) at fixed resolution. Using 5fps/16-color floor.")
            best_cfg = {
                'fps': 5, 'colors': 16, 'dither': 'none',
                'w': base_w, 'h': base_h, 'scale': 1.0,
                'sz': floor_sz,
                '_floor_fallback': True,  # Flag for execute() to emit a warning
            }

        # Dither refinement
        est_full = (best_cfg['sz'] / sample_dur) * duration
        buffer = (target_size_bytes - est_full) / target_size_bytes

        if has_gradients:
            if buffer > 0.18:
                best_cfg['dither'] = "sierra2_4a"
            elif buffer < 0.05:
                best_cfg['dither'] = "bayer:bayer_scale=5"
        else:
            best_cfg['dither'] = "none"

        emit_progress(0.70)  # Estimation complete

        return {
            'fps': best_cfg['fps'], 'colors': best_cfg['colors'], 'dither': best_cfg['dither'],
            'resolution_w': best_cfg['w'], 'resolution_h': best_cfg['h'],
            'resolution_scale': round(best_cfg.get('scale', 1.0), 3),
            'has_gradients': has_gradients,
            'estimated_total_kb': round(est_full / 1024, 1)
        }

    def execute(self, input_path: str, output_path: str, target_size_bytes: int,
                status_callback=None, stop_check=None, progress_callback=None, **options):
        self._current_stop_check = stop_check

        def emit_progress(value: float):
            if progress_callback:
                progress_callback(min(max(value, 0.0), 1.0))

        emit_progress(0.0)

        params = self.estimate(
            input_path, target_size_bytes,
            stop_check=stop_check,
            progress_callback=progress_callback,
            **options
        )
        if not params: return False

        if params.get('_floor_fallback') and status_callback:
            status_callback(f"⚠ Target too small — encoding at minimum quality ({params['resolution_w']}px, {params['fps']}fps, {params['colors']} colors)")
        elif status_callback:
            status_callback(f"Encoding: {params['resolution_w']}px, {params['fps']}fps, {params['dither']} dither")

        emit_progress(0.70)  # Estimation done, final encode starting

        d_parts = params['dither'].split(':')
        d_type, d_opts = d_parts[0], f":{d_parts[1]}" if len(d_parts) > 1 else ""
        p_opts = f"max_colors={params['colors']}:stats_mode=diff"

        vf = options.get('transform_filters', {}).get('vf_filters', [])
        vf_no_scale = [f for f in vf if not f.startswith('scale=')]

        chain = []
        if vf_no_scale:
            chain.append(f"[0:v]{','.join(vf_no_scale)}[t]")
            curr = "t"
        else:
            curr = "0:v"
        chain.append(f"[{curr}]fps={params['fps']},scale={params['resolution_w']}:{params['resolution_h']}:flags=lanczos[v];"
                     f"[v]split[a][b];[a]palettegen={p_opts}[p];[b][p]paletteuse=dither={d_type}{d_opts}:diff_mode=rectangle")

        cmd = [get_ffmpeg_binary(), '-y']
        for k, v in options.get('transform_filters', {}).get('input_args', {}).items():
            cmd.extend([f'-{k.lstrip("-")}', str(v)])
        cmd.extend(['-i', input_path, '-filter_complex', ";".join(chain), output_path])

        rc = run_ffmpeg_skill_standard(cmd, stop_check=stop_check, log_target=output_path)
        if rc != 0:
            from client.utils.error_reporter import log_error
            log_error(
                Exception(f"FFmpeg gif failed (returncode={rc})"),
                context="gif_estimator_v26",
                additional_info={"command": cmd}
            )
        if rc == 0:
            emit_progress(1.0)
        return rc == 0
