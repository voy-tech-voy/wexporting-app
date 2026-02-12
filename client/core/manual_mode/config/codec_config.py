"""Codec configuration for video and image conversion"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class CodecConfig:
    """
    Configuration for a video codec
    
    Provides mapping between UI quality (0-100) and codec-specific parameters.
    """
    name: str
    ffmpeg_codec: str
    container: str
    crf_min: int
    crf_max: int
    crf_default: int
    preset: str
    pixel_format: Optional[str] = 'yuv420p'
    audio_codec: Optional[str] = None
    audio_bitrate: str = '128k'
    extra_args: Dict[str, str] = field(default_factory=dict)
    
    def ui_quality_to_crf(self, ui_quality: int) -> int:
        """
        Convert UI quality (0-100, higher is better) to codec CRF
        
        CRF scale is inverted (lower CRF = better quality).
        
        Args:
            ui_quality: Quality from UI (0-100)
            
        Returns:
            CRF value for codec
        """
        # Invert quality (UI 100 = best quality = lowest CRF)
        normalized = 1.0 - (ui_quality / 100.0)
        crf = self.crf_min + normalized * (self.crf_max - self.crf_min)
        return int(round(crf))


# Video codec definitions matching existing conversion_engine.py logic
VIDEO_CODECS = {
    'h264': CodecConfig(
        name='H.264',
        ffmpeg_codec='libx264',
        container='mp4',
        crf_min=17,
        crf_max=28,
        crf_default=23,
        preset='medium',
        pixel_format='yuv420p',
        audio_codec='aac',
        audio_bitrate='128k'
    ),
    'h265': CodecConfig(
        name='H.265/HEVC',
        ffmpeg_codec='libx265',
        container='mp4',
        crf_min=24,
        crf_max=32,
        crf_default=28,
        preset='medium',
        pixel_format='yuv420p',
        audio_codec='aac',
        audio_bitrate='128k',
        extra_args={'x265-params': 'log-level=error'}
    ),
    'vp9': CodecConfig(
        name='VP9',
        ffmpeg_codec='libvpx-vp9',
        container='webm',
        crf_min=23,
        crf_max=40,
        crf_default=31,
        preset='',  # VP9 doesn't use preset
        pixel_format='yuv420p',
        audio_codec=None,  # WebM typically no audio in this app
        extra_args={'b:v': '0', 'row-mt': '1'}  # b:v=0 required for VP9 CRF mode
    ),
    'av1': CodecConfig(
        name='AV1',
        ffmpeg_codec='libsvtav1',
        container='mp4',
        crf_min=10,
        crf_max=63,
        crf_default=30,
        preset='8',
        pixel_format='yuv420p',
        audio_codec='aac',
        extra_args={}
    )
}


# Image quality configuration matching existing conversion_engine.py logic
IMAGE_QUALITY_CONFIG = {
    'jpg': {
        'qscale_min': 1,    # FFmpeg q:v range (1=best, 31=worst)
        'qscale_max': 31,
        'default_quality': 85
    },
    'jpeg': {
        'qscale_min': 1,
        'qscale_max': 31,
        'default_quality': 85
    },
    'png': {
        'compression_min': 0,  # PNG compression level (0=none, 9=max)
        'compression_max': 9,
        'default_quality': 85
    },
    'webp': {
        'quality_min': 0,   # WebP quality (0=worst, 100=best)
        'quality_max': 100,
        'default_quality': 85
    },
    'avif': {
        'crf_min': 0,       # AVIF CRF (0=lossless, 63=worst)
        'crf_max': 63,
        'default_quality': 85
    }
}


def get_video_codec_config(codec_name: str) -> Optional[CodecConfig]:
    """
    Get codec configuration by name
    
    Args:
        codec_name: Codec identifier (e.g., 'h264', 'vp9')
        
    Returns:
        CodecConfig instance or None if not found
    """
    return VIDEO_CODECS.get(codec_name.lower())


def get_image_quality_config(format_name: str) -> dict:
    """
    Get image quality configuration by format
    
    Args:
        format_name: Image format (e.g., 'jpg', 'png', 'webp')
        
    Returns:
        Configuration dict with quality parameters
    """
    return IMAGE_QUALITY_CONFIG.get(format_name.lower(), IMAGE_QUALITY_CONFIG['jpg'])


def get_default_codec_for_container(container: str) -> Optional[str]:
    """
    Get default codec for container format
    
    Args:
        container: Container format ('mp4', 'webm')
        
    Returns:
        Codec name or None
    """
    container_map = {
        'mp4': 'h264',
        'webm': 'vp9'
    }
    return container_map.get(container.lower())
