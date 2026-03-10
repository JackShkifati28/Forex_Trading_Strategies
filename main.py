import os
import time
import threading
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import random 

from Core.oanda_client import OandaClient
from Core.smsNotifier import SMSNotifier
from strategies.stoch_bollinger import Stoch_Bolinger

def get_seconds_to_next_m15():
    """Calculates the exact seconds until the next 15-minute candle close (:00, :15, :30, :45)."""
    now = datetime.now(timezone.utc)
    
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
        
        bot_instance.log(f"Sleeping... Waking up in {total_sleep/3600:.2f} hours.")
        
        time.sleep(total_sleep)
        bot_instance.run_cycle()

if __name__ == "__main__":

    print("Booting Quantitative Engine...")

    load_dotenv()

    # 1. Instantiate the Stateless Services (Actuators/Sensors)
    # target_emails = os.getenv("TARGET_PHONE_EMAIL")
    
    db_client = OandaClient(
        api_token=os.getenv("API_TOKEN"), 
        account_id=os.getenv("ACCOUNT_ID")
    )
    
    raw_emails_string = os.getenv("TARGET_PHONE_EMAIL")
    email_list = raw_emails_string.split(",")

    sms_client = SMSNotifier(
        sender_email=os.getenv("GMAIL_ADDRESS"),
        sender_password=os.getenv("GMAIL_APP_PASSWORD"),
        target_sms_email=email_list
    )

    # # 2. Instantiate the independent, stateful Strategy Agents
    # bots = [
    #     stoch_bollinger("AUD_CAD", db_client, sms_client),
    #     stoch_bollinger("EUR_USD", db_client, sms_client),
    #     stoch_bollinger("GBP_JPY", db_client, sms_client)
    # ]

    bots_names = db_client.getPairs()
    bots =[]

    for pair_name in  bots_names:
        bots.append(Stoch_Bolinger(pair_name, db_client, sms_client))


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