"""
Update Manifest Service

Generates manifests of available updates and serves update files.
Generates manifests of available updates and serves update files.
Scans storage/updates/ directory for presets.
"""
import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from config.settings import Config

logger = logging.getLogger(__name__)


class UpdateManifestService:
    """
    Manages update manifests and file serving.
    
    Scans server/storage/updates/ for preset files,
    generates manifests with version and hash information.
    """
    
    def __init__(self):
        # Base path for update files
        self.updates_dir = Path(__file__).parent.parent / "storage" / "updates"
        self.presets_dir = self.updates_dir / "presets"
        
        # Ensure directories exist
        self.presets_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_manifest(self) -> Dict[str, Any]:
        """
        Generate manifest of all available updates.
        
        Returns:
            dict: {
                'presets': [{'id', 'version', 'hash', 'path'}]
            }
        """
        try:
            manifest = {
                'presets': self._scan_presets(),
                'generated_at': self._get_timestamp()
            }
            
            logger.info(f"Generated manifest: {len(manifest['presets'])} presets")
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to generate manifest: {e}")
            return {'presets': [], 'error': str(e)}
    
    def _scan_presets(self) -> List[Dict[str, str]]:
        """Scan presets directory for YAML files"""
        presets = []
        
        try:
            # Recursively find all YAML files
            for yaml_file in self.presets_dir.glob("**/*.yaml"):
                try:
                    # Read file to extract version and calculate hash
                    content = yaml_file.read_text(encoding='utf-8')
                    version = self._extract_preset_version(content)
                    file_hash = self._calculate_hash(content)
                    
                    # Get relative path from presets/ directory
                    rel_path = yaml_file.relative_to(self.presets_dir)
                    
                    presets.append({
                        'id': yaml_file.stem,  # Filename without extension
                        'version': version,
                        'hash': file_hash,
                        'path': str(rel_path).replace('\\', '/')  # Normalize path separators
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to process preset {yaml_file}: {e}")
                    continue
            
            return presets
            
        except Exception as e:
            logger.error(f"Failed to scan presets: {e}")
            return []
    

    
    def _extract_preset_version(self, content: str) -> str:
        """Extract version from YAML content"""
        try:
            import yaml
            data = yaml.safe_load(content)
            meta = data.get('meta', data)
            return str(meta.get('version', '1.0'))
        except:
            return '1.0'
    
    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content"""
        return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
    
    def _get_timestamp(self) -> str:
        """Get current ISO timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_preset_content(self, preset_id: str) -> Optional[str]:
        """
        Get preset YAML content by ID.
        
        Args:
            preset_id: Preset filename without extension
            
        Returns:
            str: YAML content or None if not found
        """
        try:
            # Search recursively for the preset file
            for yaml_file in self.presets_dir.glob(f"**/{preset_id}.yaml"):
                return yaml_file.read_text(encoding='utf-8')
            
            logger.warning(f"Preset not found: {preset_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to read preset {preset_id}: {e}")
            return None
    

