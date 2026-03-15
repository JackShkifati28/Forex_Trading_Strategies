import os
import time
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import random 
from zoneinfo import ZoneInfo
from Core.oanda_client import OandaClient
from Core.smsNotifier import TelegramNotifier
from strategies.stoch_bollinger import Stoch_Bolinger
from Core.ledger import AlertLedger
import glob

def get_seconds_to_next_m15():
    """Calculates the exact seconds until the next 15-minute candle close (:00, :15, :30, :45)."""

    ny_tz = ZoneInfo("America/New_York")
       
        # Get current time specifically for NY
    now = datetime.now(ny_tz)
   
    
    # Calculate how many minutes until the next 15-minute boundary
    minutes_to_next = 15 - (now.minute % 15)
    
    # Create a datetime object for that exact future minute
    next_run_time = now + timedelta(minutes=minutes_to_next)
    next_run_time = next_run_time.replace(second=0, microsecond=0)
    
    # Add a 5-second buffer to ensure Oanda has actually painted the new candle
    seconds_to_sleep = (next_run_time - now).total_seconds() + 5
    return seconds_to_sleep

def strategy_worker(bot_instance):

    bot_instance.log("Thread started. Syncing state...")
    bot_instance.run_cycle()
    
    while True:
        # Get the exact base time
        base_sleep = get_seconds_to_next_m15()
        
        # THE FIX: Add a random delay between 1 and 30 seconds
        jitter = random.uniform(1, 30)
        total_sleep = base_sleep + jitter
        
        bot_instance.log(f"Sleeping... Waking up in {total_sleep/60:.2f} minutes.")
        
        time.sleep(total_sleep)
        bot_instance.run_cycle()

def dispatcher_loop(ledger, notifier):
   
    print("[Dispatcher] Monitoring ledger for updates...")
    while True:
        # Check every 30 seconds for a change
        time.sleep(30) 

        if ledger.has_updates():
            print("[Dispatcher] Update detected! Sending ledger...")
            
            # 1. Generate the message
            message = ledger.get_ledger_with_history()
            
            # 2. Send the alert
            try:
                notifier.send_alert(message)
                # 3. Only mark as sent if Telegram actually accepted the message
                ledger.mark_all_as_sent()
            except Exception as e:
                print(f"[Dispatcher] Failed to send update: {e}")
        else:
            # Quietly log to terminal so you know it's alive
            # print("[Dispatcher] No new updates.") 
            pass

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

    # CLEAR DATA HERE ONCE, NOT IN THE WORKER
    ledger.clear_monthly_data()


    # 1. Instantiate the Stateless Services (Actuators/Sensors)
    # target_emails = os.getenv("TARGET_PHONE_EMAIL")
    
    db_client = OandaClient(
        api_token=os.getenv("API_TOKEN"), 
        account_id=os.getenv("ACCOUNT_ID")
    )
    
    raw_emails_string = os.getenv("TARGET_PHONE_EMAIL")
    email_list = raw_emails_string.split(",")

    # sms_client = SMSNotifier(
    #     sender_email=os.getenv("GMAIL_ADDRESS"),
    #     sender_password=os.getenv("GMAIL_APP_PASSWORD"),
    #     target_sms_email=email_list
    # )

    tms = TelegramNotifier( 
    token = os.getenv("TELEGRAM_API_TOKEN"), 
    chat_ids= os.getenv("GROUP_ID")
    )

    # tms= TelegramNotifier(token = os.getenv("TELEGRAM_API_TOKEN"), 
    # chat_ids= os.getenv("PERSONAL_ID"))

    

    # # 2. Instantiate the independent, stateful Strategy Agents
    # bots = [
    #     stoch_bollinger("AUD_CAD", db_client, sms_client),
    #     stoch_bollinger("EUR_USD", db_client, sms_client),
    #     stoch_bollinger("GBP_JPY", db_client, sms_client)
    # ]

    bots_names = db_client.getPairs()
    bots =[]

    for pair_name in  bots_names:
        bots.append(Stoch_Bolinger(pair_name, db_client, tms, ledger))
    

    # 5. Start the Master Dispatcher Thread
    dispatch_thread = threading.Thread(target=dispatcher_loop, args=(ledger, tms))
    dispatch_thread.daemon = True
    dispatch_thread.start()


    # 3. The Thread Spawner
    active_threads = []
    
    for bot in bots:
        # We create an OS-level thread for each currency pair.
        # target = the function to run. args = what to pass into that function.
        t = threading.Thread(target=strategy_worker, args=(bot,))
        
        # Daemon threads automatically die when you press Ctrl+C to kill the main program
        t.daemon = True 
        t.start()
        active_threads.append(t)
        
        # Slight stagger so we don't bombard the Oanda API with 10 concurrent requests
        time.sleep(1)

    print("All threads active. Engine is running.")

    # 4. Keep the main program alive
    try:
        while True:
            time.sleep(60) # The main thread just idles forever while the worker threads do the heavy lifting
    except KeyboardInterrupt:
        print("\n Shutting down engine...")