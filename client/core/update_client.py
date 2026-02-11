"""
Update Client

Handles checking for and applying updates from the server.
Downloads presets and estimators, writes them to local paths.
"""
import asyncio
import aiohttp
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class UpdateManifest:
    """Represents an update manifest from the server"""
    
    def __init__(self, data: Dict[str, Any]):
        self.presets = data.get('presets', [])
        self.generated_at = data.get('generated_at')
    
    def has_updates(self, local_manifest: 'LocalManifest') -> bool:
        """Check if there are any updates compared to local manifest"""
        for preset in self.presets:
            local_version = local_manifest.get_preset_version(preset['id'])
            if local_version != preset['version']:
                return True
        
        return False


class LocalManifest:
    """Manages local update manifest (version tracking)"""
    
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load local manifest from disk"""
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding='utf-8'))
            except Exception as e:
                logger.error(f"Failed to load local manifest: {e}")
        
        return {
            'last_check': None,
            'installed': {
                'presets': {},
                'estimators': {}
            }
        }
    
    def save(self):
        """Save local manifest to disk"""
        try:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            self.manifest_path.write_text(
                json.dumps(self.data, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            logger.error(f"Failed to save local manifest: {e}")
    
    def get_preset_version(self, preset_id: str) -> Optional[str]:
        """Get installed version of a preset"""
        return self.data['installed']['presets'].get(preset_id)
    
    def get_estimator_version(self, estimator_id: str) -> Optional[str]:
        """Get installed version of an estimator"""
        return self.data['installed']['estimators'].get(estimator_id)
    
    def update_preset_version(self, preset_id: str, version: str):
        """Record installed preset version"""
        self.data['installed']['presets'][preset_id] = version
        self.save()
    
    def update_estimator_version(self, estimator_id: str, version: str):
        """Record installed estimator version"""
        self.data['installed']['estimators'][estimator_id] = version
        self.save()
    
    def update_last_check(self):
        """Update last check timestamp"""
        self.data['last_check'] = datetime.now().isoformat()
        self.save()


class UpdateClient:
    """
    Client for fetching and applying updates from server.
    
    Usage:
        client = UpdateClient(server_url, license_key)
        manifest = await client.check_for_updates()
        if manifest.has_updates(local_manifest):
            await client.apply_all_updates(manifest)
    """
    
    def __init__(self, server_url: str, license_key: str):
        """
        Initialize update client.
        
        Args:
            server_url: Base URL of update server (e.g., 'https://api.example.com')
            license_key: Valid license key for authentication
        """
        self.server_url = server_url.rstrip('/')
        self.license_key = license_key
        
        # Paths
        self.client_root = Path(__file__).parent.parent
        self.presets_dir = self.client_root / "plugins" / "presets" / "assets" / "presets"
        self.estimators_base = self.client_root / "core" / "target_size"
        
        # Local manifest
        manifest_path = self.presets_dir / "update_manifest.json"
        self.local_manifest = LocalManifest(manifest_path)
    
    async def check_for_updates(self) -> Optional[UpdateManifest]:
        """
        Check server for available updates.
        
        Returns:
            UpdateManifest or None if check failed
        """
        try:
            headers = {'Authorization': f'Bearer {self.license_key}'}
            url = f"{self.server_url}/api/v1/updates/manifest"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        manifest_data = data.get('manifest', {})
                        
                        self.local_manifest.update_last_check()
                        logger.info("Successfully fetched update manifest")
                        
                        return UpdateManifest(manifest_data)
                    elif response.status == 401:
                        logger.error("License validation failed for updates")
                        return None
                    else:
                        logger.error(f"Failed to fetch manifest: HTTP {response.status}")
                        return None
        
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None
    
    async def download_preset(self, preset_id: str) -> Optional[str]:
        """
        Download preset YAML content.
        
        Args:
            preset_id: Preset ID (filename without extension)
            
        Returns:
            YAML content or None if download failed
        """
        try:
            headers = {'Authorization': f'Bearer {self.license_key}'}
            url = f"{self.server_url}/api/v1/updates/download/preset/{preset_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Downloaded preset: {preset_id}")
                        return content
                    else:
                        logger.error(f"Failed to download preset {preset_id}: HTTP {response.status}")
                        return None
        
        except Exception as e:
            logger.error(f"Error downloading preset {preset_id}: {e}")
            return None
    
    async def apply_preset_update(self, preset_id: str, content: str, subdir: str = "") -> bool:
        """
        Write preset to local filesystem with security checks.
        
        Args:
            preset_id: Preset ID (sanitized for path safety)
            content: YAML content
            subdir: Subdirectory within presets/ (e.g., 'upscalers', 'video')
            
        Returns:
            True if successful
        """
        try:
            import re
            
            # SECURITY: Sanitize preset_id to prevent path traversal
            if not re.match(r'^[a-zA-Z0-9_-]+$', preset_id):
                logger.error(f"Invalid preset_id (contains unsafe characters): {preset_id}")
                return False
            
            # SECURITY: Sanitize subdir to prevent path traversal
            if subdir and not re.match(r'^[a-zA-Z0-9_/-]+$', subdir):
                logger.error(f"Invalid subdir (contains unsafe characters): {subdir}")
                return False
            
            target_dir = self.presets_dir / subdir if subdir else self.presets_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            
            target_file = target_dir / f"{preset_id}.yaml"
            
            # SECURITY: Verify final path is within presets_dir (prevent path traversal)
            try:
                if not target_file.resolve().is_relative_to(self.presets_dir.resolve()):
                    logger.error(f"Path traversal attempt blocked: {target_file}")
                    return False
            except (ValueError, OSError) as e:
                logger.error(f"Path validation failed: {e}")
                return False
            
            target_file.write_text(content, encoding='utf-8')
            
            logger.info(f"Applied preset update: {target_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to apply preset {preset_id}: {e}")
            return False
    
    async def apply_all_updates(self, manifest: UpdateManifest) -> Dict[str, Any]:
        """
        Apply all available updates from manifest.
        
        Args:
            manifest: UpdateManifest from server
            
        Returns:
            dict: {'presets_updated': int, 'errors': List[str]}
        """
        results = {
            'presets_updated': 0,
            'errors': []
        }
        
        # Update presets
        for preset in manifest.presets:
            try:
                # SECURITY: Schema validation - ensure required fields exist
                if not isinstance(preset, dict):
                    logger.error(f"Invalid preset entry (not a dict): {preset}")
                    results['errors'].append(f"Invalid preset entry format")
                    continue
                
                preset_id = preset.get('id')
                preset_version = preset.get('version')
                preset_path = preset.get('path')
                
                if not preset_id or not preset_version:
                    logger.error(f"Preset missing required fields: {preset}")
                    results['errors'].append(f"Preset missing id or version")
                    continue
                
                local_version = self.local_manifest.get_preset_version(preset_id)
                
                if local_version != preset_version:
                    content = await self.download_preset(preset_id)
                    if content:
                        # Extract subdirectory from path
                        subdir = str(Path(preset_path).parent) if preset_path else ""
                        
                        if await self.apply_preset_update(preset_id, content, subdir):
                            self.local_manifest.update_preset_version(preset_id, preset_version)
                            results['presets_updated'] += 1
                        else:
                            results['errors'].append(f"Failed to apply preset: {preset_id}")
                    else:
                        results['errors'].append(f"Failed to download preset: {preset_id}")
            
            except Exception as e:
                logger.error(f"Error processing preset: {e}")
                results['errors'].append(f"Error processing preset: {str(e)}")
        
        return results
