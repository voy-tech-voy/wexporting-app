"""
Store Receipt Validation Service

Platform-agnostic receipt validation for MS Store and Apple App Store.
Routes to appropriate validation API based on platform.
"""

import requests
import logging
import json
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger(__name__)


class StoreValidationError(Exception):
    """Raised when receipt validation fails"""
    pass


def validate_receipt(receipt_data: str, platform: str, product_id: str) -> Dict[str, Any]:
    """
    Validate a store receipt (platform-agnostic router).
    
    Args:
        receipt_data: Base64-encoded receipt from client
        platform: "msstore" or "appstore"
        product_id: Product identifier (e.g., "imgapp_lifetime")
        
    Returns:
        dict: {
            "valid": True,
            "product_type": "lifetime" | "energy_pack",
            "energy_amount": 100,  # For energy packs
            "transaction_id": "..."
        }
        
    Raises:
        StoreValidationError: If validation fails
    """
    if platform == "msstore":
        return _validate_msstore_receipt(receipt_data, product_id)
    elif platform == "appstore":
        return _validate_appstore_receipt(receipt_data, product_id)
    else:
        raise StoreValidationError(f"Unsupported platform: {platform}")


def _validate_msstore_receipt(receipt_data: str, product_id: str) -> Dict[str, Any]:
    """
    Validate Microsoft Store receipt via Collections API.
    
    Requires Azure AD credentials in environment:
    - MSSTORE_TENANT_ID
    - MSSTORE_CLIENT_ID
    - MSSTORE_CLIENT_SECRET
    
    Args:
        receipt_data: MS Store receipt XML
        product_id: Product ID from Partner Center
        
    Returns:
        dict: Validation result
    """
    # Get Azure AD credentials
    tenant_id = Config.MSSTORE_TENANT_ID
    client_id = Config.MSSTORE_CLIENT_ID
    client_secret = Config.MSSTORE_CLIENT_SECRET
    
    # ==========================================================================
    # DEV MOCK BYPASS — DEBUG MODE ONLY
    # If receipt_data starts with DEV_MOCK_TX_, skip all Azure validation.
    # Real MS Store transaction IDs are GUIDs and can NEVER match this prefix.
    # SECURITY: Only active when FLASK_DEBUG=true. Never runs in production.
    # ==========================================================================
    if Config.DEBUG and receipt_data and receipt_data.startswith("DEV_MOCK_TX_"):
        logger.warning(f"[DEV MOCK] Bypassing Azure validation for mock receipt: {receipt_data}")
        product_type = _get_product_type_from_id(product_id)
        energy_amount = _get_energy_amount_from_id(product_id) if product_type == "energy_pack" else 0
        return {
            'valid': True,
            'product_type': product_type,
            'energy_amount': energy_amount,
            'transaction_id': receipt_data,
            'platform': 'msstore',
            'is_dev_mock': True
        }

    if not all([tenant_id, client_id, client_secret]):
        logger.error("MS Store credentials not configured")
        raise StoreValidationError("MS Store validation not configured")
    
    try:
        # Step 1: Get Azure AD access token
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://onestore.microsoft.com/.default'
        }
        
        token_response = requests.post(token_url, data=token_data, timeout=10)
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']
        
        # Step 2: Validate receipt with Collections API
        collections_url = "https://collections.mp.microsoft.com/v6.0/collections/validate"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        validation_payload = {
            'receipt': receipt_data,
            'productId': product_id
        }
        
        validation_response = requests.post(
            collections_url,
            headers=headers,
            json=validation_payload,
            timeout=10
        )
        validation_response.raise_for_status()
        result = validation_response.json()
        
        # Parse result
        if result.get('isValid'):
            # Determine product type from product_id
            product_type = _get_product_type_from_id(product_id)
            energy_amount = _get_energy_amount_from_id(product_id) if product_type == "energy_pack" else 0
            
            return {
                'valid': True,
                'product_type': product_type,
                'energy_amount': energy_amount,
                'transaction_id': result.get('transactionId', ''),
                'platform': 'msstore'
            }
        else:
            logger.warning(f"MS Store receipt validation failed: {result}")
            raise StoreValidationError("Receipt validation failed")
            
    except requests.RequestException as e:
        logger.error(f"MS Store API error: {e}")
        raise StoreValidationError(f"MS Store API error: {str(e)}")


def _validate_appstore_receipt(receipt_data: str, product_id: str) -> Dict[str, Any]:
    """
    Validate Apple App Store receipt via App Store Server API.

    Args:
        receipt_data: For StoreKit 2, this is the originalTransactionId (or transactionId)
        product_id: Expected Product ID

    Returns:
        dict: Validation result
    """
    import os
    key_id = Config.APPSTORE_KEY_ID
    issuer_id = Config.APPSTORE_ISSUER_ID
    bundle_id = Config.APPSTORE_BUNDLE_ID
    private_key = Config.APPSTORE_PRIVATE_KEY
    
    if not all([key_id, issuer_id, bundle_id, private_key]):
        logger.error("App Store credentials not configured")
        raise StoreValidationError("App Store validation not configured")
        
    try:
        # Load Private Key logic
        # If private_key looks like a path, read it
        if os.path.exists(private_key) and os.path.isfile(private_key):
             with open(private_key, 'r') as f:
                 private_key_content = f.read()
        else:
             private_key_content = private_key
             
        # 1. Generate JWT for App Store API access
        import jwt
        import time
        
        now = int(time.time())
        expiry = now + 3600  # 1 hour
        
        headers = {
            "alg": "ES256",
            "kid": key_id,
            "typ": "JWT"
        }
        
        payload = {
            "iss": issuer_id,
            "iat": now,
            "exp": expiry,
            "aud": "appstoreconnect-v1",
            "bid": bundle_id
        }
        
        # Sign with ES256 using private key
        token = jwt.encode(payload, private_key_content, algorithm="ES256", headers=headers)
        
        # 2. Call Apple API to get transaction info
        # Using Get Transaction Info endpoint: GET /inApps/v1/transactions/{transactionId}
        # receipt_data is expected to be transactionId from client
        transaction_id = receipt_data
        
        # Use sandbox URL for testing, production for release. How to detect?
        # App Store Server API URL is actually the same for sandbox/prod, but the environment in response differs.
        # But wait, there is a separate sandbox endpoint?
        # NO: "The base URL for the App Store Server API is: https://api.storekit.itunes.apple.com"
        # There is a sandbox URL: "https://api.storekit-sandbox.itunes.apple.com"
        # We should try production first, if 404 try sandbox? 
        # Actually usually distinct URLs. We'll default to Production unless Config.DEBUG is True?
        
        base_url = "https://api.storekit.itunes.apple.com"
        if Config.DEBUG:
             base_url = "https://api.storekit-sandbox.itunes.apple.com"
             
        url = f"{base_url}/inApps/v1/transactions/{transaction_id}"
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404 and not Config.DEBUG:
            # Fallback to sandbox just in case? Or log warning.
            logger.warning(f"Transaction {transaction_id} not found in production. Sandbox fallback?")
        
        response.raise_for_status()
        data = response.json()
        
        # 3. Decode JWS signedTransactionInfo
        signed_tx_info = data.get('signedTransactionInfo')
        if not signed_tx_info:
             raise StoreValidationError("No signedTransactionInfo in response")
             
        # We don't verify the chain here (complex), rely on HTTPS + trusted source for now. 
        # In production, verifying certificate chain is recommended.
        # Decode without verification for extracting data
        tx_info = jwt.decode(signed_tx_info, options={"verify_signature": False})
        
        # Check matching product ID
        api_product_id = tx_info.get('productId')
        if api_product_id != product_id:
             logger.warning(f"Product ID mismatch: expected {product_id}, got {api_product_id}")
             # Depending on flow, this might be okay (e.g. upgraded), but for specific validation stricter is safer.
        
        # Determine product type
        product_type = _get_product_type_from_id(api_product_id)
        energy_amount = _get_energy_amount_from_id(api_product_id) if product_type == "energy_pack" else 0
        
        return {
            'valid': True,
            'product_type': product_type,
            'energy_amount': energy_amount,
            'transaction_id': tx_info.get('transactionId'),
            'original_transaction_id': tx_info.get('originalTransactionId'),
            'platform': 'appstore'
        }
            
    except Exception as e:
        logger.error(f"App Store API error: {e}")
        raise StoreValidationError(f"App Store API error: {str(e)}")


# MS Store product ID lookup tables (must match routes.py and purchase_options.json)
_MSSTORE_PRODUCT_TYPE_MAP = {
    '9PFHR7GMBT0T': 'energy_pack',  # 500 Credits (consumable)
    '9NNK6Q3WZN2M': 'limit_pack',   # Daily Focus Pack (+200 permanent max)
    '9P4WCMTCH89V': 'lifetime',     # Premium Lifetime
}

_MSSTORE_PRODUCT_ENERGY_MAP = {
    '9PFHR7GMBT0T': 500,
    '9NNK6Q3WZN2M': 200,
    '9P4WCMTCH89V': 0,
}


def _get_product_type_from_id(product_id: str) -> str:
    """
    Determine product type from product ID.

    Checks explicit MS Store ID table first, then falls back to keyword matching
    for forward-compatibility with future products.

    Args:
        product_id: Product identifier

    Returns:
        str: "lifetime", "energy_pack", "limit_pack", or "day_pass"
    """
    if product_id in _MSSTORE_PRODUCT_TYPE_MAP:
        return _MSSTORE_PRODUCT_TYPE_MAP[product_id]

    # Keyword fallback for future / non-MS-Store products
    pid = product_id.lower()
    if 'lifetime' in pid or 'premium' in pid:
        return 'lifetime'
    elif 'day_pass' in pid:
        return 'day_pass'
    elif 'energy' in pid or 'credit' in pid:
        return 'energy_pack'
    else:
        logger.warning(f"Unknown product_id '{product_id}' — defaulting to 'lifetime'")
        return 'lifetime'


def _get_energy_amount_from_id(product_id: str) -> int:
    """
    Extract energy amount from product ID.

    Checks explicit MS Store ID table first, then falls back to regex parsing
    for future products that encode the amount in their ID string.

    Args:
        product_id: Product identifier

    Returns:
        int: Energy amount, or 0 if not found
    """
    if product_id in _MSSTORE_PRODUCT_ENERGY_MAP:
        return _MSSTORE_PRODUCT_ENERGY_MAP[product_id]

    import re
    match = re.search(r'(?:energy|credit)[_-](\d+)', product_id.lower())
    if match:
        return int(match.group(1))
    return 0
