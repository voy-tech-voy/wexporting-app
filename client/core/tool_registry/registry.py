"""
Tool Registry - Central registry for external CLI tools
"""
import os
import re
import json
import subprocess
from typing import Dict, Optional, List, Tuple
from .descriptor import ToolDescriptor
from .bundled import (
    resolve_bundled_tool_path,
    resolve_system_tool_path,
    resolve_all_system_tool_paths,
    resolve_companion_tool_path,
    extract_bundled_tools_to_cache,
    is_frozen
)
from client.version import APP_NAME


class ToolRegistry:
    """
    Central registry for external CLI tools.
    
    Handles:
    - Tool registration via ToolDescriptor
    - Path resolution (bundled/system/custom)
    - Validation (version check + capabilities)
    - Environment variable management
    - Settings persistence
    """
    
    def __init__(self):
        self._descriptors: Dict[str, ToolDescriptor] = {}
        self._resolved_paths: Dict[str, Optional[str]] = {}
        self._availability: Dict[str, bool] = {}
        self._versions: Dict[str, Optional[str]] = {}
        self._modes: Dict[str, str] = {}  # 'bundled', 'system', 'custom'
        self._custom_paths: Dict[str, str] = {}
        self._initialized = False
    
    def register(self, descriptor: ToolDescriptor) -> None:
        """Register a tool descriptor."""
        self._descriptors[descriptor.id] = descriptor
        self._availability[descriptor.id] = False
        self._resolved_paths[descriptor.id] = None
        self._versions[descriptor.id] = None
        self._modes[descriptor.id] = 'bundled' if descriptor.is_bundled else 'system'
    
    def get_descriptor(self, tool_id: str) -> Optional[ToolDescriptor]:
        """Get descriptor for a tool."""
        return self._descriptors.get(tool_id)
    
    # =========================================================================
    # ToolRegistryProtocol Implementation
    # =========================================================================
    
    def get_tool_path(self, tool_id: str) -> Optional[str]:
        """Get resolved path to tool executable."""
        return self._resolved_paths.get(tool_id)
    
    def is_tool_available(self, tool_id: str) -> bool:
        """Check if tool is configured and valid."""
        return self._availability.get(tool_id, False)
    
    def get_tool_version(self, tool_id: str) -> Optional[str]:
        """Get detected version string."""
        return self._versions.get(tool_id)
    
    def list_available_tools(self) -> List[str]:
        """List all tool IDs that are currently available."""
        return [tid for tid, avail in self._availability.items() if avail]
    
    def list_registered_tools(self) -> List[str]:
        """List all registered tool IDs."""
        return list(self._descriptors.keys())
    
    def get_bundled_path(self, tool_id: str) -> Optional[str]:
        """
        Get the path to the bundled executable for a tool, if it exists.
        Does NOT check if it's the currently active path.
        """
        descriptor = self._descriptors.get(tool_id)
        if not descriptor or not descriptor.is_bundled:
            return None
            
        from .bundled import resolve_bundled_tool_path
        return resolve_bundled_tool_path(descriptor.binary_name, descriptor.bundle_subpath)
    
    # =========================================================================
    # Resolution and Validation
    # =========================================================================
    
    def resolve_all(self) -> None:
        """
        Resolve paths for all registered tools.
        Called at startup after registration.
        """
        # Extract bundled tools first (for frozen builds)
        extract_bundled_tools_to_cache()
        
        # Load saved settings
        self._load_all_settings()
        
        # Resolve each tool
        for tool_id in self._descriptors:
            self._resolve_tool(tool_id)
        
        self._initialized = True
    
    def _resolve_tool(self, tool_id: str) -> None:
        """Resolve path and validate a single tool."""
        descriptor = self._descriptors[tool_id]
        mode = self._modes.get(tool_id, 'bundled' if descriptor.is_bundled else 'system')
        
        # Collect candidate paths based on mode
        candidates = []
        
        if mode == 'custom':
            custom_path = self._custom_paths.get(tool_id, '')
            if custom_path and os.path.exists(custom_path):
                candidates.append(custom_path)
        
        if mode == 'bundled' or (not candidates and descriptor.is_bundled):
            bundled = resolve_bundled_tool_path(descriptor.binary_name, descriptor.bundle_subpath)
            if bundled:
                candidates.append(bundled)
        
        if mode == 'system' or not candidates:
            # Get ALL system paths, not just the first one
            system_paths = resolve_all_system_tool_paths(descriptor.binary_name)
            candidates.extend(system_paths)
        
        # Try each candidate until one validates
        for path in candidates:
            is_valid, version = self._validate_tool(tool_id, path)
            if is_valid:
                self._resolved_paths[tool_id] = path
                self._availability[tool_id] = True
                self._versions[tool_id] = version
                self._apply_to_environment(tool_id, path)
                
                # Resolve companions
                for companion in descriptor.companions:
                    companion_path = resolve_companion_tool_path(path, f"{companion}.exe" if os.name == 'nt' else companion)
                    if companion_path:
                        companion_env = f"{companion.upper()}_BINARY"
                        os.environ[companion_env] = companion_path
                
                print(f"DEBUG: Selected {tool_id}: {path}")
                return
        
        # No valid candidate found
        print(f"Warning: No valid {tool_id} found after checking {len(candidates)} candidates")
        self._resolved_paths[tool_id] = None
        self._availability[tool_id] = False
        self._versions[tool_id] = None
    
    def _validate_tool(self, tool_id: str, path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a tool executable.
        
        Returns:
            Tuple of (is_valid, version_string)
        """
        descriptor = self._descriptors[tool_id]
        
        # Basic validation: run version command
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(
                [path] + descriptor.version_args,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags
            )
            
            # Some tools (like waifu2x) return non-zero for help output
            # Check if version pattern exists in stdout or stderr first
            combined_output = result.stdout + result.stderr
            version = None
            match = re.search(descriptor.version_pattern, combined_output, re.IGNORECASE)
            if match:
                # Pattern found - tool is valid
                if match.lastindex and match.lastindex >= 1:
                    version = match.group(1)
                else:
                    version = "detected"
            elif result.returncode != 0:
                # No pattern match AND non-zero exit - tool is invalid
                return False, None
            
            # Advanced validation if configured
            if descriptor.validate_capabilities:
                success, error_msg, missing = descriptor.validate_capabilities(path)
                if not success:
                    print(f"Tool {tool_id} capability validation failed: {error_msg}")
                    return False, version
            
            return True, version
            
        except subprocess.TimeoutExpired:
            print(f"Tool {tool_id} validation timed out")
            return False, None
        except Exception as e:
            print(f"Tool {tool_id} validation error: {e}")
            return False, None
    
    def validate_custom_path(self, tool_id: str, path: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a custom path before applying.
        Used by Advanced Settings UI.
        
        Returns:
            Tuple of (is_valid, error_message, version)
        """
        descriptor = self._descriptors.get(tool_id)
        if not descriptor:
            return False, f"Unknown tool: {tool_id}", None
        
        if not path or not os.path.exists(path):
            return False, "File does not exist", None
        
        # Version check
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(
                [path] + descriptor.version_args,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags
            )
            
            if result.returncode != 0:
                return False, "Version check failed", None
            
            version = None
            match = re.search(descriptor.version_pattern, result.stdout, re.IGNORECASE)
            if match:
                version = match.group(1)
            
            # Capability validation
            if descriptor.validate_capabilities:
                success, error_msg, missing = descriptor.validate_capabilities(path)
                if not success:
                    return False, error_msg, version
            
            return True, "", version
            
        except subprocess.TimeoutExpired:
            return False, "Validation timed out", None
        except Exception as e:
            return False, str(e), None
    
    # =========================================================================
    # Settings Management
    # =========================================================================
    
    def _get_settings_path(self, tool_id: str) -> str:
        """Get path to settings JSON file for a tool."""
        if os.name == 'nt':
            app_data = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA') or os.path.expanduser('~')
        else:
            app_data = os.getenv('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
        
        settings_dir = os.path.join(app_data, APP_NAME)
        os.makedirs(settings_dir, exist_ok=True)
        return os.path.join(settings_dir, f'{tool_id}_settings.json')
    
    def _load_all_settings(self) -> None:
        """Load settings for all registered tools."""
        for tool_id in self._descriptors:
            self._load_settings(tool_id)
    
    def _load_settings(self, tool_id: str) -> None:
        """Load settings for a single tool."""
        settings_path = self._get_settings_path(tool_id)
        
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._modes[tool_id] = data.get('mode', 'bundled')
                    self._custom_paths[tool_id] = data.get('custom_path', '')
            except Exception as e:
                print(f"Error loading {tool_id} settings: {e}")
    
    def _save_settings(self, tool_id: str) -> None:
        """Save settings for a single tool."""
        settings_path = self._get_settings_path(tool_id)
        
        try:
            data = {
                'mode': self._modes.get(tool_id, 'bundled'),
                'custom_path': self._custom_paths.get(tool_id, '')
            }
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving {tool_id} settings: {e}")
    
    def set_tool_mode(self, tool_id: str, mode: str, custom_path: str = '') -> None:
        """
        Set tool mode and re-resolve.
        
        Args:
            tool_id: Tool identifier
            mode: 'bundled', 'system', or 'custom'
            custom_path: Path for custom mode
        """
        if tool_id not in self._descriptors:
            return
        
        self._modes[tool_id] = mode
        if mode == 'custom':
            self._custom_paths[tool_id] = custom_path
        
        self._save_settings(tool_id)
        self._resolve_tool(tool_id)
    
    def get_tool_mode(self, tool_id: str) -> str:
        """Get current mode for a tool."""
        return self._modes.get(tool_id, 'bundled')
    
    def get_custom_path(self, tool_id: str) -> str:
        """Get custom path for a tool."""
        return self._custom_paths.get(tool_id, '')
    
    # =========================================================================
    # Environment
    # =========================================================================
    
    def _apply_to_environment(self, tool_id: str, path: str) -> None:
        """Set environment variable for a tool."""
        descriptor = self._descriptors[tool_id]
        os.environ[descriptor.env_var_name] = path
