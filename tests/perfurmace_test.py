import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

from Core.oanda_client import OandaClient
from Core.smsNotifier import TelegramNotifier
from strategies.stoch_bollinger import Stoch_Bolinger
from Core.ledger import AlertLedger

# --- BENCHMARK TOGGLE ---
# Change this to "SERIAL" or "THREADED" to test performance
EXECUTION_MODE = "SERIALcle" 
MAX_WORKERS =10

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
CHAT_ID = os.getenv("PERSONAL_ID")

def main():
    print(f"🚀 Initializing Forex Engine (Mode: {EXECUTION_MODE})...")
    
    ledger = AlertLedger()
    notifier = TelegramNotifier( 
    token = os.getenv("TELEGRAM_API_TOKEN"), 
    chat_ids= os.getenv("PERSONAL_ID")
    )
    api_client = OandaClient(
        api_token=os.getenv("API_TOKEN"), 
        account_id=os.getenv("ACCOUNT_ID")
    )
    
    pairs = api_client.getPairs()
    print(f"📡 Found {len(pairs)} pairs on Oanda.")
    
    # Initialize all 68 strategies into RAM
    strategies = [Stoch_Bolinger(pair, api_client, notifier, ledger) for pair in pairs]
    
    while True:
        print(f"\n--- Starting Cycle at {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')} NY Time ---")
        
        # Start the stopwatch!
        start_time = time.time()
        
        if EXECUTION_MODE == "SERIAL":
            print("⏳ Running sequentially (One by one)...")
            for strat in strategies:
                strat.run_cycle()
                
        elif EXECUTION_MODE == "THREADED":
            print(f"⚡ Running ThreadPool with {MAX_WORKERS} workers...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(strat.run_cycle) for strat in strategies]
                for f in futures:
                    f.result() # Catches any hidden thread crashes
                    
        # Stop the stopwatch!
        execution_time = time.time() - start_time
        
        print("="*40)
        print(f"⏱️ BENCHMARK ({EXECUTION_MODE}): {len(pairs)} pairs completed in {execution_time:.2f} seconds.")
        print("="*40)
        
        # --- MASTER DISPATCHER ---
        if ledger.has_updates():
            print("📤 Updates found! Dispatching unified Telegram Ledger...")
            msg = ledger.get_ledger_with_history()
            notifier.send_alert(msg)
            ledger.mark_all_as_sent()
        else:
            print("💤 No new updates for this cycle.")

        # Sleep for 60 seconds just for benchmarking purposes so you don't have to wait 15 mins
        print("Sleeping 60 seconds before next test...")
        time.sleep(60)

if __name__ == "__main__":
    main()