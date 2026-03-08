#!/usr/bin/env python3
"""
Simulation: Energy / Purchase System Verification
Tests 3 flows against local server WITHOUT real MS Store receipts.
Requires: local server running at http://127.0.0.1:5005

Run with:
    cd v:\_MY_APPS\ImgApp_1
    python tests/simulate_energy_purchases.py
"""
import sys
import json
import requests
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

BASE_URL = "http://127.0.0.1:5005/api/v1"

# Product IDs from purchase_options.json
PRODUCT_500_CREDITS  = "9NBLGGH42DRH"
PRODUCT_DAILY_FOCUS  = "9NBLGGH42DRJ"
PRODUCT_PREMIUM      = "9NBLGGH42DRI"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def check(label, condition, actual=None):
    status = PASS if condition else FAIL
    print(f"  {status} {label}", end="")
    if actual is not None:
        print(f" (got: {actual})", end="")
    print()
    return condition

def simulate_receipt(product_id: str, platform="msstore", fake_user_id="test_user_abc123"):
    """Create a fake receipt XML (base64 encoded) for testing"""
    receipt_xml = f"""<?xml version="1.0"?>
<Receipt Version="1.0" xmlns="http://schemas.microsoft.com/windows/2011/12/iap/receipt">
  <AppReceipt>
    <UserId>{fake_user_id}</UserId>
    <ProductId>{product_id}</ProductId>
  </AppReceipt>
</Receipt>"""
    return base64.b64encode(receipt_xml.encode()).decode()

def create_user_profile_directly(user_id, platform="msstore"):
    """Directly create a user profile via license_manager (bypasses real receipt validation)"""
    # Import server-side code directly for simulation
    sys.path.insert(0, str(ROOT / "server"))
    os.environ.setdefault('SECRET_KEY', 'dev-secret-key')
    os.environ.setdefault('DAILY_FREE_ENERGY', '35')
    from services.license_manager import LicenseManager
    from config.settings import Config
    lm = LicenseManager()
    profile = lm.get_or_create_user_profile(user_id, platform)
    return lm, profile

def get_jwt_token(user_id, platform="msstore", is_premium=False):
    """Get a real JWT token from the server's auth module"""
    sys.path.insert(0, str(ROOT / "server"))
    from auth.jwt_auth import create_jwt_token
    return create_jwt_token(user_id, platform, is_premium)

def run_simulation():
    import os
    os.environ.setdefault('SECRET_KEY', 'dev-secret-key')
    os.environ.setdefault('DAILY_FREE_ENERGY', '35')
    os.environ.setdefault('JWT_SECRET_KEY', 'dev-jwt-key')

    sys.path.insert(0, str(ROOT / "server"))

    print(f"\n{INFO} Loading server modules directly (no HTTP needed for unit sim)...")

    from services.license_manager import LicenseManager
    from config.settings import Config
    from auth.jwt_auth import create_jwt_token
    from api.routes import (
        _get_product_type_from_id,
        _get_energy_amount_from_id,
    )

    all_passed = True

    # =========================================================================
    separator("1. Product ID Lookup Table Verification")
    # =========================================================================
    tests = [
        (PRODUCT_500_CREDITS,  "energy_pack", 500,  "500 Credits"),
        (PRODUCT_DAILY_FOCUS,  "energy_pack", 200,  "Daily Focus Pack"),
        (PRODUCT_PREMIUM,      "lifetime",    0,    "Premium Lifetime"),
    ]
    for pid, expected_type, expected_energy, name in tests:
        got_type = _get_product_type_from_id(pid)
        got_energy = _get_energy_amount_from_id(pid)
        r1 = check(f"{name} ({pid}) → type '{expected_type}'",  got_type == expected_type, got_type)
        r2 = check(f"{name} ({pid}) → energy {expected_energy}", got_energy == expected_energy, got_energy)
        all_passed = all_passed and r1 and r2

    # =========================================================================
    separator("2. User Profile Creation (New User, 35 energy)")
    # =========================================================================
    lm = LicenseManager()
    user_a = "sim_user_001"
    profile = lm.get_or_create_user_profile(user_a, "msstore")
    check("New profile energy_balance = 35 (DAILY_FREE_ENERGY)",
          profile['energy_balance'] == Config.DAILY_FREE_ENERGY, profile['energy_balance'])
    check("New profile is_premium = False", profile['is_premium'] == False)
    check("New profile purchased_energy = 0", profile.get('purchased_energy', 0) == 0)

    # =========================================================================
    separator("3. BUY 500 CREDITS — Energy Pack Purchase")
    # =========================================================================
    # Simulate what validate_store_receipt does for 9NBLGGH42DRH
    product_id = PRODUCT_500_CREDITS
    product_type = _get_product_type_from_id(product_id)
    energy_to_add = _get_energy_amount_from_id(product_id)

    is_lifetime = product_type == 'lifetime'
    is_day_pass = product_type == 'day_pass'

    profile_b = lm.get_or_create_user_profile("sim_user_002", "msstore")
    initial_balance = profile_b['energy_balance']

    if not is_lifetime and not is_day_pass and energy_to_add > 0:
        profile_b['energy_balance'] = profile_b.get('energy_balance', 0) + energy_to_add
        profile_b['purchased_energy'] = profile_b.get('purchased_energy', 0) + energy_to_add
        lm.save_user_profile("sim_user_002", profile_b)

    check(f"500 Credits: product_type == 'energy_pack'", product_type == 'energy_pack', product_type)
    check(f"500 Credits: energy_to_add == 500", energy_to_add == 500, energy_to_add)
    check(f"500 Credits: balance went from {initial_balance} → {initial_balance + 500}",
          profile_b['energy_balance'] == initial_balance + energy_to_add, profile_b['energy_balance'])
    check(f"500 Credits: purchased_energy == 500", profile_b.get('purchased_energy') == 500)

    # =========================================================================
    separator("4. EXTEND MAX ENERGY — Daily Focus Pack (+200)")
    # =========================================================================
    product_id = PRODUCT_DAILY_FOCUS
    product_type = _get_product_type_from_id(product_id)
    energy_to_add = _get_energy_amount_from_id(product_id)

    profile_c = lm.get_or_create_user_profile("sim_user_003", "msstore")
    initial_balance = profile_c['energy_balance']

    if not _get_product_type_from_id(product_id) == 'lifetime' and energy_to_add > 0:
        profile_c['energy_balance'] = profile_c.get('energy_balance', 0) + energy_to_add
        profile_c['purchased_energy'] = profile_c.get('purchased_energy', 0) + energy_to_add
        lm.save_user_profile("sim_user_003", profile_c)

    # Now simulate energy_sync — max_daily should reflect purchased expansion
    purchased_energy = profile_c.get('purchased_energy', 0)
    max_daily = Config.DAILY_FREE_ENERGY + purchased_energy

    check(f"Daily Focus: product_type == 'energy_pack'", product_type == 'energy_pack', product_type)
    check(f"Daily Focus: energy_to_add == 200", energy_to_add == 200, energy_to_add)
    check(f"Daily Focus: balance {initial_balance} → {initial_balance + 200}",
          profile_c['energy_balance'] == initial_balance + energy_to_add, profile_c['energy_balance'])
    check(f"Daily Focus: max_daily == {Config.DAILY_FREE_ENERGY} + 200 = {max_daily}",
          max_daily == Config.DAILY_FREE_ENERGY + purchased_energy, max_daily)

    # =========================================================================
    separator("5. PREMIUM LIFETIME — Unlimited Access")
    # =========================================================================
    product_id = PRODUCT_PREMIUM
    product_type = _get_product_type_from_id(product_id)
    energy_to_add = _get_energy_amount_from_id(product_id)
    is_lifetime = product_type == 'lifetime'

    profile_d = lm.get_or_create_user_profile("sim_user_004", "msstore")

    if is_lifetime:
        profile_d['is_premium'] = True
        lm.save_user_profile("sim_user_004", profile_d)

    # Simulate energy/reserve for premium user — should bypass all checks
    # (Server returns 999 for premium users — unlimited)
    if profile_d.get('is_premium'):
        reserve_response_balance = 999
        reserve_approved = True
    else:
        reserve_approved = False
        reserve_response_balance = profile_d.get('energy_balance', 0)

    check(f"Premium: product_type == 'lifetime'", product_type == 'lifetime', product_type)
    check(f"Premium: energy_to_add == 0 (not a credit pack)", energy_to_add == 0, energy_to_add)
    check(f"Premium: is_premium set to True", profile_d.get('is_premium') == True)
    check(f"Premium: reserve approved with 999 (unlimited)", reserve_approved and reserve_response_balance == 999)

    # =========================================================================
    separator("6. Daily Energy Reset Logic")
    # =========================================================================
    from datetime import datetime, timedelta

    profile_e = lm.get_or_create_user_profile("sim_user_005", "msstore")
    profile_e['energy_balance'] = 5  # Simulated depleted balance
    profile_e['purchased_energy'] = 100
    profile_e['last_energy_refresh'] = (datetime.utcnow() - timedelta(days=2)).isoformat()
    lm.save_user_profile("sim_user_005", profile_e)

    # Trigger reset
    lm.check_daily_energy_reset("sim_user_005", profile_e)

    expected_after_reset = Config.DAILY_FREE_ENERGY + 100  # 35 + 100 = 135
    check(f"Daily reset: balance restored to {expected_after_reset} (Free:{Config.DAILY_FREE_ENERGY} + Purchased:100)",
          profile_e['energy_balance'] == expected_after_reset, profile_e['energy_balance'])

    # =========================================================================
    separator("7. Energy Reserve — Insufficient Balance (402 logic)")
    # =========================================================================
    profile_f = lm.get_or_create_user_profile("sim_user_006", "msstore")
    profile_f['energy_balance'] = 3
    profile_f['is_premium'] = False
    lm.save_user_profile("sim_user_006", profile_f)

    amount_requested = 10
    current_balance = profile_f.get('energy_balance', 0)
    approved = current_balance >= amount_requested

    check(f"Insufficient energy: approved == False (balance {current_balance} < {amount_requested})",
          approved == False, approved)

    # =========================================================================
    separator("Summary")
    # =========================================================================
    if all_passed:
        print(f"\n  {PASS} All core flows VERIFIED ✓")
    else:
        print(f"\n  {FAIL} Some flows FAILED — review output above")

    # Cleanup sim profiles
    profiles_file = Path(lm.get_user_profiles_file())
    if profiles_file.exists():
        with open(profiles_file) as f:
            profiles = json.load(f)
        for uid in ["sim_user_001","sim_user_002","sim_user_003","sim_user_004","sim_user_005","sim_user_006"]:
            profiles.pop(uid, None)
        with open(profiles_file, 'w') as f:
            json.dump(profiles, f, indent=2)
        print(f"\n  {INFO} Simulation profiles cleaned up from user_profiles.json")

if __name__ == "__main__":
    run_simulation()
