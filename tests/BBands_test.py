import os
import requests
import json
import pandas as pd
# import mplfinance as mpf
import pandas_ta as ta
import numpy
from datetime import date, timedelta
from dotenv import load_dotenv, dotenv_values 


load_dotenv() 

API_ENDPOINT = os.getenv("API_ENDPOINT")
API_TOKEN = os.getenv("API_TOKEN")


header = {"Authorization": f"Bearer {API_TOKEN}"}

quary = {"count":300 , "granularity": "H4"}

inst = "AUD_CAD"
CANDLES_PATH = "/v3/instruments/AUD_CAD/candles"
url = f"{API_ENDPOINT}{CANDLES_PATH}"

response = requests.get(url, headers=header, params=quary)

if response.status_code == 200:
    
    candles = response.json().get('candles', [])
    data_list = []

    for c in candles:
        data_list.append({
            'Date': c['time'],
            'Open': float(c['mid']['o']),
            'High': float(c['mid']['h']),
            'Low': float(c['mid']['l']),
            'Close': float(c['mid']['c']),
            'Volume': int(c['volume'])
        })

    # 3. Create a DataFrame
    df = pd.DataFrame(data_list)

    # Calculate Bollinger Bands
    df.ta.bbands(close='Close', length=30, std=2, append=True)
    df.dropna(inplace=True)

    print(df.tail(3))

    # df['Date'] = pd.to_datetime(df['Date'])
    # df.set_index('Date', inplace=True)

    # apds = [
    # # Layer 1: Bollinger Bands (On top of the candles, Panel 0)
    # mpf.make_addplot(df['BBU_20_2.0_2.0'], color='blue', width=2, linestyle='dashed'),
    # mpf.make_addplot(df['BBM_20_2.0_2.0'], color='blue', width=2, linestyle='dotted'),
    # mpf.make_addplot(df['BBL_20_2.0_2.0'], color='blue', width=2, linestyle='dashed')
    # ]

    # mpf.plot(
    #     df, 
    #      type='candle', 
    #      style='charles', 
    #      addplot=apds,
    #      title=f'{inst} 4 hour Bollinger Graph',
    #      figratio=(12, 8),    # Overall window size
    #      tight_layout=True
    # )


else:
    print(f"Error {response.status_code}: {response.text}")
