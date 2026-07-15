import pytest
from strategies.stoch_bollinger import Stoch_Bolinger, SignalState

def test_strategy_sync_logic_identifies_short(dummy_candle_data, mock_dependencies):
    """Tests the ping-pong state logic for identifying a SHORT signal."""
    api_client, notifier, ledger = mock_dependencies
    
    # Configure the mock to return our dummy DataFrame when fetch_candles is called
    api_client.get_candles.return_value = dummy_candle_data
    
    strategy = Stoch_Bolinger("EUR_USD", api_client, notifier, ledger)
    
    # Force the cached trends so the execution logic evaluates them[cite: 11]
    strategy.cached_monthly_trend = "SHORT"
    strategy.cached_weekly_trend = "SHORT"
    
    # Run the initial sync to parse the last 150 candles[cite: 11]
    strategy._Sync()
    
    # Since the mock data goes up sequentially, the last hit band should be UPPER[cite: 11]
    assert strategy.last_touched_band == "UPPER"
    assert strategy.last_signal == SignalState.SHORT