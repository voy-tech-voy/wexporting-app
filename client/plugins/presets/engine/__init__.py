"""
Preset Conversion Engine - Async execution for preset conversions.

This module provides a QThread-based engine that runs preset conversions
in the background, preventing UI freezes and enabling immediate cancellation.
"""
from .preset_conversion_engine import PresetConversionEngine

__all__ = ['PresetConversionEngine']
