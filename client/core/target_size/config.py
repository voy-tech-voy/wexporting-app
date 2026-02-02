"""
Target Size Mode Configuration
Easy selection of estimator versions per tab/codec for production.
"""

# Default estimator versions per media type and format
PRODUCTION_DEFAULTS = {
    'image': {
        'jpg': 'v5',
        'webp': 'v6', 
        'png': 'v5',
    },
    'video': {
        'mp4_h264': 'v4',
        'mp4_h265': 'v4',
        'webm_vp9': 'v3',
        'webm_av1': 'v6',
    },
    'loop': {
        'gif': 'v4',
        'webm_loop': 'v2',
    }
}

# Fallback version if specific format not found
DEFAULT_VERSION = 'v2'
