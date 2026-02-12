# In-App Purchase (IAP) Test Plan

## 1. Prerequisites
- **Store Account**: A Microsoft Store developer account (for real purchases) or a test account.
- **App Packaged**: The app must be running as an MSIX package (even if sideloaded) to access `StoreContext`.

## 2. Test Scenarios

### Scenario A: Dual Pool Energy Logic (Server Side)
**Goal**: Verify that "Purchased" energy is NOT wiped by daily reset.

1.  **Preparation**:
    - Manually edit your user profile in `server/data/user_profiles.json`.
    - Set `energy_balance`: 150
    - Set `purchased_energy`: 100
    - Set `last_energy_refresh`: "2020-01-01" (Force reset).
2.  **Action**:
    - Restart server or trigger `check_daily_energy_reset`.
    - Login with the client.
3.  **Expected Result**:
    - `energy_balance` should be **150** (50 Free + 100 Purchased).
    - If it is 50, the Dual Pool logic FAILED.

### Scenario B: Spending Energy
**Goal**: Verify spending deducts from Free first.

1.  **State**: Free=50, Purchased=100. Total=150.
2.  **Action**: Run a job costing 40 energy.
3.  **Result**:
    - Total=110.
    - Purchased=100. (Touched Free only).
4.  **Action**: Run another job costing 20 energy.
    - (Remaining Free=10).
    - Cost=20.
5.  **Result**:
    - Total=90.
    - Purchased=90. (Used 10 Free + 10 Purchased).

### Scenario C: Day Pass Purchase
**Goal**: Verify Day Pass grants temporary premium.

1.  **Action**:
    - Use `StoreContext` simulator or live buy "Day Pass".
    - Client calls `validate-receipt`.
2.  **Expected Result**:
    - Server returns `is_premium: true`.
    - `jwt_token` has `is_premium: true`.
    - `user_profile` has `premium_expiry` set to tomorrow.
3.  **Verification**:
    - Check `server/data/user_profiles.json`.
    - Confirm `is_premium` is `false` (permanent flag).
    - Confirm `premium_expiry` is set.

## 3. Automated Verification Script
Run `tests/verify_iap_logic.py` (to be created) to test server logic without real money.

```python
# Create this script to mock the license_manager behavior (Example)
from server.services.license_manager import LicenseManager
from server.config.settings import Config

def test_dual_pool():
    profile = {
        'energy_balance': 150,
        'purchased_energy': 100,
        'last_energy_refresh': '2020-01-01'
    }
    lm = LicenseManager()
    lm.check_daily_energy_reset('test_user', profile)
    
    print(f"New Balance: {profile['energy_balance']}")
    # Should be 50 (Free) + 100 (Purchased) = 150
    if profile['energy_balance'] == 150:
         print("✓ Dual Pool Reset Logic Passed")
    else:
         print("❌ FAILED: Balance incorrect")

if __name__ == "__main__":
    test_dual_pool()
```
