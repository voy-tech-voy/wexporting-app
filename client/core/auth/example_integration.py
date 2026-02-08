"""
Example: Integrating Store Authentication with Energy System

This example demonstrates how to use the new Store authentication
abstraction layer with the Energy system.
"""

from client.core.auth import get_store_auth_provider
from client.core.energy_manager import EnergyManager


def example_store_login_flow():
    """
    Example of complete Store login and Energy sync flow.
    """
    
    # Step 1: Get platform-specific Store auth provider
    store_auth = get_store_auth_provider()
    
    # Step 2: Trigger Store login (platform-native UI)
    auth_result = store_auth.login()
    
    if not auth_result.success:
        print(f"Login failed: {auth_result.error_message}")
        return
    
    print(f"Login successful!")
    print(f"Store User ID: {auth_result.store_user_id}")
    print(f"Premium Status: {auth_result.is_premium}")
    
    # Step 3: Configure Energy Manager with Store credentials
    energy_mgr = EnergyManager.instance()
    energy_mgr.set_store_auth(
        store_user_id=auth_result.store_user_id,
        jwt_token=auth_result.jwt_token,
        is_premium=auth_result.is_premium
    )
    
    # Step 4: Energy system is now ready
    if auth_result.is_premium:
        print("Premium user - unlimited conversions!")
    else:
        balance = energy_mgr.get_balance()
        print(f"Free tier - {balance} energy remaining today")


def example_receipt_validation():
    """
    Example of validating an IAP receipt (e.g., after purchasing Premium).
    """
    
    store_auth = get_store_auth_provider()
    
    # Assume we have a receipt from an in-app purchase
    receipt_data = b"..."  # Platform-specific receipt blob
    
    # Validate with backend server
    is_valid = store_auth.validate_receipt(receipt_data)
    
    if is_valid:
        print("Receipt validated! Premium unlocked.")
        energy_mgr = EnergyManager.instance()
        energy_mgr.set_premium_status(True)
    else:
        print("Receipt validation failed")


if __name__ == "__main__":
    # Run example login flow
    example_store_login_flow()
