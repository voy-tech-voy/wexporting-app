"""
Unit tests for Store Authentication System
Tests the abstraction layer and integration with EnergyManager
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add client to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from client.core.auth import get_store_auth_provider, IStoreAuthProvider
from client.core.auth.ms_store_provider import MSStoreProvider
from client.core.energy_manager import EnergyManager


class TestStoreAuthProvider(unittest.TestCase):
    """Test Store Authentication Provider Factory"""
    
    def test_factory_returns_ms_store_on_windows(self):
        """Factory should return MSStoreProvider on Windows"""
        with patch('sys.platform', 'win32'):
            provider = get_store_auth_provider()
            self.assertIsInstance(provider, MSStoreProvider)
    
    def test_factory_raises_on_unsupported_platform(self):
        """Factory should raise RuntimeError on unsupported platforms"""
        with patch('sys.platform', 'linux'):
            with self.assertRaises(RuntimeError):
                get_store_auth_provider()


class TestMSStoreProvider(unittest.TestCase):
    """Test MS Store Provider Implementation"""
    
    def setUp(self):
        self.provider = MSStoreProvider()
    
    @patch('client.core.auth.ms_store_provider.StoreContext')
    def test_login_success(self, mock_store_context):
        """Test successful login flow"""
        # Mock StoreContext
        mock_context = MagicMock()
        mock_user = MagicMock()
        mock_user.NonRoamableId = "test-user-123"
        mock_context.User = mock_user
        mock_store_context.GetDefault.return_value = mock_context
        
        # Attempt login
        result = self.provider.login()
        
        # Verify
        self.assertTrue(result)
        self.assertEqual(self.provider.get_store_user_id(), "test-user-123")
    
    def test_get_credentials_returns_token(self):
        """Test that get_credentials returns a token"""
        self.provider._user_id = "test-user-123"
        
        creds = self.provider.get_credentials()
        
        self.assertIn('token', creds)
        self.assertIsInstance(creds['token'], str)
        self.assertTrue(len(creds['token']) > 0)


class TestEnergyManagerIntegration(unittest.TestCase):
    """Test EnergyManager integration with Store Auth"""
    
    def setUp(self):
        # Create fresh instance
        EnergyManager._instance = None
        self.energy_mgr = EnergyManager.instance()
    
    def test_set_store_auth_configures_manager(self):
        """Test that set_store_auth properly configures EnergyManager"""
        user_id = "test-user-456"
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        is_premium = True
        
        self.energy_mgr.set_store_auth(user_id, jwt_token, is_premium)
        
        # Verify state
        self.assertEqual(self.energy_mgr.store_user_id, user_id)
        self.assertEqual(self.energy_mgr.jwt_token, jwt_token)
        self.assertEqual(self.energy_mgr.is_premium, is_premium)
    
    def test_premium_user_bypasses_energy_checks(self):
        """Test that premium users bypass energy consumption"""
        self.energy_mgr.set_store_auth("premium-user", "token", is_premium=True)
        
        # Premium users should always pass energy checks
        result = self.energy_mgr.request_job_energy(cost=1000, conversion_type="video")
        
        self.assertTrue(result)
    
    def test_free_user_consumes_energy(self):
        """Test that free users consume energy for small jobs"""
        self.energy_mgr.set_store_auth("free-user", "token", is_premium=False)
        self.energy_mgr.balance = 10
        
        # Small job (<=5) should consume locally
        result = self.energy_mgr.request_job_energy(cost=3, conversion_type="image")
        
        self.assertTrue(result)
        self.assertEqual(self.energy_mgr.balance, 7)


class TestEnergyAPIClient(unittest.TestCase):
    """Test Energy API Client JWT integration"""
    
    def setUp(self):
        from client.core.energy_api_client import EnergyAPIClient
        self.api_client = EnergyAPIClient("https://test-api.com")
    
    def test_set_jwt_token_updates_headers(self):
        """Test that set_jwt_token updates session headers"""
        token = "test-jwt-token"
        
        self.api_client.set_jwt_token(token)
        
        self.assertEqual(self.api_client.jwt_token, token)
        self.assertIn("Authorization", self.api_client.session.headers)
        self.assertEqual(
            self.api_client.session.headers["Authorization"],
            f"Bearer {token}"
        )
    
    def test_clear_jwt_token_removes_headers(self):
        """Test that clearing JWT token removes Authorization header"""
        self.api_client.set_jwt_token("test-token")
        self.api_client.set_jwt_token(None)
        
        self.assertIsNone(self.api_client.jwt_token)
        self.assertNotIn("Authorization", self.api_client.session.headers)


if __name__ == '__main__':
    unittest.main()
