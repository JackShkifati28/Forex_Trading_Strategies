from strategies.base_strategy import BaseStrategy
from Core.indicator import Indicator
from datetime import datetime
from zoneinfo import ZoneInfo
from enum import Enum, auto
import numpy as np

class SignalState(Enum):
    SEARCHING= auto()
    SHORT = auto()
    BUY = auto()

class Stoch_Bolinger(BaseStrategy):

    def __init__(self, pair, api_client, notifier, ledger):
        # Call the parent constructor first
        super().__init__(pair, api_client, notifier, ledger)


        # --- State Cache ---
        self.cached_4h_upper = None
        self.cached_4h_lower = None
        self.cached_monthly_trend = None
        self.cached_weekly_trend = None

        # Tracker to know exactly when we last updated the cache
        self.last_4h_fetch_hour = None
        self.last_month_fetch =None
        self.last_weekly_fetch =None

        # --- THE PING-PONG STATE ---
        # Can be "UPPER", "LOWER", or None (if it hasn't synced yet)
        self.last_signal= SignalState.SEARCHING
        self.last_touched_band = None
        self.is_message_sent =False
        self.last_trigger_time = None
    
    
    def _format_oanda_time(self, raw_time):
        """Helper to convert Oanda UTC timestamps to clean NY time."""
        try:
            time_str = str(raw_time)
            clean_str = time_str.split(".")[0].replace("T", " ").replace("Z", "")
            utc_dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
            utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
            ny_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
            return ny_dt.strftime("%m-%d-%Y %H:%M:%S")
        except:
            return datetime.now(ZoneInfo("America/New_York")).strftime("%m-%d-%Y %H:%M:%S")

    def _Sync(self):
        
        self.log(f"{self.pair} Syncing historical state... Finding the signal.")

        # Getting 150 candles of 4 Hour data 
        df_sync = self.fetch_candles("H4", 180)

        if df_sync is None:
            self.log("Sync failed: Could not fetch H4 candles.")
            return
       

        df = Indicator.bollinger(df_sync)
        
        # State tracking variables
        # We start 'SEARCHING' until we can prove a trip happened
        self.last_signal = SignalState.SEARCHING
        last_hit_band = None 

        # 2. IMPORTANT: Drop NaNs and fix the index so 0 is the first valid candle
        df = df.dropna().reset_index(drop=True)
    
        n = len(df) # This will be 150


        for i in range(n):

            high = np.round(df['High'].iloc[i], 4)
            low = np.round(df['Low'].iloc[i], 4)
            upper = np.round( df['BBU_30_2.0_2.0'].iloc[i],4)
            lower = np.round( df['BBL_30_2.0_2.0'].iloc[i], 4)
    

            # Get the exact time of THIS historical candle
            raw_time = df['Date'].iloc[i]
            candle_time_str = self._format_oanda_time(raw_time)

            # CASE 1: Price touches the TOP band
            # if high >= upper:
            if high >=upper:
                # If our previous landmark was the BOTTOM, we just completed a BUY trip
                # and now we are ready to look for a SHORT
                if last_hit_band == "LOWER":

                    if self.last_signal != SignalState.SEARCHING:
                        self.ledger.deactivate_signal(self.pair ,override_time=candle_time_str)
                        self.log(f"Decativated Signal {self.last_signal} at time {candle_time_str}")

                    self.last_signal = SignalState.SHORT
                    self.log(f"Trip Completed: Bottom -> Top. Signal is now SHORT.")

                    # NEW: Update the RAM cache!
                    self.last_trigger_time = candle_time_str
        

                    if self.cached_monthly_trend =="SHORT":
                        # ADDED: override_time here is CRITICAL
                        self.ledger.update_status(self.pair, self.last_signal, self.cached_monthly_trend,self.cached_weekly_trend,override_time=candle_time_str)
                
                # Update our landmark to Top
                last_hit_band = "UPPER"

            # CASE 2: Price touches the BOTTOM band
            elif  low <= lower:
                # If our previous landmark was the TOP, we just completed a SHORT trip
                # and now we are ready to look for a BUY
                if last_hit_band == "UPPER":

                    if self.last_signal != SignalState.SEARCHING:
                        self.ledger.deactivate_signal(self.pair, override_time=candle_time_str)
                        self.log(f"Decativated Signal {self.last_signal} at time {candle_time_str}")

                    self.last_signal = SignalState.BUY
                    self.log(f"Trip Completed: Top -> Bottom. Signal is now BUY.")
                    # NEW: Update the RAM cache!
                    self.last_trigger_time = candle_time_str

                    if self.cached_monthly_trend =="BUY":
                        self.ledger.update_status(self.pair, self.last_signal, self.cached_monthly_trend , self.cached_weekly_trend,override_time=candle_time_str)
                
                # Update our landmark to Bottom
                last_hit_band = "LOWER"

            # CASE 3: Price is in the middle
            else:
                # We DO NOTHING. We don't change last_signal and we don't change last_hit_band.
                # This "remembers" the last signal until the opposite band is hit.
                continue

        # Final reporting
        self.last_touched_band = last_hit_band or "UNKNOWN"

        # FIX 2: Lock the door so run_cycle doesn't duplicate the final signal
        self.is_message_sent = True
        
        if self.last_signal == SignalState.SEARCHING:
            self.log(f"{self.pair} Info: Price has not traveled between both bands in the last 150 candles.")
        else:
            self.log(f"{self.pair} Final Sync Result: {self.last_signal}")
    
    
    def _get_Month(self):
        self.log(f"{self.pair} Resetting Monthly Trend ")

        df_monthly = self.fetch_candles("M", 21)

        if df_monthly is None:
            self.log(f"{self.pair} Network dropped. Skipping this cycle.")
            return
             
        df_monthly = Indicator.stocastic(df_monthly)

        k_monthly = df_monthly['STOCHk_14_3_3'].iloc[-2]
        d_monthly = df_monthly['STOCHd_14_3_3'].iloc[-2]

        self.cached_monthly_trend = "BUY" if k_monthly > d_monthly else "SHORT"
    
    def _get_weekly(self):
         
         self.log(f"{self.pair} Resetting Weekly Trend ")

         df_weekly = self.fetch_candles("W", 21)

         if df_weekly is None:
            self.log(f"{self.pair} Network dropped. Skipping this cycle.")
            return
         
         df_weekly = Indicator.stocastic(df_weekly)

         k_weekly = df_weekly['STOCHk_14_3_3'].iloc[-2]
         d_weekly = df_weekly['STOCHd_14_3_3'].iloc[-2]

         self.cached_weekly_trend = "BUY" if  k_weekly > d_weekly else "SHORT"

    def _get_4hour(self):
        self.log(f"{self.pair} Resetting 4-Hour Boundary.")
        
        df_h4 = self.fetch_candles( "H4", 50)

        
        if df_h4 is None:
            self.log(f"{self.pair} Network dropped. Skipping this cycle.")
            return
        

        df_h4 = Indicator.bollinger(df_h4)
            
            # 4. 4H Trigger Logic
        self.cached_4h_lower = np.round(df_h4['BBL_30_2.0_2.0'].iloc[-1], 4)
        self.cached_4h_upper = np.round(df_h4['BBU_30_2.0_2.0'].iloc[-1], 4)


    
    def _get_15Min(self):

        df_m15 = self.fetch_candles("M15", 5)

        if df_m15 is None:
            self.log(f"{self.pair} Network dropped during 15m fetch. Skipping cycle.")
            return
            

        high = np.round(df_m15['High'].iloc[-1], 4)
        low = np.round(df_m15['Low'].iloc[-1], 4)
       
    

        # NEW: Extract the raw Oanda UTC time from the live candle
        raw_time = df_m15['Date'].iloc[-1]

        if high >= self.cached_4h_upper:
            
            if self.last_touched_band =="LOWER":

                # if self.last_signal != SignalState.SEARCHING:
                #         self.ledger.deactivate_signal(self.pair)
            
                self.last_signal = SignalState.SHORT        
                self.is_message_sent =False
                # NEW: Format to NY Time and save it!
                self.last_trigger_time = self._format_oanda_time(raw_time)

            # Update RAM so we don't buy again until it hits the top band and comes back down
            self.last_touched_band = "UPPER"


        elif low <= self.cached_4h_lower:

            if self.last_touched_band =="UPPER":
                
                # if self.last_signal != SignalState.SEARCHING:
                #     self.ledger.deactivate_signal(self.pair)

                self.last_signal = SignalState.BUY
                self.is_message_sent =False
                 # NEW: Format to NY Time and save it!
                self.last_trigger_time = self._format_oanda_time(raw_time)

             # Update RAM
            self.last_touched_band = "LOWER"
        
        
    def run_cycle(self):
        ny_tz = ZoneInfo("America/New_York")
       
            # Get current time specifically for NY
        now_ny = datetime.now(ny_tz)
        current_4hour = (now_ny.hour//4)*4


        try:

            current_month = self.fetch_candles("M",3)['Date'].iloc[-1]
            last_week = self.fetch_candles("W",4)['Date'].iloc[-1]
          
         
            # Run every month
            if self.last_month_fetch is None or self.last_month_fetch != current_month:
                self._get_Month()
                self.is_message_sent =False
                self.last_month_fetch = current_month

            #Run every week
            if self.last_weekly_fetch is None or self.last_weekly_fetch !=  last_week:
                self._get_weekly()
                self.is_message_sent =False
                self.last_weekly_fetch =  last_week

            # Run every 4 hours
            if self.cached_4h_upper is None or  current_4hour!= self.last_4h_fetch_hour:
                self._get_4hour()
                # Lock the cache so it doesn't fetch again this hour
                self.last_4h_fetch_hour = current_4hour
        
            # INITIAL SYNC (Run only once at startup)
            if self.last_touched_band is None: 
                self._Sync()

            elif self.last_touched_band is not None:
                self._get_15Min()


            if not self.is_message_sent:

                # 5. The Ping-Pong Execution Logic
                if self.cached_monthly_trend == "BUY" and self.last_signal == SignalState.BUY:
                    # Update RAM so we don't buy again until it hits the top band and comes back down
                    # self.alert("BUY POTENTIAL: Traveled Top-to-Bottom. Price hit Lower Band.")
                    self.ledger.update_status(self.pair, self.last_signal, self.cached_monthly_trend, self.cached_weekly_trend ,override_time=self.last_trigger_time)
                    self.is_message_sent =True
                    self.log(f"Trip Completed: Top -> Bottom. Signal is now BUY.")
                   
                
                    
                elif self.cached_monthly_trend == "SHORT" and self.last_signal == SignalState.SHORT:
                    # self.alert("SHORT POTENTIAL: Traveled Bottom-to-Top. Price hit Upper Band.")
                    self.ledger.update_status(self.pair, self.last_signal, self.cached_monthly_trend,self.cached_weekly_trend ,override_time=self.last_trigger_time)
                    self.is_message_sent =True
                    self.log(f"Trip Completed: Bottom -> Top. Signal is now SHORT.")
                
                else: 
                     self.ledger.deactivate_signal(self.pair)
                     self.is_message_sent =True
                     self.log(f"Deactivated Signal.")
                
            else:
                self.log(f"{self.pair} Monitoring | Monthly Momentum: { self.cached_monthly_trend} | Weekly Momentum: {self.cached_weekly_trend} | Last Signal: {self.last_signal}")
        
        except Exception as e:
            self.log(f"CRITICAL ERROR in run_cycle: {e}")
