"""
Store Authentication Provider Interface

Defines the contract for platform-specific store authentication implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AuthResult:
    """Result of an authentication attempt."""
    success: bool
    store_user_id: Optional[str] = None
    jwt_token: Optional[str] = None
    is_premium: bool = False
    error_message: Optional[str] = None


class IStoreAuthProvider(ABC):
    """
    Abstract interface for Store authentication providers.
    
    Platform-specific implementations (MS Store, Apple App Store) must
    implement all methods defined here.
    """
    
    @abstractmethod
    def login(self) -> AuthResult:
        """
        Trigger platform-native login flow.
        
        For MS Store: Uses StoreContext API
        For Apple Store: Uses StoreKit 2
        
        Returns:
            AuthResult: Contains store_user_id, JWT token, and premium status
        """
        pass
    
    @abstractmethod
    def get_store_user_id(self) -> Optional[str]:
        """
        Return platform-specific user ID.
        
        For MS Store: SubjectID from Microsoft Account
        For Apple Store: SubjectID from Apple ID
        
        Returns:
            str: Unique user identifier, or None if not logged in
        """
        pass
    
    @abstractmethod
    def validate_receipt(self, receipt_data: bytes) -> bool:
        """
        Send receipt to server for validation.
        
        This method sends the IAP receipt to the backend server,
        which validates it with the respective store API.
        
        Args:
            receipt_data: Platform-specific receipt blob
            
        Returns:
            bool: True if receipt is valid and premium unlocked
        """
        pass
    
    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated with the store.
        
        Returns:
            bool: True if authenticated
        """
        pass
