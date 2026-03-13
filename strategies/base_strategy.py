from abc import ABC, abstractmethod
import random 
import time
import logging
import os
from logging.handlers import TimedRotatingFileHandler

class BaseStrategy(ABC):
    def __init__(self, pair, api_client, notifier):
        # --- DEPENDENCY INJECTION ---
        self.pair = pair
        self.api_client = api_client
        self.notifier = notifier
        
        # --- THREAD-SAFE STATE MACHINE ---
        # This state belongs ONLY to this specific currency pair instance.
        self.current_position = "NONE" 

        # --- LOGGING SETUP ---
        log_dir = "Logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Set up a logger specific to this pair
        self.logger = logging.getLogger(self.pair)
        self.logger.setLevel(logging.INFO)

        # 1. File Handler: Creates 'logs/EUR_USD.log', rotates at midnight
        # 'when="midnight"' creates a new file every day
        log_file = os.path.join(log_dir, f"{self.pair}.log")
        file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=30)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        # Avoid adding multiple handlers if the strategy is re-initialized
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)

    def log(self, message):
       
        formatted_message = f"[{self.pair}] {message}"
        
        # Print to terminal for live monitoring
        print(formatted_message)
        
        # Write to daily log file
        self.logger.info(message)

    def alert(self, message):
        """Combines console logging and SMS dispatch into one clean method."""
        full_message = f"[{self.pair}] {message}"
        self.log(full_message)
        
        # We wrap this in a try/except just in case the email server drops, 
        # so a failed text message doesn't crash your trading loop.
        try:
            self.notifier.send_alert(full_message)
            self.log(full_message)
        except Exception as e:
            self.log(f"Failed to send SMS: {e}")

    
    def fetch_candles(self, timeframe, count, max_retries=5):
        """
        Standardized fetcher for all child strategies.
        Implements exponential backoff to handle Oanda/Cloudflare 502 errors.
        """
        retries = 0
        while retries < max_retries:
            try:
                df = self.api_client.get_candles(self.pair, timeframe, count)
                if df is not None:
                    return df
            except Exception as e:
                # This catches connection resets and timeout errors
                print(f"[{self.pair}] API Exception: {e}")
            
            retries += 1
            if retries < max_retries:
                # Exponential backoff: 2, 4, 8, 16... plus jitter
                wait_time = (2 ** retries) + random.uniform(0.1, 1.0)
                print(f"[{self.pair}] Network issue. Retry {retries}/{max_retries} in {wait_time:.2f}s...")
                time.sleep(wait_time)
        
        print(f"[{self.pair}] CRITICAL: Could not recover connection after {max_retries} retries.")
        return None

    

    @abstractmethod
    def run_cycle(self):
        """
        THE CONTRACT:
        Every child strategy MUST implement this method. 
        This is the single function the main multithreading loop will call.
        """
        pass