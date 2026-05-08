# from abc import ABC, abstractmethod
# import random 
# import time
# import logging
# import os
# from logging.handlers import TimedRotatingFileHandler

# class BaseStrategy(ABC):
#     def __init__(self, pair, api_client, notifier, ledger):
#         # --- DEPENDENCY INJECTION ---
#         self.pair = pair
#         self.api_client = api_client
#         self.notifier = notifier
#         self.ledger = ledger
        
#         # --- THREAD-SAFE STATE MACHINE ---
#         # This state belongs ONLY to this specific currency pair instance.
#         self.current_position = "NONE" 

#         # --- LOGGING SETUP ---
#         log_dir = "Logs"
#         if not os.path.exists(log_dir):
#             os.makedirs(log_dir)

#         # Set up a logger specific to this pair
#         self.logger = logging.getLogger(self.pair)
#         self.logger.setLevel(logging.INFO)

#         # 1. File Handler: Creates 'logs/EUR_USD.log', rotates at midnight
#         # 'when="midnight"' creates a new file every day
#         log_file = os.path.join(log_dir, f"{self.pair}.log")
#         file_handler = TimedRotatingFileHandler(log_file, when="W0", interval=1, backupCount=4)
#         file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#         file_handler.setFormatter(file_formatter)

#         # Avoid adding multiple handlers if the strategy is re-initialized
#         if not self.logger.handlers:
#             self.logger.addHandler(file_handler)

#     def log(self, message):
       
#         formatted_message = f"[{self.pair}] {message}"
        
#         # Print to terminal for live monitoring
#         print(formatted_message)
        
#         # Write to daily log file
#         self.logger.info(message)

#     def alert(self, message):
#         """Combines console logging and SMS dispatch into one clean method."""
#         full_message = f"[{self.pair}] {message}"
#         self.log(full_message)
        
#         # We wrap this in a try/except just in case the email server drops, 
#         # so a failed text message doesn't crash your trading loop.
#         try:
#             self.notifier.send_alert(full_message)
#             self.log(full_message)
#         except Exception as e:
#             self.log(f"Failed to send SMS: {e}")

    
#     def fetch_candles(self, timeframe, count, max_retries=5):
#         """
#         Standardized fetcher for all child strategies.
#         Implements exponential backoff to handle Oanda/Cloudflare 502 errors.
#         """
#         retries = 0
#         while retries < max_retries:
#             try:
#                 df = self.api_client.get_candles(self.pair, timeframe, count)
#                 if df is not None:
#                     return df
#             except Exception as e:
#                 # This catches connection resets and timeout errors
#                 print(f"[{self.pair}] API Exception: {e}")
#                 self.log(f"API Exception: {e}")
            
#             retries += 1
#             if retries < max_retries:
#                 # Exponential backoff: 2, 4, 8, 16... plus jitter
#                 wait_time = (2 ** retries) + random.uniform(0.1, 1.0)
#                 print(f"[{self.pair}] Network issue. Retry {retries}/{max_retries} in {wait_time:.2f}s...")
#                 self.log(f"Network issue. Retry {retries}/{max_retries} in {wait_time:.2f}s...")
#                 time.sleep(wait_time)
        
#         print(f"[{self.pair}] CRITICAL: Could not recover connection after {max_retries} retries.")
#         self.log(f"CRITICAL: Could not recover connection after {max_retries} retries.")
#         return None

    

#     @abstractmethod
#     def run_cycle(self):
#         """
#         THE CONTRACT:
#         Every child strategy MUST implement this method. 
#         This is the single function the main multithreading loop will call.
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
