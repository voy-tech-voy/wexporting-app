"""
Target Size Mode Configuration
Easy selection of estimator versions per tab/codec for production.
"""

# Default estimator versions per media type and format
PRODUCTION_DEFAULTS = {
    'image': {
        'jpg': 'v5',
        'webp': 'v5', 
        'png': 'v5',
    },
    'video': {
        'mp4_h264': 'v2',
        'mp4_h265': 'v2',
        'webm_vp9': 'v2',
        'webm_av1': 'v2',
    },
    'loop': {
        'gif': 'v2',
        'webm_loop': 'v2',
    }
}

# Fallback version if specific format not found
DEFAULT_VERSION = 'v2'
