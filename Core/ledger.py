import sqlite3
import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

class AlertLedger:
    def __init__(self, db_path="Logs/trading_ledger.db"):
        # Ensure directory exists for local or AWS environment
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.tz = ZoneInfo("America/New_York")
        
        # Thread lock for critical write operations
        self._lock = threading.Lock()

        # Dedicated Ledger Logger
        self.db_logger = logging.getLogger("Ledger")
        if not self.db_logger.handlers:
            handler = logging.FileHandler("Logs/database_errors.log")
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.db_logger.addHandler(handler)


        self._bootstrap()

    def _get_connection(self):
        """Returns a connection with timeout and WAL mode for concurrency."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _bootstrap(self):
        """Initializes the database schema if it doesn't exist."""
        with self._get_connection() as conn:
            # Table 1: Current Live State
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    pair TEXT PRIMARY KEY,
                    signal TEXT,
                    trend TEXT,
                    timestamp TEXT,
                    sent INTEGER DEFAULT 0
                )
            """)
            
            # Table 2: Signal History (For Monthly tracking)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT,
                    signal TEXT,
                    trend TEXT,
                    activated_at TEXT,
                    deactivated_at TEXT
                )
            """)
    
    def _execute_query(self, query, params=()):
        """
        Centralized helper for all WRITE operations.
        Handles locking, committing, and error logging.
        """
        with self._lock:
            try:
                # Using the connection as a context manager handles AUTO-COMMIT
                with self._get_connection() as conn:
                    conn.execute(query, params)
            except sqlite3.Error as e:
                self.db_logger.error(f"SQL Error: {e} | Query: {query} | Params: {params}")
                print(f"🛑 [DATABASE ERROR] {e}")

    def clear_active_alerts(self):
        """Clears current active alerts (called at the start of a 15m Sync)."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM alerts")
                print("✅ [Ledger] Active alerts cleared for new Sync.")

    def clear_monthly_data(self):
        """Wipes active alerts and history for a fresh month."""
        # Standard deletions (these run perfectly through the helper)
        self._execute_query("DELETE FROM alerts")
        self._execute_query("DELETE FROM signal_history")
        self._execute_query("DELETE FROM sqlite_sequence WHERE name='signal_history'")
        
        # VACUUM requires its own special connection without a transaction block
        with self._lock:
            try:
                conn = self._get_connection()
                # Setting isolation_level to None disables the automatic transaction
                conn.isolation_level = None 
                conn.execute("VACUUM")
                conn.close()
            except sqlite3.Error as e:
                self.db_logger.error(f"SQL Error during VACUUM: {e}")
                print(f"🛑 [DATABASE ERROR] {e}")

        print("🚀 [Ledger] Monthly Reset Complete.")


    def update_status(self, pair, signal, trend, override_time=None):
        """Adds or updates an active signal with New York time or historical time."""
        # Use the provided historical time if it exists, otherwise use current NY time
        now_str = override_time if override_time else datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
            INSERT INTO alerts (pair, signal, trend, timestamp, sent)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(pair) DO UPDATE SET
                sent = CASE WHEN excluded.signal != alerts.signal THEN 0 ELSE alerts.sent END,
                signal = excluded.signal,
                trend = excluded.trend,
                timestamp = excluded.timestamp
        """
        self._execute_query(query, (pair, str(signal), trend, now_str))

    def deactivate_signal(self, pair, override_time=None):
        """Archives an active signal into history and removes it from live alerts."""
        now_str = override_time if override_time else datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')
        
        # READS don't need the lock
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT signal, trend, timestamp FROM alerts WHERE pair = ?", (pair,))
            row = cursor.fetchone()
        
        if row:
            # 1. Archive to history
            insert_query = """
                INSERT INTO signal_history (pair, signal, trend, activated_at, deactivated_at)
                VALUES (?, ?, ?, ?, ?)
            """
            self._execute_query(insert_query, (pair, row[0], row[1], row[2], now_str))
            
            # 2. Delete from active
            self._execute_query("DELETE FROM alerts WHERE pair = ?", (pair,))


    def get_ledger_with_history(self):
        """Generates the bundled Telegram message with clean, multi-line formatting."""
        with self._get_connection() as conn:
            active_rows = conn.execute(
                "SELECT pair, signal, trend, timestamp FROM alerts ORDER BY timestamp DESC"
            ).fetchall()

            history_rows = conn.execute(
                "SELECT pair, signal, trend, deactivated_at FROM signal_history "
                "ORDER BY deactivated_at DESC LIMIT 10"
            ).fetchall()

        msg = "📊 *Quantitative Ledger Update*\n\n"

        # --- ACTIVE SECTION ---
        msg += "🟢 *ACTIVE SIGNALS*\n\n"
        if not active_rows:
            msg += "_No active signals._\n\n"
        else:
            for row in active_rows:
                pair = row[0]
                
                # Clean up "SignalState.SHORT" -> "SHORT"
                signal_clean = str(row[1]).replace("SignalState.", "")
                
                # Map Trend to UP/DOWN
                trend_raw = str(row[2])
                if trend_raw == "BUY":
                    direction = " STOCH UP 📈"
                elif trend_raw == "SHORT":
                    direction = "STOCH DOWN 📉"
                else:
                    direction = trend_raw

                # Format Time
                time_val = row[3].split(" ")[1][:5] if row[3] else "??"

                # Build the multi-line card
                msg += f"🔹 *{pair}*\n"
                msg += f"  ├ Monthly Direction: {direction}\n"
                msg += f"  ├ Signal: {signal_clean}\n"
                msg += f"  └ Time: {time_val}\n\n"

        msg += "─" * 20 + "\n\n"

        # # --- HISTORY SECTION ---
        # msg += "⚪️ * CLOSED SIGNALS (Last 10)*\n\n"
        # if not history_rows:
        #     msg += "_No history recorded yet._\n"
        # else:
        #     for row in history_rows:
            
        #         pair = row[0]
        #         signal_clean = str(row[1]).replace("SignalState.", "")
        #         time_val = row[3].split(" ")[1][:5] if row[3] else "??"
                
        #         msg += f"🔸 *{pair}*\n"
        #         msg += f"  ├ Signal: {signal_clean}\n"
        #         msg += f"  └ Ended at: {time_val}\n\n"

        return msg
    

    def has_updates(self):
        """Returns True if any active signal has not been alerted yet."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM alerts WHERE sent = 0")
            count = cursor.fetchone()[0]
            return count > 0

    def mark_all_as_sent(self):
        """Call this after sending the Telegram alert."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("UPDATE alerts SET sent = 1")