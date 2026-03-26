"""
Presets Plugin

A modular plugin for managing conversion presets.
Uses YAML-defined presets with ToolRegistry integration.
"""
from client.plugins.presets.logic import (
    PresetManager,
    CommandBuilder,
    PresetDefinition,
    PresetStatus
)

# NOTE: Qt-dependent classes (PresetOrchestrator, PresetCard, PresetGallery) are
# intentionally NOT imported here. They require a running QApplication, which causes
# PyInstaller's headless dependency scanner subprocess to crash.
# Import them directly where needed:
#   from client.plugins.presets.orchestrator import PresetOrchestrator
#   from client.plugins.presets.ui.gallery import PresetGallery
#   from client.plugins.presets.ui.card import PresetCard

__all__ = [
    'PresetManager',
    'CommandBuilder',
    'PresetDefinition',
    'PresetStatus',
]
