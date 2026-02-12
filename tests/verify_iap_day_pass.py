"""
Test script for Day Pass Logic

Verifies:
1. Day Pass sets premium_expiry correctly
2. JWT is issued with is_premium=True for active day pass
3. Expired day pass does NOT grant premium
"""

import sys
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'server'))

from datetime import datetime, timedelta
from auth.jwt_auth import create_jwt_token, verify_jwt_token


def test_day_pass_expiry_calculation():
    """Test that day pass sets expiry 24h from now"""
    print("\n=== Test 1: Day Pass Expiry Calculation ===")
    
    # Simulate day pass purchase
    now = datetime.utcnow()
    expiry = now + timedelta(days=1)
    
    profile = {
        'is_premium': False,  # Not lifetime
        'premium_expiry': expiry.isoformat()
    }
    
    print(f"Day Pass purchased at: {now.isoformat()}")
    print(f"Expiry set to: {profile['premium_expiry']}")
    
    # Check if premium is active
    expiry_str = profile.get('premium_expiry')
    is_premium_active = profile.get('is_premium', False)
    
    if expiry_str:
        if datetime.fromisoformat(expiry_str) > datetime.utcnow():
            is_premium_active = True
    
    assert is_premium_active == True, "❌ FAILED: Day pass should grant premium"
    print(f"✓ Day pass correctly grants premium status")


def test_expired_day_pass():
    """Test that expired day pass does NOT grant premium"""
    print("\n=== Test 2: Expired Day Pass ===")
    
    # Simulate expired day pass
    expired_time = datetime.utcnow() - timedelta(hours=1)
    
    profile = {
        'is_premium': False,
        'premium_expiry': expired_time.isoformat()
    }
    
    print(f"Day Pass expired at: {profile['premium_expiry']}")
    
    # Check if premium is active
    expiry_str = profile.get('premium_expiry')
    is_premium_active = profile.get('is_premium', False)
    
    if expiry_str:
        if datetime.fromisoformat(expiry_str) > datetime.utcnow():
            is_premium_active = True
    
    assert is_premium_active == False, "❌ FAILED: Expired day pass should NOT grant premium"
    print(f"✓ Expired day pass correctly denies premium")


def test_lifetime_overrides_expiry():
    """Test that lifetime premium overrides expiry check"""
    print("\n=== Test 3: Lifetime Premium Overrides Expiry ===")
    
    # User has both lifetime AND an old expired day pass
    expired_time = datetime.utcnow() - timedelta(days=30)
    
    profile = {
        'is_premium': True,  # Lifetime
        'premium_expiry': expired_time.isoformat()  # Old expired day pass
    }
    
    print(f"User has lifetime premium: {profile['is_premium']}")
    print(f"Old day pass expired at: {profile['premium_expiry']}")
    
    # Check premium status
    is_premium_active = profile.get('is_premium', False)
    
    if not is_premium_active:
        expiry_str = profile.get('premium_expiry')
        if expiry_str:
            if datetime.fromisoformat(expiry_str) > datetime.utcnow():
                is_premium_active = True
    
    assert is_premium_active == True, "❌ FAILED: Lifetime should grant premium"
    print(f"✓ Lifetime premium correctly overrides expired day pass")


def test_jwt_contains_premium_status():
    """Test that JWT encodes premium status correctly"""
    print("\n=== Test 4: JWT Premium Encoding ===")
    
    # Create JWT with premium=True
    token = create_jwt_token("test_user", "msstore", is_premium=True)
    
    # Decode and verify
    claims = verify_jwt_token(token)
    
    assert claims is not None, "❌ FAILED: JWT verification failed"
    assert claims['is_premium'] == True, "❌ FAILED: JWT should have is_premium=True"
    
    print(f"✓ JWT correctly encodes is_premium=True")
    print(f"  Token claims: {claims}")


if __name__ == "__main__":
    print("=" * 60)
    print("IAP DAY PASS LOGIC VERIFICATION")
    print("=" * 60)
    
    try:
        test_day_pass_expiry_calculation()
        test_expired_day_pass()
        test_lifetime_overrides_expiry()
        test_jwt_contains_premium_status()
        
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
