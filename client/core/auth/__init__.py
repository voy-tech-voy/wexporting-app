"""
Store Authentication Abstraction Layer

Provides platform-agnostic authentication via Store APIs.
Supports Windows (MS Store) and iOS (App Store) through a unified interface.
"""

import sys
from .store_auth_provider import IStoreAuthProvider


def get_store_auth_provider() -> IStoreAuthProvider:
    """
    Factory function to get the appropriate store authentication provider
    based on the current platform.
    
    Returns:
        IStoreAuthProvider: Platform-specific implementation
        
    Raises:
        RuntimeError: If platform is not supported
    """
    if sys.platform == "win32":
        from .ms_store_provider import MSStoreProvider
        return MSStoreProvider()
    elif sys.platform == "darwin":  # macOS/iOS
        from .apple_store_provider import AppleStoreProvider
        return AppleStoreProvider()
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")


__all__ = ['IStoreAuthProvider', 'get_store_auth_provider']
