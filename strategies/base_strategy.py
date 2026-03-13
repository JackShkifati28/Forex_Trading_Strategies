from abc import ABC, abstractmethod
import random 
import time

class BaseStrategy(ABC):
    def __init__(self, pair, api_client, notifier):
        # --- DEPENDENCY INJECTION ---
        self.pair = pair
        self.api_client = api_client
        self.notifier = notifier
        
        # --- THREAD-SAFE STATE MACHINE ---
        # This state belongs ONLY to this specific currency pair instance.
        self.current_position = "NONE" 

    def log(self, message):
        """Standardized console logging so threads don't create a messy terminal."""
        print(f"[{self.pair}] {message}")

    def alert(self, message):
        """Combines console logging and SMS dispatch into one clean method."""
        full_message = f"[{self.pair}] {message}"
        self.log(full_message)
        
        # We wrap this in a try/except just in case the email server drops, 
        # so a failed text message doesn't crash your trading loop.
        try:
            self.notifier.send_alert(full_message)
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