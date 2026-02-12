# Risk Assessment Report: Remote Update Architecture
**Auditor:** AntiGravity Senior Architect
**Date:** Feb 11, 2026
**Scope:** Microsoft Store (Windows) & Apple App Store (iOS/macOS) Compliance

## Executive Summary
**🚨 CRITICAL FAIL**: The current architecture contains a defined "Remote Code Execution" mechanism that will result in **immediate rejection** from both the Microsoft Store and Apple App Store. The "Estimator" update system downloads and executes executable Python code, which is strictly prohibited.

## 1. Code Injection Risk (CRITICAL)

### Violation
**Apple Guideline 2.5.2**: "Apps may not... download, install, or execute code."
**Microsoft Policy 10.2.5**: "Product must not attempt to change or extend its described functionality through any form of dynamic inclusion of code."

### Findings
The application implements a mechanism to download Python source files (`.py`) from a remote server and dynamically import them into the runtime.

1.  **Arbitrary File Write (Executable Code)**
    *   **File**: `client/core/update_client.py`
    *   **Lines**: 260-261
    *   **Code**: `target_file.write_text(content, ...)` writes downloaded content to a `.py` file.
    *   **Risk**: The server dictates the content of executable files on the user's machine.

2.  **Dynamic Execution**
    *   **File**: `client/core/target_size/size_estimator_registry.py`
    *   **Lines**: 155, 121
    *   **Code**: `importlib.import_module(module_name)`
    *   **Mechanism**: The registry automatically scans for the "highest version" file and imports it. An attacker (or compromised server) can push `v999` with malicious code, and the client will automatically execute it upon the next conversion.

### Recommendation
*   **IMMEDIATE**: Remove the "Estimator Update" feature entirely.
*   **REMEDIATION**: Estimators must be interpreted data (e.g., JSON coefficients for a formula), not executable code. If the logic is complex, it must be shipped with the app binary updates, not side-loaded.

---

## 2. IAP Bypass & Receipt Validation (HIGH)

### Violation
**Microsoft Policy 10.13.1**: "You must use the Microsoft Store in-app purchase API."
**Apple Guideline 3.1.1**: "Apps may not use their own mechanisms to unlock content... such as license keys."

### Findings
1.  **No Client-Side Validation**
    *   **File**: `client/core/conductors/update_conductor.py`, `client/core/update_client.py`
    *   **Logic**: The app relies entirely on a `license_key` string sent to the server. If the server returns a download, the client accepts it.
    *   **Risk**: A modified `manifest.json` (via MITM or local file modification) can instruct the client to download "Premium" presets without payment. There is no check against `StoreKit` (Apple) or `Windows.Services.Store` (Microsoft) to verify the user actually owns the entitlement.

### Recommendation
*   **Implement Native Receipt Validation**: The app must ask the OS "Does this user own Product X?" before enabling the feature.
*   **Deprecate License Keys**: Store apps should use the store's identity system, not legacy license keys, unless fulfilling a cross-platform entitlement (which requires specific approval).

---

## 3. Data Safety & Path Traversal (MEDIUM)

### Violation
**General Security Best Practices** (Microsoft Policy 10.2.1)

### Findings
1.  **Path Traversal Vulnerability**
    *   **File**: `client/core/update_client.py`
    *   **Lines**: 260, 234
    *   **Code**: `target_file = target_dir / f"{estimator_id}.py"`
    *   **Risk**: `estimator_id` comes directly from the server manifest. A malicious ID like `../../../../startup_script` could overwrite system files. There is no sanitization of the ID.

2.  **Manifest Parsing**
    *   **File**: `client/core/update_client.py`
    *   **Lines**: 288, 307
    *   **Risk**: Direct dictionary access (`preset['id']`) will cause worker thread crashes if fields are missing. While better than a main-thread crash, it leads to undefined behavior.

### Recommendation
*   **Sanitize Inputs**: Ensure `estimator_id` contains only alphanumeric characters before using it in a file path.
*   **Schema Validation**: Use a library like `pydantic` or `jsonschema` to validate the `manifest.json` structure before processing.

---

## Summary of Actions

| Severity | Issue | Remediation |
|:---|:---|:---|
| 🔴 **CRITICAL** | **Remote Code Execution** | **Remove** dynamic `.py` loading. Convert estimators to data-driven logic (JSON). |
| 🟠 **HIGH** | **IAP Bypass** | Implement `Windows.Services.Store` receipt checks for premium features. |
| 🟡 **MEDIUM** | **Path Traversal** | Sanitize all filenames derived from server data. |

**Audit Status**: ❌ **PASS/FAIL**: **FAIL**
Your application **WILL BE REJECTED** in its current state.
