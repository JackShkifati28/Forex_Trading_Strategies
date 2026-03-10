# importing os module for environment variables
import os
# importing necessary functions from dotenv library
from dotenv import load_dotenv, dotenv_values 
from Core.oanda_client import OandaClient
from Core.smsNotifier import SMSNotifier
from Core.indicator import Indicator

import requests

# loading variables from .env file
load_dotenv() 

raw_emails_string = os.getenv("TARGET_PHONE_EMAIL")
email_list = raw_emails_string.split(",")

ms_client = SMSNotifier(
        sender_email=os.getenv("GMAIL_ADDRESS"),
        sender_password=os.getenv("GMAIL_APP_PASSWORD"),
        target_sms_email=email_list
    )

db_client = OandaClient(
        api_token=os.getenv("API_TOKEN"), 
        account_id=os.getenv("ACCOUNT_ID")
    )

df_monthly = db_client.get_candles("USD_CNH", "M", 20)

df =Indicator.stocastic(df_monthly)

k_monthly = df_monthly['STOCHk_14_3_3'].iloc[-2]
d_monthly = df_monthly['STOCHd_14_3_3'].iloc[-2]

print(k_monthly )
print(d_monthly)

# ms_client.send_alert("Testing Message")





 