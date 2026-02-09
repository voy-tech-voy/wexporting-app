"""
Test Azure AD Authentication

This script tests if the server can successfully authenticate with Azure AD
and obtain an access token for the Microsoft Store Collections API.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_azure_ad_auth():
    """Test Azure AD authentication with client credentials flow"""
    
    # Get credentials from environment
    tenant_id = os.environ.get('MSSTORE_TENANT_ID')
    client_id = os.environ.get('MSSTORE_CLIENT_ID')
    client_secret = os.environ.get('MSSTORE_CLIENT_SECRET')
    
    print("=" * 70)
    print("Azure AD Authentication Test")
    print("=" * 70)
    print(f"Tenant ID: {tenant_id}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {'*' * 20 if client_secret else 'NOT SET'}")
    print()
    
    if not all([tenant_id, client_id, client_secret]):
        print("❌ ERROR: Missing credentials in .env file")
        return False
    
    # Step 1: Get Azure AD access token
    print("Step 1: Requesting access token from Azure AD...")
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://onestore.microsoft.com/.default'
    }
    
    try:
        token_response = requests.post(token_url, data=token_data, timeout=10)
        token_response.raise_for_status()
        token_result = token_response.json()
        
        access_token = token_result.get('access_token')
        expires_in = token_result.get('expires_in')
        
        print(f"✅ SUCCESS: Obtained access token")
        print(f"   Token expires in: {expires_in} seconds ({expires_in // 3600} hours)")
        print(f"   Token preview: {access_token[:50]}...")
        print()
        
        # Step 2: Verify token structure
        print("Step 2: Verifying token structure...")
        import base64
        import json
        
        # Decode JWT (without verification, just for inspection)
        parts = access_token.split('.')
        if len(parts) == 3:
            # Decode payload (add padding if needed)
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded)
            
            print(f"✅ Token claims:")
            print(f"   Issuer: {claims.get('iss')}")
            print(f"   Audience: {claims.get('aud')}")
            print(f"   App ID: {claims.get('appid')}")
            print(f"   Tenant ID: {claims.get('tid')}")
            print()
        
        print("=" * 70)
        print("✅ AZURE AD AUTHENTICATION TEST PASSED")
        print("=" * 70)
        print()
        print("Your server can now validate MS Store receipts!")
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP ERROR: {e}")
        print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_azure_ad_auth()
    sys.exit(0 if success else 1)
