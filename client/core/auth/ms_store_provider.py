"""
Microsoft Store Authentication Provider

Implements Store authentication using Windows StoreContext API.
Handles MS Store login, user identification, and receipt validation.
"""

import hashlib
import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from .store_auth_provider import IStoreAuthProvider, AuthResult

logger = logging.getLogger("MSStoreProvider")

# Product IDs that are consumables (can be repurchased after fulfillment)
_CONSUMABLE_PRODUCT_IDS = {'9PFHR7GMBT0T'}  # credits_500


def _get_stable_user_id() -> str:
    """
    Return a stable per-Windows-user identifier that survives AppData deletion.

    Strategy:
      1. Get the current user's Windows SID via `whoami /user` (stable, per-account).
         Hash it with an app-specific salt so the raw SID is never stored.
      2. On failure, fall back to a UUID persisted in %APPDATA%\\wexporting\\config\\user_id.dat.
         Since %APPDATA% is per-Windows-user, different accounts still get different IDs.
      3. If even that fails, generate and return a fresh UUID (not persisted).
    """
    # --- 1. Windows SID (most stable: survives AppData deletion, unique per account) ---
    try:
        result = subprocess.run(
            ['whoami', '/user', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Output format: "DOMAIN\\username","S-1-5-21-..."
            parts = result.stdout.strip().split(',')
            sid = parts[-1].strip().strip('"')
            if sid.startswith('S-'):
                return 'win_' + hashlib.sha256(
                    f"wexporting_v1_{sid}".encode()
                ).hexdigest()[:32]
    except Exception as e:
        logger.debug(f"[StableID] SID lookup failed: {e}")

    # --- 2. Persisted UUID in %APPDATA% ---
    app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
    id_file = Path(app_data) / 'wexporting' / 'config' / 'user_id.dat'
    try:
        if id_file.exists():
            stored = id_file.read_text(encoding='utf-8').strip()
            if stored and len(stored) >= 32:
                return stored
    except Exception as e:
        logger.debug(f"[StableID] Could not read user_id.dat: {e}")

    # Generate a new UUID and persist it
    new_id = 'win_' + uuid.uuid4().hex
    try:
        id_file.parent.mkdir(parents=True, exist_ok=True)
        id_file.write_text(new_id, encoding='utf-8')
        logger.info(f"[StableID] Generated and persisted new user_id")
    except Exception as e:
        logger.warning(f"[StableID] Could not persist user_id.dat: {e}")

    return new_id


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
                    # Use a stable per-Windows-user ID (SID-based) instead of
                    # sku_store_id which is a shared product SKU, not per-user.
                    self._store_user_id = _get_stable_user_id()
                    
                    # Check if user has premium entitlement
                    # This checks for durable add-ons (lifetime purchase)
                    addons_result = await self._store_context.get_user_collection_async(["Durable"])
                    
                    # .products is IMapView<string, StoreProduct> — iterating yields keys (strings)
                    for store_id_key in addons_result.products:
                        if "lifetime" in store_id_key.lower() or "premium" in store_id_key.lower():
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
                
                # Load persisted JWT from a previous session so the server sync
                # can run on this launch even without a new purchase.
                persisted_jwt = session.load_persisted_jwt()
                if persisted_jwt:
                    session.set_jwt_token(persisted_jwt)
                    logger.info("[MSStoreProvider] Loaded persisted JWT for server sync")
                
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
    
    def validate_receipt(self, receipt_data, product_id: str = "unknown") -> bool:
        """
        Acknowledge a completed MS Store purchase with the server.

        Uses JWT authentication — no receipt needed. The winrt Python binding
        does not expose GetAppReceiptAsync(), so receipt-based validation is
        not possible. JWT proves user identity; the Store UI proves payment.

        Args:
            receipt_data: Ignored (kept for interface compatibility).
            product_id: The actual MS Store product ID that was purchased.

        Returns:
            bool: True if the server acknowledged the purchase successfully.
        """
        try:
            import requests
            from client.config.config import API_BASE_URL
            from client.core.session_manager import SessionManager

            session = SessionManager.instance()
            jwt_token = session.jwt_token
            if not jwt_token:
                logger.error("Cannot acknowledge purchase: no JWT available")
                return False

            response = requests.post(
                f"{API_BASE_URL}/api/v1/store/acknowledge-purchase",
                json={"product_id": product_id},
                headers={"Authorization": f"Bearer {jwt_token}"},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self._is_premium = result.get('is_premium', False)
                    new_jwt = result.get('jwt_token')
                    energy_balance = result.get('energy_balance')

                    if self._store_user_id and new_jwt:
                        session.start_session(
                            store_user_id=self._store_user_id,
                            jwt_token=new_jwt,
                            is_premium=self._is_premium
                        )
                        session.persist_jwt(new_jwt)

                    logger.info(f"Purchase acknowledged (premium={self._is_premium}, balance={energy_balance})")
                    return True

            logger.warning(f"Purchase acknowledgement failed: {response.status_code} {response.text}")
            return False

        except Exception as e:
            logger.error(f"Purchase acknowledgement failed: {e}")
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
    
    
    def purchase_add_on(self, store_id: str, window_handle: Optional[int] = None) -> bool:
        """
        Purchase an add-on (consumable or durable).
        
        Args:
            store_id: Store ID (12 chars, e.g. '9NBLGGH42DRG')
            window_handle: HWND of the main window (required for modal dialog)
            
        Returns:
            bool: True if purchase successful (or already owned) AND fulfilled/validated.
        """
        return self.request_purchase(store_id, window_handle)

    def request_purchase(self, product_id: str, window_handle: Optional[int] = None) -> bool:
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
                    WinRTInterop.InitializeWithWindow.Initialize(self._store_context, window_handle)
                except Exception as ex:
                    logger.warning(f"Failed to initialize with window handle: {ex}")
                    # Continue anyway, might fail or show behind
            
            async def _purchase_flow():
                # 2. Fetch Product (to ensure validity)
                logger.info(f"Fetching product details for {product_id}...")
                products_result = await self._store_context.get_store_products_async(
                    ["Consumable", "Durable", "UnmanagedConsumable"], [product_id]
                )
                
                product = products_result.products.lookup(product_id) if products_result.products.has_key(product_id) else None
                
                if not product:
                    logger.error(f"Product {product_id} not found in Store")
                    return False

                # 3. Request Purchase
                logger.info(f"Requesting purchase for {product.title} ({product_id})...")
                result = await self._store_context.request_purchase_async(product_id)
                
                status = result.status

                # 4. Result Handling
                if status == StorePurchaseStatus.SUCCEEDED:
                    logger.info("Purchase SUCCEEDED.")
                    # StorePurchaseResult has no transaction_id — generate a tracking ID for fulfillment
                    import time as _time
                    return f"tx_{product_id}_{int(_time.time())}"

                elif status == StorePurchaseStatus.ALREADY_PURCHASED:
                    logger.info("Product ALREADY_PURCHASED — checking for unfulfilled balance.")
                    is_consumable = product_id in _CONSUMABLE_PRODUCT_IDS

                    if is_consumable:
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
                                    "recovery"
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
                return self.validate_receipt(None, product_id)

            # For new purchase: validate then fulfill consumable
            is_valid = self.validate_receipt(None, product_id)

            if is_valid:
                is_consumable = product_id in _CONSUMABLE_PRODUCT_IDS
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
    a single method Initialize(HWND).
    """

    class InitializeWithWindow:
        @staticmethod
        def Initialize(winrt_obj, hwnd: int) -> bool:
            """
            Parent winrt_obj to the Win32 window identified by hwnd.
            """
            try:
                import ctypes
                import ctypes.wintypes

                class PyWinRTObject(ctypes.Structure):
                    _fields_ = [
                        ("ob_refcnt", ctypes.c_ssize_t),
                        ("ob_type", ctypes.c_void_p),
                        ("com_ptr", ctypes.c_void_p)
                    ]

                class GUID(ctypes.Structure):
                    _fields_ = [
                        ("Data1", ctypes.c_ulong),
                        ("Data2", ctypes.c_ushort),
                        ("Data3", ctypes.c_ushort),
                        ("Data4", ctypes.c_ubyte * 8)
                    ]
                    def __init__(self, data1, data2, data3, data4):
                        super().__init__()
                        self.Data1 = data1
                        self.Data2 = data2
                        self.Data3 = data3
                        for i in range(8):
                            self.Data4[i] = data4[i]

                IID_IInitializeWithWindow = GUID(
                    0x3E68D4BD, 0x7135, 0x4D10, 
                    (0x80, 0x18, 0x9F, 0xB6, 0xD9, 0xF3, 0x3F, 0xA1)
                )

                # 1. Retrieve the raw COM pointer from the winrt Python wrapper memory
                obj_struct = PyWinRTObject.from_address(id(winrt_obj))
                raw_ptr = obj_struct.com_ptr

                if not raw_ptr:
                    logger.warning("IInitializeWithWindow: failed to get com_ptr from python object")
                    return False

                # 2. QueryInterface for IInitializeWithWindow
                vtable_p = ctypes.cast(raw_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
                vtable = vtable_p[0]

                QueryInterface = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p,
                    ctypes.POINTER(GUID),
                    ctypes.POINTER(ctypes.c_void_p)
                )(vtable[0])

                init_with_window_ptr = ctypes.c_void_p()
                hr = QueryInterface(raw_ptr, ctypes.byref(IID_IInitializeWithWindow), ctypes.byref(init_with_window_ptr))

                if hr != 0 or not init_with_window_ptr.value:
                    logger.warning(f"IInitializeWithWindow::QueryInterface HRESULT=0x{hr & 0xFFFFFFFF:08X}")
                    return False

                # 3. Call Initialize(hwnd) on the queried interface
                try:
                    init_vtable_p = ctypes.cast(init_with_window_ptr.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
                    init_vtable = init_vtable_p[0]
                    Initialize_fn = ctypes.WINFUNCTYPE(
                        ctypes.HRESULT,
                        ctypes.c_void_p,
                        ctypes.wintypes.HWND
                    )(init_vtable[3])

                    hr_init = Initialize_fn(init_with_window_ptr.value, hwnd)
                    if hr_init != 0:
                        logger.warning(f"IInitializeWithWindow::Initialize HRESULT=0x{hr_init & 0xFFFFFFFF:08X}")
                        return False
                    
                    logger.info(f"IInitializeWithWindow: parented to HWND {hwnd:#x}")
                    return True

                finally:
                    # Release the IInitializeWithWindow pointer
                    Release_fn = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(init_vtable[2])
                    Release_fn(init_with_window_ptr.value)

            except Exception as e:
                logger.warning(f"IInitializeWithWindow: failed: {e}")
                return False


# ==============================================================================
# DEV ONLY: Mock Store Provider
# Used automatically when Config.DEVELOPMENT_MODE is True (running from source).
# Never runs inside a frozen PyInstaller build.
# ==============================================================================

class MockStoreProvider(IStoreAuthProvider):
    """
    DEV ONLY: Simulates MS Store purchases without real Windows Store APIs.

    Generates a fake DEV_MOCK_TX_... transaction ID and sends it to the
    PythonAnywhere server, which has a matching bypass for this prefix.
    """

    def __init__(self):
        import time
        self._store_user_id = f"DEV_MOCK_USER_{int(time.time())}"
        self._is_premium = False
        self._jwt_token = None
        logger.warning(f"[DEV MOCK] MockStoreProvider initialized — user_id: {self._store_user_id}")

    def login(self) -> AuthResult:
        from client.core.session_manager import SessionManager
        self._is_premium = False
        session = SessionManager.instance()

        # DEV: always start clean — no persisted JWT carryover between runs
        session.start_session(
            store_user_id=self._store_user_id,
            jwt_token="",
            is_premium=False
        )

        logger.warning("[DEV MOCK] login() called — fresh session, no JWT carryover")
        return AuthResult(
            success=True,
            store_user_id=self._store_user_id,
            jwt_token="",
            is_premium=False
        )

    def get_store_user_id(self) -> Optional[str]:
        return self._store_user_id

    def get_credentials(self) -> dict:
        return {
            'token': self._jwt_token,
            'store_token': None,
            'user_id': self._store_user_id,
            'is_premium': self._is_premium
        }

    def get_receipt(self) -> Optional[str]:
        return "DEV_MOCK_RECEIPT"

    def validate_receipt(self, receipt_data) -> bool:
        logger.warning("[DEV MOCK] validate_receipt() — always True in dev mode")
        return True

    def is_authenticated(self) -> bool:
        return True

    def report_fulfillment(self, product_id: str, transaction_id: str) -> bool:
        logger.warning(f"[DEV MOCK] report_fulfillment({product_id}, {transaction_id}) — no-op")
        return True

    def purchase_add_on(self, store_id: str, window_handle: Optional[int] = None) -> bool:
        """
        Simulate a full purchase flow:
        1. Fake 1.5s delay (Store dialog simulation)
        2. Generate a DEV_MOCK_TX_ transaction ID
        3. POST to server validate-receipt — server has a matching bypass
        4. Update SessionManager with real JWT returned by server
        5. Return True if server responds with success
        """
        import time
        import requests
        from client.config.config import API_BASE_URL

        logger.warning(f"[DEV MOCK] Simulating purchase for product: {store_id}")
        time.sleep(1.5)  # Simulate Store overlay appearing and processing

        tx_id = f"DEV_MOCK_TX_{store_id}_{int(time.time())}"
        logger.info(f"[DEV MOCK] Generated transaction ID: {tx_id}")

        try:
            resp = requests.post(
                f"{API_BASE_URL}/api/v1/store/validate-receipt",
                json={
                    "transaction_id": tx_id,
                    "receipt_data": tx_id,
                    "product_id": store_id,
                    "platform": "msstore",
                    "is_dev_mock": True,
                    "store_user_id": self._store_user_id  # So server creates a fresh profile per run
                },
                timeout=15
            )
            if resp.status_code == 200 and resp.json().get("success"):
                data = resp.json()
                jwt_token = data.get("jwt_token")
                is_premium = data.get("is_premium", False)
                energy_balance = data.get("energy_balance")
                logger.info(f"[DEV MOCK] Server validated. JWT received, Balance: {energy_balance}")

                # Update session with the real JWT returned by the server
                from client.core.session_manager import SessionManager
                SessionManager.instance().start_session(
                    store_user_id=self._store_user_id,
                    jwt_token=jwt_token,
                    is_premium=is_premium
                )
                self._jwt_token = jwt_token
                
                # Persist JWT so subsequent launches trigger the server sync
                if jwt_token:
                    SessionManager.instance().persist_jwt(jwt_token)
                    logger.info("[DEV MOCK] JWT persisted for next launch")
                
                return True
            else:
                logger.error(f"[DEV MOCK] Server rejected: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"[DEV MOCK] Server call failed: {e}")
            return False

    def request_purchase(self, product_id: str, window_handle: Optional[int] = None) -> bool:
        return self.purchase_add_on(product_id, window_handle)
