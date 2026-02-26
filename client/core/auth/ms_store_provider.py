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
                
                # Check for developer override (DEV MODE ONLY)
                from client.config.config import Config, PREMIUM_OVERRIDE
                final_premium_status = self._is_premium
                if Config.DEVELOPMENT_MODE and PREMIUM_OVERRIDE is not None:
                    final_premium_status = PREMIUM_OVERRIDE
                    logger.warning(f"DEV: Forcing Premium Status to {final_premium_status} (Override)")
                
                # Initialize SessionManager with auth result
                from client.core.session_manager import SessionManager
                session = SessionManager.instance()
                session.start_session(
                    store_user_id=self._store_user_id,
                    jwt_token=self._jwt_token or "",
                    is_premium=final_premium_status
                )
                
                return AuthResult(
                    success=True,
                    store_user_id=self._store_user_id,
                    jwt_token=self._jwt_token,
                    is_premium=final_premium_status
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
    
    
    def purchase_add_on(self, store_id: str, window_handle: int = None) -> bool:
        """
        Purchase an add-on (consumable or durable).
        
        Args:
            store_id: Store ID (12 chars, e.g. '9NBLGGH42DRG')
            window_handle: HWND of the main window (required for modal dialog)
            
        Returns:
            bool: True if purchase successful (or already owned) AND fulfilled/validated.
        """
        return self.request_purchase(store_id, window_handle)

    def request_purchase(self, product_id: str, window_handle: int = None) -> bool:
        """
        Trigger native MS Store purchase UI.
        
        Args:
            product_id: Store ID usually (12 chars).
            window_handle: HWND for modal dialog.
            
        Returns:
            bool: True if purchase succeeded/validated.
        """
        if not self._store_available:
            logger.error("Cannot purchase: MS Store APIs not available")
            return False
            
        try:
            import asyncio
            from winrt.windows.services.store import StorePurchaseStatus
            
            # 1. Initialize logic (Window Handle)
            if window_handle:
                try:
                    # Attempt to use IInitializeWithWindow
                    # Note: specific implementation depends on winrt projection details.
                    # Here we try a standard pattern or the user's requested syntax helper.
                    WinRTInterop.InitializeWithWindow.Initialize(self._store_context, window_handle)
                except Exception as ex:
                    logger.warning(f"Failed to initialize with window handle: {ex}")
                    # Continue anyway, might fail or show behind
            
            async def _purchase_flow():
                # 2. Fetch Product (to ensure validity)
                # Note: GetStoreProductsAsync expects list of specific Store IDs
                # 'product_id' here should be the StoreID (12 chars)
                
                logger.info(f"Fetching product details for {product_id}...")
                products_result = await self._store_context.get_store_products_async(
                    ["Product"], [product_id]
                )
                
                product = products_result.products.lookup(product_id) if products_result.products.has_key(product_id) else None
                
                if not product:
                    logger.error(f"Product {product_id} not found in Store")
                    return False

                # 3. Request Purchase
                logger.info(f"Requesting purchase for {product.title} ({product_id})...")
                result = await self._store_context.request_purchase_async(product_id)
                
                status = result.status
                transaction_id = result.transaction_id
                
                # 4. Result Handling
                if status == StorePurchaseStatus.SUCCEEDED:
                    logger.info("Purchase SUCCEEDED.")
                    return transaction_id

                elif status == StorePurchaseStatus.ALREADY_PURCHASED:
                    logger.info("Product ALREADY_PURCHASED — checking for unfulfilled balance.")
                    is_consumable = 'energy' in product_id.lower() or 'day_pass' in product_id.lower()

                    if is_consumable:
                        # Safe recovery: the Store may be holding unfulfilled units from a
                        # previous interrupted session. Check and fulfill any owed quantity.
                        try:
                            balance_result = await self._store_context.get_consumable_balance_remaining_async(
                                product_id
                            )
                            remaining = getattr(balance_result, 'balance', 0)
                            if remaining and remaining > 0:
                                logger.info(f"Found {remaining} unfulfilled unit(s) for {product_id} — fulfilling.")
                                await self._store_context.report_consumable_fulfillment_async(
                                    product_id,
                                    remaining,
                                    transaction_id or "recovery"
                                )
                            else:
                                logger.info(f"No unfulfilled balance found for {product_id}.")
                        except Exception as bal_err:
                            logger.warning(f"Balance check failed for {product_id}: {bal_err}")

                    return "already_owned"

                elif status == StorePurchaseStatus.NOT_PURCHASED:
                    logger.info("User cancelled purchase.")
                    return None

                elif status in (StorePurchaseStatus.NETWORK_ERROR, StorePurchaseStatus.SERVER_ERROR):
                    logger.error(f"Store Error: {status} (Extended: {result.extended_error})")
                    return None

                else:
                    logger.warning(f"Purchase failed with status: {status}")
                    return None

            # Execute Async
            tx_id = asyncio.run(_purchase_flow())

            if not tx_id:
                return False

            # 5. Validation & Fulfillment
            logger.info("Validating purchase with server...")

            # For already_owned: validate entitlements (fulfillment was handled inside async flow)
            if tx_id == "already_owned":
                return self.validate_receipt(None)

            # For new purchase: validate then fulfill consumable
            is_valid = self.validate_receipt(None)

            if is_valid:
                is_consumable = 'energy' in product_id.lower() or 'day_pass' in product_id.lower()
                if is_consumable:
                    logger.info(f"Fulfilling consumable: {product_id}")
                    self.report_fulfillment(product_id, tx_id)

            return is_valid

        except Exception as e:
            logger.error(f"Purchase flow failed: {e}")
            return False

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated with MS Store.
        
        Returns:
            bool: True if authenticated
        """
        return self._authenticated


class WinRTInterop:
    """
    Interop helper: parents a WinRT UI object to a Win32 HWND.

    IInitializeWithWindow (GUID 3E68D4BD-7135-4D10-8018-9FB6D9F33FA1) exposes
    a single method Initialize(HWND). Called via raw vtable pointer using ctypes.
    Vtable layout: [0]=QI, [1]=AddRef, [2]=Release, [3]=Initialize
    """

    class InitializeWithWindow:
        @staticmethod
        def Initialize(winrt_obj, hwnd: int) -> bool:
            """
            Parent winrt_obj to the Win32 window identified by hwnd.

            Args:
                winrt_obj: A winrt Python object (StoreContext).
                hwnd:      HWND integer from window.winId().

            Returns:
                True if succeeded, False on any error.
            """
            try:
                import ctypes
                import ctypes.wintypes

                # Retrieve the raw COM pointer from the winrt Python wrapper.
                raw_ptr = getattr(winrt_obj, '_as_parameter_', None)
                if raw_ptr is None:
                    logger.warning("IInitializeWithWindow: winrt object has no _as_parameter_")
                    return False

                # Dereference vtable pointer (first field of COM object is vtable ptr)
                vtable_p = ctypes.cast(raw_ptr, ctypes.POINTER(ctypes.c_void_p))
                vtable = ctypes.cast(vtable_p[0], ctypes.POINTER(ctypes.c_void_p))

                # Slot 3: HRESULT Initialize(HWND hwnd)
                Initialize_fn = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,        # return type
                    ctypes.c_void_p,       # this
                    ctypes.wintypes.HWND,  # hwnd
                )(vtable[3])

                hr = Initialize_fn(raw_ptr, hwnd)
                if hr != 0:
                    logger.warning(
                        f"IInitializeWithWindow::Initialize HRESULT=0x{hr & 0xFFFFFFFF:08X}"
                    )
                    return False

                logger.info(f"IInitializeWithWindow: parented to HWND {hwnd:#x}")
                return True

            except Exception as e:
                logger.warning(f"IInitializeWithWindow: failed: {e}")
                return False

