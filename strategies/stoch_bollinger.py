from strategies.base_strategy import BaseStrategy
from Core.indicator import Indicator

class Stoch_Bolinger(BaseStrategy):

    def __init__(self, pair, api_client, notifier):
        # Call the parent constructor first
        super().__init__(pair, api_client, notifier)
        
        # --- THE PING-PONG STATE ---
        # Can be "UPPER", "LOWER", or None (if it hasn't synced yet)
        self.last_touched_band = None

    def _sync_historical_state(self):
        
        """Looks backward in time to find the last band the price touched."""

        self.log(f"{self.pair} Syncing historical state... hunting for last band touch.")
        
        # We try fetching progressively larger chunks of history
        candle_counts = [100, 500, 1000] 
        
        for count in candle_counts:
            df = self.api_client.get_candles(self.pair, "H4", count)
            if df is None:
                continue
                
            df = Indicator.bollinger(df)
            
            # Read the dataframe backward (from newest candle to oldest candle)
            # We use Low and High to see if the wicks touched the bands
            for i in range(len(df) - 1, -1, -1):
                high = df['High'].iloc[i]
                low = df['Low'].iloc[i]
                upper = df['BBU_20_2.0_2.0'].iloc[i]
                lower = df['BBL_20_2.0_2.0'].iloc[i]
                
                if high >= upper:
                    self.last_touched_band = "UPPER"
                    self.log(f"{self.pair} Synced! Last touch was UPPER band {len(df)-i} candles ago.")
                    return
                elif low <= lower:
                    self.last_touched_band = "LOWER"
                    self.log(f"{self.pair} Synced! Last touch was LOWER band {len(df)-i} candles ago.")
                    return
                    
        # If the market was entirely flat for 1000 candles (very rare)
        self.last_touched_band = "UNKNOWN"
        self.log(f"{self.pair} Warning: Could not find a band touch in the last 1000 candles.")

    

    def run_cycle(self):

        # 1. Boot-up Sync (Only runs the very first time the bot starts)
        if self.last_touched_band is None:
            self._sync_historical_state()

            if self.last_touched_band is None:
                return # Still failing network, try again next cycle

        # 2. Normal execution (Standard 50 candles)
        df_monthly = self.api_client.get_candles(self.pair, "M", 20)
        df_h4 = self.api_client.get_candles(self.pair, "H4", 50)
        
        if df_monthly is None or df_h4 is None:
            self.log(f"{self.pair} Network dropped. Skipping this cycle.")
            return

        df_monthly = Indicator.stocastic(df_monthly)
        df_h4 = Indicator.bollinger(df_h4)

        # 3. Monthly Gate Logic
        k_monthly = df_monthly['STOCHk_14_3_3'].iloc[-1]
        d_monthly = df_monthly['STOCHd_14_3_3'].iloc[-1]

        momentum = "BUY" if k_monthly > d_monthly else "SHORT"

        # 4. 4H Trigger Logic
        current_low = df_h4['Low'].iloc[-1]
        current_high = df_h4['High'].iloc[-1]
        lower_band = df_h4['BBL_20_2.0_2.0'].iloc[-1]
        upper_band = df_h4['BBU_20_2.0_2.0'].iloc[-1]

        # Check what band the CURRENT candle is touching
        current_touch = None

        if current_low <= lower_band:
            current_touch = "LOWER"

        elif current_high >= upper_band:
            current_touch = "UPPER"

        # 5. The Ping-Pong Execution Logic
        if momentum == "BUY" and current_touch == "LOWER" and self.last_touched_band == "UPPER":
            self.alert(f"{self.pair}  LONG SETUP: Traveled Top-to-Bottom. Price hit Lower Band.")
            # Update RAM so we don't buy again until it hits the top band and comes back down
            self.last_touched_band = "LOWER" 
            
        elif momentum == "SHORT" and current_touch == "UPPER" and self.last_touched_band == "LOWER":
            self.alert(f"{self.pair} SHORT SETUP: Traveled Bottom-to-Top. Price hit Upper Band.")
            # Update RAM
            self.last_touched_band = "UPPER"

        # 6. State Maintenance
        # If it hit a band but didn't trigger an alert (e.g., wrong momentum), 
        # we still MUST update the historical state.
        elif current_touch:
            if self.last_touched_band != current_touch:
                self.log(f"{self.pair} Price hit {current_touch} band. (No trade taken due to Momentum). Updating memory.")
                self.last_touched_band = current_touch
        
        else:
            self.log(f"{self.pair} Monitoring | Momentum: {momentum} | Last Touch: {self.last_touched_band}")


















