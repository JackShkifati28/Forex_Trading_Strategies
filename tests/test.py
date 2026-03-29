# importing os module for environment variables
import os
# importing necessary functions from dotenv library
from dotenv import load_dotenv, dotenv_values 
from Core.oanda_client import OandaClient
from Core.smsNotifier import TelegramNotifier
from Core.indicator import Indicator
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
from Core.visualizer import Visualizer
import sqlite3

def check_db():
    conn = sqlite3.connect("Logs/trading_ledger.db")
    
    print("=== ACTIVE ALERTS (CAD_CHF) ===")
    active = conn.execute("SELECT * FROM alerts WHERE pair='CAD_CHF'").fetchall()
    if not active:
        print("No active alerts found.")
    for row in active:
        print(f"Pair: {row[0]} | Signal: {row[1]} | Trend: {row[2]} | Time: {row[3]} | Sent: {row[4]}")
        
    print("\n=== SIGNAL HISTORY (CAD_CHF) ===")
    history = conn.execute("SELECT * FROM signal_history WHERE pair='CAD_CHF' ORDER BY id ASC").fetchall()
    if not history:
        print("No history found.")
    for row in history:
        print(f"ID: {row[0]} | Pair: {row[1]} | Signal: {row[2]} | Trend: {row[3]} | Activated: {row[4]} | Deactivated: {row[5]}")

# check_db()
# loading variables from .env file
load_dotenv() 


# raw_emails_string = os.getenv("TARGET_PHONE_EMAIL")
# email_list = raw_emails_string.split(",")

# ms_client = SMSNotifier(
#         sender_email=os.getenv("GMAIL_ADDRESS"),
#         sender_password=os.getenv("GMAIL_APP_PASSWORD"),
#         target_sms_email=email_list
#     )

tms = TelegramNotifier( 
    token = os.getenv("TELEGRAM_API_TOKEN"), 
    chat_ids= os.getenv("PERSONAL_ID")
    )





db_client = OandaClient(
        api_token=os.getenv("API_TOKEN"), 
        account_id=os.getenv("ACCOUNT_ID")
    )

check_db()


# df_monthly = db_client.get_candles("CAD_CHF", "H4", 180)

# print(df_monthly.head(20))

# df =Indicator.stocastic(df_monthly)
# Visualizer.plot_stoch(df, "CAD_JPY" ,"Monthly")


# df_4hour = db_client.get_candles("USD_CNH", "H4", 100)

# df = Indicator.bollinger(df_monthly)

# # value = df.loc[df['Date'] == '2026-03-17T13:00:00.000000000', 'BBB_30_2.0_2.0']

# print(df.tail(25))

# history_rows = conn.execute(
#                 "SELECT pair, signal, trend, deactivated_at FROM signal_history "
#                 "ORDER BY deactivated_at DESC LIMIT 10"
#             ).fetchall()


# Visualizer.plot_bollinger(df, "USD_CNH" ," Four Hour")



# df_4hour= db_client.get_candles("USD_CNH", "H4", 150)

# df = Indicator.bollinger(df_4hour)

# print(df.iloc[120])
   


# print(df_monthly.tail(10))



# df =Indicator.stocastic(df_monthly)

# k_monthly = df_monthly['STOCHk_14_3_3'].iloc[-2]
# d_monthly = df_monthly['STOCHd_14_3_3'].iloc[-2]



# print(datetime.now(timezone.utc))

# Define the NY timezone
# ny_tz = ZoneInfo("America/New_York")

# # # Get current time specifically for NY
# now_ny = datetime.now(ny_tz)

# currnt_date= f"Date: {now_ny.date():%m-%d-%Y}"
# currnt_time = f"Time: {now_ny.time():%H:%M:%S}"

# print(currnt_date)
# print(currnt_time)

# # Get the month as an integer (1-12)
# current_month = now_ny.month
# current_hour = now_ny.hour



# print(f"Current NY Month: {current_month}")
# print(f"Current NY Hour: {current_hour}")


tms.send_alert("Testing Message")



# bots_names = db_client.getPairs()

# print(bots_names)

 