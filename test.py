# importing os module for environment variables
import os
# importing necessary functions from dotenv library
from dotenv import load_dotenv, dotenv_values 
from Core.oanda_client import OandaClient
from Core.smsNotifier import SMSNotifier

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

ms_client.send_alert("Testing Message")





 