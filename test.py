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

# loading variables from .env file
load_dotenv() 

# raw_emails_string = os.getenv("TARGET_PHONE_EMAIL")
# email_list = raw_emails_string.split(",")

# ms_client = SMSNotifier(
#         sender_email=os.getenv("GMAIL_ADDRESS"),
#         sender_password=os.getenv("GMAIL_APP_PASSWORD"),
#         target_sms_email=email_list
#     )

# tms = TelegramNotifier( 
#     token = os.getenv("TELEGRAM_API_TOKEN"), 
#     chat_ids= os.getenv("GROUP_ID")
#     )

# tms.send_alert("This is a test message")



db_client = OandaClient(
        api_token=os.getenv("API_TOKEN"), 
        account_id=os.getenv("ACCOUNT_ID")
    )



df_monthly = db_client.get_candles("CAD_JPY", "H4", 150)

# print(df_monthly.head(20))

# df =Indicator.stocastic(df_monthly)
# Visualizer.plot_stoch(df, "CAD_JPY" ,"Monthly")


# df_4hour = db_client.get_candles("USD_CNH", "H4", 100)

df = Indicator.bollinger(df_monthly)

print(df.head(10))


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

# # Get current time specifically for NY
# now_ny = datetime.now(ny_tz)

# # Get the month as an integer (1-12)
# current_month = now_ny.month
# current_hour = now_ny.hour



# print(f"Current NY Month: {current_month}")
# print(f"Current NY Hour: {current_hour}")


# ms_client.send_alert("Testing Message")





 