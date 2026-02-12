import asyncio
import os
import shutil
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from client.core.update_client import UpdateClient, UpdateManifest, LocalManifest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyUpdates")

# Mock data
MOCK_SERVER_URL = "http://mock-server"
MOCK_LICENSE = "test_license"

MOCK_MANIFEST_RESPONSE = {
    "success": True,
    "manifest": {
        "presets": [
            {
                "id": "new_preset",
                "version": "2.0",
                "hash": "sha256:123456",
                "path": "video/new_preset.yaml"
            }
        ],
        # Estimators should be ignored even if present in response (simulating old server or attack)
        "estimators": [
            {
                "id": "malicious_estimator",
                "version": "9.9",
                "hash": "sha256:badbad",
                "type": "video"
            }
        ],
        "generated_at": "2026-02-11T12:00:00"
    }
}

MOCK_PRESET_CONTENT = """
meta:
  version: 2.0
  description: "A test preset"
test: true
"""

MOCK_ESTIMATOR_CONTENT = "import os; os.system('calc.exe')"

async def run_verification():
    print("🚀 Starting Update System Verification...")
    
    # Setup test environment
    base_dir = Path("temp_test_updates")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    presets_dir = base_dir / "presets"
    estimators_dir = base_dir / "estimators" # Should remain empty
    
    # Initialize client
    client = UpdateClient(MOCK_SERVER_URL, MOCK_LICENSE)
    client.params_dir = base_dir # redirect updates here
    client.presets_dir = presets_dir
    client.estimators_base = estimators_dir # Should not be used
    
    # Initialize local manifest
    manifest_path = base_dir / "manifest.json"
    client.local_manifest = LocalManifest(manifest_path)
    
    # Custom mock context manager class
    class MockRequestContext:
        def __init__(self, response):
            self.response = response
        
        async def __aenter__(self):
            return self.response
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Mock aiohttp session
    with patch('aiohttp.ClientSession') as MockSession:
        mock_session_instance = AsyncMock()
        # IMPORTANT: session.get is a SYNC method that returns an async context manager
        mock_session_instance.get = MagicMock() 
        MockSession.return_value.__aenter__.return_value = mock_session_instance
        
        # Setup specific responses for URLs
        def side_effect(url, headers=None):
            print(f"  Mocking URL: {url}")
            mock_response = AsyncMock()
            
            if "/manifest" in url:
                print("  ✓ Mocking Manifest Download")
                mock_response.status = 200
                mock_response.json.return_value = MOCK_MANIFEST_RESPONSE
            elif "preset" in url and "new_preset" in url:
                print("  ✓ Mocking Preset Download")
                mock_response.status = 200
                mock_response.text.return_value = MOCK_PRESET_CONTENT
            elif "estimator" in url or "download/estimator" in url:
                print("  ❌ ERROR: Client attempted to download estimator!")
                mock_response.status = 200
                mock_response.text.return_value = MOCK_ESTIMATOR_CONTENT
            else:
                print(f"  Unknown URL: {url}")
                mock_response.status = 404
            
            return MockRequestContext(mock_response)

        mock_session_instance.get.side_effect = side_effect

        
        # 1. Check for updates
        print("\nStep 1: Checking for updates...")
        manifest = await client.check_for_updates()
        
        if not manifest:
            print("❌ Failed to get manifest")
            return
            
        print("  ✓ Manifest received")
        
        # Verify Manifest object doesn't have estimators field (from our class change)
        if hasattr(manifest, 'estimators'):
            print("❌ Manifest class still has 'estimators' field")
        else:
            print("  ✓ Manifest class correctly cleaned of 'estimators'")
            
        # 2. Apply updates
        print("\nStep 2: Applying updates...")
        results = await client.apply_all_updates(manifest)
        
        # 3. Verification
        print("\nStep 3: Verifying results...")
        
        # Check preset
        expected_preset = presets_dir / "video" / "new_preset.yaml"
        if expected_preset.exists():
            print(f"  ✓ Presets Updated: new_preset.yaml found at {expected_preset}")
        else:
            print(f"  ❌ Preset not found at {expected_preset}")
            
        # Check return dict
        if 'estimators_updated' in results:
            print("  ❌ 'estimators_updated' found in results dict")
        else:
            print("  ✓ 'estimators_updated' correctly absent from results")
            
        # Check filesystem for estimators
        est_files = list(estimators_dir.glob("**/*.py"))
        if est_files:
            print(f"  ❌ SECURITY FAIL: Found estimator files: {est_files}")
        else:
            print("  ✓ SECURITY PASS: No estimator files downloaded")
            
        print("\n--- Summary ---")
        print(f"Presets Updated: {results.get('presets_updated')}")
        print(f"Errors: {results.get('errors')}")
        
    # Cleanup
    shutil.rmtree(base_dir)
    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(run_verification())
