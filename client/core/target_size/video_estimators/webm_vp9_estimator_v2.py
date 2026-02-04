"""
WebM VP9 Video Estimator v2
Optimizes VP9/WebM videos for target file size using 2-pass CBR encoding.
Codec efficiency: 1.4x (40% better than H.264)

This is a self-contained estimator that owns its complete encoding strategy.
"""
import os
import time
import tempfile
import ffmpeg
from typing import Dict, Optional, Callable, Any

from .._estimator_protocol import EstimatorProtocol
from .._common import get_media_metadata


class Estimator(EstimatorProtocol):
    """WebM VP9 2-pass CBR encoding estimator."""
    
    @property
    def version(self) -> str:
        return "v2"
    
    @property
    def description(self) -> str:
        return "VP9 2-pass CBR encoding (40% more efficient)"
    
    def get_output_extension(self) -> str:
        return "webm"
    
    def estimate(
        self, 
        input_path: str, 
        target_size_bytes: int, 
        **options
    ) -> Dict[str, Any]:
        allow_downscale = options.get('allow_downscale', False)
        print(f"[VP9_v2] Estimating for {target_size_bytes} bytes, downscale={allow_downscale}")
        
        meta = get_media_metadata(input_path)
        if meta['duration'] == 0:
            return {'video_bitrate_kbps': 1000, 'audio_bitrate_kbps': 64, 'encoding_mode': '2-pass', 'codec': 'libvpx-vp9', 'resolution_scale': 1.0}
        
        total_bits = target_size_bytes * 8 * 0.92
        audio_kbps = 64 if target_size_bytes < 5*1024*1024 else 128
        vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'] if meta['has_audio'] else 0)
        
        if vid_bits < total_bits * 0.5:
            audio_kbps = 32
            vid_bits = total_bits - ((audio_kbps*1000)*meta['duration'])
        
        vid_bps = max(vid_bits / meta['duration'], 50000)
        codec = "libvpx-vp9"
        efficiency = 1.4
        
        curr_w = meta['width']
        if allow_downscale:
            target_bpp = 0.08 / efficiency
            while (vid_bps / (curr_w * (curr_w * meta['height'] / meta['width']) * meta['fps'])) < target_bpp and curr_w > 480:
                curr_w = int(curr_w * 0.85)
                curr_w -= (curr_w % 2)
        
        print(f"[VP9_v2] Estimated: {int(vid_bps/1000)}kbps, {curr_w}x{int(meta['height'] * (curr_w / meta['width'])) & ~1}")
        
        return {
            'video_bitrate_kbps': int(vid_bps / 1000),
            'audio_bitrate_kbps': audio_kbps,
            'resolution_scale': curr_w / meta['width'],
            'resolution_w': curr_w,
            'resolution_h': int(meta['height'] * (curr_w / meta['width'])) & ~1,
            'estimated_size': target_size_bytes,
            'codec': codec,
            'encoding_mode': '2-pass',
            'has_audio': meta['has_audio']
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
        def emit(msg: str):
            if status_callback:
                status_callback(msg)
        
        def should_stop() -> bool:
            return stop_check() if stop_check else False
        
        params = self.estimate(input_path, target_size_bytes, **options)
        video_bitrate = params['video_bitrate_kbps']
        resolution_scale = params.get('resolution_scale', 1.0)
        codec = params['codec']
        rotation = options.get('rotation')
        
        emit(f"Using {codec}, {video_bitrate}kbps video (WebM: no audio)")
        
        passlogfile = os.path.join(tempfile.gettempdir(), f'ffmpeg2pass_{os.getpid()}_{id(self)}')
        
        try:
            encode_args = {
                'vcodec': codec,
                'b:v': f'{video_bitrate}k',
                'maxrate': f'{int(video_bitrate * 1.5)}k',
                'bufsize': f'{int(video_bitrate * 2)}k',
                'passlogfile': passlogfile,
                'an': None,  # WebM: no audio
            }
            
            # PASS 1
            emit("Pass 1/2: Analyzing video...")
            input_stream, video_stream = self._build_stream(input_path, resolution_scale, rotation)
            
            pass1_args = encode_args.copy()
            pass1_args['f'] = 'null'
            pass1_args['pass'] = 1
            
            null_output = 'NUL' if os.name == 'nt' else '/dev/null'
            pass1_stream = ffmpeg.output(video_stream, null_output, **pass1_args)
            pass1_stream = ffmpeg.overwrite_output(pass1_stream)
            
            try:
                ffmpeg.run(pass1_stream, capture_stdout=True, capture_stderr=True)
            except ffmpeg.Error as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                emit(f"Pass 1 failed: {error_msg[:200]}")
                return False
            
            if should_stop():
                emit("Stopped by user")
                return False
            
            # PASS 2
            emit("Pass 2/2: Encoding final video...")
            input_stream2, video_stream2 = self._build_stream(input_path, resolution_scale, rotation)
            
            pass2_args = encode_args.copy()
            pass2_args['pass'] = 2
            
            pass2_stream = ffmpeg.output(video_stream2, output_path, **pass2_args)
            pass2_stream = ffmpeg.overwrite_output(pass2_stream)
            
            try:
                ffmpeg.run(pass2_stream, capture_stdout=True, capture_stderr=True)
            except ffmpeg.Error as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                emit(f"Pass 2 failed: {error_msg[:200]}")
                return False
            
            self._cleanup_passlog(passlogfile)
            
            if os.path.exists(output_path):
                actual_mb = os.path.getsize(output_path) / (1024 * 1024)
                emit(f"[OK] Complete: {actual_mb:.2f} MB")
                return True
            return False
                
        except Exception as e:
            emit(f"Error: {str(e)}")
            return False
    
    def _build_stream(self, input_path: str, resolution_scale: float, rotation: Optional[str]):
        input_stream = ffmpeg.input(input_path)
        video_stream = input_stream.video
        
        if resolution_scale < 1.0:
            meta = get_media_metadata(input_path)
            new_width = int(meta['width'] * resolution_scale)
            new_width = new_width - (new_width % 2)
            video_stream = ffmpeg.filter(video_stream, 'scale', new_width, -2)
        
        if rotation and rotation != "No rotation":
            if rotation == "90° clockwise":
                video_stream = ffmpeg.filter(video_stream, 'transpose', 1)
            elif rotation == "180°":
                video_stream = ffmpeg.filter(video_stream, 'transpose', 2)
                video_stream = ffmpeg.filter(video_stream, 'transpose', 2)
            elif rotation == "270° clockwise":
                video_stream = ffmpeg.filter(video_stream, 'transpose', 2)
        
        return input_stream, video_stream
    
    def _cleanup_passlog(self, passlogfile: str):
        try:
            for suffix in ['-0.log', '-0.log.mbtree']:
                log_path = passlogfile + suffix
                if os.path.exists(log_path):
                    os.remove(log_path)
        except Exception:
            pass


_estimator = Estimator()

def optimize_video_params(file_path: str, target_size_bytes: int, allow_downscale: bool = False, **kwargs) -> Dict:
    return _estimator.estimate(file_path, target_size_bytes, allow_downscale=allow_downscale, **kwargs)
