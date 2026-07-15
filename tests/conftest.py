import pytest
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

@pytest.fixture
def dummy_candle_data():
    """Generates a standard 200-candle DataFrame simulating Oanda's output."""
    data = []
    base_time = datetime(2026, 7, 15, 12, 0)
    for i in range(200):
        data.append({
            'Date': (base_time + timedelta(hours=i)).isoformat() + "Z",
            'Open': 1.0900 + (i * 0.0001),
            'High': 1.0950 + (i * 0.0001),
            'Low': 1.0850 + (i * 0.0001),
            'Close': 1.0925 + (i * 0.0001),
            'Volume': 1000,
            'Complete': True
        })
    return pd.DataFrame(data)

@pytest.fixture
def mock_dependencies(mocker):
    """Mocks the API client, Notifier, and Ledger for isolated strategy testing."""
    api_client = mocker.MagicMock()
    notifier = mocker.MagicMock()
    ledger = mocker.MagicMock()
    return api_client, notifier, ledger