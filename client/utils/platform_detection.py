"""
Platform detection utilities for multi-store support.

Detects whether the application is running as:
- Standard desktop app (Gumroad license)
- Microsoft Store app (MSIX package)
- Future: Other distribution platforms

Author: VoyTech
"""

import os
import sys
import ctypes
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AppPlatform(str, Enum):
    """Supported application distribution platforms"""
    GUMROAD = "gumroad"
    MSSTORE = "msstore"
    DIRECT = "direct"
    UNKNOWN = "unknown"


def is_msstore_app() -> bool:
    """
    Detect if the app is running as a Microsoft Store (MSIX) package.
    
    MS Store apps run in a special app container with specific characteristics:
    1. Have a Package Family Name (PFN) in the Windows.CurrentApp API
    2. Run from WindowsApps folder
    3. Have specific environment variables set
    4. Can access Windows.ApplicationModel.Store namespace
    
    Returns:
        bool: True if running as MS Store app, False otherwise
    """
    if sys.platform != 'win32':
        return False
    
    # Method 1: Check for package identity (most reliable)
    try:
        from ctypes import windll, wintypes
        
        # GetCurrentPackageFullName returns ERROR_INSUFFICIENT_BUFFER (122) if packaged
        # and APPMODEL_ERROR_NO_PACKAGE (15700) if not packaged
        length = wintypes.UINT(0)
        result = windll.kernel32.GetCurrentPackageFullName(ctypes.byref(length), None)
        
        # 122 = ERROR_INSUFFICIENT_BUFFER (means we ARE in a package)
        # 15700 = APPMODEL_ERROR_NO_PACKAGE (means we are NOT in a package)
        if result == 122:
            logger.debug("MS Store detection: Package identity found (MSIX)")
            return True
        elif result == 15700:
            logger.debug("MS Store detection: No package identity")
            return False
            
    except Exception as e:
        logger.debug(f"MS Store detection via GetCurrentPackageFullName failed: {e}")
    
    # Method 2: Check installation path
    try:
        exe_path = os.path.abspath(sys.executable)
        if 'WindowsApps' in exe_path:
            logger.debug(f"MS Store detection: Running from WindowsApps folder")
            return True
    except Exception as e:
        logger.debug(f"MS Store detection via path check failed: {e}")
    
    # Method 3: Check for MSIX environment variables
    msix_indicators = [
        'LOCALAPPDATA',  # Different in app container
        'ProgramFiles\\WindowsApps' in os.environ.get('PATH', ''),
    ]
    
    # Method 4: Try to import Windows Runtime APIs (only work in packaged apps)
    try:
        # This import only succeeds in Windows Store apps with the Windows Runtime
        import winrt.windows.applicationmodel.store as store
        # If we get here without exception, we're likely in a Store app
        logger.debug("MS Store detection: Windows.ApplicationModel.Store available")
        return True
    except ImportError:
        logger.debug("MS Store detection: Windows Runtime not available")
    except Exception as e:
        logger.debug(f"MS Store detection via WinRT failed: {e}")
    
    return False


def get_msstore_package_info() -> Optional[Dict[str, Any]]:
    """
    Get Microsoft Store package information if running as MSIX.
    
    Returns:
        dict: Package info including PFN, version, etc., or None if not MS Store app
    """
    if not is_msstore_app():
        return None
    
    try:
        from ctypes import windll, wintypes, create_unicode_buffer
        
        # Get package full name
        length = wintypes.UINT(256)
        buffer = create_unicode_buffer(256)
        result = windll.kernel32.GetCurrentPackageFullName(ctypes.byref(length), buffer)
        
        if result == 0:  # ERROR_SUCCESS
            package_full_name = buffer.value
            
            # Parse Package Full Name (format: Name_Version_Arch_ResourceId_Publisher)
            parts = package_full_name.split('_')
            
            return {
                'package_full_name': package_full_name,
                'package_name': parts[0] if len(parts) > 0 else None,
                'version': parts[1] if len(parts) > 1 else None,
                'architecture': parts[2] if len(parts) > 2 else None,
                'publisher_id': parts[4] if len(parts) > 4 else None,
            }
    except Exception as e:
        logger.error(f"Failed to get MS Store package info: {e}")
    
    return None


def get_app_platform() -> AppPlatform:
    """
    Determine the current app distribution platform.
    
    Returns:
        AppPlatform: The detected platform
    """
    if is_msstore_app():
        return AppPlatform.MSSTORE
    
    # Check for Gumroad indicators (our standard distribution)
    # If we have a local config with Gumroad license, it's Gumroad
    try:
        # Import Settings dynamically to avoid circular imports
        from client.config.settings import Settings
        settings = Settings()
        platform = settings.get('license_platform', '')
        
        if platform == 'msstore':
            return AppPlatform.MSSTORE
        elif platform == 'gumroad':
            return AppPlatform.GUMROAD
    except ImportError:
        # Settings module not available - use default detection
        pass
    except Exception as e:
        logger.debug(f"Settings check failed: {e}")
    
    # Default to Gumroad for non-Store installations
    return AppPlatform.GUMROAD


def get_platform_display_name(platform: AppPlatform = None) -> str:
    """Get human-readable platform name for UI display"""
    if platform is None:
        platform = get_app_platform()
    
    display_names = {
        AppPlatform.GUMROAD: "Gumroad",
        AppPlatform.MSSTORE: "Microsoft Store",
        AppPlatform.DIRECT: "Direct",
        AppPlatform.UNKNOWN: "Unknown",
    }
    return display_names.get(platform, "Unknown")


def get_platform_purchase_url(platform: AppPlatform = None) -> str:
    """Get the purchase URL for the current platform"""
    if platform is None:
        platform = get_app_platform()
    
    urls = {
        AppPlatform.GUMROAD: "https://voytechapps.gumroad.com/l/imgwave",
        AppPlatform.MSSTORE: "ms-windows-store://pdp/?ProductId=YOUR_APP_ID",  # Update with real ID
        AppPlatform.DIRECT: "https://voytechapps.com/buy",
    }
    return urls.get(platform, urls[AppPlatform.GUMROAD])


def should_show_gumroad_ui() -> bool:
    """
    Check if Gumroad-specific UI elements should be shown.
    
    Returns False for MS Store apps (which handle purchases through Store)
    """
    return get_app_platform() != AppPlatform.MSSTORE


def should_use_store_license() -> bool:
    """
    Check if the app should use MS Store licensing instead of server validation.
    
    MS Store apps can use Windows.Services.Store APIs for license checking.
    """
    return get_app_platform() == AppPlatform.MSSTORE


class MSStoreLicenseChecker:
    """
    Check license status using Microsoft Store APIs.
    
    Only works when running as MSIX package from MS Store.
    """
    
    def __init__(self):
        self.is_available = is_msstore_app()
        self._context = None
    
    def check_license(self) -> Dict[str, Any]:
        """
        Check MS Store license status.
        
        Returns:
            dict: License status including is_active, expiry, etc.
        """
        if not self.is_available:
            return {
                'success': False,
                'error': 'not_msstore_app',
                'message': 'Not running as Microsoft Store app'
            }
        
        try:
            # Try to use Windows.Services.Store APIs
            import asyncio
            return asyncio.run(self._async_check_license())
        except Exception as e:
            logger.error(f"MS Store license check failed: {e}")
            return {
                'success': False,
                'error': 'license_check_failed',
                'message': str(e)
            }
    
    async def _async_check_license(self) -> Dict[str, Any]:
        """Async implementation of license check using WinRT"""
        try:
            import winrt.windows.services.store as store
            
            # Get store context
            context = store.StoreContext.get_default()
            
            # Get app license
            result = await context.get_app_license_async()
            
            if result:
                return {
                    'success': True,
                    'is_active': result.is_active,
                    'is_trial': result.is_trial,
                    'is_trial_owned': getattr(result, 'is_trial_owned', False),
                    'expiry_date': str(result.expiration_date) if hasattr(result, 'expiration_date') else None,
                    'sku_store_id': result.sku_store_id if hasattr(result, 'sku_store_id') else None,
                }
            else:
                return {
                    'success': False,
                    'error': 'no_license',
                    'message': 'No license found'
                }
                
        except ImportError:
            return {
                'success': False,
                'error': 'winrt_not_available',
                'message': 'Windows Runtime APIs not available'
            }
        except Exception as e:
            return {
                'success': False,
                'error': 'license_check_failed',
                'message': str(e)
            }


# Module-level cached detection
_cached_platform: Optional[AppPlatform] = None

def get_cached_platform() -> AppPlatform:
    """Get cached platform detection (only runs detection once)"""
    global _cached_platform
    if _cached_platform is None:
        _cached_platform = get_app_platform()
        logger.info(f"Platform detected: {_cached_platform.value}")
    return _cached_platform


def open_store_url(url: str) -> bool:
    """
    Open a store URL (MS Store, App Store, etc.) using platform-specific method.
    
    Args:
        url: Store URL (e.g., "ms-windows-store://pdp/?productid=...")
        
    Returns:
        True if successful, False otherwise
    """
    import sys
    import subprocess
    import os
    
    try:
        if sys.platform == 'win32':
            # Windows: Use os.startfile or subprocess
            try:
                os.startfile(url)
                logger.info(f"Opened store URL: {url}")
                return True
            except Exception as e:
                logger.warning(f"os.startfile failed, trying subprocess: {e}")
                subprocess.run(['start', url], shell=True, check=False)
                return True
                
        elif sys.platform == 'darwin':
            # macOS: Use 'open' command
            subprocess.run(['open', url], check=False)
            logger.info(f"Opened store URL: {url}")
            return True
            
        else:
            # Linux/other: Try xdg-open
            subprocess.run(['xdg-open', url], check=False)
            logger.info(f"Opened store URL: {url}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to open store URL '{url}': {e}")
        return False


# Convenience exports
__all__ = [
    'AppPlatform',
    'is_msstore_app',
    'get_app_platform',
    'get_cached_platform',
    'get_platform_display_name',
    'get_platform_purchase_url',
    'should_show_gumroad_ui',
    'should_use_store_license',
    'get_msstore_package_info',
    'MSStoreLicenseChecker',
    'open_store_url',
]
