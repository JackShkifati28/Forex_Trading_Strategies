import os
import requests
import json
import pandas as pd
import mplfinance as mpf
import pandas_ta as ta
import numpy
from datetime import date, timedelta

def getStocastic(df):
    
    # 1. Calculate Stochastic using pandas_ta
    # k=14, d=3, smooth_k=3 are the standard "Slow Stochastic" settings
    stoch_df = ta.stoch(high=df['High'], low=df['Low'], close=df['Close'], k=14, d=3, smooth_k=3)
   
    # 2. Add the results back to our main DataFrame
    #    pandas_ta returns columns like STOCHk_14_3_3 and STOCHd_14_3_3
    return pd.concat([df, stoch_df], axis=1)



API_TOKEN = "7efba9fb830aaa1178b54bf4b2899e4c-63d7c62edd2278c34e520190019add55"
ACCOUNT_ID = "101-001-38676409-001"


API_ENDPOINT= "https://api-fxpractice.oanda.com"


header = {"Authorization": f"Bearer {API_TOKEN}"}

quary = {"count":50 , "granularity": "M"}

inst = "AUD_CAD"
CANDLES_PATH = "/v3/instruments/AUD_CAD/candles"
url = f"{API_ENDPOINT}{CANDLES_PATH}"
# CANDLES_PATH = f"v3/Instruments/{inst}/candles"

response = requests.get(url, headers=header, params=quary)




# Print the status to help debug
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

    df = getStocastic(df)

    last_h = df['STOCHh_14_3_3'].iloc[-1]

    bias ="None"

    if last_h > 0:
        bias ="Momentium Direction Buying"
    elif last_h < 0:
        bias ="Momentium Direction Short"



    # 4. Format the Date so Matplotlib understands it
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)

    apds= [
    mpf.make_addplot(df['STOCHk_14_3_3'], panel=1, color='green', ylabel='Stoch (14,3,3)'),
    mpf.make_addplot(df['STOCHd_14_3_3'], panel=1, color='red')
    ]
    
    mpf.plot(
        df, 
         type='candle', 
         style='charles', 
         addplot=apds,
         title=f'{inst} Montly Stochastic',
         panel_ratios=(3, 1), # Makes the Candle chart 3 times taller than the Stochastic chart
         figratio=(12, 8),    # Overall window size
         tight_layout=True
    )


    # # 5. Plot it!
    # mpf.plot(df, type='candle', style='charles', 
    #         title=f'AUD_CAD {quary["granularity"]} Candles',
    #         ylabel='Price',
    #         volume=True)
#   print("Feb Candles:\n{}".format(json.dumps(response.json(), indent=2)))
    
else:
    print(f"Error {response.status_code}: {response.text}")
