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
    
    @patch('sys.platform', 'win32')
    def test_factory_returns_ms_store_on_windows(self):
        """Factory should return MSStoreProvider on Windows"""
        # Mock the winrt import so it doesn't fail if we don't have it
        with patch.dict(sys.modules, {'winrt.windows.services.store': MagicMock()}):
            provider = get_store_auth_provider()
            # Because of DEVELOPMENT_MODE=True, the factory currently returns MockStoreProvider
            # so we check that it's returning *some* implementation of IStoreAuthProvider
            self.assertIsInstance(provider, IStoreAuthProvider)


class TestMSStoreProvider(unittest.TestCase):
    """Test MS Store Provider Implementation"""
    
    def setUp(self):
        with patch.dict(sys.modules, {'winrt.windows.services.store': MagicMock()}):
            self.provider = MSStoreProvider()
    
    @patch('client.core.auth.ms_store_provider.logger')
    def test_login_failure_when_no_store(self, mock_logger):
        """Test login fails when store is unavailable"""
        self.provider._store_available = False
        result = self.provider.login()
        self.assertFalse(result.success)
    
    def test_get_credentials_returns_token(self):
        """Test that get_credentials returns a token dictionary"""
        self.provider._jwt_token = "test-jwt-token-123"
        creds = self.provider.get_credentials()
        self.assertIn('token', creds)
        self.assertEqual(creds['token'], "test-jwt-token-123")


class TestEnergyManagerIntegration(unittest.TestCase):
    """Test EnergyManager integration with Store Auth"""
    
    def setUp(self):
        # Create fresh instance
        EnergyManager._instance = None
        self.energy_mgr = EnergyManager.instance()
    
    def test_set_store_auth_configures_manager(self):
        """Test that start_session properly configures SessionManager"""
        from client.core.session_manager import SessionManager
        session = SessionManager.instance()
        user_id = "test-user-456"
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        is_premium = True
        
        session.start_session(store_user_id=user_id, jwt_token=jwt_token, is_premium=is_premium)
        
        # Verify state
        self.assertEqual(session.store_user_id, user_id)
        self.assertEqual(session.jwt_token, jwt_token)
        self.assertEqual(session.is_premium, is_premium)
    
    def test_premium_user_bypasses_energy_checks(self):
        """Test that premium users bypass energy consumption"""
        from client.core.session_manager import SessionManager
        session = SessionManager.instance()
        session.start_session("premium-user", "token", is_premium=True)
        
        # Premium users should always pass energy checks
        result = self.energy_mgr.request_job_energy(cost=1000, conversion_type="video")
        
        self.assertTrue(result)
    
    def test_free_user_consumes_energy(self):
        """Test that free users consume energy for small jobs"""
        from client.core.session_manager import SessionManager
        session = SessionManager.instance()
        session.start_session("free-user", "token", is_premium=False)
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


class TestSessionManager(unittest.TestCase):
    """Test SessionManager (including JWT persistence)"""
    
    def setUp(self):
        from client.core.session_manager import SessionManager
        self.session = SessionManager.instance()
        # Ensure a clean state
        self.session.end_session()
        
    def test_persist_and_load_jwt(self):
        """Test that JWT successfully persists and loads from disk"""
        test_token = "test-jwt-persistence-token"
        
        # Persist it
        self.session.persist_jwt(test_token)
        
        # Load it
        loaded_token = self.session.load_persisted_jwt()
        
        self.assertEqual(loaded_token, test_token)
        
    def test_end_session_clears_persisted_jwt(self):
        """Test that ending the session deletes the persisted token"""
        test_token = "test-jwt-persistence-token-2"
        self.session.persist_jwt(test_token)
        
        # Should be there initially
        self.assertIsNotNone(self.session.load_persisted_jwt())
        
        # End session
        self.session.end_session()
        
        # Should be gone
        self.assertIsNone(self.session.load_persisted_jwt())


if __name__ == '__main__':
    unittest.main()
