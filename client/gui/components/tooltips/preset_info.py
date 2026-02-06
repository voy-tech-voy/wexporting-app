"""
Preset Informational Tooltip Content

Provides messages for preset-related informational tooltips.
"""

PRESET_MESSAGES = {
    "gpu_required": {
        "title": "GPU Required",
        "message": "This preset requires GPU acceleration (NVIDIA, AMD, or Intel). No compatible GPU detected on this system.",
        "icon": "warning"
    },
    "missing_tool": {
        "title": "Tool Not Found",
        "message": "Required tool not available: {tool_name}",
        "icon": "error"
    },
    "incompatible_format": {
        "title": "Incompatible Format",
        "message": "This preset does not support the selected file format.",
        "icon": "warning"
    }
}
