"""
Target Size Mode Configuration
Easy selection of estimator versions per tab/codec for production.
"""

# Default estimator versions per media type and format
PRODUCTION_DEFAULTS = {
    'image': {
        'jpg': 'v7',
        'webp': 'v9',
        'png': 'v7',
        'avif': 'v2',
    },
    'video': {
        'mp4_h264': 'v6',
        'mp4_h265': 'v6',
        'webm_vp9': 'v3',
        'webm_av1': 'v6',
    },
    'loop': {
        'gif': 'v26',
        'webm_loop': 'v7',  # VP9 loop
        'webm_av1_loop': 'v7',  # AV1 loop
    }
}

# Fallback version if specific format not found
DEFAULT_VERSION = 'v2'
