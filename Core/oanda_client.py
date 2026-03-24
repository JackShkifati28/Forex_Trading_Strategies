import requests
import json
import pandas as pd

class OandaClient:
   
    def __init__(self, api_token, account_id, environment="practice"):
        self._api_token = api_token
        self.account_id = account_id
        
        if environment == "practice":
            self.base_url = "https://api-fxpractice.oanda.com"
        else:
            self.base_url = "https://api-fxtrade.oanda.com"
            
        self.headers = {
            "Authorization": f"Bearer {self._api_token}"
        }

        self._test_connection()
    

    def _test_connection(self):
        
        url = f"{self.base_url}/v3/accounts/{self.account_id}/summary"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code != 200:
               raise ConnectionError(f"Oanda Connection Failed! Status: {response.status_code}. Response: {response.text}")

        except requests.exceptions.RequestException as e:
            # Catches physical internet disconnection (e.g., your WiFi is down)
            raise SystemExit(f" Critical Network Failure: {e}")
    

    
    def getPairs(self):

        url =f"{self.base_url}/v3/accounts/{self.account_id}/instruments"

        try:
            r = requests.get(url, headers=self.headers, timeout=10)

            if r.status_code == 200:
                data=r.json()
                instruments_list = data['instruments']
                pair_names=[item['name'] for item in instruments_list]
                return pair_names
            else:
                raise Exception(f"Failed to fetch pairs. HTTP {r.status_code}")
               
        except requests.exceptions.RequestException as e:
            # Catches physical internet disconnection (e.g., your WiFi is down)
            raise SystemExit(f" Critical Network Failure: {e}")



    def get_candles(self,pair, granularity="M", count = 20):
        
        params = {"count": count, "granularity":granularity}
        url = f"{self.base_url}/v3/instruments/{pair}/candles"

        try:

            response = requests.get(url, headers=self.headers, params= params, timeout=10)
        
        except requests.exceptions.RequestException as e:
            print(f"[{pair}] Network disconnected! Cannot reach Oanda: {e}")
            return None  # Return None so the Strategy knows to try again later

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

            return pd.DataFrame(data_list)

        else:
            # Clean up the massive HTML dumps from 502/503 errors
            # Removes newlines and grabs just the first 150 characters
            clean_error = str(response.text).replace('\n', ' ').replace('\r', '')[:150]
            
            # RAISE the exception to trigger the BaseStrategy backoff
            raise Exception(f"HTTP {response.status_code}: {clean_error}...")
            

        





    