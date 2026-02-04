"""
Conversion Presets Configuration

This file contains preset definitions for:
- Video Quality Presets (Standard and Auto-Resize)
- Social Platform Optimization Settings (e.g. Instagram)
- Aspect Ratio Maps
"""

# ============================================================================
# VIDEO QUALITY PRESETS (CRF, RESOLUTION, BITRATE, SIZE_FACTOR)
# ============================================================================

# Preset Index for Reference (typically middle quality)
VIDEO_REFERENCE_PRESET_IDX = 2

# Standard Presets
# (CRF, Resolution %, Audio kbps, Size Factor vs Reference)
VIDEO_QUALITY_PRESETS_STANDARD = [
    (18, 100, 192, 2.5),  # High Quality (CRF 18)
    (23, 100, 128, 1.0),  # Medium (CRF 23) - Reference
    (28, 100, 96, 0.45),  # Low (CRF 28)
    (32, 100, 64, 0.25),  # Very Low (CRF 32)
]

# Auto-Resize Presets (Includes downscaling logic)
VIDEO_QUALITY_PRESETS_AUTORESIZE = [
    (18, 100, 192, 2.5),  # High Quality
    (23, 100, 128, 1.0),  # Medium (No resize)
    (26, 90, 112, 0.65),  # Medium-Low + 90% scale
    (28, 80, 96, 0.40),   # Low + 80% scale
    (30, 70, 80, 0.25),   # Lower + 70% scale
    (32, 60, 64, 0.15),   # Very Low + 60% scale
    (34, 50, 48, 0.10)    # Minimum + 50% scale
]


# ============================================================================
# SOCIAL PLATFORM PRESETS
# ============================================================================

SOCIAL_PLATFORM_PRESETS = {
    'Instagram': {
        # Core codec settings
        'vcodec': 'libx264',
        'profile:v': 'high',
        'level:v': '4.2',
        'pix_fmt': 'yuv420p',
        
        # Color Integrity
        'color_primaries': 'bt709',
        'color_trc': 'bt709',
        'colorspace': 'bt709',
        
        # Audio
        'acodec': 'aac',
        'b:a': '128k',
        'ar': '44100',
        'ac': '2', # Stereo
        
        # Bitrate & GOP
        'r': '30',
        'g': '60',        # 2-second keyframe interval for 30fps
        'b:v': '5000k',   # 5Mbps target
        'maxrate': '8000k',
        'bufsize': '10000k',
        
        # Metadata
        'movflags': '+faststart',
        'f': 'mp4',
        
        # Scaling Logic
        'force_original_aspect_ratio': 'decrease', # Default (fit)
        'scaling_flags': 'lanczos', 
        'use_padding': True,     # Default
        'supported_background_styles': ['Black Bars', 'Blurred Background', 'Fill/Zoom']
    },
    'X': {
        # Core codec settings (X Server "Wall" Optimization)
        'vcodec': 'libx264',
        'profile:v': 'high',
        'level:v': '4.1', # Capped at 4.1
        'pix_fmt': 'yuv420p',
        
        # Color Integrity
        'color_primaries': 'bt709',
        'color_trc': 'bt709',
        'colorspace': 'bt709',
        
        # Audio
        'acodec': 'aac',
        'b:a': '128k',
        'ar': '44100',
        'ac': '2',
        
        # Bitrate & GOP
        'r': '30',
        'g': '60',
        'b:v': '5000k',   # 5Mbps target
        'maxrate': '5000k', # Capped at 5M
        'bufsize': '10000k',
        
        # Metadata
        'movflags': '+faststart',
        'f': 'mp4',
        
        # Scaling Logic
        'force_original_aspect_ratio': 'decrease',
        'scaling_flags': 'lanczos', 
        'use_padding': True,
        'supported_background_styles': ['Black Bars', 'Blurred Background', 'Fill/Zoom']
    }
}

# ============================================================================
# BACKGROUND STYLES
# ============================================================================
BG_STYLE_BLACK_BARS = 'Black Bars'
BG_STYLE_BLURRED = 'Blurred Background'
BG_STYLE_FILL_ZOOM = 'Fill/Zoom'

# ============================================================================
# ASPECT RATIO MAPS
# ============================================================================

RATIO_MAPS = {
    '4:3': (1440, 1080),
    '1:1': (1080, 1080),
    '16:9': (1920, 1080),
    '9:16': (1080, 1920),
    '3:4': (1080, 1350)
}

# ============================================================================
# LOOP TAB PRESETS
# ============================================================================

LOOP_PRESETS = {
    'Hero 720p': {
        'format_type': 'webm',
        'vcodec': 'libaom-av1',
        'crf': '35',
        'b:v': '0',
        'an': True,
        'tile-columns': '1',
        'scale': '1280:720',
        'row': 'Hero',
        'tooltip_title': '[FAST] Core Web Vitals Optimized',
        'tooltip_body': 'Specifically tuned for website headers. Uses AV1/VP9 for ultra-low file sizes and strips audio to ensure it autoplays instantly in all browsers without slowing down your PageSpeed score.'
    },
    'Hero 1920p': {
        'format_type': 'webm',
        'vcodec': 'libaom-av1',
        'crf': '35',
        'b:v': '0',
        'an': True,
        'tile-columns': '1',
        'scale': '1920:1080',
        'allow_upscaling': True,
        'row': 'Hero',
        'tooltip_title': '[FAST] Core Web Vitals Optimized (FHD)',
        'tooltip_body': 'Specifically tuned for website headers. Uses AV1/VP9 for ultra-low file sizes and strips audio to ensure it autoplays instantly in all browsers without slowing down your PageSpeed score.'
    },
    'Alpha Loop': {
        'format_type': 'webm',
        'vcodec': 'libvpx-vp9',
        'pix_fmt': 'yuva420p',
        'metadata': {'s:v:0': 'alpha_mode=1'},
        'tune': 'animation', # Note: Verify encoder support
        'row': 'Features',
        'tooltip_title': '💎 Transparent (Glass) Mode',
        'tooltip_body': "Preserves the 'Alpha Channel' (transparency). Perfect for floating UI icons, logos, or overlaying animations on a website."
    }
}
