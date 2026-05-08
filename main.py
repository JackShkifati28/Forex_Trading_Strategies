# import os
# import time
# import sys
# from concurrent.futures import ThreadPoolExecutor
# import concurrent.futures
# from datetime import datetime, timedelta
# from dotenv import load_dotenv
# from zoneinfo import ZoneInfo
# from Core.oanda_client import OandaClient
# from Core.smsNotifier import TelegramNotifier
# from strategies.stoch_bollinger import Stoch_Bolinger
# from Core.ledger import AlertLedger
# import glob

# # --- CONFIGURATION ---
# MAX_WORKERS = 10  # The benchmarked sweet spot!

# def get_seconds_to_next_m15():

#     """Calculates the exact seconds until the next 15-minute candle close (:00, :15, :30, :45)."""

#     ny_tz = ZoneInfo("America/New_York")
#     now = datetime.now(ny_tz)
    
#     # Calculate how many minutes until the next 15-minute boundary
#     minutes_to_next = 15 - (now.minute % 15)
    
#     # Create a datetime object for that exact future minute
#     next_run_time = now + timedelta(minutes=minutes_to_next)
#     next_run_time = next_run_time.replace(second=0, microsecond=0)
    
#     # Add a 5-second buffer to ensure Oanda has actually painted the new candle
#     seconds_to_sleep = (next_run_time - now).total_seconds() + 5
#     return max(seconds_to_sleep, 1.0)

# if __name__ == "__main__":

#     print("Booting Quantitative Engine...")

#     load_dotenv()

#     # --- NEW: Clear active logs on boot ---
#     print("Sweeping old active log files...")
#     # This finds all base .log files but leaves rotated backups untouched
#     for log_path in glob.glob("Logs/*.log"):
#         try:
#             os.remove(log_path)
#         except Exception as e:
#             print(f"Could not clear {log_path}: {e}")


#     ledger =AlertLedger()

#    # --- THE PRODUCTION-SAFE WIPE COMMAND ---
#     # Run the bot with: python main.py --wipe 
#     # Otherwise, it defaults to keeping your data safely intact.
#     if "--wipe" in sys.argv:
#         print("⚠️ '--wipe' flag detected. Purging all database records...")
#         ledger.clear_monthly_data()
#         # Optional: You could also add a command here to run a SQL query 
#         # to TRUNCATE your signal_history table so you don't get duplicates!
#         print("✅ Database cleared. Starting fresh.")
#     else:
#         print("💾 Booting with existing database records intact.")


#     # 1. Instantiate the Stateless Services (Actuators/Sensors)
#     # target_emails = os.getenv("TARGET_PHONE_EMAIL")
    
#     db_client = OandaClient(
#         api_token=os.getenv("API_TOKEN"), 
#         account_id=os.getenv("ACCOUNT_ID")
#     )
    
#     # raw_emails_string = os.getenv("TARGET_PHONE_EMAIL")
#     # email_list = raw_emails_string.split(",")

#     # sms_client = SMSNotifier(
#     #     sender_email=os.getenv("GMAIL_ADDRESS"),
#     #     sender_password=os.getenv("GMAIL_APP_PASSWORD"),
#     #     target_sms_email=email_list
#     # )

#     tms = TelegramNotifier( 
#     token = os.getenv("TELEGRAM_API_TOKEN"), 
#     chat_ids= os.getenv("GROUP_ID")
#     )

#     bots_names = db_client.getPairs()
#     bots = [Stoch_Bolinger(pair_name, db_client, tms, ledger) for pair_name in bots_names]

#     try:

#         while True:

#             start_time = time.time()
            
#             print(f"\n--- Starting Cycle at {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')} NY Time ---")
            
#             # --- THE THREAD POOL BARRIER ---
#             # This processes all 68 bots using 10 concurrent threads. 
#             # The script will pause here until EVERY bot finishes its run_cycle.
#             with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                
#                 future_to_bot = {executor.submit(bot.run_cycle): bot.pair for bot in bots}
                
#                 # as_completed allows us to process them as they finish and enforce a strict timeout
#                 for future in concurrent.futures.as_completed(future_to_bot, timeout=30):
#                     pair_name = future_to_bot[future]
#                     try:
#                         future.result() 
#                     except Exception as e:
#                         print(f"[{pair_name}] ⚠️ Engine caught an error and skipped this cycle: {e}")
            
#             execution_time = time.time() - start_time

#             print(f"✅ All {len(bots)} pairs completed in {execution_time:.2f} seconds.")

#             # --- MASTER DISPATCHER ---
#             # Because we waited for the ThreadPool to finish, we are 100% guaranteed
#             # that the database is completely synced before we check it.

#             print("[Dispatcher] Checking ledger for updates...")
            
#             if ledger.has_updates():
#                 print("[Dispatcher] Update detected! Sending unified ledger...")

#                 message = ledger.get_ledger_with_history()

#                 try:
#                     tms.send_alert(message)
#                     ledger.mark_all_as_sent()

#                 except Exception as e:
#                     print(f"[Dispatcher] Failed to send Telegram update: {e}")
#             else:
#                 print("[Dispatcher] No new updates.")

#             # --- PRECISION TIMING ---
#             sleep_seconds = get_seconds_to_next_m15()
#             print(f"⏳ Sleeping for {sleep_seconds / 60:.2f} minutes until the next candle...")
#             time.sleep(sleep_seconds)

#     except KeyboardInterrupt:
#         print("\n🛑 Shutting down engine cleanly...")

import os
import time
import sys
import logging
import glob
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from datetime import datetime, timedelta
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

from Core.oanda_client import OandaClient
from Core.smsNotifier import TelegramNotifier
from Core.ledger import AlertLedger
from strategies.stoch_bollinger import Stoch_Bolinger

# --- CONFIGURATION ---
MAX_WORKERS = 10
CYCLE_TIMEOUT = 60  # was 30 — too tight for 68 pairs when Oanda is sluggish
BOOT_RETRY_MAX_BACKOFF = 300  # cap retry backoff at 5 min

# --- LOGGING ---
# Configure ONCE here. Do NOT call logging.basicConfig or addHandler anywhere else
# (oanda_client.py, strategies, etc.) — that's what's causing your duplicate log lines.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("engine")


def get_seconds_to_next_m15():
    """Seconds until the next 15-minute candle close (:00, :15, :30, :45) + 5s buffer."""
    ny_tz = ZoneInfo("America/New_York")
    now = datetime.now(ny_tz)
    minutes_to_next = 15 - (now.minute % 15)
    next_run = (now + timedelta(minutes=minutes_to_next)).replace(second=0, microsecond=0)
    return max((next_run - now).total_seconds() + 5, 1.0)


def run_cycle(bots, max_workers, timeout):
    """
    Run every bot once, concurrently. Catches both per-bot exceptions AND the
    cycle-level TimeoutError so a slow Oanda response can't kill the engine.

    Returns the list of pairs that didn't finish in time (laggards).
    """
    laggards = []
    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        future_to_pair = {executor.submit(bot.run_cycle): bot.pair for bot in bots}

        try:
            for future in concurrent.futures.as_completed(future_to_pair, timeout=timeout):
                pair = future_to_pair[future]
                try:
                    future.result()
                except Exception as e:
                    log.warning(f"[{pair}] bot raised: {e}")
        except concurrent.futures.TimeoutError:
            # THE critical fix: catch the cycle timeout and continue.
            laggards = [future_to_pair[f] for f in future_to_pair if not f.done()]
            log.warning(
                f"Cycle timed out after {timeout}s — {len(laggards)}/{len(future_to_pair)} "
                f"unfinished: {laggards}"
            )
    finally:
        # wait=False + cancel_futures=True: don't block on laggards.
        # Already-running threads will finish in the background (Python can't kill threads),
        # but new cycles aren't blocked by them.
        executor.shutdown(wait=False, cancel_futures=True)
    return laggards


def connect_oanda_with_retry(api_token, account_id):
    """
    Don't let an Oanda 503 (maintenance window) crash the bot at boot.
    PM2 was restart-looping you because OandaClient.__init__ raised on 503.
    """
    backoff = 5
    while True:
        try:
            return OandaClient(api_token=api_token, account_id=account_id)
        except ConnectionError as e:
            log.warning(f"Oanda connect failed: {e} — retrying in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, BOOT_RETRY_MAX_BACKOFF)


if __name__ == "__main__":
    log.info("Booting Quantitative Engine...")
    load_dotenv()

    wipe = "--wipe" in sys.argv

    # Only nuke logs on explicit --wipe. Otherwise PM2 crash-loops would erase
    # the very logs you need to debug them.
    if wipe:
        log.info("Sweeping old active log files...")
        for log_path in glob.glob("Logs/*.log"):
            try:
                os.remove(log_path)
            except Exception as e:
                log.warning(f"Could not clear {log_path}: {e}")

    ledger = AlertLedger()

    if wipe:
        log.warning("'--wipe' flag detected. Purging all database records...")
        ledger.clear_monthly_data()
        log.info("Database cleared. Starting fresh.")
    else:
        log.info("Booting with existing database records intact.")

    db_client = connect_oanda_with_retry(
        api_token=os.getenv("API_TOKEN"),
        account_id=os.getenv("ACCOUNT_ID"),
    )

    tms = TelegramNotifier(
        token=os.getenv("TELEGRAM_API_TOKEN"),
        chat_ids=os.getenv("GROUP_ID"),
    )

    bots_names = db_client.getPairs()
    bots = [Stoch_Bolinger(name, db_client, tms, ledger) for name in bots_names]
    log.info(f"Loaded {len(bots)} pairs.")

    try:
        while True:
            start = time.time()
            now_ny = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
            log.info(f"--- Starting Cycle at {now_ny} NY Time ---")

            laggards = run_cycle(bots, MAX_WORKERS, CYCLE_TIMEOUT)

            elapsed = time.time() - start
            ok = len(bots) - len(laggards)
            log.info(f"Cycle finished in {elapsed:.2f}s — {ok}/{len(bots)} succeeded")

            log.info("[Dispatcher] Checking ledger for updates...")
            if ledger.has_updates():
                log.info("[Dispatcher] Update detected — sending unified ledger.")
                try:
                    tms.send_alert(ledger.get_ledger_with_history())
                    ledger.mark_all_as_sent()
                except Exception as e:
                    log.error(f"[Dispatcher] Failed to send Telegram update: {e}")
            else:
                log.info("[Dispatcher] No new updates.")

            sleep_seconds = get_seconds_to_next_m15()
            log.info(f"Sleeping {sleep_seconds / 60:.2f} min until next candle...")
            time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        log.info("Shutting down engine cleanly...")