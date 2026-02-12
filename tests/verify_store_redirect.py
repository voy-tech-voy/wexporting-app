import unittest
from unittest.mock import MagicMock, patch
from client.utils.update_checker import check_for_updates, UpdateState, UpdateCheckResult

# Mock data
MOCK_APP_CONFIG_RESPONSE = {
    "success": True,
    "latest_version": "7.5.0",
    "min_required_version": "7.0.0",
    "update_url": "ms-windows-store://pdp/?productid=9NBLGGH4NNS1",
    "release_notes": "New features!"
}

class TestStoreRedirect(unittest.TestCase):
    
    @patch('client.utils.update_checker.requests.get')
    @patch('client.version.get_version')
    def test_optional_update(self, mock_get_version, mock_get):
        """Test detection of optional update"""
        print("\nTesting Optional Update Scenario...")
        
        # Setup mocks
        mock_get_version.return_value = "7.4.0"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_APP_CONFIG_RESPONSE
        mock_get.return_value = mock_response
        
        # Run check
        result = check_for_updates()
        
        # Verify
        self.assertEqual(result.state, UpdateState.OPTIONAL_UPDATE)
        self.assertEqual(result.latest_version, "7.5.0")
        self.assertEqual(result.update_url, "ms-windows-store://pdp/?productid=9NBLGGH4NNS1")
        print("✓ Correctly identified optional update")

    @patch('client.utils.update_checker.requests.get')
    @patch('client.version.get_version')
    def test_mandatory_update(self, mock_get_version, mock_get):
        """Test detection of mandatory update"""
        print("\nTesting Mandatory Update Scenario...")
        
        # Setup mocks: Local version is OLDER than min_required
        mock_get_version.return_value = "6.9.0"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_APP_CONFIG_RESPONSE
        mock_get.return_value = mock_response
        
        # Run check
        result = check_for_updates()
        
        # Verify
        self.assertEqual(result.state, UpdateState.MANDATORY_UPDATE)
        self.assertEqual(result.min_required_version, "7.0.0")
        print("✓ Correctly identified mandatory update")

    @patch('client.utils.update_checker.requests.get')
    @patch('client.version.get_version')
    def test_up_to_date(self, mock_get_version, mock_get):
        """Test up-to-date scenario"""
        print("\nTesting Up-to-Date Scenario...")
        
        # Setup mocks: Local version matches latest
        mock_get_version.return_value = "7.5.0"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_APP_CONFIG_RESPONSE
        mock_get.return_value = mock_response
        
        # Run check
        result = check_for_updates()
        
        # Verify
        self.assertEqual(result.state, UpdateState.UP_TO_DATE)
        print("✓ Correctly identified up-to-date state")

if __name__ == '__main__':
    unittest.main()
