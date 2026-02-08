#!/usr/bin/env python3
"""
Test refund policy implementation.
Verifies that:
1. Licenses can be marked as refunded
2. Refunded licenses are deactivated
3. Refund info is logged to audit trail
4. Refund status can be queried
"""

import json
import os
import sys
from datetime import datetime

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from services.license_manager import LicenseManager
from config.settings import Config

def test_refund_policy():
    """Test refund handling"""
    
    print("=" * 70)
    print("TEST: Refund Policy Implementation")
    print("=" * 70)
    
    # Initialize
    manager = LicenseManager()
    
    # Create a test license
    print(f"\n📝 Creating test license for refund testing...")
    license_key = manager.create_license(
        email='refund_test@example.com',
        customer_name='Refund Test Customer',
        expires_days=365,
        purchase_info={
            'source': 'gumroad',
            'source_license_key': 'TEST-GUMROAD-KEY-123',
            'sale_id': 'test_sale_id_456',
            'customer_id': '1234567890',
            'product_id': 'product_xyz',
            'product_name': 'Test Product',
            'tier': 'Lifetime',
            'price': '100',
            'currency': 'usd',
            'purchase_date': datetime.now().isoformat(),
            'is_recurring': False,
            'recurrence': None,
            'subscription_id': None,
            'is_refunded': False,
            'is_disputed': False,
            'is_test': True
        }
    )
    
    print(f"✓ License created: {license_key}")
    
    # 1. Check license is active
    print(f"\n✅ Step 1: Verify license is active")
    licenses = manager.load_licenses()
    license_data = licenses[license_key]
    
    print(f"  Is active: {license_data['is_active']}")
    print(f"  Refund date: {license_data['refund_date']}")
    print(f"  Refund reason: {license_data['refund_reason']}")
    
    if not license_data['is_active']:
        print(f"  ✗ License should be active!")
        return False
    
    if license_data['refund_date'] is not None:
        print(f"  ✗ Refund date should be None!")
        return False
    
    print(f"  ✓ License is active (not refunded)")
    
    # 2. Validate license before refund
    print(f"\n✅ Step 2: Validate license before refund")
    validation = manager.validate_license(
        email='refund_test@example.com',
        license_key=license_key,
        hardware_id='test_hardware_id_123'
    )
    
    if not validation['success']:
        print(f"  ✗ Validation failed: {validation}")
        return False
    
    print(f"  ✓ License validates successfully")
    
    # 3. Process refund
    print(f"\n✅ Step 3: Process refund")
    refund_result = manager.handle_refund(license_key, "customer_request")
    
    if not refund_result['success']:
        print(f"  ✗ Refund failed: {refund_result}")
        return False
    
    print(f"  ✓ Refund processed: {refund_result['message']}")
    
    # 4. Verify license is deactivated
    print(f"\n✅ Step 4: Verify license is deactivated")
    licenses = manager.load_licenses()
    license_data = licenses[license_key]
    
    print(f"  Is active: {license_data['is_active']}")
    print(f"  Refund date: {license_data['refund_date']}")
    print(f"  Refund reason: {license_data['refund_reason']}")
    
    if license_data['is_active']:
        print(f"  ✗ License should be deactivated!")
        return False
    
    if license_data['refund_date'] is None:
        print(f"  ✗ Refund date should be set!")
        return False
    
    if license_data['refund_reason'] != 'customer_request':
        print(f"  ✗ Refund reason mismatch!")
        return False
    
    print(f"  ✓ License is deactivated")
    
    # 5. Try to validate refunded license (should fail)
    print(f"\n✅ Step 5: Try validating refunded license (should fail)")
    validation = manager.validate_license(
        email='refund_test@example.com',
        license_key=license_key,
        hardware_id='test_hardware_id_123'
    )
    
    if validation['success']:
        print(f"  ✗ Validation should fail for inactive license!")
        return False
    
    if validation['error'] != 'license_deactivated':
        print(f"  ✗ Error should be 'license_deactivated', got: {validation['error']}")
        return False
    
    print(f"  ✓ Validation fails with correct error: {validation['error']}")
    
    # 6. Check refund status
    print(f"\n✅ Step 6: Check refund status")
    refund_status = manager.get_refund_status(license_key)
    
    if not refund_status['success']:
        print(f"  ✗ Failed to get refund status: {refund_status}")
        return False
    
    print(f"  License key: {refund_status['license_key']}")
    print(f"  Is active: {refund_status['is_active']}")
    print(f"  Is refunded: {refund_status['is_refunded']}")
    print(f"  Refund date: {refund_status['refund_date']}")
    print(f"  Refund reason: {refund_status['refund_reason']}")
    
    if not refund_status['is_refunded']:
        print(f"  ✗ Should be marked as refunded!")
        return False
    
    print(f"  ✓ Refund status correct")
    
    # 7. Check audit log
    print(f"\n✅ Step 7: Check refund in audit log")
    purchases_file = manager.purchases_file
    
    refund_logged = False
    with open(purchases_file, 'r') as f:
        for line in f:
            record = json.loads(line)
            if record.get('license_key') == license_key and record.get('event') == 'refund':
                print(f"  Found refund record:")
                print(f"    Timestamp: {record.get('timestamp')}")
                print(f"    License key: {record.get('license_key')}")
                print(f"    Reason: {record.get('refund_reason')}")
                refund_logged = True
                break
    
    if not refund_logged:
        print(f"  ✗ Refund not logged to audit trail!")
        return False
    
    print(f"  ✓ Refund logged to audit trail")
    
    # 8. Get complete license info
    print(f"\n✅ Step 8: Get complete license info")
    license_info = manager.get_license_info(license_key)
    
    if not license_info['success']:
        print(f"  ✗ Failed to get license info: {license_info}")
        return False
    
    print(f"  License info retrieved:")
    print(f"    Email: {license_info['license']['email']}")
    print(f"    Is active: {license_info['license']['is_active']}")
    print(f"    Refund reason: {license_info['license']['refund_reason']}")
    
    if license_info['purchase']:
        print(f"    Purchase product: {license_info['purchase'].get('product_name')}")
    
    print(f"  ✓ License info complete")
    
    print(f"\n" + "=" * 70)
    print(f"✅ ALL TESTS PASSED!")
    print(f"=" * 70)
    print(f"\n📊 Summary:")
    print(f"  ✓ Licenses can be marked as refunded")
    print(f"  ✓ Refunded licenses are deactivated")
    print(f"  ✓ Refund info is logged to audit trail")
    print(f"  ✓ Validation fails for refunded licenses")
    print(f"  ✓ Refund status can be queried")
    print(f"  ✓ Complete license info is retrievable")
    print(f"\n💡 Refund workflow verified:")
    print(f"  1. Customer refunded on Gumroad")
    print(f"  2. Gumroad sends refund webhook")
    print(f"  3. Our license is deactivated")
    print(f"  4. App validation fails on next check")
    
    return True

if __name__ == '__main__':
    success = test_refund_policy()
    sys.exit(0 if success else 1)
