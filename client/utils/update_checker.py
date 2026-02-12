"""
Update Checker for Version Gateway Pattern

Checks for app updates by querying the server gateway.
Compares versions using semantic versioning and determines update state.
"""
import requests
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class UpdateState(Enum):
    """Update availability states"""
    UP_TO_DATE = "up_to_date"
    OPTIONAL_UPDATE = "optional_update"
    MANDATORY_UPDATE = "mandatory_update"


@dataclass
class UpdateCheckResult:
    """Result of an update check"""
    state: UpdateState
    latest_version: Optional[str] = None
    min_required_version: Optional[str] = None
    update_url: Optional[str] = None
    release_notes: Optional[str] = None


def normalize_version(version_str: str) -> Tuple[int, int, int]:
    """
    Normalize version string to (major, minor, patch) tuple.
    Handles both 2-part ("7.4") and 3-part ("7.4.0") formats.
    
    Args:
        version_str: Version string (e.g., "7.4" or "7.4.0")
        
    Returns:
        Tuple of (major, minor, patch) as integers
    """
    try:
        parts = str(version_str).strip().split('.')
        
        if len(parts) == 2:
            # "7.4" → (7, 4, 0)
            return (int(parts[0]), int(parts[1]), 0)
        elif len(parts) >= 3:
            # "7.4.0" → (7, 4, 0)
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            # Fallback for malformed versions
            logger.warning(f"Malformed version string: {version_str}")
            return (0, 0, 0)
            
    except (ValueError, AttributeError, IndexError) as e:
        logger.error(f"Failed to parse version '{version_str}': {e}")
        return (0, 0, 0)


def compare_versions(local: str, remote: str) -> int:
    """
    Compare two version strings using semantic versioning.
    
    Args:
        local: Local version string
        remote: Remote version string
        
    Returns:
        -1 if local < remote (update available)
         0 if local == remote (up to date)
         1 if local > remote (local is newer)
    """
    local_tuple = normalize_version(local)
    remote_tuple = normalize_version(remote)
    
    if local_tuple < remote_tuple:
        return -1
    elif local_tuple > remote_tuple:
        return 1
    else:
        return 0


def get_current_version() -> str:
    """
    Get the current app version.
    
    Returns:
        Version string (normalized to 3-part format)
    """
    try:
        from client.version import get_version
        version = get_version()
        
        # Normalize to 3-part format
        major, minor, patch = normalize_version(version)
        return f"{major}.{minor}.{patch}"
        
    except Exception as e:
        logger.error(f"Failed to get current version: {e}")
        return "0.0.0"


def get_platform_identifier() -> str:
    """
    Get the platform identifier for the current OS.
    
    Returns:
        Platform string ('windows', 'ios', 'macos')
    """
    import sys
    
    if sys.platform == 'win32':
        return 'windows'
    elif sys.platform == 'darwin':
        # TODO: Distinguish between iOS and macOS if needed
        return 'macos'
    elif sys.platform == 'ios':
        return 'ios'
    else:
        # Default to windows for unknown platforms
        return 'windows'


def check_for_updates(timeout: int = 5) -> UpdateCheckResult:
    """
    Check for app updates from the server gateway.
    
    Args:
        timeout: HTTP request timeout in seconds (default: 5)
        
    Returns:
        UpdateCheckResult with state and metadata
    """
    try:
        from client.config.config import APP_CONFIG_URL
        
        # Get current version and platform
        current_version = get_current_version()
        platform = get_platform_identifier()
        
        logger.info(f"Checking for updates: current={current_version}, platform={platform}")
        
        # Make HTTP request to server
        url = f"{APP_CONFIG_URL}?platform={platform}"
        response = requests.get(url, timeout=timeout)
        
        if response.status_code != 200:
            logger.warning(f"Update check failed with status {response.status_code}")
            # Fail silently - let user into app
            return UpdateCheckResult(state=UpdateState.UP_TO_DATE)
        
        data = response.json()
        
        if not data.get('success'):
            logger.warning(f"Update check returned success=false: {data.get('message')}")
            return UpdateCheckResult(state=UpdateState.UP_TO_DATE)
        
        # Extract version info
        latest_version = data.get('latest_version')
        min_required_version = data.get('min_required_version')
        update_url = data.get('update_url')
        release_notes = data.get('release_notes', '')
        
        if not latest_version or not min_required_version:
            logger.warning("Update check response missing version fields")
            return UpdateCheckResult(state=UpdateState.UP_TO_DATE)
        
        # Compare versions
        latest_cmp = compare_versions(current_version, latest_version)
        min_cmp = compare_versions(current_version, min_required_version)
        
        # Determine update state
        if min_cmp < 0:
            # Current version is below minimum required → MANDATORY
            logger.warning(f"Mandatory update required: {current_version} < {min_required_version}")
            return UpdateCheckResult(
                state=UpdateState.MANDATORY_UPDATE,
                latest_version=latest_version,
                min_required_version=min_required_version,
                update_url=update_url,
                release_notes=release_notes
            )
        elif latest_cmp < 0:
            # Current version is below latest but above minimum → OPTIONAL
            logger.info(f"Optional update available: {current_version} < {latest_version}")
            return UpdateCheckResult(
                state=UpdateState.OPTIONAL_UPDATE,
                latest_version=latest_version,
                min_required_version=min_required_version,
                update_url=update_url,
                release_notes=release_notes
            )
        else:
            # Current version is up to date or newer
            logger.info(f"App is up to date: {current_version}")
            return UpdateCheckResult(state=UpdateState.UP_TO_DATE)
        
    except requests.Timeout:
        logger.warning(f"Update check timed out after {timeout}s - failing silently")
        return UpdateCheckResult(state=UpdateState.UP_TO_DATE)
        
    except requests.RequestException as e:
        logger.warning(f"Update check network error: {e} - failing silently")
        return UpdateCheckResult(state=UpdateState.UP_TO_DATE)
        
    except Exception as e:
        logger.error(f"Unexpected error during update check: {e}")
        return UpdateCheckResult(state=UpdateState.UP_TO_DATE)
