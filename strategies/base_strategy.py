from abc import ABC, abstractmethod

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

    @abstractmethod
    def run_cycle(self):
        """
        THE CONTRACT:
        Every child strategy MUST implement this method. 
        This is the single function the main multithreading loop will call.
        """
        pass