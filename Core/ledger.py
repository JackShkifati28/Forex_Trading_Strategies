
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