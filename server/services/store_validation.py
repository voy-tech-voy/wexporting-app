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
    
    NOTE: This is a stub for future implementation when Mac dev environment is available.
    
    Will require:
    - App Store Connect API key
    - StoreKit 2 server-to-server notifications
    
    Args:
        receipt_data: App Store receipt (base64)
        product_id: Product ID from App Store Connect
        
    Returns:
        dict: Validation result
    """
    # TODO: Implement when Mac development begins
    logger.warning("Apple App Store validation not yet implemented")
    raise StoreValidationError("Apple App Store validation not yet implemented")


def _get_product_type_from_id(product_id: str) -> str:
    """
    Determine product type from product ID.
    
    Args:
        product_id: Product identifier
        
    Returns:
        str: "lifetime" or "energy_pack"
    """
    if 'lifetime' in product_id.lower() or 'premium' in product_id.lower():
        return 'lifetime'
    elif 'energy' in product_id.lower():
        return 'energy_pack'
    else:
        # Default to lifetime for unknown products
        return 'lifetime'


def _get_energy_amount_from_id(product_id: str) -> int:
    """
    Extract energy amount from product ID.
    
    Examples:
        "imgapp_energy_100" -> 100
        "imgapp_energy_500" -> 500
        
    Args:
        product_id: Product identifier
        
    Returns:
        int: Energy amount, or 0 if not found
    """
    import re
    match = re.search(r'energy[_-](\d+)', product_id.lower())
    if match:
        return int(match.group(1))
    return 0
