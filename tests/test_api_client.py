import pytest
import requests
from requests.exceptions import Timeout
from unittest.mock import patch
from Core.oanda_client import OandaClient

@patch("requests.Session.get")
def test_oanda_client_timeout_raises_connection_error(mock_get):
    """Tests that physical timeouts are caught and re-raised as ConnectionError."""
    # Simulate a hard network timeout[cite: 6]
    mock_get.side_effect = Timeout("DNS resolution failed")
    
    client = OandaClient("fake_token", "fake_account")
    
    # The client should convert the timeout to a ConnectionError[cite: 6]
    with pytest.raises(ConnectionError) as exc:
        client.getPairs()
        
    assert "Network error contacting Oanda" in str(exc.value)

@patch("requests.Session.get")
def test_oanda_client_handles_503_maintenance(mock_get):
    """Tests that a 503 Maintenance response raises an Exception for strategy backoff."""
    # Simulate a successful connection, but Oanda returns 503[cite: 6]
    mock_response = mock_get.return_value
    mock_response.status_code = 503
    mock_response.text = "Oanda is down for maintenance"
    
    client = OandaClient("fake_token", "fake_account")
    
    # Ensure the non-200 status code triggers an Exception[cite: 6]
    with pytest.raises(Exception) as exc:
        client.get_candles("EUR_USD")
        
    assert "HTTP 503" in str(exc.value)