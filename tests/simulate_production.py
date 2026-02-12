
import sys
import os
import asyncio
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from client.core.auth.ms_store_provider import MSStoreProvider
from client.core.session_manager import SessionManager
import client.config.config as config

def run_simulation():
    print("--- STARTING PRODUCTION SIMULATION (PREMIUM_OVERRIDE = None) ---")
    
    # 1. Reset Singleton
    SessionManager._instance = None
    
    # 2. Simulate Production Config
    config.PREMIUM_OVERRIDE = None
    print(f"Config: PREMIUM_OVERRIDE = {config.PREMIUM_OVERRIDE}")
    
    # 3. Initialize Provider
    provider = MSStoreProvider()
    provider._store_available = True # Force available
    
    # 4. Mock asyncio.run to simulate successful Store response
    # We simulate a Store that returns "True" for license check AND finds a generic "Premium" addon
    def mock_store_check(coro):
        # Simulate finding a premium license
        print("[SIMULATION] Store found valid Premium License")
        provider._is_premium = True 
        provider._store_user_id = "prod_user_123"
        provider._jwt_token = "prod_token_xyz"
        return True # success
        
    with patch('asyncio.run', side_effect=mock_store_check):
        # 5. Perform Login
        print("Logging in...")
        result = provider.login()
        
        # 6. Verify Result
        print(f"Login Result Success: {result.success}")
        print(f"Provider Internal is_premium: {provider._is_premium}")
        
        # 7. Verify Session Manager (The Source of Truth)
        session_premium = SessionManager.instance().is_premium
        print(f"SessionManager is_premium: {session_premium}")
        
        if session_premium is True:
            print("\n✅ PASS: Production logic correctly accepted Store Premium status.")
        else:
            print("\n❌ FAIL: Production logic ignored Store Premium status.")

    print("\n\n--- STARTING OVERRIDE SIMULATION (PREMIUM_OVERRIDE = False) ---")
    # Test that Override takes precedence over Store
    
    # Reset
    SessionManager._instance = None
    config.PREMIUM_OVERRIDE = False # Force Free despite Store saying Premium
    print(f"Config: PREMIUM_OVERRIDE = {config.PREMIUM_OVERRIDE}")
    
    provider = MSStoreProvider()
    provider._store_available = True
    
    with patch('asyncio.run', side_effect=mock_store_check):
        # Store will say True (inside mock_store_check), but Config says False
        print("Logging in...")
        result = provider.login()
        
        session_premium = SessionManager.instance().is_premium
        print(f"Provider Internal is_premium: {provider._is_premium} (Store said True)")
        print(f"SessionManager is_premium: {session_premium}")
        
        if session_premium is False:
             print("\n✅ PASS: Override correctly blocked Store Premium status.")
        else:
             print("\n❌ FAIL: Override failed to block Store Premium status.")

if __name__ == "__main__":
    run_simulation()
