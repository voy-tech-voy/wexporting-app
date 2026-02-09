"""
Microsoft Store Authentication Provider

Implements Store authentication using Windows StoreContext API.
Handles MS Store login, user identification, and receipt validation.
"""

import logging
from typing import Optional
from .store_auth_provider import IStoreAuthProvider, AuthResult

logger = logging.getLogger("MSStoreProvider")


class MSStoreProvider(IStoreAuthProvider):
    """
    Microsoft Store authentication provider for Windows.
    
    Uses Windows.Services.Store.StoreContext API for authentication
    and purchase validation.
    """
    
    def __init__(self):
        self._store_user_id: Optional[str] = None
        self._jwt_token: Optional[str] = None
        self._is_premium: bool = False
        self._authenticated: bool = False
        
        # Try to import Windows Store APIs
        try:
            from winrt.windows.services.store import StoreContext
            self._store_context = StoreContext.get_default()
            self._store_available = True
            logger.info("MS Store APIs initialized successfully")
        except ImportError:
            self._store_context = None
            self._store_available = False
            logger.warning("Windows Store APIs not available - winrt package not installed")
    
    def login(self) -> AuthResult:
        """
        Trigger Microsoft Store login flow.
        
        Uses StoreContext.GetAppLicenseAsync() to check entitlements.
        
        Returns:
            AuthResult: Contains store_user_id and authentication status
        """
        if not self._store_available:
            return AuthResult(
                success=False,
                error_message="Microsoft Store APIs not available on this system"
            )
        
        try:
            import asyncio
            
            async def _get_license():
                # Get app license to check entitlements
                license_result = await self._store_context.get_app_license_async()
                
                if license_result:
                    # Extract user ID from license
                    # Note: MS Store user ID is in the license's extended JSON data
                    self._store_user_id = license_result.sku_store_id or "unknown"
                    
                    # Check if user has premium entitlement
                    # This checks for durable add-ons (lifetime purchase)
                    addons_result = await self._store_context.get_user_collection_async(["Durable"])
                    
                    for addon in addons_result.products:
                        if "lifetime" in addon.store_id.lower() or "premium" in addon.store_id.lower():
                            self._is_premium = True
                            break
                    
                    return True
                return False
            
            # Run async operation
            success = asyncio.run(_get_license())
            
            if success:
                self._authenticated = True
                logger.info(f"MS Store login successful for user {self._store_user_id[:8]}...")
                
                return AuthResult(
                    success=True,
                    store_user_id=self._store_user_id,
                    jwt_token=self._jwt_token,
                    is_premium=self._is_premium
                )
            else:
                return AuthResult(
                    success=False,
                    error_message="Failed to retrieve app license"
                )
            
        except Exception as e:
            logger.error(f"MS Store login failed: {e}")
            return AuthResult(
                success=False,
                error_message=str(e)
            )
    
    def get_store_user_id(self) -> Optional[str]:
        """
        Return Microsoft Account SubjectID.
        
        Returns:
            str: Unique user identifier from MS Store, or None if not logged in
        """
        return self._store_user_id

    def get_credentials(self) -> dict:
        """
        Get current credentials (token and user info).
        
        Returns:
            dict: Dictionary containing 'token', 'user_id', etc.
        """
        return {
            'token': self._jwt_token,  # JWT from server validation
            'store_token': None,       # Raw store token if needed
            'user_id': self._store_user_id,
            'is_premium': self._is_premium
        }
    
    def get_receipt(self) -> Optional[str]:
        """
        Get MS Store receipt for server validation.
        
        Returns:
            str: Base64-encoded receipt XML
        """
        if not self._store_available:
            logger.error("Cannot get receipt: MS Store APIs not available")
            return None
        
        try:
            import asyncio
            import base64
            
            async def _get_receipt():
                # Get app receipt
                receipt_result = await self._store_context.get_app_receipt_async()
                if receipt_result:
                    # Receipt is XML, encode to base64 for transmission
                    receipt_bytes = receipt_result.encode('utf-8')
                    return base64.b64encode(receipt_bytes).decode('utf-8')
                return None
            
            return asyncio.run(_get_receipt())
            
        except Exception as e:
            logger.error(f"Failed to get receipt: {e}")
            return None
    
    def validate_receipt(self, receipt_data: bytes) -> bool:
        """
        Validate MS Store receipt with backend server.
        
        Sends the receipt to POST /api/v1/store/validate-receipt
        which validates it with Microsoft Store Collections API.
        
        Args:
            receipt_data: MS Store receipt blob
            
        Returns:
            bool: True if receipt is valid and premium unlocked
        """
        if not self._store_available:
            logger.error("Cannot validate receipt: MS Store APIs not available")
            return False
        
        try:
            import requests
            from client.config.config import API_BASE_URL
            
            # Get receipt if not provided
            if not receipt_data:
                receipt_data = self.get_receipt()
            
            if not receipt_data:
                logger.error("No receipt data available")
                return False
            
            # Send to server for validation
            response = requests.post(
                f"{API_BASE_URL}/api/v1/store/validate-receipt",
                json={
                    "receipt_data": receipt_data,
                    "platform": "msstore",
                    "product_id": "imgapp_lifetime"  # Or detect from receipt
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self._is_premium = result.get('is_premium', False)
                    self._jwt_token = result.get('jwt_token')
                    logger.info(f"Receipt validated successfully (premium: {self._is_premium})")
                    return True
            
            logger.warning(f"Receipt validation failed: {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Receipt validation failed: {e}")
            return False
    
    def report_fulfillment(self, product_id: str, transaction_id: str) -> bool:
        """
        Report consumable fulfillment to MS Store.
        
        Called after energy pack purchase to mark it as fulfilled.
        
        Args:
            product_id: Product ID (e.g., "imgapp_energy_100")
            transaction_id: Transaction ID from purchase
            
        Returns:
            bool: True if fulfillment reported successfully
        """
        if not self._store_available:
            logger.error("Cannot report fulfillment: MS Store APIs not available")
            return False
        
        try:
            import asyncio
            
            async def _report_fulfillment():
                # Report consumable fulfillment
                result = await self._store_context.report_consumable_fulfillment_async(
                    product_id,
                    1,  # Quantity
                    transaction_id
                )
                return result.status == 0  # Success
            
            success = asyncio.run(_report_fulfillment())
            
            if success:
                logger.info(f"Fulfillment reported for {product_id}")
            else:
                logger.warning(f"Failed to report fulfillment for {product_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Fulfillment reporting failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated with MS Store.
        
        Returns:
            bool: True if authenticated
        """
        return self._authenticated
