# # import sqlite3
# # import os
# # import threading
# # from datetime import datetime
# # from zoneinfo import ZoneInfo
# # import logging

# # class AlertLedger:
# #     def __init__(self, db_path="Logs/trading_ledger.db"):
# #         # Ensure directory exists for local or AWS environment
# #         os.makedirs(os.path.dirname(db_path), exist_ok=True)
# #         self.db_path = db_path
# #         self.tz = ZoneInfo("America/New_York")
# #         self.lastLedger =[]
# #         self.removed_pairs = set()
        
# #         # Thread lock for critical write operations
# #         self._lock = threading.Lock()

# #         # Dedicated Ledger Logger
# #         self.db_logger = logging.getLogger("Ledger")
# #         if not self.db_logger.handlers:
# #             handler = logging.FileHandler("Logs/database_errors.log")
# #             formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# #             handler.setFormatter(formatter)
# #             self.db_logger.addHandler(handler)


# #         self._bootstrap()

# #     def _get_connection(self):
# #         """Returns a connection with timeout and WAL mode for concurrency."""
# #         conn = sqlite3.connect(self.db_path, timeout=30.0)
# #         conn.execute("PRAGMA journal_mode=WAL")
# #         return conn

# #     def _bootstrap(self):
# #         """Initializes the database schema if it doesn't exist."""
# #         with self._get_connection() as conn:
# #             # Table 1: Current Live State
# #             conn.execute("""
# #                 CREATE TABLE IF NOT EXISTS alerts (
# #                     pair TEXT PRIMARY KEY,
# #                     signal TEXT,
# #                     trend TEXT,
# #                     timestamp TEXT,
# #                     sent INTEGER DEFAULT 0
# #                 )
# #             """)
            
# #             # Table 2: Signal History (For Monthly tracking)
# #             conn.execute("""
# #                 CREATE TABLE IF NOT EXISTS signal_history (
# #                     id INTEGER PRIMARY KEY AUTOINCREMENT,
# #                     pair TEXT,
# #                     signal TEXT,
# #                     trend TEXT,
# #                     activated_at TEXT,
# #                     deactivated_at TEXT,
# #                     UNIQUE(pair, activated_at)
# #                 )
# #             """)
    
# #     def _execute_query(self, query, params=()):
# #         """
# #         Centralized helper for all WRITE operations.
# #         Handles locking, committing, and error logging.
# #         """
# #         with self._lock:
# #             try:
# #                 # Using the connection as a context manager handles AUTO-COMMIT
# #                 with self._get_connection() as conn:
# #                     conn.execute(query, params)
# #             except sqlite3.Error as e:
# #                 self.db_logger.error(f"SQL Error: {e} | Query: {query} | Params: {params}")
# #                 print(f"🛑 [DATABASE ERROR] {e}")

# #     def clear_active_alerts(self):
# #         """Clears current active alerts (called at the start of a 15m Sync)."""
# #         with self._lock:
# #             with self._get_connection() as conn:
# #                 conn.execute("DELETE FROM alerts")
# #                 print("✅ [Ledger] Active alerts cleared for new Sync.")

# #     def clear_monthly_data(self):
# #         """Wipes active alerts and history for a fresh month."""
# #         # Standard deletions (these run perfectly through the helper)
# #         self._execute_query("DELETE FROM alerts")
# #         self._execute_query("DELETE FROM signal_history")
# #         self._execute_query("DELETE FROM sqlite_sequence WHERE name='signal_history'")
        
# #         # VACUUM requires its own special connection without a transaction block
# #         with self._lock:
# #             try:
# #                 conn = self._get_connection()
# #                 # Setting isolation_level to None disables the automatic transaction
# #                 conn.isolation_level = None 
# #                 conn.execute("VACUUM")
# #                 conn.close()
# #             except sqlite3.Error as e:
# #                 self.db_logger.error(f"SQL Error during VACUUM: {e}")
# #                 print(f"🛑 [DATABASE ERROR] {e}")

# #         print("🚀 [Ledger] Monthly Reset Complete.")


# #     def update_status(self, pair, signal, trend ,override_time=None):
# #         """Adds or updates an active signal with New York time or historical time."""
# #         # Use the provided historical time if it exists, otherwise use current NY time
# #         now_str = override_time if override_time else datetime.now(self.tz).strftime('%m-%d-%Y %H:%M:%S')
        
# #         query = """
# #             INSERT INTO alerts (pair, signal, trend, timestamp, sent)
# #             VALUES (?, ?, ?, ?, 0)
# #             ON CONFLICT(pair) DO UPDATE SET
# #                 sent = CASE WHEN excluded.signal != alerts.signal THEN 0 ELSE alerts.sent END,
# #                 signal = excluded.signal,
# #                 trend = excluded.trend,
# #                 timestamp = excluded.timestamp
# #         """
# #         self._execute_query(query, (pair, str(signal), trend,now_str))
    
# #     # def _get_removed_pairs(self, current_pairs )->set:
      
# #     #         # 1. Convert your lastLedger to a set (if it's not already)
# #     #     last_ledger_set = set(self.lastLedger)
            
# #     #         # 2. Find pairs that were in the last ledger but are NOT in the current one
# #     #         # This is the "Set Difference" (A - B)
# #     #     removed_pairs = last_ledger_set - current_pairs

# #         # return   set(removed_pairs)
    
# #     def check_removed_signals(self):

# #         with self._get_connection() as conn:
# #             rows = conn.execute(
# #                 "SELECT pair FROM alerts ORDER BY pair ASC"
# #             ).fetchall()
        
# #         # 1. Extract the strings from the SQL tuples into a set
# #         current_pairs = {row[0] for row in rows}

# #         last_ledger_set = set(self.lastLedger)

# #         self.removed_pairs = last_ledger_set -current_pairs




# #     def deactivate_signal(self, pair, override_time=None):
# #         """Archives an active signal into history and removes it from live alerts."""
# #         now_str = override_time if override_time else datetime.now(self.tz).strftime('%m-%d-%Y %H:%M:%S')
        
# #         # READS don't need the lock
# #         with self._get_connection() as conn:
# #             cursor = conn.execute("SELECT signal, trend, timestamp FROM alerts WHERE pair = ?", (pair,))
# #             row = cursor.fetchone()
        
# #         if row:
# #             # 1. Archive to history
# #             insert_query = """
# #                 INSERT OR IGNORE INTO signal_history (pair, signal, trend, activated_at, deactivated_at)
# #                 VALUES (?, ?, ?, ?, ?)
# #             """
# #             self._execute_query(insert_query, (pair, row[0], row[1], row[2], now_str))
            
# #             # 2. Delete from active
# #             self._execute_query("DELETE FROM alerts WHERE pair = ?", (pair,))
        

# #     def get_ledger_with_history(self):
# #         """Generates the bundled Telegram message with clean, multi-line formatting."""

# #         with self._get_connection() as conn:
# #             active_rows = conn.execute(
# #                 "SELECT pair, signal, trend, timestamp , sent FROM alerts ORDER BY pair ASC"
# #             ).fetchall()

# #             # history_rows = conn.execute(
# #             #     "SELECT pair, signal, trend, deactivated_at FROM signal_history "
# #             #     "ORDER BY deactivated_at DESC LIMIT 10"
# #             # ).fetchall()
        

# #         ny = datetime.now(self.tz)

# #         currnt_date= f"Date: {ny.date():%m-%d-%Y} \n"
# #         currnt_time = f"Time: {ny.time():%H:%M:%S} \n\n"


# #         msg = "📊 *Quantitative Ledger Update*\n"

# #         msg +=  currnt_date

# #         msg +=  currnt_time

# #         # --- ACTIVE SECTION ---
# #         msg += "🟢 *ACTIVE SIGNALS*\n\n"
# #         if not active_rows:
# #             msg += "_No active signals._\n\n"
# #         else:
# #             for row in active_rows:
# #                 pair = row[0]
                
# #                 # Clean up "SignalState.SHORT" -> "SHORT"
# #                 signal_clean = str(row[1]).replace("SignalState.", "")
                
# #                 # Map Trend to UP/DOWN
# #                 trend_raw = str(row[2])
# #                 if trend_raw == "BUY":
# #                     direction = " STOCH UP 🟢"
# #                 elif trend_raw == "SHORT":
# #                     direction = "STOCH DOWN 🔴"
# #                 else:
# #                     direction = trend_raw

# #                 # Format Time
# #                 # time_val = row[3].split(" ")[1][:5] if row[3] else "??"
# #                 time_val = row[3]

# #                 # Sent Status
# #                 sent_status = row[4]
                 
# #                 # Build the multi-line card 

# #                 # New Pairs on the ledger is Orange Diamond and old is blue
# #                 if sent_status == 0:
# #                     msg += f"🔶 *{pair}* Newly Added! \n"
# #                 else:
# #                     msg += f"🔷 *{pair}*\n"
                
# #                 msg += f"  ├ Monthly: {direction}\n"
# #                 msg += f"  ├ Signal: {signal_clean}\n"
# #                 msg += f"  └ Ts: {time_val}\n\n"

# #         msg += "─" * 15 + "\n\n"

# #         # # --- HISTORY SECTION ---
# #         msg += "⚪️ * REMOVED FROM LAST LEDGER *\n\n"

# #         if not self.removed_pairs:
# #             msg +="No Signals Removed from last ledger"

# #         else:

# #             for rp in self.removed_pairs:
                
# #                 msg += f"❌ *{rp}*\n"
                

# #         # if not history_rows:
# #         #     msg += "_No history recorded yet._\n"
# #         # else:
# #         #     for row in history_rows:
            
# #         #         pair = row[0]
# #         #         signal_clean = str(row[1]).replace("SignalState.", "")
# #         #         time_val = row[3].split(" ")[1][:5] if row[3] else "??"
                
# #         #         msg += f" *{pair}*\n"
# #         #         msg += f"  ├ Signal: {signal_clean}\n"
# #         #         msg += f"  └ Ended at: {time_val}\n\n"
      
       
# #         # Extract just the pair names from your SQL results into a set
# #         current_pairs = {row[0] for row in active_rows}
# #         # Update the history for the next cycle
# #         self.lastLedger = list(current_pairs)
                
# #         return msg
    

# #     def has_updates(self):
# #         """Returns True if any active signal has not been alerted yet or if removed pair."""

# #         # Checks if new Singals
# #         with self._get_connection() as conn:
# #             cursor = conn.execute("SELECT COUNT(*) FROM alerts WHERE sent = 0")
# #             count = cursor.fetchone()[0]
        
# #         #checks if any signals from pervious ledger got removed
# #         self.check_removed_signals()

# #         return count > 0 or len(self.removed_pairs) > 0

# #     def mark_all_as_sent(self):
# #         """Call this after sending the Telegram alert."""
# #         with self._lock:
# #             with self._get_connection() as conn:
# #                 conn.execute("UPDATE alerts SET sent = 1")

# import sqlite3
# import os
# import threading
# from datetime import datetime
# from zoneinfo import ZoneInfo
# import logging


# class AlertLedger:
#     def __init__(self, db_path="Logs/trading_ledger.db"):
#         os.makedirs(os.path.dirname(db_path), exist_ok=True)
#         self.db_path = db_path
#         self.tz = ZoneInfo("America/New_York")

#         # FIX #9: Store as a set from the start — no more list<->set conversions
#         self._last_ledger: set = set()
#         self._removed_pairs: set = set()

#         # Single master lock for ALL shared state (DB writes + instance variables)
#         self._lock = threading.Lock()

#         # FIX #7: Explicitly set log level so it's never silently suppressed
#         self.db_logger = logging.getLogger("Ledger")
#         self.db_logger.setLevel(logging.ERROR)
#         if not self.db_logger.handlers:
#             handler = logging.FileHandler("Logs/database_errors.log")
#             formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#             handler.setFormatter(formatter)
#             self.db_logger.addHandler(handler)

#         # FIX #8: Use thread-local storage so each thread gets its own
#         # persistent connection — eliminates per-query connection churn
#         self._local = threading.local()

#         self._bootstrap()

#     # -------------------------------------------------------------------------
#     # CONNECTION MANAGEMENT
#     # -------------------------------------------------------------------------

#     def _get_connection(self) -> sqlite3.Connection:
#         """
#         Returns a persistent, thread-local connection.
#         Each thread gets exactly one connection that is reused across calls,
#         eliminating the overhead of creating a new connection on every query.
#         WAL mode is set once per connection.
#         """
#         if not hasattr(self._local, "conn") or self._local.conn is None:
#             conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
#             conn.execute("PRAGMA journal_mode=WAL")
#             conn.execute("PRAGMA foreign_keys=ON")
#             self._local.conn = conn
#         return self._local.conn

#     def _close_local_connection(self):
#         """Explicitly close the thread-local connection (call from thread cleanup)."""
#         if hasattr(self._local, "conn") and self._local.conn:
#             self._local.conn.close()
#             self._local.conn = None

#     # -------------------------------------------------------------------------
#     # CORE WRITE HELPER
#     # -------------------------------------------------------------------------

#     def _execute_write(self, query: str, params: tuple = (), raise_on_error: bool = False):
#         """
#         FIX #1 + #6: Single, canonical path for ALL write operations.
#         - Acquires the lock before every write (no more ad-hoc locking elsewhere)
#         - Raises on error when the caller needs to know about failures
#           instead of silently swallowing them
#         """
#         with self._lock:
#             try:
#                 conn = self._get_connection()
#                 conn.execute(query, params)
#                 conn.commit()
#             except sqlite3.Error as e:
#                 self.db_logger.error(f"SQL Error: {e} | Query: {query} | Params: {params}")
#                 print(f"🛑 [DATABASE ERROR] {e}")
#                 try:
#                     conn.rollback()
#                 except Exception:
#                     pass
#                 if raise_on_error:
#                     raise

#     def _execute_many_writes(self, operations: list[tuple]):
#         """
#         FIX #4: Executes multiple write operations atomically under one lock.
#         Each operation is a (query, params) tuple.
#         Prevents other threads from sneaking writes between related operations.
#         """
#         with self._lock:
#             conn = self._get_connection()
#             try:
#                 for query, params in operations:
#                     conn.execute(query, params)
#                 conn.commit()
#             except sqlite3.Error as e:
#                 self.db_logger.error(f"SQL Error in batch write: {e}")
#                 print(f"🛑 [DATABASE ERROR] {e}")
#                 try:
#                     conn.rollback()
#                 except Exception:
#                     pass
#                 raise

#     # -------------------------------------------------------------------------
#     # SCHEMA
#     # -------------------------------------------------------------------------

#     def _bootstrap(self):
#         """Initializes the database schema if it doesn't exist."""
#         self._execute_many_writes([
#             ("""
#                 CREATE TABLE IF NOT EXISTS alerts (
#                     pair TEXT PRIMARY KEY,
#                     signal TEXT,
#                     montly_trend TEXT,
#                     weekly_trend TEXT,
#                     timestamp TEXT,
#                     sent INTEGER DEFAULT 0
#                 )
#             """, ()),
#             ("""
#                 CREATE TABLE IF NOT EXISTS signal_history (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     pair TEXT,
#                     signal TEXT,
#                     montly_trend TEXT,
#                     weekly_trend  TEXT,
#                     activated_at TEXT,
#                     deactivated_at TEXT,
#                     UNIQUE(pair, activated_at)
#                 )
#             """, ()),
#         ])

#     # -------------------------------------------------------------------------
#     # WRITE OPERATIONS
#     # -------------------------------------------------------------------------

#     def clear_active_alerts(self):
#         """
#         FIX #1: Now routes through _execute_write instead of manually
#         managing its own lock + connection.
#         """
#         self._execute_write("DELETE FROM alerts", raise_on_error=True)
#         print("✅ [Ledger] Active alerts cleared for new Sync.")

#     def clear_monthly_data(self):
#         """
#         FIX #4: All three deletes happen atomically in one lock acquisition
#         so no thread can write between them.
#         VACUUM still needs its own special handling (cannot run inside a transaction).
#         """
#         self._execute_many_writes([
#             ("DELETE FROM alerts", ()),
#             ("DELETE FROM signal_history", ()),
#             ("DELETE FROM sqlite_sequence WHERE name='signal_history'", ()),
#         ])

#         # VACUUM cannot run inside a transaction — handled separately
#         with self._lock:
#             conn = self._get_connection()
#             try:
#                 conn.isolation_level = None   # Disable auto-transaction
#                 conn.execute("VACUUM")
#                 conn.isolation_level = ""     # Restore default
#             except sqlite3.Error as e:
#                 self.db_logger.error(f"SQL Error during VACUUM: {e}")
#                 print(f"🛑 [DATABASE ERROR] {e}")

#         print("🚀 [Ledger] Monthly Reset Complete.")

#     def update_status(self, pair: str, signal, montly_trend: str, weekly_trend: str, override_time: str = None):
#         """Adds or updates an active signal."""
#         now_str = override_time or datetime.now(self.tz).strftime('%m-%d-%Y %H:%M:%S')
#         query = """
#             INSERT INTO alerts (pair, signal, montly_trend, weekly_trend, timestamp, sent)
#             VALUES (?, ?, ?, ? ,?, 0)
#             ON CONFLICT(pair) DO UPDATE SET
#                 sent = CASE WHEN excluded.signal != alerts.signal THEN 0 ELSE alerts.sent END,
#                 signal = excluded.signal,
#                 montly_trend = excluded.montly_trend,
#                 weekly_trend = excluded.weekly_trend,
#                 timestamp = excluded.timestamp
#         """
#         self._execute_write(query, (pair, str(signal),montly_trend, weekly_trend, now_str), raise_on_error=True)

#     def deactivate_signal(self, pair: str, override_time: str = None):
#         """
#         FIX #3: The read and both writes now happen atomically under one lock,
#         eliminating the TOCTOU race between reading the row and deleting it.
#         """
#         now_str = override_time or datetime.now(self.tz).strftime('%m-%d-%Y %H:%M:%S')

#         with self._lock:
#             conn = self._get_connection()
#             try:
#                 row = conn.execute(
#                     "SELECT signal, montly_trend, weekly_trend, timestamp FROM alerts WHERE pair = ?", (pair,)
#                 ).fetchone()

#                 if row:
#                     conn.execute(
#                         """
#                         INSERT OR IGNORE INTO signal_history
#                             (pair, signal, montly_trend, weekly_trend, activated_at, deactivated_at)
#                         VALUES (?, ?, ?, ?, ?, ?)
#                         """,
#                         (pair, row[0], row[1], row[2], row[3],now_str)
#                     )
#                     conn.execute("DELETE FROM alerts WHERE pair = ?", (pair,))
#                     conn.commit()

#             except sqlite3.Error as e:
#                 self.db_logger.error(f"SQL Error in deactivate_signal: {e} | pair={pair}")
#                 print(f"🛑 [DATABASE ERROR] {e}")
#                 try:
#                     conn.rollback()
#                 except Exception:
#                     pass
#                 raise

#     def mark_all_as_sent(self):
#         """
#         FIX #1: Routes through _execute_write instead of managing its own lock.
#         """
#         self._execute_write("UPDATE alerts SET sent = 1", raise_on_error=True)

#     # -------------------------------------------------------------------------
#     # READ OPERATIONS
#     # -------------------------------------------------------------------------

#     def _fetch_active_rows(self) -> list:
#         conn = self._get_connection()
#         # FIX: Select the actual column names
#         return conn.execute(
#             "SELECT pair, signal, montly_trend, weekly_trend, timestamp, sent FROM alerts ORDER BY pair ASC"
#         ).fetchall()

#     def has_updates(self) -> bool:
#         """
#         FIX #2 + #5: Takes a single consistent snapshot under the lock.
#         Computes removed_pairs here and stores it so get_ledger_with_history()
#         uses the exact same snapshot — no staleness between the two calls.
#         """
#         with self._lock:
#             conn = self._get_connection()
#             unsent_count = conn.execute(
#                 "SELECT COUNT(*) FROM alerts WHERE sent = 0"
#             ).fetchone()[0]

#             current_pairs = {
#                 row[0] for row in conn.execute(
#                     "SELECT pair FROM alerts"
#                 ).fetchall()
#             }

#             # Compute and store removed_pairs atomically with the DB read
#             self._removed_pairs = self._last_ledger - current_pairs

#         return unsent_count > 0 or len(self._removed_pairs) > 0

#     def get_ledger_with_history(self) -> str:
#         """
#         FIX #2 + #5: Reads active rows and updates _last_ledger under the lock
#         so _last_ledger is always consistent with what was sent to Telegram.
#         Uses _removed_pairs computed by has_updates() — same snapshot, no drift.
#         """
#         with self._lock:
#             active_rows = self._fetch_active_rows()
#             # Update last ledger immediately after reading, still inside the lock
#             current_pairs = {row[0] for row in active_rows}
#             self._last_ledger = current_pairs

#         # Snapshot removed_pairs (already computed by has_updates)
#         removed_pairs = self._removed_pairs
#         n = len(current_pairs)

#         ny = datetime.now(self.tz)
#         msg = "📊 *Quantitative Ledger Update*\n"
#         msg += f"Date: {ny.date():%m-%d-%Y} \n"
#         msg += f"Time: {ny.time():%H:%M:%S} \n\n"

#         msg += f"🟢 *ACTIVE SIGNALS ({n})*\n\n"
#         if not active_rows:
#             msg += "_No active signals._\n\n"
#         else:
#             for i, row in enumerate(active_rows):
                
#                 i=i+1
                
#                 pair, signal_raw, monthly_trend_raw, weekly_trend_raw ,time_val, sent_status = row

#                 signal_clean = str(signal_raw).replace("SignalState.", "")

#                 if monthly_trend_raw == "BUY":
#                     direction = "STOCH UP 🟢"
#                 elif monthly_trend_raw == "SHORT":
#                     direction = "STOCH DOWN 🔴"
#                 else:
#                     direction = monthly_trend_raw
                
#                 if weekly_trend_raw == "BUY":
#                     direction2 = "STOCH UP 🟢"
#                 elif weekly_trend_raw == "SHORT":
#                     direction2 = "STOCH DOWN 🔴"
#                 else:
#                     direction2 = weekly_trend_raw
                


#                 if sent_status == 0:
#                     msg += f"🔶 ({i}). *{pair}* Newly Added! \n"
#                 else:
#                     msg += f"🔷 ({i}). *{pair}*\n"

#                 msg += f"  ├ Monthly: {direction}\n"
#                 msg += f"  ├ Weekly: {direction2}\n"
#                 msg += f"  └ Ts: {time_val}\n\n"

#         msg += "─" * 15 + "\n\n"
#         msg += "⚪️ *REMOVED FROM LAST LEDGER*\n\n"

#         if not removed_pairs:
#             msg += "No Signals Removed from last ledger"
#         else:
#             for rp in removed_pairs:
#                 msg += f"❌ *{rp}*\n"

#         return msg 

import sqlite3
import os
import threading
import logging
from datetime import datetime
from zoneinfo import ZoneInfo


class AlertLedger:
    def __init__(self, db_path="Logs/trading_ledger.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.tz = ZoneInfo("America/New_York")

        self._last_ledger: set = set()
        self._removed_pairs: set = set()

        self._lock = threading.Lock()

        # --- LOGGING ---
        # Use the central logging config from main.py. No print() calls anywhere.
        # Errors propagate to root + a dedicated error file for forensics.
        self.log = logging.getLogger("Ledger")

        # Dedicated error sink — only ERROR-level records, written to its own file.
        if not any(getattr(h, "_ledger_error_handler", False) for h in self.log.handlers):
            err_handler = logging.FileHandler("Logs/database_errors.log")
            err_handler.setLevel(logging.ERROR)
            err_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            err_handler._ledger_error_handler = True  # marker for dedup
            self.log.addHandler(err_handler)

        self._local = threading.local()
        self._bootstrap()

    # -------------------------------------------------------------------------
    # CONNECTION MANAGEMENT
    # -------------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            # Production tuning. WAL allows concurrent readers; NORMAL is the
            # standard pairing (only loses uncommitted txn on OS crash, not power).
            # autocheckpoint keeps the WAL file from growing unbounded.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA wal_autocheckpoint=1000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")  # 10s wait if locked
            self._local.conn = conn
        return self._local.conn

    # -------------------------------------------------------------------------
    # CORE WRITE HELPER
    # -------------------------------------------------------------------------

    def _execute_write(self, query: str, params: tuple = (), raise_on_error: bool = False):
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(query, params)
                conn.commit()
            except sqlite3.Error as e:
                self.log.error(f"SQL Error: {e} | Query: {query[:80]} | Params: {params}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                if raise_on_error:
                    raise

    def _execute_many_writes(self, operations: list[tuple]):
        with self._lock:
            conn = self._get_connection()
            try:
                for query, params in operations:
                    conn.execute(query, params)
                conn.commit()
            except sqlite3.Error as e:
                self.log.error(f"SQL Error in batch write: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

    # -------------------------------------------------------------------------
    # SCHEMA
    # -------------------------------------------------------------------------

    def _bootstrap(self):
        self._execute_many_writes([
            ("""
                CREATE TABLE IF NOT EXISTS alerts (
                    pair TEXT PRIMARY KEY,
                    signal TEXT,
                    montly_trend TEXT,
                    weekly_trend TEXT,
                    timestamp TEXT,
                    sent INTEGER DEFAULT 0
                )
            """, ()),
            ("""
                CREATE TABLE IF NOT EXISTS signal_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT,
                    signal TEXT,
                    montly_trend TEXT,
                    weekly_trend TEXT,
                    activated_at TEXT,
                    deactivated_at TEXT,
                    UNIQUE(pair, activated_at)
                )
            """, ()),
            # Index for future history queries (cheap to add now)
            ("CREATE INDEX IF NOT EXISTS idx_history_pair ON signal_history(pair)", ()),
        ])

    # -------------------------------------------------------------------------
    # WRITE OPERATIONS
    # -------------------------------------------------------------------------

    def clear_monthly_data(self):
        self._execute_many_writes([
            ("DELETE FROM alerts", ()),
            ("DELETE FROM signal_history", ()),
            ("DELETE FROM sqlite_sequence WHERE name='signal_history'", ()),
        ])
        # VACUUM cannot run inside a transaction
        with self._lock:
            conn = self._get_connection()
            try:
                conn.isolation_level = None
                conn.execute("VACUUM")
                conn.isolation_level = ""
            except sqlite3.Error as e:
                self.log.error(f"SQL Error during VACUUM: {e}")
        self.log.info("Monthly Reset Complete.")

    def update_status(self, pair: str, signal, montly_trend: str, weekly_trend: str, override_time: str = None):
        now_str = override_time or datetime.now(self.tz).strftime("%m-%d-%Y %H:%M:%S")
        query = """
            INSERT INTO alerts (pair, signal, montly_trend, weekly_trend, timestamp, sent)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(pair) DO UPDATE SET
                sent = CASE WHEN excluded.signal != alerts.signal THEN 0 ELSE alerts.sent END,
                signal = excluded.signal,
                montly_trend = excluded.montly_trend,
                weekly_trend = excluded.weekly_trend,
                timestamp = excluded.timestamp
        """
        self._execute_write(
            query,
            (pair, str(signal), montly_trend, weekly_trend, now_str),
            raise_on_error=True,
        )

    def deactivate_signal(self, pair: str, override_time: str = None):
        now_str = override_time or datetime.now(self.tz).strftime("%m-%d-%Y %H:%M:%S")

        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT signal, montly_trend, weekly_trend, timestamp FROM alerts WHERE pair = ?",
                    (pair,),
                ).fetchone()

                if row:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO signal_history
                            (pair, signal, montly_trend, weekly_trend, activated_at, deactivated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (pair, row[0], row[1], row[2], row[3], now_str),
                    )
                    conn.execute("DELETE FROM alerts WHERE pair = ?", (pair,))
                    conn.commit()

            except sqlite3.Error as e:
                self.log.error(f"SQL Error in deactivate_signal: {e} | pair={pair}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

    def mark_pairs_as_sent(self, pairs: list[str]):
        """
        FIX: Scoped to a specific set of pairs, not 'all unsent'. Eliminates
        the race where a signal added between get_ledger_with_history() and
        the previous mark_all_as_sent() got marked as sent without ever being
        included in any Telegram message.
        """
        if not pairs:
            return
        with self._lock:
            conn = self._get_connection()
            try:
                placeholders = ",".join("?" * len(pairs))
                conn.execute(
                    f"UPDATE alerts SET sent = 1 WHERE pair IN ({placeholders})",
                    tuple(pairs),
                )
                conn.commit()
            except sqlite3.Error as e:
                self.log.error(f"SQL Error in mark_pairs_as_sent: {e}")
                raise

    # Kept for backward compatibility with any caller still using the old name.
    # If nothing calls it, you can delete it.
    def mark_all_as_sent(self):
        self._execute_write("UPDATE alerts SET sent = 1", raise_on_error=True)

    # -------------------------------------------------------------------------
    # READ OPERATIONS
    # -------------------------------------------------------------------------

    def get_active_signal(self, pair: str) -> dict | None:
        """
        Returns the persisted state for a pair, or None if no active signal.
        Used by strategies on restart to reconcile in-memory replay with the
        DB without spuriously resetting the 'sent' flag.
        """
        with self._lock:
            conn = self._get_connection()
            row = conn.execute(
                "SELECT signal, montly_trend, weekly_trend, timestamp, sent "
                "FROM alerts WHERE pair = ?",
                (pair,),
            ).fetchone()
        if not row:
            return None
        return {
            "signal": row[0],
            "monthly_trend": row[1],
            "weekly_trend": row[2],
            "timestamp": row[3],
            "sent": row[4],
        }

    def has_updates(self) -> bool:
        """Single consistent snapshot: counts unsent rows AND computes removed pairs."""
        with self._lock:
            conn = self._get_connection()
            unsent_count = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE sent = 0"
            ).fetchone()[0]

            current_pairs = {
                row[0] for row in conn.execute("SELECT pair FROM alerts").fetchall()
            }
            self._removed_pairs = self._last_ledger - current_pairs

        return unsent_count > 0 or len(self._removed_pairs) > 0

    def get_ledger_with_history(self) -> tuple[str, list[str]]:
        """
        Returns (telegram_message, list_of_pair_names_included).
        The caller passes that list to mark_pairs_as_sent so we only mark what
        was actually transmitted.
        """
        with self._lock:
            conn = self._get_connection()
            active_rows = conn.execute(
                "SELECT pair, signal, montly_trend, weekly_trend, timestamp, sent "
                "FROM alerts ORDER BY pair ASC"
            ).fetchall()

            current_pairs = {row[0] for row in active_rows}
            self._last_ledger = current_pairs
            # Snapshot removed_pairs INSIDE the lock so a concurrent has_updates()
            # can't clobber it before we use it.
            removed_pairs = set(self._removed_pairs)

        included_pairs = [row[0] for row in active_rows]
        n = len(active_rows)
        ny = datetime.now(self.tz)

        msg = "📊 *Quantitative Ledger Update*\n"
        msg += f"Date: {ny.date():%m-%d-%Y} \n"
        msg += f"Time: {ny.time():%H:%M:%S} \n\n"
        msg += f"🟢 *ACTIVE SIGNALS ({n})*\n\n"

        if not active_rows:
            msg += "_No active signals._\n\n"
        else:
            for i, row in enumerate(active_rows, start=1):
                pair, signal_raw, monthly_trend_raw, weekly_trend_raw, time_val, sent_status = row
                signal_clean = str(signal_raw).replace("SignalState.", "")

                direction = (
                    "STOCH UP 🟢" if monthly_trend_raw == "BUY"
                    else "STOCH DOWN 🔴" if monthly_trend_raw == "SHORT"
                    else monthly_trend_raw
                )
                direction2 = (
                    "STOCH UP 🟢" if weekly_trend_raw == "BUY"
                    else "STOCH DOWN 🔴" if weekly_trend_raw == "SHORT"
                    else weekly_trend_raw
                )

                if sent_status == 0:
                    msg += f"🔶 ({i}). *{pair}* Newly Added! \n"
                else:
                    msg += f"🔷 ({i}). *{pair}*\n"

                msg += f"  ├ Monthly: {direction}\n"
                msg += f"  ├ Weekly: {direction2}\n"
                msg += f"  └ Ts: {time_val}\n\n"

        msg += "─" * 15 + "\n\n"
        msg += "⚪️ *REMOVED FROM LAST LEDGER*\n\n"
        if not removed_pairs:
            msg += "No Signals Removed from last ledger"
        else:
            for rp in removed_pairs:
                msg += f"❌ *{rp}*\n"

        return msg, included_pairs