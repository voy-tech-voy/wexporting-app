"""
Update Manifest Service

Generates manifests of available updates and serves update files.
Scans storage/updates/ directory for presets and estimators.
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
    
    Scans server/storage/updates/ for preset and estimator files,
    generates manifests with version and hash information.
    """
    
    def __init__(self):
        # Base path for update files
        self.updates_dir = Path(__file__).parent.parent / "storage" / "updates"
        self.presets_dir = self.updates_dir / "presets"
        self.estimators_dir = self.updates_dir / "estimators"
        
        # Ensure directories exist
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self.estimators_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_manifest(self) -> Dict[str, Any]:
        """
        Generate manifest of all available updates.
        
        Returns:
            dict: {
                'presets': [{'id', 'version', 'hash', 'path'}],
                'estimators': [{'id', 'version', 'hash', 'type'}]
            }
        """
        try:
            manifest = {
                'presets': self._scan_presets(),
                'estimators': self._scan_estimators(),
                'generated_at': self._get_timestamp()
            }
            
            logger.info(f"Generated manifest: {len(manifest['presets'])} presets, {len(manifest['estimators'])} estimators")
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to generate manifest: {e}")
            return {'presets': [], 'estimators': [], 'error': str(e)}
    
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
    
    def _scan_estimators(self) -> List[Dict[str, str]]:
        """Scan estimators directory for Python files"""
        estimators = []
        
        try:
            # Find all Python files
            for py_file in self.estimators_dir.glob("*.py"):
                try:
                    content = py_file.read_text(encoding='utf-8')
                    version = self._extract_estimator_version(py_file.name)
                    file_hash = self._calculate_hash(content)
                    estimator_type = self._detect_estimator_type(py_file.name)
                    
                    estimators.append({
                        'id': py_file.stem,  # Filename without extension
                        'version': version,
                        'hash': file_hash,
                        'type': estimator_type  # 'loop', 'video', 'image'
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to process estimator {py_file}: {e}")
                    continue
            
            return estimators
            
        except Exception as e:
            logger.error(f"Failed to scan estimators: {e}")
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
    
    def _extract_estimator_version(self, filename: str) -> str:
        """Extract version from estimator filename (e.g., loop_av1_v7.py -> 7.0)"""
        try:
            # Pattern: {type}_{codec}_v{version}.py
            if '_v' in filename:
                version_part = filename.split('_v')[-1].replace('.py', '')
                return f"{version_part}.0"
            return '1.0'
        except:
            return '1.0'
    
    def _detect_estimator_type(self, filename: str) -> str:
        """Detect estimator type from filename"""
        if filename.startswith('loop_'):
            return 'loop'
        elif filename.startswith('video_'):
            return 'video'
        elif filename.startswith('image_'):
            return 'image'
        else:
            return 'unknown'
    
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
    
    def get_estimator_content(self, estimator_id: str) -> Optional[str]:
        """
        Get estimator Python content by ID.
        
        Args:
            estimator_id: Estimator filename without extension
            
        Returns:
            str: Python content or None if not found
        """
        try:
            estimator_file = self.estimators_dir / f"{estimator_id}.py"
            
            if estimator_file.exists():
                return estimator_file.read_text(encoding='utf-8')
            
            logger.warning(f"Estimator not found: {estimator_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to read estimator {estimator_id}: {e}")
            return None
