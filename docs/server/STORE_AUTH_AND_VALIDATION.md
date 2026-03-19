# MS Store & Server Architecture — Auth, Validation & Energy System

> **Reference document.** Describes the live system as of v1.0.3. Update this file whenever the auth or energy flow changes.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [MS Store Auth Provider (Client)](#2-ms-store-auth-provider-client)
3. [Session Manager](#3-session-manager)
4. [Server JWT Architecture](#4-server-jwt-architecture)
5. [API Endpoints Reference](#5-api-endpoints-reference)
6. [Energy System Architecture](#6-energy-system-architecture)
7. [Validation Flows](#7-validation-flows)
8. [Data Structures](#8-data-structures)
9. [Security Model & Trust Boundary](#9-security-model--trust-boundary)
10. [Dev Mode Differences](#10-dev-mode-differences)
11. [File Map](#11-file-map)

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  MS STORE (Source of Truth — Entitlements)                          │
│                                                                     │
│  ALL users →  add-on license check (is_premium)                     │
│  Premium   →  durable add-on product ID contains "lifetime"         │
│  Free      →  no add-ons in collection                              │
└─────────────────────┬───────────────────────────────────────────────┘
                      │  WinRT API (in-process, no network needed)
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CLIENT  (V:\_MY_APPS\ImgApp_1\client\)                             │
│                                                                     │
│  MSStoreProvider.login()                                            │
│    └─ StoreContext.get_app_license_async()  → checks entitlements   │
│    └─ get_user_collection_async(["Durable"]) → is_premium           │
│    └─ _get_stable_user_id()                 → store_user_id (SID)   │
│    └─ load_persisted_jwt()                  → JWT (if returning)    │
│                                                                     │
│  SessionManager  ── stores: store_user_id, jwt_token, is_premium    │
│  EnergyManager   ── stores: balance, max_daily, pending_server_init │
│  EnergyAPIClient ── HTTP to server (HMAC-verified responses)        │
└─────────────────────┬───────────────────────────────────────────────┘
                      │  HTTPS (requests library)
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SERVER  (https://wavyvoy.pythonanywhere.com)                       │
│                                                                     │
│  POST /store/register-free  → JWT for free users (first launch)     │
│  POST /store/validate-receipt → JWT after purchase                  │
│  POST /energy/sync     (JWT) → current server balance               │
│  POST /energy/reserve  (JWT) → deduct for large jobs                │
│  POST /energy/report   (JWT) → batch-report small-job usage         │
│  GET  /updates/manifest (JWT) → preset update manifest              │
│                                                                     │
│  LicenseManager  ── user_profiles.json  (server-side balance store) │
└─────────────────────────────────────────────────────────────────────┘
```

**Core principle:** The server is the sole authority on energy balance. `energy.dat` is a local cache only. The MS Store is the sole authority on entitlements. A JWT is the bridge — it carries the server's recognition of the user's identity and tier.

---

## 2. MS Store Auth Provider (Client)

### Provider hierarchy

```
IStoreAuthProvider  (abstract interface)
    └─ MSStoreProvider   — Windows production (sys.platform == "win32", frozen)
    └─ MockStoreProvider — Dev only (Config.DEVELOPMENT_MODE == True)
```

Factory: `client/core/auth/__init__.py → get_store_auth_provider()` (singleton)

In a frozen (packaged) build `Config.DEVELOPMENT_MODE` is always `False`, so `MockStoreProvider` is never used in production.

### `_get_stable_user_id()` — per-user identity

**Why not `sku_store_id`:** `StoreAppLicense.sku_store_id` is the product SKU identifier — the same value for every user. Using it as identity would merge all users into one server profile.

**What we use instead** — priority chain in `ms_store_provider._get_stable_user_id()`:

| Priority | Method | Stability |
|----------|--------|-----------|
| 1 | Windows user SID via `whoami /user /fo csv /nh`, SHA-256 hashed with app salt | Survives AppData deletion; unique per Windows account |
| 2 | UUID persisted in `%APPDATA%\wexporting\config\user_id.dat` | Survives reboots; lost if AppData deleted |
| 3 | Fresh `uuid.uuid4()` (not persisted — last resort) | Session only |

The SID is hashed as `sha256("wexporting_v1_{SID}")[:32]` and prefixed with `win_`. The raw SID is never stored or transmitted.

### `MSStoreProvider.login()` — step by step

| Step | Action | Notes |
|------|--------|-------|
| 1 | `StoreContext.get_default()` | Store context bound to running app |
| 2 | `get_app_license_async()` | `StoreAppLicense` object |
| 3 | `_get_stable_user_id()` | SID-based hash (see above) |
| 4 | `get_user_collection_async(["Durable"])` | Check add-on licenses for premium |
| 5 | Check `sku_store_id` of each add-on | `is_premium = True` if ID contains `"lifetime"` or `"premium"` |
| 6 | `SessionManager.start_session(store_user_id, "", is_premium)` | Session started |
| 7 | `load_persisted_jwt()` | Injects previously persisted JWT if present |
| 8 | Returns `AuthResult(success=True, ...)` | |

### `MSStoreProvider.request_purchase(product_id, window_handle)`

Purchase runs in a `_PurchaseWorker(QThread)` launched by `PurchaseDialog._on_purchase_requested()`. This keeps the Qt event loop alive during the blocking MS Store dialog.

```
PurchaseDialog._on_purchase_requested(product_id)
  └─ captures HWND on main thread
  └─ starts _PurchaseWorker(product_id, hwnd)
       └─ [background thread] provider.purchase_add_on(product_id, hwnd)
            └─ asyncio.run(_purchase_flow())
                 └─ StoreContext.request_purchase_async(product_id)
                 └─ On SUCCEEDED: validate_receipt(None, product_id)  ← real product_id
                 └─ For consumables: report_fulfillment(product_id, tx_id)
       └─ emits finished(bool)
  └─ _on_purchase_finished(success) updates UI on main thread
```

### Receipt validation (purchase path only)

`validate_receipt(receipt_data, product_id)` — `product_id` is now the actual purchased MS Store ID (e.g. `"9P4WCMTCH89V"`), not a hardcoded string.

```python
# Client sends:
{
    "receipt_data": base64(StoreContext.get_app_receipt_async()),
    "platform":     "msstore",
    "product_id":   "9P4WCMTCH89V"   # real MS Store product ID
}

# Server responds:
{
    "success":        true,
    "is_premium":     true,
    "energy_balance": 535,
    "jwt_token":      "eyJ..."
}
```

---

## 3. Session Manager

`client/core/session_manager.py` — singleton, holds in-memory session state.

### State fields

| Field | Type | Description |
|-------|------|-------------|
| `_store_user_id` | `str` | SID-based hash from `_get_stable_user_id()` |
| `_jwt_token` | `str` | Server-issued JWT (empty until register-free or purchase) |
| `_is_authenticated` | `bool` | True once `start_session()` called |
| `_premium_obf` | `int` | Premium flag XOR-obfuscated with random per-session key |

### Persistence

- `session.dat` — `%APPDATA%\wexporting\config\session.dat`
- Format: base64-encoded JWT string
- Written by `persist_jwt(token)` on first successful auth
- Read by `load_persisted_jwt()` inside `MSStoreProvider.login()` on every launch

---

## 4. Server JWT Architecture

`server/auth/jwt_auth.py`

### Token shape

```json
{
  "sub":        "win_a3f91c...",
  "platform":   "msstore",
  "is_premium": false,
  "iat":        1711000000,
  "exp":        1711086400
}
```

- Signed with **HS256** using `JWT_SECRET_KEY` (falls back to `SECRET_KEY` — both required env vars)
- Expiry: `JWT_EXPIRY_HOURS` env var, default **24 hours**
- `sub` is the `store_user_id` — used as the primary key in `user_profiles.json`

### Environment variables required on server

| Variable | Purpose | Fallback |
|----------|---------|---------|
| `SECRET_KEY` | HMAC signing base key | **None — crashes on startup if missing** |
| `JWT_SECRET_KEY` | JWT signing key | Falls back to `SECRET_KEY` |
| `ENERGY_HMAC_KEY` | Energy response signing | Falls back to `SECRET_KEY` |
| `MSSTORE_TENANT_ID` | Azure AD tenant | None |
| `MSSTORE_CLIENT_ID` | Azure AD client | None |
| `MSSTORE_CLIENT_SECRET` | Azure AD secret | None |

---

## 5. API Endpoints Reference

Base URL: `https://wavyvoy.pythonanywhere.com/api/v1`
Dev URL: `http://127.0.0.1:5005/api/v1`

---

### `POST /store/register-free`

**Auth:** None
**Purpose:** First-launch registration for free users.

```json
// Request
{ "store_user_id": "win_a3f91c...", "platform": "msstore" }

// Response 200
{ "success": true, "is_premium": false, "energy_balance": 35, "jwt_token": "eyJ..." }

// Response 400 — rejected ID
{ "success": false, "error": "invalid_store_id" }
```

**Server logic:**
1. Reject IDs in `{"dev-user", "unknown", "test", "null", "none"}`
2. Rate-limit by IP (10 requests / 10 min)
3. `get_or_create_user_profile(store_user_id, platform)` — atomic, thread-safe
4. `check_daily_energy_reset()` — refresh if new UTC day
5. `create_jwt_token(store_user_id, platform, is_premium)`
6. Return JWT + current balance

**Idempotency:** Safe to call on every first launch or after AppData deletion. Returns remaining balance, not a fresh 35.

---

### `POST /store/validate-receipt`

**Auth:** None
**Purpose:** Post-purchase receipt validation.

```json
// Request
{
    "receipt_data": "<base64 MS Store XML receipt>",
    "platform": "msstore",
    "product_id": "9P4WCMTCH89V"   // real MS Store product ID
}

// Dev mock (DEBUG server only — FLASK_DEBUG=true required):
{
    "receipt_data": "DEV_MOCK_TX_{product_id}_{timestamp}",
    "platform": "msstore",
    "product_id": "9P4WCMTCH89V",
    "is_dev_mock": true,
    "store_user_id": "DEV_MOCK_USER_001"
}
```

**Product ID → behavior mapping:**

| Product ID | Type | Server action |
|------------|------|---------------|
| `9P4WCMTCH89V` | `lifetime` | `is_premium = True` |
| `9PFHR7GMBT0T` | `energy_pack` | `energy_balance += 500` (consumable) |
| `9NNK6Q3WZN2M` | `limit_pack` | `purchased_energy += 200`, `energy_balance += 200` (durable) |

**Dev mock bypass:** Only active when `FLASK_DEBUG=true`. Completely disabled in production (`FLASK_DEBUG` defaults to `false`).

---

### `POST /energy/sync`

**Auth:** `Bearer JWT`

```json
// Response 200
{
  "success": true, "balance": 30, "max_daily": 235,
  "is_premium": false, "timestamp": "...", "signature": "<hmac-sha256>"
}
```

`max_daily = DAILY_FREE_ENERGY (35) + purchased_energy`

Client verifies the HMAC signature using `ENERGY_HMAC_SECRET` env var (must match server's `ENERGY_HMAC_KEY`).

---

### `POST /energy/reserve`

**Auth:** `Bearer JWT`

```json
// Request: { "amount": 15 }
// Response 200 — approved: { "success": true, "approved": true, "new_balance": 20, "signature": "..." }
// Response 402 — insufficient: { "approved": false, "error": "insufficient_energy" }
```

Premium users always receive `approved: true, new_balance: 999`.

**Dual-pool deduction:** Clamps `purchased_energy` if `new_balance` dips below it.

---

### `POST /energy/report`

**Auth:** `Bearer JWT`

Batch-reports accumulated local usage (small jobs ≤ 10 credits). Called every 60 s by timer.
Also clamps `purchased_energy` consistently with `/energy/reserve`.

---

### `GET /updates/manifest`

**Auth:** `Bearer JWT` *(changed from old license key auth)*

Returns the preset update manifest. Any authenticated store user (free or premium) can fetch updates.

---

## 6. Energy System Architecture

### Tiers

| Tier | Daily limit | Server sync | Local deduction | Large-job threshold |
|------|-------------|-------------|-----------------|---------------------|
| Free | 35 + `purchased_energy` | On launch + 60 s batch | Yes (≤ 10 credits) | > 10 → server reserve |
| Premium | Unlimited | On launch (status check) | No | No threshold |

### `pending_server_init` flag

Set to `True` in `EnergyManager.load()` when `energy.dat` does not exist.
Cleared when any server call succeeds: `register-free`, `/energy/sync`.

While `True`:
- `balance` is 0
- `ConversionConductor._check_energy_for_job/preset()` blocks export
- User must be online at first launch

---

## 7. Validation Flows

### 7.1 First Launch (online, no prior data)

```
Client                          MS Store WinRT              Server
  │                                   │                        │
  ├─ get_app_license_async() ────────►│                        │
  │◄──── license (entitlements) ──────┤                        │
  │                                   │                        │
  ├─ _get_stable_user_id()            │                        │
  │    → SHA256(SID) = "win_a3f91c..."│                        │
  │                                   │                        │
  ├─ load_persisted_jwt() → None      │                        │
  ├─ EnergyManager.load() → balance=0, pending_server_init=True│
  │                                   │                        │
  ├─ register_free_tier("win_a3f91c...", "msstore") ──────────►│
  │◄───────────── {jwt, balance=35, is_premium=false} ──────────┤
  │                                   │                        │
  ├─ session.set_jwt_token(jwt)        │                        │
  ├─ session.persist_jwt(jwt) → session.dat                    │
  ├─ energy_mgr.balance = 35, pending_server_init = False      │
  ├─ energy_mgr.save() → energy.dat   │                        │
  └─ Main window opens, balance = 35  │                        │
```

### 7.2 Subsequent Launches (returning user)

```
Client                          MS Store WinRT              Server
  │                                   │                        │
  ├─ get_app_license_async() ────────►│                        │
  │◄──── license (entitlements) ──────┤                        │
  ├─ _get_stable_user_id() → same "win_a3f91c..." (SID stable) │
  ├─ load_persisted_jwt() → JWT       │                        │
  ├─ EnergyManager.load() → balance=30 (from energy.dat)       │
  │                                   │                        │
  ├─ sync_with_server_jwt()           │                        │
  │    POST /energy/sync ─────────────────────────────────────►│
  │◄────────────── {balance=30, max_daily=35, sig} ────────────┤
  │    client verifies HMAC signature │                        │
  └─ Main window opens, balance = 30  │                        │
```

### 7.3 Purchase Flow

```
PurchaseDialog                  _PurchaseWorker (QThread)   MS Store / Server
  │                                   │                        │
  ├─ capture hwnd (main thread)       │                        │
  ├─ start worker ───────────────────►│                        │
  │  [UI stays responsive]            │                        │
  │                                   ├─ asyncio.run(purchase) │
  │                                   ├──── request_purchase_async(product_id) ─►│
  │                                   │◄─ SUCCEEDED + tx_id ───┤
  │                                   │                        │
  │                                   ├─ validate_receipt(None, product_id) ────►│
  │                                   │   {receipt_data, platform, product_id}   │
  │                                   │                    Azure AD validation   │
  │                                   │◄── {jwt, is_premium, energy_balance} ────┤
  │                                   │                        │
  │                                   ├─ session.start_session(...)              │
  │                                   ├─ session.persist_jwt(jwt)                │
  │◄─ finished(True) ─────────────────┤                        │
  ├─ sync_with_server_jwt()           │                        │
  └─ UI refreshes: new credits / premium badge                │
```

### 7.4 AppData Deletion (Exploit Prevention)

```
User deletes %APPDATA%\wexporting\config\

Client                                              Server
  │                                                    │
  ├─ get_app_license_async() → entitlements OK          │
  ├─ _get_stable_user_id() → same "win_a3f91c..." (SID)│
  ├─ load_persisted_jwt() → None (session.dat gone)    │
  ├─ energy.dat missing → balance=0, pending_server_init=True
  │                                                    │
  ├─ register_free_tier("win_a3f91c...") ─────────────►│
  │                                  look up existing  │
  │                                  profile by ID     │
  │◄──── {balance=5 (remaining), jwt} ─────────────────┤
  │                                                    │
  └─ balance=5 (not 35!) — exploit blocked             │
```

### 7.5 Offline First Launch

```
Client                                              Server
  │                                                    │
  ├─ get_app_license_async() → store_user_id           │
  ├─ _get_stable_user_id() → "win_a3f91c..."           │
  ├─ energy.dat missing → balance=0, pending=True      │
  │                                                    │
  ├─ register_free_tier() ──────── TIMEOUT ────────────┤
  │                                                    │
  ├─ If session.is_authenticated (store confirmed):    │
  │    energy_mgr.balance = 35 (offline grace)         │
  │    pending_server_init = False                     │
  │    → Exports allowed; reconciled on next launch    │
  │                                                    │
  └─ If not authenticated: balance stays 0, blocked   │
```

---

## 8. Data Structures

### JWT payload

```json
{
  "sub":        "win_a3f91c1234567890abcdef12345678",
  "platform":   "msstore",
  "is_premium": false,
  "iat":        1711000000,
  "exp":        1711086400
}
```

### Server user profile (`user_profiles.json`)

```json
{
  "win_a3f91c...": {
    "store_user_id":       "win_a3f91c...",
    "platform":            "msstore",
    "energy_balance":      30,
    "purchased_energy":    200,
    "is_premium":          false,
    "premium_expiry":      null,
    "last_energy_refresh": "2026-03-19T00:00:00",
    "created_at":          "2026-03-15T10:30:00.123456"
  }
}
```

`energy_balance` = free daily pool + purchased pool combined.
`purchased_energy` = permanent add-on portion (carries over daily reset; free pool resets to 35 each day).

Both `/energy/reserve` and `/energy/report` now clamp `purchased_energy` consistently when balance is deducted.

### `energy.dat` (AES-GCM encrypted)

```json
{ "balance": 30, "last_refresh": "2026-03-19", "max_daily_energy": 235 }
```

### HMAC signature (energy endpoints)

```python
payload   = f"{balance}:{timestamp}"
signature = hmac.new(ENERGY_HMAC_KEY.encode(), payload.encode(), sha256).hexdigest()
```

Client verifies using `ENERGY_HMAC_SECRET` env var → passed as `secret_key` to `EnergyAPIClient`.

---

## 9. Security Model & Trust Boundary

### What the server trusts

| Input | How trust is established |
|-------|--------------------------|
| `store_user_id` in `register-free` | IP rate-limited; blocklist of fake IDs; SID-based IDs are long opaque hashes |
| `Authorization: Bearer JWT` | HS256 signature verified with `JWT_SECRET_KEY`; expiry checked |
| MS Store receipt | Validated against Microsoft Collections API (Azure AD) |
| Dev mock receipts | `DEV_MOCK_TX_` prefix only accepted when `FLASK_DEBUG=true` — **never in production** |

### What the client trusts

| Input | How trust is established |
|-------|--------------------------|
| Server energy response | HMAC-SHA256 verified with `ENERGY_HMAC_SECRET` (matches server `ENERGY_HMAC_KEY`) |
| Persisted JWT | Loaded from disk, re-validated server-side on every API call |
| Premium status | Set from server's `is_premium` field on sync (overrides any local value) |

### What is NOT a security boundary (by design)

- `energy.dat` encryption — AES-GCM with static app key. Prevents casual tampering. Real security is server-side.
- `session.dat` base64 — obfuscation only. Token is validated server-side.
- `user_id.dat` — stores the hashed SID. Deleting it triggers UUID fallback (server profile still found by same SID on next launch).

### Attack: delete AppData to reset credits

**Blocked.** SID-based identity means `register-free` finds the existing profile and returns the remaining balance.

### Attack: forge dev mock receipt in production

**Blocked.** `DEV_MOCK_TX_` bypass gated behind `Config.DEBUG`. PythonAnywhere production server has `FLASK_DEBUG=false` (default).

### Attack: use sideloaded MSIX (no Store listing)

`get_app_license_async()` fails → `_get_stable_user_id()` still runs (based on Windows SID, no Store needed) → session starts with `IMGAPP_DEV_STORE_ID` env var or is left unauthenticated → `register-free` called → works normally if server reachable.

---

## 10. Dev Mode Differences

`Config.DEVELOPMENT_MODE = True` when running from source (`not frozen`). Never True in production.

| Behavior | Dev mode | Production |
|----------|----------|------------|
| Auth provider | `MockStoreProvider` | `MSStoreProvider` |
| `store_user_id` | `"DEV_MOCK_USER_{timestamp}"` | `win_` + SHA256(Windows SID)[:32] |
| Store APIs unavailable fallback | Start `"dev-user"` session | Use `IMGAPP_DEV_STORE_ID` env var or leave unauthenticated |
| Receipt data | `"DEV_MOCK_TX_{product_id}_{timestamp}"` | Base64-encoded MS Store XML |
| Server bypasses Azure validation | Yes (`FLASK_DEBUG=true` required on server) | No |
| `PREMIUM_OVERRIDE` in `local_config.py` | Overrides `is_premium` for testing | Never loaded |
| API base URL | `http://127.0.0.1:5005` | `https://wavyvoy.pythonanywhere.com` |
| Purchase UI blocking | `time.sleep(1.5)` in mock (UI freezes briefly) | Runs in `_PurchaseWorker` QThread (UI stays live) |
| HMAC verification | Skipped (no `ENERGY_HMAC_SECRET` set) | Active if `ENERGY_HMAC_SECRET` env var set |

### Sideloaded MSIX testing (pre-Store submission)

Set `IMGAPP_DEV_STORE_ID` as a user env var:
```cmd
setx IMGAPP_DEV_STORE_ID "my-test-id-001"
```
Relaunch from Start Menu. The app calls `register_free_tier("my-test-id-001", "msstore")`, gets a JWT, and grants 35 credits. The server rejects known fake names (`dev-user`, `test`, `null`, etc.) but accepts any other string.

---

## 11. File Map

```
client/
├── config/
│   ├── config.py                        API_BASE_URL, DEVELOPMENT_MODE, ENERGY_HMAC_SECRET
│   ├── credits_lab.json                 Lab mode credit costs per format/codec/operation
│   └── credits_presets.json             Preset mode credit costs per ID/category
│
├── core/
│   ├── auth/
│   │   ├── __init__.py                  get_store_auth_provider() singleton factory
│   │   ├── store_auth_provider.py       IStoreAuthProvider interface (incl. purchase_add_on)
│   │   └── ms_store_provider.py         MSStoreProvider + _get_stable_user_id() + MockStoreProvider
│   │
│   ├── session_manager.py               Singleton: store_user_id, jwt_token, is_premium
│   ├── energy_manager.py                Singleton: balance, max_daily, pending_server_init
│   ├── energy_api_client.py             HTTP client: sync, reserve, report, register_free_tier
│   │                                    HMAC verification active when secret_key is set
│   └── conductors/
│       └── conversion_conductor.py      Export guard: checks pending_server_init + balance
│
├── gui/
│   └── dialogs/
│       └── purchase_dialog.py           _PurchaseWorker (QThread) + PurchaseDialog
│
└── main.py                              Startup auth block: login → register-free → sync

server/
├── api/
│   ├── routes.py                        /store/register-free, /store/validate-receipt, /energy/*
│   │                                    Admin endpoints (fixed method name, hash, purchased_energy)
│   ├── updates.py                       /updates/manifest — now JWT-protected (not license key)
│   └── app_config.py                    /app-config — public, version gateway
│
├── auth/
│   └── jwt_auth.py                      create_jwt_token, verify_jwt_token, @require_jwt
│
├── services/
│   ├── license_manager.py               user_profiles.json — thread-safe (_profiles_lock, atomic writes)
│   │                                    is_trial_license / _deactivate_trial_for_email fixed to use trials.json
│   │                                    migrate_existing_licenses_platform — Platform.GUMROAD → DIRECT
│   ├── store_validation.py              MS Store ID lookup table added; Apple function fixed;
│   │                                    DEV_MOCK_TX_ bypass gated behind Config.DEBUG
│   └── rate_limiter.py                  IP-based rate limiting
│
├── config/
│   └── settings.py                      SECRET_KEY required (crashes if missing); ENERGY_HMAC_KEY added
│
└── data/
    ├── user_profiles.json               Live user balance store
    └── app_versions.json                Version gateway — updated to 1.0.3.0

%APPDATA%\wexporting\config\
├── energy.dat                           AES-GCM encrypted local balance cache
├── session.dat                          base64-encoded JWT (persisted across launches)
└── user_id.dat                          Persisted fallback user ID (UUID, used if SID lookup fails)
```
