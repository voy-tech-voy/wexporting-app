# Apple App Store Implementation Plan

## Current Status
- **Client**: `AppleStoreProvider` is a stub (raises `NotImplementedError`).
- **Server**: `_validate_appstore_receipt` is a stub.

## 1. Prerequisites
- **Apple Developer Account** ($99/year).
- **Mac Hardware**: Required for building/testing the client (StoreKit 2).
- **App Store Connect**: Create App and In-App Purchases.

## 2. Server Implementation (`store_validation.py`)
We need to verify receipts using the **App Store Server API**.

### Required Config
- `APPSTORE_KEY_ID`: From App Store Connect.
- `APPSTORE_ISSUER_ID`: From App Store Connect.
- `APPSTORE_PRIVATE_KEY`: .p8 file content.
- `APPSTORE_BUNDLE_ID`: e.g. `com.imgapp.client`

### Validation Logic
1.  Generate JWT for Apple API access.
2.  Call `GET /inApps/v1/history/{originalTransactionId}` (or verify JWS receipt).
3.  Parse the signed JWS transaction info.

**Note**: Apple moved away from the old `verifyReceipt` endpoint. Use the new **App Store Server API** (JWS based).

```python
def _validate_appstore_receipt(receipt_data, product_id):
    # 1. Create JWT for Apple API
    token = create_apple_jwt()
    
    # 2. Call Apple API
    url = f"https://api.storekit.itunes.apple.com/inApps/v1/transactions/{receipt_data}"
    # ...
```

## 3. Client Implementation (`apple_store_provider.py`)
**Challenge**: Python on macOS needs access to native StoreKit 2.
**Solution**: Use `pyobjc` framework to bridge to Swift/Objective-C StoreKit APIs.

```python
import StoreKit  # via pyobjc

async def request_purchase(product_id):
    # Bridge to native StoreKit 2
    products = await Product.products(for=[product_id])
    result = await products[0].purchase()
    # ...
```

### Alternative: Swift Wrapper
Write a small Swift shared library or helper executable that handles StoreKit, and have the Python client call it. This is often more stable than `pyobjc` for complex modern Swift APIs like StoreKit 2.

## 4. Next Steps
1.  Obtain Mac hardware/environment.
2.  Set up App Store Connect app.
3.  Implement Server API (can be done on Windows if you have the keys).
4.  Implement Client (requires Mac).
