"""
GPU Acceleration Detection and Configuration for FFmpeg

Detects available hardware encoders and provides mapping from UI selections
to the best available encoder with CPU fallback support.
"""

import subprocess
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class EncoderType(Enum):
    """Encoder hardware type"""
    NVIDIA = "nvidia"
    INTEL = "intel"
    AMD = "amd"
    CPU = "cpu"


@dataclass
class EncoderInfo:
    """Information about an available encoder"""
    name: str
    encoder_type: EncoderType
    codec: str  # h264, hevc, av1, vp9
    priority: int  # Lower = higher priority


# Encoder definitions with priorities (lower = preferred)
ENCODER_DEFINITIONS = {
    # H.264 / AVC
    "h264_nvenc": EncoderInfo("h264_nvenc", EncoderType.NVIDIA, "h264", 1),
    "h264_amf": EncoderInfo("h264_amf", EncoderType.AMD, "h264", 2),
    "h264_qsv": EncoderInfo("h264_qsv", EncoderType.INTEL, "h264", 3),
    "libx264": EncoderInfo("libx264", EncoderType.CPU, "h264", 10),
    "libopenh264": EncoderInfo("libopenh264", EncoderType.CPU, "h264", 11),  # BSD fallback
    
    # HEVC / H.265
    "hevc_nvenc": EncoderInfo("hevc_nvenc", EncoderType.NVIDIA, "hevc", 1),
    "hevc_amf": EncoderInfo("hevc_amf", EncoderType.AMD, "hevc", 2),
    "hevc_qsv": EncoderInfo("hevc_qsv", EncoderType.INTEL, "hevc", 3),
    "libx265": EncoderInfo("libx265", EncoderType.CPU, "hevc", 10),
    "libkvazaar": EncoderInfo("libkvazaar", EncoderType.CPU, "hevc", 11),  # LGPL fallback
    
    # AV1
    "av1_nvenc": EncoderInfo("av1_nvenc", EncoderType.NVIDIA, "av1", 1),
    "av1_amf": EncoderInfo("av1_amf", EncoderType.AMD, "av1", 2),
    "av1_qsv": EncoderInfo("av1_qsv", EncoderType.INTEL, "av1", 3),
    "libsvtav1": EncoderInfo("libsvtav1", EncoderType.CPU, "av1", 10),
    "libaom-av1": EncoderInfo("libaom-av1", EncoderType.CPU, "av1", 11),  # Reference encoder
    
    # VP9
    "vp9_qsv": EncoderInfo("vp9_qsv", EncoderType.INTEL, "vp9", 3),
    "libvpx-vp9": EncoderInfo("libvpx-vp9", EncoderType.CPU, "vp9", 10),
}

# UI Selection to codec mapping
UI_TO_CODEC = {
    "MP4 (H.264)": "h264",
    "MP4 (H.265)": "hevc",
    "MP4 (AV1)": "av1",
    "WebM (VP9)": "vp9",
    "WebM (AV1)": "av1",
}


class GPUDetector:
    """
    Detects and manages GPU acceleration for FFmpeg encoding.
    """
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._available_encoders: Optional[List[str]] = None
        self._encoder_map: Dict[str, List[EncoderInfo]] = {}
        self._gpu_active: bool = False
        self._current_encoder_type: EncoderType = EncoderType.CPU
        
    @property
    def gpu_active(self) -> bool:
        """Returns True if GPU acceleration is currently being used"""
        return self._gpu_active
    
    @property
    def current_encoder_type(self) -> EncoderType:
        """Returns the type of encoder currently in use"""
        return self._current_encoder_type
        
    def detect_encoders(self) -> List[str]:
        """
        Execute ffmpeg -hide_banner -encoders and parse available encoders.
        Returns list of available encoder names.
        """
        if self._available_encoders is not None:
            return self._available_encoders
            
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = result.stdout
            available = []
            
            # Parse encoder list - format: " V..... encodername    Description"
            # Lines with encoders start with space and have format indicators
            for line in output.split('\n'):
                # Match encoder lines (start with space, have V/A/S indicator)
                match = re.match(r'\s+[VAS][F.][S.][X.][B.][D.]\s+(\w+)', line)
                if match:
                    encoder_name = match.group(1)
                    if encoder_name in ENCODER_DEFINITIONS:
                        available.append(encoder_name)
                        
            self._available_encoders = available
            self._build_encoder_map()
            
            print(f"GPU Detector: Found encoders: {available}")
            return available
            
        except subprocess.TimeoutExpired:
            print("GPU Detector: FFmpeg encoder detection timed out")
            self._available_encoders = []
            return []
        except Exception as e:
            print(f"GPU Detector: Error detecting encoders: {e}")
            self._available_encoders = []
            return []
            
    def _build_encoder_map(self):
        """Build mapping of codec -> sorted list of available encoders"""
        self._encoder_map = {}
        
        for encoder_name in self._available_encoders or []:
            if encoder_name in ENCODER_DEFINITIONS:
                info = ENCODER_DEFINITIONS[encoder_name]
                if info.codec not in self._encoder_map:
                    self._encoder_map[info.codec] = []
                self._encoder_map[info.codec].append(info)
                
        # Sort each codec's encoders by priority
        for codec in self._encoder_map:
            self._encoder_map[codec].sort(key=lambda x: x.priority)
            
    def get_best_encoder(self, ui_selection: str, prefer_gpu: bool = True) -> Tuple[str, EncoderType]:
        """
        Get the best available encoder for a UI selection.
        
        Args:
            ui_selection: The UI format selection (e.g., "MP4 (H.264)")
            prefer_gpu: If True, prefer GPU encoders when available
            
        Returns:
            Tuple of (encoder_name, encoder_type)
        """
        # Ensure encoders are detected
        if self._available_encoders is None:
            self.detect_encoders()
            
        codec = UI_TO_CODEC.get(ui_selection)
        if not codec:
            # Default fallback for unknown selections
            return ("libx264", EncoderType.CPU)
            
        available_for_codec = self._encoder_map.get(codec, [])
        
        if prefer_gpu:
            # Return highest priority (first in sorted list)
            for encoder_info in available_for_codec:
                self._gpu_active = encoder_info.encoder_type != EncoderType.CPU
                self._current_encoder_type = encoder_info.encoder_type
                return (encoder_info.name, encoder_info.encoder_type)
        else:
            # Find CPU encoder
            for encoder_info in available_for_codec:
                if encoder_info.encoder_type == EncoderType.CPU:
                    self._gpu_active = False
                    self._current_encoder_type = EncoderType.CPU
                    return (encoder_info.name, EncoderType.CPU)
                    
        # Ultimate fallback based on codec
        # Prefer LGPL-compatible fallbacks (libopenh264, libkvazaar)
        fallbacks = {
            "h264": "libopenh264",
            "hevc": "libkvazaar", 
            "av1": "libsvtav1",
            "vp9": "libvpx-vp9",
        }
        self._gpu_active = False
        self._current_encoder_type = EncoderType.CPU
        return (fallbacks.get(codec, "libopenh264"), EncoderType.CPU)
        
    def get_fallback_encoder(self, current_encoder: str) -> Tuple[str, EncoderType]:
        """
        Get CPU fallback encoder when GPU encoder fails.
        
        Args:
            current_encoder: The encoder that failed
            
        Returns:
            Tuple of (fallback_encoder_name, encoder_type)
        """
        if current_encoder not in ENCODER_DEFINITIONS:
            return ("libx264", EncoderType.CPU)
            
        codec = ENCODER_DEFINITIONS[current_encoder].codec
        
        # Find CPU encoder for this codec
        available_for_codec = self._encoder_map.get(codec, [])
        for encoder_info in available_for_codec:
            if encoder_info.encoder_type == EncoderType.CPU:
                self._gpu_active = False
                self._current_encoder_type = EncoderType.CPU
                return (encoder_info.name, EncoderType.CPU)
                
        # Ultimate fallback - prefer LGPL-compatible encoders
        fallbacks = {
            "h264": "libopenh264",
            "hevc": "libkvazaar",
            "av1": "libsvtav1", 
            "vp9": "libvpx-vp9",
        }
        self._gpu_active = False
        self._current_encoder_type = EncoderType.CPU
        return (fallbacks.get(codec, "libopenh264"), EncoderType.CPU)
        
    def get_encoder_params(self, encoder_name: str, quality: int) -> Dict[str, str]:
        """
        Get encoder-specific parameters.
        
        Args:
            encoder_name: The encoder to configure
            quality: Quality value (0-100 or CRF value depending on context)
            
        Returns:
            Dict of FFmpeg parameters for this encoder
        """
        params = {}
        
        # NVIDIA NVENC
        if encoder_name.endswith("_nvenc"):
            # NVENC uses different quality presets
            # Map quality to preset and CQ value
            if quality <= 20:
                params["preset"] = "p7"  # Slowest, best quality
                params["cq"] = str(max(0, quality))
            elif quality <= 40:
                params["preset"] = "p5"
                params["cq"] = str(quality)
            else:
                params["preset"] = "p4"  # Balanced
                params["cq"] = str(min(51, quality))
            params["rc"] = "vbr"
            
        # Intel QSV
        elif encoder_name.endswith("_qsv"):
            params["preset"] = "medium"
            params["global_quality"] = str(quality)
            
        # AMD AMF
        elif encoder_name.endswith("_amf"):
            params["quality"] = "quality" if quality <= 30 else "balanced"
            params["rc"] = "cqp"
            params["qp_i"] = str(quality)
            params["qp_p"] = str(quality)
            
        # CPU encoders (libx264, libx265, libsvtav1, libvpx-vp9)
        else:
            params["crf"] = str(quality)
            if encoder_name == "libx264":
                params["preset"] = "medium"
            elif encoder_name == "libx265":
                params["preset"] = "medium"
            elif encoder_name == "libsvtav1":
                params["preset"] = "6"  # Balanced speed/quality
                
        return params
        
    def is_gpu_error(self, error_message: str) -> bool:
        """
        Check if an error message indicates a GPU encoder failure.
        These errors suggest we should fallback to CPU.
        """
        gpu_error_patterns = [
            "Driver too old",
            "No NVENC capable devices found",
            "Cannot load nvcuda.dll",
            "device not found",
            "InitializeEncoder failed",
            "Hardware does not support",
            "Cannot initialize encoder",
            "OpenCL initialization failed",
            "Could not initialize the decoder",
            "Failed to create",
            "NVENC",
            "QSV",
            "AMF",
        ]
        
        error_lower = error_message.lower()
        for pattern in gpu_error_patterns:
            if pattern.lower() in error_lower:
                return True
        return False


# Global instance for easy access
_gpu_detector: Optional[GPUDetector] = None


def get_gpu_detector(ffmpeg_path: str = "ffmpeg") -> GPUDetector:
    """Get or create the global GPU detector instance"""
    global _gpu_detector
    if _gpu_detector is None:
        _gpu_detector = GPUDetector(ffmpeg_path)
    elif _gpu_detector.ffmpeg_path != ffmpeg_path:
        _gpu_detector = GPUDetector(ffmpeg_path)
    return _gpu_detector


def detect_gpu_acceleration(ffmpeg_path: str = "ffmpeg") -> Dict[str, bool]:
    """
    Quick check for available GPU acceleration.
    Returns dict with vendor availability.
    """
    detector = get_gpu_detector(ffmpeg_path)
    encoders = detector.detect_encoders()
    
    return {
        "nvidia": any("nvenc" in e for e in encoders),
        "intel": any("qsv" in e for e in encoders),
        "amd": any("amf" in e for e in encoders),
        "any_gpu": any("nvenc" in e or "qsv" in e or "amf" in e for e in encoders),
    }
