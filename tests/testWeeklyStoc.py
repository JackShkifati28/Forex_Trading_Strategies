import os
# importing necessary functions from dotenv library
from dotenv import load_dotenv 
from Core.oanda_client import OandaClient
from Core.smsNotifier import TelegramNotifier
from Core.indicator import Indicator

def main():
    load_dotenv() 

    tms = TelegramNotifier( 
    token = os.getenv("TELEGRAM_API_TOKEN"), 
    chat_ids= os.getenv("ID")
    )


    db_client = OandaClient(
            api_token=os.getenv("API_TOKEN"), 
            account_id=os.getenv("ACCOUNT_ID")
        )
    
    df_weekly =db_client.get_candles("AUD_CAD", "W", 21)

    df = Indicator.stocastic(df_weekly)

    print(df)
    






if __name__ == "__main__":
    main()
