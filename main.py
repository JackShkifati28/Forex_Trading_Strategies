import os
import time
import sys
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from datetime import datetime, timedelta
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from Core.oanda_client import OandaClient
from Core.smsNotifier import TelegramNotifier
from strategies.stoch_bollinger import Stoch_Bolinger
from Core.ledger import AlertLedger
import glob

# --- CONFIGURATION ---
MAX_WORKERS = 10  # The benchmarked sweet spot!

def get_seconds_to_next_m15():

    """Calculates the exact seconds until the next 15-minute candle close (:00, :15, :30, :45)."""

    ny_tz = ZoneInfo("America/New_York")
    now = datetime.now(ny_tz)
    
    # Calculate how many minutes until the next 15-minute boundary
    minutes_to_next = 15 - (now.minute % 15)
    
    # Create a datetime object for that exact future minute
    next_run_time = now + timedelta(minutes=minutes_to_next)
    next_run_time = next_run_time.replace(second=0, microsecond=0)
    
    # Add a 5-second buffer to ensure Oanda has actually painted the new candle
    seconds_to_sleep = (next_run_time - now).total_seconds() + 5
    return max(seconds_to_sleep, 1.0)

if __name__ == "__main__":

    print("Booting Quantitative Engine...")

    load_dotenv()

    # --- NEW: Clear active logs on boot ---
    print("Sweeping old active log files...")
    # This finds all base .log files but leaves rotated backups untouched
    for log_path in glob.glob("Logs/*.log"):
        try:
            os.remove(log_path)
        except Exception as e:
            print(f"Could not clear {log_path}: {e}")


    ledger =AlertLedger()

   # --- THE PRODUCTION-SAFE WIPE COMMAND ---
    # Run the bot with: python main.py --wipe 
    # Otherwise, it defaults to keeping your data safely intact.
    if "--wipe" in sys.argv:
        print("⚠️ '--wipe' flag detected. Purging all database records...")
        ledger.clear_monthly_data()
        # Optional: You could also add a command here to run a SQL query 
        # to TRUNCATE your signal_history table so you don't get duplicates!
        print("✅ Database cleared. Starting fresh.")
    else:
        print("💾 Booting with existing database records intact.")


    # 1. Instantiate the Stateless Services (Actuators/Sensors)
    # target_emails = os.getenv("TARGET_PHONE_EMAIL")
    
    db_client = OandaClient(
        api_token=os.getenv("API_TOKEN"), 
        account_id=os.getenv("ACCOUNT_ID")
    )
    
    # raw_emails_string = os.getenv("TARGET_PHONE_EMAIL")
    # email_list = raw_emails_string.split(",")

    # sms_client = SMSNotifier(
    #     sender_email=os.getenv("GMAIL_ADDRESS"),
    #     sender_password=os.getenv("GMAIL_APP_PASSWORD"),
    #     target_sms_email=email_list
    # )

    tms = TelegramNotifier( 
    token = os.getenv("TELEGRAM_API_TOKEN"), 
    chat_ids= os.getenv("ID")
    )

    bots_names = db_client.getPairs()
    bots = [Stoch_Bolinger(pair_name, db_client, tms, ledger) for pair_name in bots_names]

    try:

        while True:

            start_time = time.time()
            
            print(f"\n--- Starting Cycle at {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')} NY Time ---")
            
            # --- THE THREAD POOL BARRIER ---
            # This processes all 68 bots using 10 concurrent threads. 
            # The script will pause here until EVERY bot finishes its run_cycle.
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                
                future_to_bot = {executor.submit(bot.run_cycle): bot.pair for bot in bots}
                
                # as_completed allows us to process them as they finish and enforce a strict timeout
                for future in concurrent.futures.as_completed(future_to_bot, timeout=30):
                    pair_name = future_to_bot[future]
                    try:
                        future.result() 
                    except Exception as e:
                        print(f"[{pair_name}] ⚠️ Engine caught an error and skipped this cycle: {e}")
            
            execution_time = time.time() - start_time

            print(f"✅ All {len(bots)} pairs completed in {execution_time:.2f} seconds.")

            # --- MASTER DISPATCHER ---
            # Because we waited for the ThreadPool to finish, we are 100% guaranteed
            # that the database is completely synced before we check it.

            print("[Dispatcher] Checking ledger for updates...")
            
            if ledger.has_updates():
                print("[Dispatcher] Update detected! Sending unified ledger...")

                message = ledger.get_ledger_with_history()

                try:
                    tms.send_alert(message)
                    ledger.mark_all_as_sent()

                except Exception as e:
                    print(f"[Dispatcher] Failed to send Telegram update: {e}")
            else:
                print("[Dispatcher] No new updates.")

            # --- PRECISION TIMING ---
            sleep_seconds = get_seconds_to_next_m15()
            print(f"⏳ Sleeping for {sleep_seconds / 60:.2f} minutes until the next candle...")
            time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down engine cleanly...")