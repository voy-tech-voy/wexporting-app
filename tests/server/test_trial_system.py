"""
Test Trial System Implementation
Tests trial creation, eligibility checks, and offline restrictions
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from services.license_manager import LicenseManager
from datetime import datetime, timedelta
import json

def test_trial_eligibility_check():
    """Test trial eligibility checking"""
    print("\n=== TEST: Trial Eligibility Check ===")
    
    license_manager = LicenseManager()
    
    # Test 1: New user should be eligible
    result = license_manager.check_trial_eligibility("newuser@example.com", "NEW-DEVICE-123")
    print(f"New user eligibility: {result}")
    assert result['eligible'] == True, "New user should be eligible"
    print("✅ New user is eligible for trial")
    
    # Test 2: Create trial for this user
    trial_result = license_manager.create_trial_license(
        email="newuser@example.com",
        hardware_id="NEW-DEVICE-123",
        device_name="Test Device"
    )
    print(f"Trial creation: {trial_result}")
    assert trial_result['success'] == True, "Trial creation should succeed"
    print(f"✅ Trial created: {trial_result['license_key']}")
    
    # Test 3: Same email should NOT be eligible again
    result = license_manager.check_trial_eligibility("newuser@example.com", "DIFFERENT-DEVICE-456")
    print(f"Same email eligibility: {result}")
    assert result['eligible'] == False, "Same email should not be eligible"
    assert result['reason'] == 'trial_already_used_email', "Should detect email reuse"
    print("✅ Duplicate email correctly rejected")
    
    # Test 4: Same device should NOT be eligible again
    result = license_manager.check_trial_eligibility("differentuser@example.com", "NEW-DEVICE-123")
    print(f"Same device eligibility: {result}")
    assert result['eligible'] == False, "Same device should not be eligible"
    assert result['reason'] == 'trial_already_used_device', "Should detect device reuse"
    print("✅ Duplicate device correctly rejected")
    
    print("\n✅ ALL TRIAL ELIGIBILITY TESTS PASSED\n")

def test_trial_creation():
    """Test trial license creation"""
    print("\n=== TEST: Trial Creation ===")
    
    license_manager = LicenseManager()
    
    # Create trial
    result = license_manager.create_trial_license(
        email="trial-test@example.com",
        hardware_id="TRIAL-DEVICE-789",
        device_name="Trial Test Device"
    )
    
    print(f"Trial creation result: {json.dumps(result, indent=2)}")
    assert result['success'] == True, "Trial creation should succeed"
    
    license_key = result['license_key']
    print(f"✅ Trial license created: {license_key}")
    
    # Verify license is a trial
    is_trial = license_manager.is_trial_license(license_key)
    print(f"Is trial license: {is_trial}")
    assert is_trial == True, "License should be identified as trial"
    print("✅ License correctly identified as trial")
    
    # Verify license details
    licenses = license_manager.load_licenses()
    license_data = licenses[license_key]
    
    print(f"License data: {json.dumps(license_data, indent=2)}")
    
    # Check immediately bound to device
    assert license_data['hardware_id'] == "TRIAL-DEVICE-789", "Should be immediately bound"
    print("✅ License immediately bound to device")
    
    # Check 7-day expiry
    created = datetime.fromisoformat(license_data['created_date'])
    expiry = datetime.fromisoformat(license_data['expiry_date'])
    duration = (expiry - created).days
    assert duration == 7, f"Trial should be 7 days, got {duration}"
    print(f"✅ Trial duration correct: {duration} days")
    
    print("\n✅ ALL TRIAL CREATION TESTS PASSED\n")

def test_trial_validation_restrictions():
    """Test trial validation with offline restrictions"""
    print("\n=== TEST: Trial Validation & Offline Restrictions ===")
    
    license_manager = LicenseManager()
    
    # Create trial
    result = license_manager.create_trial_license(
        email="validation-test@example.com",
        hardware_id="VALIDATION-DEVICE-456",
        device_name="Validation Test Device"
    )
    
    license_key = result['license_key']
    print(f"Created trial license: {license_key}")
    
    # Test 1: Online validation should work
    val_result = license_manager.validate_license(
        email="validation-test@example.com",
        license_key=license_key,
        hardware_id="VALIDATION-DEVICE-456",
        device_name="Validation Test Device",
        is_offline=False
    )
    print(f"Online validation: {val_result}")
    assert val_result['success'] == True, "Online validation should succeed"
    assert val_result['is_trial'] == True, "Should indicate trial license"
    print("✅ Online validation works for trial")
    
    # Test 2: Offline validation should FAIL for trials
    val_result = license_manager.validate_license(
        email="validation-test@example.com",
        license_key=license_key,
        hardware_id="VALIDATION-DEVICE-456",
        device_name="Validation Test Device",
        is_offline=True
    )
    print(f"Offline validation: {val_result}")
    assert val_result['success'] == False, "Offline validation should fail for trials"
    assert val_result['error'] == 'trial_requires_online', "Should indicate trial requires online"
    print("✅ Offline validation correctly blocked for trial")
    
    print("\n✅ ALL TRIAL VALIDATION TESTS PASSED\n")

def test_paid_license_offline_grace():
    """Test offline grace period for paid licenses (NOT trials)"""
    print("\n=== TEST: Paid License Offline Grace Period ===")
    
    license_manager = LicenseManager()
    
    # Create paid license (30 days)
    purchase_info = {
        'source': 'direct',
        'source_license_key': 'direct-test-paid-123',
        'tier': 'Monthly',
        'price': 5,
        'is_trial': False
    }

    
    license_key = license_manager.create_license(
        email="paid-test@example.com",
        expires_days=30,
        purchase_info=purchase_info
    )
    
    print(f"Created paid license: {license_key}")
    
    # Test 1: First activation online
    val_result = license_manager.validate_license(
        email="paid-test@example.com",
        license_key=license_key,
        hardware_id="PAID-DEVICE-789",
        device_name="Paid Test Device",
        is_offline=False
    )
    print(f"First online validation: {val_result}")
    assert val_result['success'] == True, "First validation should succeed"
    assert val_result['is_trial'] == False, "Should NOT be trial"
    print("✅ Paid license activated online")
    
    # Test 2: Offline validation within grace period (0 days) should work
    val_result = license_manager.validate_license(
        email="paid-test@example.com",
        license_key=license_key,
        hardware_id="PAID-DEVICE-789",
        device_name="Paid Test Device",
        is_offline=True
    )
    print(f"Offline validation (0 days): {val_result}")
    assert val_result['success'] == True, "Offline within grace should succeed"
    print("✅ Offline validation works within grace period")
    
    # Test 3: Simulate 4 days offline (should fail - grace is 3 days)
    licenses = license_manager.load_licenses()
    license_data = licenses[license_key]
    old_date = (datetime.now() - timedelta(days=4)).isoformat()
    license_data['last_validation'] = old_date
    licenses[license_key] = license_data
    license_manager.save_licenses(licenses)
    
    val_result = license_manager.validate_license(
        email="paid-test@example.com",
        license_key=license_key,
        hardware_id="PAID-DEVICE-789",
        device_name="Paid Test Device",
        is_offline=True
    )
    print(f"Offline validation (4 days): {val_result}")
    assert val_result['success'] == False, "Should fail after grace period"
    assert val_result['error'] == 'offline_grace_expired', "Should indicate grace expired"
    print("✅ Offline validation correctly blocked after grace period")
    
    print("\n✅ ALL OFFLINE GRACE TESTS PASSED\n")

def test_trial_abuse_prevention():
    """Test comprehensive abuse prevention"""
    print("\n=== TEST: Trial Abuse Prevention ===")
    
    license_manager = LicenseManager()
    
    # Create first trial
    result1 = license_manager.create_trial_license(
        email="abuse-test@example.com",
        hardware_id="ABUSE-DEVICE-111",
        device_name="Device 1"
    )
    assert result1['success'] == True
    print(f"✅ First trial created: {result1['license_key']}")
    
    # Try to create second trial with same email, different device
    result2 = license_manager.create_trial_license(
        email="abuse-test@example.com",
        hardware_id="ABUSE-DEVICE-222",
        device_name="Device 2"
    )
    assert result2['success'] == False
    assert result2['error'] == 'trial_already_used_email'
    print("✅ Second trial blocked (same email)")
    
    # Try to create trial with different email, same device
    result3 = license_manager.create_trial_license(
        email="different-abuse@example.com",
        hardware_id="ABUSE-DEVICE-111",
        device_name="Device 1"
    )
    assert result3['success'] == False
    assert result3['error'] == 'trial_already_used_device'
    print("✅ Trial blocked (same device)")
    
    # New email + new device should work
    result4 = license_manager.create_trial_license(
        email="legitimate-user@example.com",
        hardware_id="LEGITIMATE-DEVICE-333",
        device_name="Device 3"
    )
    assert result4['success'] == True
    print(f"✅ Legitimate trial created: {result4['license_key']}")
    
    print("\n✅ ALL ABUSE PREVENTION TESTS PASSED\n")

if __name__ == "__main__":
    print("="*60)
    print("TRIAL SYSTEM TEST SUITE")
    print("="*60)
    
    try:
        test_trial_eligibility_check()
        test_trial_creation()
        test_trial_validation_restrictions()
        test_paid_license_offline_grace()
        test_trial_abuse_prevention()
        
        print("="*60)
        print("🎉 ALL TRIAL SYSTEM TESTS PASSED! 🎉")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
