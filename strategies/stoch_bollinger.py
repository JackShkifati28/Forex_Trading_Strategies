from strategies.base_strategy import BaseStrategy
from Core.indicator import Indicator
from datetime import datetime
from zoneinfo import ZoneInfo
from enum import Enum, auto

class SignalState(Enum):
    SEARCHING= auto()
    SHORT = auto()
    BUY = auto()

class Stoch_Bolinger(BaseStrategy):

    def __init__(self, pair, api_client, notifier):
        # Call the parent constructor first
        super().__init__(pair, api_client, notifier)

        # --- State Cache ---
        self.cached_4h_upper = None
        self.cached_4h_lower = None
        self.cached_monthly_trend = None
        # Tracker to know exactly when we last updated the cache
        self.last_4h_fetch_hour = None
        self.last_month_fetch =None
        # --- THE PING-PONG STATE ---
        # Can be "UPPER", "LOWER", or None (if it hasn't synced yet)
        self.last_signal= SignalState.SEARCHING
        self.last_touched_band = None
        self.is_message_sent =False

      

    # def _sync_historical_state(self):
        
    #     """Looks backward in time to find the last band the price touched."""

    #     self.log(f"{self.pair} Syncing historical state... hunting for last band touch.")
        
    #     # We try fetching progressively larger chunks of history
    #     candle_counts = [100, 500, 1000] 
        
    #     for count in candle_counts:
    #         df = self.api_client.get_candles(self.pair, "H4", count)
    #         if df is None:
    #             continue
                
    #         df = Indicator.bollinger(df)
            
    #         # Read the dataframe backward (from newest candle to oldest candle)
    #         # We use Low and High to see if the wicks touched the bands
    #         for i in range(len(df) - 1, -1, -1):
    #             high = df['High'].iloc[i]
    #             low = df['Low'].iloc[i]
    #             upper = df['BBU_30_2.0_2.0'].iloc[i]
    #             lower = df['BBL_30_2.0_2.0'].iloc[i]
                
    #             if high >= upper:
    #                 self.last_touched_band = "UPPER"
    #                 self.log(f"{self.pair} Synced! Last touch was UPPER band {len(df)-i} candles ago.")
    #                 return
    #             elif low <= lower:
    #                 self.last_touched_band = "LOWER"
    #                 self.log(f"{self.pair} Synced! Last touch was LOWER band {len(df)-i} candles ago.")
    #                 return
                    
    #     # If the market was entirely flat for 1000 candles (very rare)
    #     self.last_touched_band = "UNKNOWN"
    #     self.log(f"{self.pair} Warning: Could not find a band touch in the last 1000 candles.")


    def _Sync(self):
        
        self.log(f"{self.pair} Syncing historical state... Finding the signal.")

        # Getting 150 candles of 4 Hour data 
        df_sync = self.fetch_candles(self.pair, "H4", 150)
       

        df = Indicator.bollinger(df_sync)
        
        # State tracking variables
        # We start 'SEARCHING' until we can prove a trip happened
        self.last_signal = SignalState.SEARCHING
        last_hit_band = None 

        # 2. IMPORTANT: Drop NaNs and fix the index so 0 is the first valid candle
        df = df.dropna().reset_index(drop=True)
    
        n = len(df) # This will be 121


        for i in range(n):

            high = df['High'].iloc[i]
            low = df['Low'].iloc[i]
            upper = df['BBU_30_2.0_2.0'].iloc[i]
            lower = df['BBL_30_2.0_2.0'].iloc[i]

            # CASE 1: Price touches the TOP band
            if high >= upper:
                # If our previous landmark was the BOTTOM, we just completed a BUY trip
                # and now we are ready to look for a SHORT
                if last_hit_band == "LOWER":
                    self.last_signal = SignalState.SHORT
                    self.log(f"Trip Completed: Bottom -> Top. Signal is now SHORT.")
                    self.is_message_sent =False
                
                # Update our landmark to Top
                last_hit_band = "UPPER"

            # CASE 2: Price touches the BOTTOM band
            elif low <= lower:
                # If our previous landmark was the TOP, we just completed a SHORT trip
                # and now we are ready to look for a BUY
                if last_hit_band == "UPPER":
                    self.last_signal = SignalState.BUY
                    self.log(f"Trip Completed: Top -> Bottom. Signal is now BUY.")
                    self.is_message_sent =False
                
                # Update our landmark to Bottom
                last_hit_band = "LOWER"

            # CASE 3: Price is in the middle
            else:
                # We DO NOTHING. We don't change last_signal and we don't change last_hit_band.
                # This "remembers" the last signal until the opposite band is hit.
                continue

        # Final reporting
        self.last_touched_band = last_hit_band or "UNKNOWN"
        
        if self.last_signal == SignalState.SEARCHING:
            self.log(f"{self.pair} Info: Price has not traveled between both bands in the last 150 candles.")
        else:
            self.log(f"{self.pair} Final Sync Result: {self.last_signal}")
    
    
    def _get_Month(self):
        self.log(f"{self.pair} Resetting Monthly Trend ")

        df_monthly = self.fetch_candles(self.pair, "M", 21)
        if df_monthly is None:
            self.log(f"{self.pair} Network dropped. Skipping this cycle.")
            return
             
        df_monthly = Indicator.stocastic(df_monthly)

        k_monthly = df_monthly['STOCHk_14_3_3'].iloc[-2]
        d_monthly = df_monthly['STOCHd_14_3_3'].iloc[-2]

        self.cached_monthly_trend = "BUY" if k_monthly > d_monthly else "SHORT"


    def _get_4hour(self):
        self.log(f"{self.pair} Resetting 4-Hour Boundary.")
        
        df_h4 = self.fetch_candles(self.pair, "H4", 50)
        
        if df_h4 is None:
            self.log(f"{self.pair} Network dropped. Skipping this cycle.")
            return

        df_h4 = Indicator.bollinger(df_h4)
            
            # 4. 4H Trigger Logic
        self.cached_4h_lower = df_h4['BBL_30_2.0_2.0'].iloc[-1]
        self.cached_4h_upper = df_h4['BBU_30_2.0_2.0'].iloc[-1]

    
    def _get_15Min(self):

        df_m15 = self.fetch_candles(self.pair, "M15", 5)

        if df_m15 is None:
            self.log(f"{self.pair} Network dropped during 15m fetch. Skipping cycle.")
            return
            
        high = df_m15 ['High'].iloc[-1]
        low =  df_m15 ['Low'].iloc[-1]

        if high >= self.cached_4h_upper:
            
            if self.last_touched_band =="LOWER":
                self.last_signal = SignalState.SHORT
                self.is_message_sent =False

            # Update RAM so we don't buy again until it hits the top band and comes back down
            self.last_touched_band = "UPPER"


        elif low <= self.cached_4h_lower:

            if self.last_touched_band =="UPPER":
                self.last_signal = SignalState.BUY
                self.is_message_sent =False

             # Update RAM
            self.last_touched_band = "LOWER"
        

        
    def run_cycle(self):


        ny_tz = ZoneInfo("America/New_York")
       
        # Get current time specifically for NY
        now_ny = datetime.now(ny_tz)

        current_month = now_ny.month
        current_hour = now_ny.hour
         
        # Run every month
        if self.last_month_fetch is None or self.last_month_fetch != current_month:
            self._get_Month()
            self.last_month_fetch = current_month

        # Run every 4 hours
        if self.cached_4h_upper is None or current_hour != self.last_4h_fetch_hour:
            self._get_4hour()
            # Lock the cache so it doesn't fetch again this hour
            self.last_4h_fetch_hour = current_hour
     
        # INITIAL SYNC (Run only once at startup)
        if self.last_touched_band is None: 
            self._Sync()

        elif self.last_touched_band is not None:
            self._get_15Min()


        if not self.is_message_sent:

            # 5. The Ping-Pong Execution Logic
            if self.cached_monthly_trend == "BUY" and self.last_signal == SignalState.BUY:
                  # Update RAM so we don't buy again until it hits the top band and comes back down
                self.alert("BUY POTENTIAL: Traveled Top-to-Bottom. Price hit Lower Band.")
                self.is_message_sent =True
            
                
            elif self.cached_monthly_trend == "SHORT" and self.last_signal == SignalState.SHORT:
                self.alert("SHORT POTENTIAL: Traveled Bottom-to-Top. Price hit Upper Band.")
                self.is_message_sent =True
            
        else:
            self.log(f"{self.pair} Monitoring | Momentum: { self.cached_monthly_trend} | Last Signal: {self.last_signal}")
