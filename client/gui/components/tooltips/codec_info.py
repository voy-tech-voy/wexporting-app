"""
Codec Comparison Tooltip Content

Provides data for codec efficiency comparison tooltips.
"""

CODEC_COMPARISONS = {
    "video": {
        "title": "Video Codec Efficiency",
        "desc": "Higher efficiency = better quality at same file size",
        "items": [
            ("H.264", 40, "warning", "Standard"),
            ("H.265", 70, "info", "Better"),
            ("AV1", 100, "success", "Best")
        ]
    },
    "loop": {
        "title": "Loop Format Efficiency",
        "desc": "WebM provides HD quality for same size as low-res GIF",
        "items": [
            ("GIF", 15, "error", "Poor"),
            ("WebM", 100, "success", "Excellent")
        ]
    },
    "loop_av1": {
        "title": "WebM AV1 Codec",
        "desc": "Smallest files with best quality. Slower encoding speed.",
        "items": [
            ("VP9", 70, "info", "Fast encode"),
            ("AV1", 100, "success", "Best quality")
        ]
    },
    "loop_vp9": {
        "title": "WebM VP9 Codec",
        "desc": "Faster encoding with good quality. Larger files than AV1.",
        "items": [
            ("VP9", 70, "info", "Fast encode"),
            ("AV1", 100, "success", "Best quality")
        ]
    },
    "image": {
        "title": "Image Format Efficiency",
        "desc": "AVIF offers best compression, WebP balances quality and speed",
        "items": [
            ("PNG", 30, "warning", "Lossless"),
            ("JPEG", 60, "info", "Standard"),
            ("WebP", 85, "success", "Efficient"),
            ("AVIF", 100, "success", "Best")
        ]
    }
}
