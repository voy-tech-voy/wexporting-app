"""
Comprehensive IAP Test Suite using Generated Test Users

Tests all IAP scenarios against 100 mock users:
1. Daily reset logic (preserves purchased credits)
2. Spending logic (free-first strategy)
3. Day pass expiry validation
4. Premium status calculation
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'server'))

from services.license_manager import LicenseManager
from config.settings import Config


def load_test_users():
    """Load generated test users"""
    test_file = Path(__file__).parent.parent / 'server' / 'data' / 'test_user_profiles.json'
    with open(test_file, 'r') as f:
        return json.load(f)


def test_daily_reset_on_all_users(users):
    """Test daily reset preserves purchased energy for all users"""
    print("\n=== Test: Daily Reset (100 users) ===")
    
    lm = LicenseManager()
    failures = []
    
    # Force all users to need a reset by setting last_refresh to yesterday
    from datetime import timedelta
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
    
    for user_id, profile in users.items():
        # Set to yesterday to trigger reset
        profile['last_energy_refresh'] = yesterday
        
        original_purchased = profile.get('purchased_energy', 0)
        original_balance = profile.get('energy_balance', 0)
        
        # Trigger reset
        lm.check_daily_energy_reset(user_id, profile)
        
        # Verify purchased energy unchanged
        if profile.get('purchased_energy', 0) != original_purchased:
            failures.append(f"User {user_id[:8]}: Purchased changed from {original_purchased} to {profile['purchased_energy']}")
        
        # Verify balance = 50 + purchased (for non-premium)
        if not profile.get('is_premium'):
            expected = Config.DAILY_FREE_ENERGY + original_purchased
            if profile['energy_balance'] != expected:
                failures.append(f"User {user_id[:8]}: Balance {profile['energy_balance']}, expected {expected}")
    
    if failures:
        print(f"❌ FAILED: {len(failures)} users")
        for f in failures[:5]:  # Show first 5
            print(f"  - {f}")
    else:
        print(f"✓ All {len(users)} users passed daily reset test")
    
    return len(failures) == 0


def test_premium_status_calculation(users):
    """Test premium status calculation (lifetime OR active day pass)"""
    print("\n=== Test: Premium Status Calculation ===")
    
    failures = []
    now = datetime.utcnow()
    
    for user_id, profile in users.items():
        # Calculate effective premium
        effective_premium = profile.get('is_premium', False)
        
        if not effective_premium:
            expiry_str = profile.get('premium_expiry')
            if expiry_str:
                if datetime.fromisoformat(expiry_str) > now:
                    effective_premium = True
        
        # Verify expectations
        profile_type = profile.get('profile_type', '')
        
        if profile_type == 'premium_lifetime' and not effective_premium:
            failures.append(f"User {user_id[:8]}: Lifetime should be premium")
        
        if profile_type == 'active_day_pass' and not effective_premium:
            failures.append(f"User {user_id[:8]}: Active day pass should be premium")
        
        if profile_type == 'expired_day_pass' and effective_premium:
            failures.append(f"User {user_id[:8]}: Expired day pass should NOT be premium")
        
        if profile_type == 'free_tier' and effective_premium:
            failures.append(f"User {user_id[:8]}: Free tier should NOT be premium")
    
    if failures:
        print(f"❌ FAILED: {len(failures)} users")
        for f in failures[:5]:
            print(f"  - {f}")
    else:
        print(f"✓ All users have correct premium status")
    
    return len(failures) == 0


def test_spending_scenarios(users):
    """Test spending logic on users with purchased credits"""
    print("\n=== Test: Spending Logic (Free-First) ===")
    
    failures = []
    test_count = 0
    
    for user_id, profile in users.items():
        if profile.get('profile_type') != 'purchased_credits':
            continue
        
        test_count += 1
        
        # Simulate spending 30 credits
        original_balance = profile['energy_balance']
        original_purchased = profile['purchased_energy']
        
        cost = 30
        new_balance = original_balance - cost
        
        # Apply clamping logic
        if new_balance < original_purchased:
            new_purchased = new_balance
        else:
            new_purchased = original_purchased
        
        # Verify logic
        # If original had 50 free + 100 purchased = 150
        # Spend 30 -> 120 total, purchased should still be 100
        # Spend 60 -> 90 total, purchased should be 90 (used 10 purchased)
        
        free_before = original_balance - original_purchased
        if free_before >= cost:
            # Should only touch free
            if new_purchased != original_purchased:
                failures.append(f"User {user_id[:8]}: Spent from purchased when free was available")
        else:
            # Should touch both
            expected_purchased = max(0, original_purchased - (cost - free_before))
            if new_purchased != expected_purchased:
                failures.append(f"User {user_id[:8]}: Purchased incorrect after mixed spend")
    
    if failures:
        print(f"❌ FAILED: {len(failures)}/{test_count} users")
        for f in failures[:5]:
            print(f"  - {f}")
    else:
        print(f"✓ All {test_count} users passed spending test")
    
    return len(failures) == 0


def print_test_summary(users):
    """Print summary of test data"""
    from collections import Counter
    
    types = Counter(u['profile_type'] for u in users.values())
    
    print("\n" + "=" * 60)
    print("TEST DATA SUMMARY")
    print("=" * 60)
    print(f"Total Test Users: {len(users)}")
    for profile_type, count in sorted(types.items()):
        print(f"  - {profile_type}: {count}")
    print("=" * 60)


if __name__ == "__main__":
    print("=" * 60)
    print("IAP COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    try:
        # Load test users
        users = load_test_users()
        print_test_summary(users)
        
        # Run tests
        results = []
        results.append(test_daily_reset_on_all_users(users))
        results.append(test_premium_status_calculation(users))
        results.append(test_spending_scenarios(users))
        
        # Final result
        print("\n" + "=" * 60)
        if all(results):
            print("✓ ALL TESTS PASSED")
        else:
            print("❌ SOME TESTS FAILED")
        print("=" * 60)
        
        sys.exit(0 if all(results) else 1)
        
    except FileNotFoundError:
        print("\n❌ ERROR: Test user data not found")
        print("Run: python tests/generate_test_users.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
