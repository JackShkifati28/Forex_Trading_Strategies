import pytest
import threading
import os
from Core.ledger import AlertLedger

def test_ledger_thread_safety(tmp_path):
    """Simulates 50 threads writing to the SQLite database simultaneously."""
    # Use a temporary directory for the test database
    db_path = tmp_path / "test_trading_ledger.db"
    ledger = AlertLedger(db_path=str(db_path))
    
    errors = []
    
    def worker_thread(pair_name):
        try:
            # Attempt to acquire the lock and write[cite: 5]
            ledger.update_status(
                pair=pair_name, 
                signal="BUY", 
                montly_trend="BUY", 
                weekly_trend="SHORT"
            )
        except Exception as e:
            errors.append(e)

    # Spawn 50 concurrent threads
    threads = []
    for i in range(50):
        t = threading.Thread(target=worker_thread, args=(f"PAIR_{i}",))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # If the lock failed, SQLite would throw 'database is locked' errors
    assert len(errors) == 0, f"Concurrency errors detected: {errors}"
    assert ledger.has_updates() == True