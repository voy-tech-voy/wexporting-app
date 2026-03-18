"""
ImgApp Version Management Module
Handles automatic version tracking, building, and bump management.

SECURITY NOTE: In production builds (frozen/packaged), version.json is read-only
to prevent users from tampering with the app version. Version bumping only works
in development mode.
"""

import json
import os
from pathlib import Path
from datetime import datetime

APP_NAME = "wexporting"
AUTHOR = "voy-tech apps"
__author__ = AUTHOR
__email__ = "voytechapps@gmail.com"
__license__ = "MIT"


class VersionManager:
    """Manage application versioning and auto-bumping."""
    
    def __init__(self):
        """Initialize version manager."""
        self.version_file = os.path.join(os.path.dirname(__file__), 'version.json')
        self.releases_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ImgApp_Releases')
        self.version_data = self._load_version_data()
    
    def _load_version_data(self):
        """Load version data from version.json file."""
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading version.json: {e}")
        
        return {
            "version": "1.0.1.0",
            "build": 1,
            "last_build": datetime.now().isoformat() + "Z",
            "changelog": {}
        }
    
    def _save_version_data(self):
        """
        Save version data to version.json file.
        
        SECURITY: In production builds (frozen/packaged), this is a no-op
        to prevent users from tampering with the app version.
        """
        import sys
        
        # Only allow saving in development mode
        if getattr(sys, 'frozen', False):
            # Running as compiled executable - version.json is read-only
            print("Version file is read-only in production builds")
            return
        
        try:
            with open(self.version_file, 'w') as f:
                json.dump(self.version_data, f, indent=2)
        except Exception as e:
            print(f"Error saving version.json: {e}")
    
    def get_current_version(self):
        """Get current version string."""
        return self.version_data.get('version', '1.0.0.7')
    
    def get_version_info(self):
        """Get full version information."""
        return self.version_data.copy()
    
    def _parse_version(self, version_str):
        """Parse version string into (major, minor, patch) tuple."""
        try:
            parts = str(version_str).split('.')
            # Handle both "7.4" and "7.4.0" formats
            if len(parts) == 2:
                return (int(parts[0]), int(parts[1]), 0)
            elif len(parts) >= 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            else:
                return (7, 4, 0)
        except (ValueError, AttributeError, IndexError):
            return (7, 4, 0)
    
    def _format_version(self, major, minor, patch):
        """Format version tuple into string."""
        return f"{major}.{minor}.{patch}"
    
    def _scan_releases_for_versions(self):
        """Scan ImgApp_Releases folder for existing versions."""
        versions = []
        if os.path.exists(self.releases_dir):
            try:
                for folder in os.listdir(self.releases_dir):
                    folder_path = os.path.join(self.releases_dir, folder)
                    if folder.startswith('v') and os.path.isdir(folder_path):
                        version = folder[1:]  # Remove 'v' prefix
                        try:
                            parsed = self._parse_version(version)
                            versions.append((parsed, version))
                        except:
                            pass
            except Exception as e:
                print(f"Error scanning releases: {e}")
        
        return sorted(versions, key=lambda x: x[0], reverse=True)
    
    def suggest_next_version(self, increment_type='patch'):
        """
        Suggest next version based on existing releases.
        
        Args:
            increment_type: 'patch' (default), 'minor', or 'major'
        
        Returns:
            Next version string (e.g., "7.5")
        """
        existing_versions = self._scan_releases_for_versions()
        
        if existing_versions:
            highest = existing_versions[0][0]  # Get highest parsed version
            major, minor, patch = highest
        else:
            major, minor, patch = self._parse_version(self.get_current_version())
        
        if increment_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif increment_type == 'minor':
            minor += 1
            patch = 0
        else:  # patch (default)
            patch += 1
        
        return self._format_version(major, minor, patch)
    
    def set_version(self, version_str, changelog_entry=None):
        """
        Set version to a specific version.
        
        Args:
            version_str: Version string (e.g., "7.5")
            changelog_entry: Optional changelog entry for this version
        """
        self.version_data['version'] = version_str
        self.version_data['build'] += 1
        self.version_data['last_build'] = datetime.now().isoformat() + "Z"
        
        if changelog_entry:
            if 'changelog' not in self.version_data:
                self.version_data['changelog'] = {}
            self.version_data['changelog'][version_str] = changelog_entry
        
        self._save_version_data()
        return version_str
    
    def bump_version(self, increment_type='patch', changelog_entry=None):
        """
        Bump version and save.
        
        Args:
            increment_type: 'patch' (default), 'minor', or 'major'
            changelog_entry: Optional changelog entry
        
        Returns:
            New version string
        """
        next_version = self.suggest_next_version(increment_type)
        return self.set_version(next_version, changelog_entry)


# Global instance
_version_manager = None

def get_version_manager():
    """Get or create version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager


def get_version():
    """Get current version string"""
    manager = get_version_manager()
    return manager.get_current_version()


def get_version_info():
    """Get detailed version information"""
    manager = get_version_manager()
    return {
        "version": manager.get_current_version(),
        "author": __author__,
        "description": APP_NAME,
        "license": __license__
    }