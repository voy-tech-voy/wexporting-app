"""
Store Authentication Abstraction Layer

Provides platform-agnostic authentication via Store APIs.
Supports Windows (MS Store) and iOS (App Store) through a unified interface.
"""

import sys
from .store_auth_provider import IStoreAuthProvider

_provider_instance = None


def get_store_auth_provider() -> IStoreAuthProvider:
    """
    Factory function to get the appropriate store authentication provider
    based on the current platform. Returns a singleton instance.
    
    Returns:
        IStoreAuthProvider: Platform-specific implementation
        
    Raises:
        RuntimeError: If platform is not supported
    """
    global _provider_instance
    
    if _provider_instance is None:
        # --- DEV MODE: Use Mock Provider (runs from source, never in frozen build) ---
        from client.config.config import Config
        if Config.DEVELOPMENT_MODE:
            from .ms_store_provider import MockStoreProvider
            _provider_instance = MockStoreProvider()
        elif sys.platform == "win32":
            from .ms_store_provider import MSStoreProvider
            _provider_instance = MSStoreProvider()
        elif sys.platform == "darwin":  # macOS/iOS
            from .apple_store_provider import AppleStoreProvider
            _provider_instance = AppleStoreProvider()
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
            
    return _provider_instance


__all__ = ['IStoreAuthProvider', 'get_store_auth_provider']
