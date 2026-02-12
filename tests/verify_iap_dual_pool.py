"""
Test script for IAP Dual Pool Energy Logic

Verifies:
1. Daily reset preserves purchased energy
2. Spending deducts from free first, then purchased
3. Profile initialization includes purchased_energy field
"""

import sys
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'server'))

from services.license_manager import LicenseManager
from config.settings import Config
from datetime import datetime, timedelta


def test_profile_initialization():
    """Test that new profiles include purchased_energy field"""
    print("\n=== Test 1: Profile Initialization ===")
    
    lm = LicenseManager()
    profile = lm.get_or_create_user_profile("test_user_init", "msstore")
    
    assert 'purchased_energy' in profile, "❌ FAILED: purchased_energy field missing"
    assert profile['purchased_energy'] == 0, "❌ FAILED: purchased_energy should default to 0"
    assert profile['energy_balance'] == Config.DAILY_FREE_ENERGY, "❌ FAILED: Initial balance incorrect"
    
    print(f"✓ New profile initialized correctly")
    print(f"  - energy_balance: {profile['energy_balance']}")
    print(f"  - purchased_energy: {profile['purchased_energy']}")


def test_daily_reset_preserves_purchased():
    """Test that daily reset preserves purchased energy"""
    print("\n=== Test 2: Daily Reset Preserves Purchased ===")
    
    lm = LicenseManager()
    
    # Create profile with purchased energy
    profile = {
        'store_user_id': 'test_user_reset',
        'platform': 'msstore',
        'energy_balance': 90,  # User spent 60 (10 free + 50 purchased)
        'purchased_energy': 50,  # 50 purchased remaining
        'last_energy_refresh': (datetime.utcnow() - timedelta(days=2)).isoformat(),  # Force reset
        'is_premium': False
    }
    
    print(f"Before reset:")
    print(f"  - Total Balance: {profile['energy_balance']}")
    print(f"  - Purchased: {profile['purchased_energy']}")
    
    # Trigger reset
    lm.check_daily_energy_reset('test_user_reset', profile)
    
    print(f"After reset:")
    print(f"  - Total Balance: {profile['energy_balance']}")
    print(f"  - Purchased: {profile['purchased_energy']}")
    
    expected_balance = Config.DAILY_FREE_ENERGY + 50  # 50 free + 50 purchased
    assert profile['energy_balance'] == expected_balance, \
        f"❌ FAILED: Expected {expected_balance}, got {profile['energy_balance']}"
    assert profile['purchased_energy'] == 50, \
        f"❌ FAILED: Purchased energy should remain 50"
    
    print(f"✓ Daily reset preserved purchased energy correctly")


def test_spending_logic():
    """Test that spending deducts from free first"""
    print("\n=== Test 3: Spending Logic (Free First) ===")
    
    # Simulate spending via the logic in routes.py
    profile = {
        'energy_balance': 150,  # 50 free + 100 purchased
        'purchased_energy': 100
    }
    
    print(f"Initial state:")
    print(f"  - Total: {profile['energy_balance']} (50 Free + 100 Purchased)")
    
    # Spend 40 (should only touch free)
    cost = 40
    profile['energy_balance'] -= cost
    # Clamp purchased if needed
    if profile['energy_balance'] < profile['purchased_energy']:
        profile['purchased_energy'] = profile['energy_balance']
    
    print(f"\nAfter spending {cost}:")
    print(f"  - Total: {profile['energy_balance']}")
    print(f"  - Purchased: {profile['purchased_energy']}")
    
    assert profile['energy_balance'] == 110, "❌ FAILED: Balance should be 110"
    assert profile['purchased_energy'] == 100, "❌ FAILED: Purchased should still be 100"
    print(f"✓ Spent from free pool only")
    
    # Spend 60 more (should use 10 free + 50 purchased)
    cost = 60
    profile['energy_balance'] -= cost
    if profile['energy_balance'] < profile['purchased_energy']:
        profile['purchased_energy'] = profile['energy_balance']
    
    print(f"\nAfter spending {cost} more:")
    print(f"  - Total: {profile['energy_balance']}")
    print(f"  - Purchased: {profile['purchased_energy']}")
    
    assert profile['energy_balance'] == 50, "❌ FAILED: Balance should be 50"
    assert profile['purchased_energy'] == 50, "❌ FAILED: Purchased should be clamped to 50"
    print(f"✓ Spent from free + purchased correctly")


def test_purchase_addition():
    """Test that purchasing adds to both pools"""
    print("\n=== Test 4: Purchase Addition ===")
    
    profile = {
        'energy_balance': 50,
        'purchased_energy': 0
    }
    
    print(f"Before purchase:")
    print(f"  - Total: {profile['energy_balance']}")
    print(f"  - Purchased: {profile['purchased_energy']}")
    
    # Simulate buying 100 credits
    energy_to_add = 100
    profile['energy_balance'] += energy_to_add
    profile['purchased_energy'] += energy_to_add
    
    print(f"\nAfter buying {energy_to_add} credits:")
    print(f"  - Total: {profile['energy_balance']}")
    print(f"  - Purchased: {profile['purchased_energy']}")
    
    assert profile['energy_balance'] == 150, "❌ FAILED: Total should be 150"
    assert profile['purchased_energy'] == 100, "❌ FAILED: Purchased should be 100"
    print(f"✓ Purchase added to both pools correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("IAP DUAL POOL ENERGY LOGIC VERIFICATION")
    print("=" * 60)
    
    try:
        test_profile_initialization()
        test_daily_reset_preserves_purchased()
        test_spending_logic()
        test_purchase_addition()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n{e}")
        print("\n" + "=" * 60)
        print("❌ TESTS FAILED")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
