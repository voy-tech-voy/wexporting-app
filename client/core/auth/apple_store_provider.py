"""
Apple App Store Authentication Provider (STUB)

This is a stub implementation for iOS/macOS App Store authentication.
iOS development is deferred until Mac testing environment is available.

When implementing on Mac:
1. Import StoreKit 2 (requires PyObjC or similar bridge)
2. Implement App Store Server API validation
3. Handle App Store receipts and transactions
"""

from .store_auth_provider import IStoreAuthProvider, AuthResult
from typing import Optional


class AppleStoreProvider(IStoreAuthProvider):
    """
    Apple App Store authentication provider (STUB).
    
    This stub raises NotImplementedError for all methods.
    Implement these methods when iOS development begins on Mac.
    """
    
    def login(self) -> AuthResult:
        """Trigger StoreKit 2 login flow (NOT IMPLEMENTED)."""
        raise NotImplementedError(
            "iOS StoreKit authentication not available on Windows. "
            "This feature will be implemented when iOS development begins on Mac."
        )
    
    def get_store_user_id(self) -> Optional[str]:
        """Return Apple ID SubjectID (NOT IMPLEMENTED)."""
        raise NotImplementedError(
            "iOS StoreKit not available on Windows"
        )
    
    def validate_receipt(self, receipt_data: bytes) -> bool:
        """Validate App Store receipt (NOT IMPLEMENTED)."""
        raise NotImplementedError(
            "iOS StoreKit receipt validation not available on Windows"
        )
    
    def is_authenticated(self) -> bool:
        """Check Apple ID authentication status (NOT IMPLEMENTED)."""
        raise NotImplementedError(
            "iOS StoreKit not available on Windows"
        )
