
#         """
#         pass

import os
import time
import random
import logging
from abc import ABC, abstractmethod
from logging.handlers import TimedRotatingFileHandler

# --- TUNING ---
# Total worst-case time for fetch_candles must stay under main.py's CYCLE_TIMEOUT
# (currently 60s) divided by the number of fetches a strategy makes per cycle.
#
# urllib3.Retry in OandaClient already handles transport-level retries
# (3 attempts, ~4.5s of backoff). So this layer only needs a couple of
# higher-level retries to handle anything that escapes that.
MAX_FETCH_RETRIES = 3            # was 5
BASE_BACKOFF_SECONDS = 1.5       # was 2 with bigger exponent

LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)


class BaseStrategy(ABC):
    def __init__(self, pair, api_client, notifier, ledger):
        # --- DEPENDENCY INJECTION ---
        self.pair = pair
        self.api_client = api_client
        self.notifier = notifier
        self.ledger = ledger
        self.current_position = "NONE"

        # --- LOGGING SETUP ---
        # Use a hierarchical name so we can configure all pair loggers at once
        # if needed (e.g. logging.getLogger("pair").setLevel(...)).
        self.logger = logging.getLogger(f"pair.{pair}")
        self.logger.setLevel(logging.INFO)

        # propagate=True means records also go to the root logger's stdout
        # handler (configured in main.py). That's what we want for live
        # monitoring — and it means we DON'T need print() anywhere.
        self.logger.propagate = True

        # Attach a per-pair file handler exactly once. logging.getLogger() is
        # idempotent, so re-instantiating the strategy returns the same logger
        # object — without this guard you'd accumulate handlers and produce
        # duplicate file lines on every restart.
        if not self.logger.handlers:
            log_file = os.path.join(LOG_DIR, f"{pair}.log")
            file_handler = TimedRotatingFileHandler(
                log_file, when="W0", interval=1, backupCount=4
            )
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(file_handler)

    # ---------- logging ----------

    def log(self, message: str, level: int = logging.INFO):
        """
        Single source of truth for output. NO print() calls anywhere — the
        root StreamHandler configured in main.py prints to stdout, and our
        per-pair FileHandler writes to Logs/{pair}.log. One call, two sinks.
        """
        self.logger.log(level, f"[{self.pair}] {message}")

    def alert(self, message: str):
        """Log the event AND notify externally. Each event logs exactly once."""
        self.log(message)
        try:
            self.notifier.send_alert(f"[{self.pair}] {message}")
        except Exception as e:
            self.log(f"Failed to send alert: {e}", level=logging.ERROR)

    # ---------- candle fetching ----------

    def fetch_candles(self, timeframe, count, max_retries: int = MAX_FETCH_RETRIES):
        """
        Bounded-retry candle fetcher.

        Contract with api_client.get_candles:
          - returns DataFrame -> success, return it
          - returns None      -> PERMANENT failure for this pair (401/403/404,
                                 already cached as unauthorized in OandaClient).
                                 Do NOT retry — return None and let the strategy
                                 skip this cycle.
          - raises            -> TRANSIENT failure (5xx after urllib3 backoff,
                                 transport error). Retry with backoff.
        """
        for attempt in range(1, max_retries + 1):
            try:
                df = self.api_client.get_candles(self.pair, timeframe, count)
                # None here means permanent — get out, don't burn the cycle budget.
                return df
            except Exception as e:
                if attempt == max_retries:
                    self.log(
                        f"Giving up after {attempt} attempts: {e}",
                        level=logging.ERROR,
                    )
                    return None

                wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                self.log(
                    f"Transient error ({e}); retry {attempt}/{max_retries} in {wait:.2f}s",
                    level=logging.WARNING,
                )
                time.sleep(wait)

        return None

    # ---------- contract ----------

    @abstractmethod
    def run_cycle(self):
        """
        THE CONTRACT:
        Every child strategy MUST implement this method. This is the single
        function the main multithreading loop will call.
        """
        pass
