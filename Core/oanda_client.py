# import requests
# import json
# import pandas as pd

# class OandaClient:
   
#     def __init__(self, api_token, account_id, environment="practice"):
#         self._api_token = api_token
#         self.account_id = account_id
        
#         if environment == "practice":
#             self.base_url = "https://api-fxpractice.oanda.com"
#         else:
#             self.base_url = "https://api-fxtrade.oanda.com"
            
#         self.headers = {
#             "Authorization": f"Bearer {self._api_token}"
#         }

#         self._test_connection()
    

#     def _test_connection(self):
        
#         url = f"{self.base_url}/v3/accounts/{self.account_id}/summary"
#         try:
#             response = requests.get(url, headers=self.headers, timeout=10)

#             if response.status_code != 200:
#                raise ConnectionError(f"Oanda Connection Failed! Status: {response.status_code}. Response: {response.text}")

#         except requests.exceptions.RequestException as e:
#             # Catches physical internet disconnection (e.g., your WiFi is down)
#             raise SystemExit(f" Critical Network Failure: {e}")
    

    
#     def getPairs(self):

#         url =f"{self.base_url}/v3/accounts/{self.account_id}/instruments"

#         try:
#             r = requests.get(url, headers=self.headers, timeout=10)

#             if r.status_code == 200:
#                 data=r.json()
#                 instruments_list = data['instruments']
#                 pair_names=[item['name'] for item in instruments_list]
#                 return pair_names
#             else:
#                 raise Exception(f"Failed to fetch pairs. HTTP {r.status_code}")
               
#         except requests.exceptions.RequestException as e:
#             # Catches physical internet disconnection (e.g., your WiFi is down)
#             raise SystemExit(f" Critical Network Failure: {e}")



#     def get_candles(self,pair, granularity="M", count = 20):
        
#         params = {"count": count, "granularity":granularity}
#         url = f"{self.base_url}/v3/instruments/{pair}/candles"

#         try:

#             response = requests.get(url, headers=self.headers, params= params, timeout=10)
        
#         except requests.exceptions.RequestException as e:
#             print(f"[{pair}] Network disconnected! Cannot reach Oanda: {e}")
#             return None  # Return None so the Strategy knows to try again later

#         if response.status_code == 200:

#             candles = response.json().get('candles', [])
#             data_list = []

#             for c in candles:
#                 data_list.append({
#                     'Date': c['time'],
#                     'Open': float(c['mid']['o']),
#                     'High': float(c['mid']['h']),
#                     'Low': float(c['mid']['l']),
#                     'Close': float(c['mid']['c']),
#                     'Volume': int(c['volume']),
#                     'Complete': bool(c['complete'])   
#                 })

#             return pd.DataFrame(data_list)

#         else:
#             # Clean up the massive HTML dumps from 502/503 errors
#             # Removes newlines and grabs just the first 150 characters
#             clean_error = str(response.text).replace('\n', ' ').replace('\r', '')[:150]
            
#             # RAISE the exception to trigger the BaseStrategy backoff
#             raise Exception(f"HTTP {response.status_code}: {clean_error}...")
            
import logging
from typing import Optional

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# (connect_timeout, read_timeout) — separate so a slow DNS doesn't burn read budget
DEFAULT_TIMEOUT = (5, 15)


class OandaClient:
    def __init__(self, api_token, account_id, environment="practice"):
        self._api_token = api_token
        self.account_id = account_id

        if environment == "practice":
            self.base_url = "https://api-fxpractice.oanda.com"
        else:
            self.base_url = "https://api-fxtrade.oanda.com"

        # Single Session reused for every call. Big latency win for 68 pairs.
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self._api_token}",
            "Accept-Datetime-Format": "RFC3339",
            "User-Agent": "forex-bot/1.0",
        })

        # Automatic retry on 5xx (Oanda maintenance / gateway flakiness).
        # 429 included for rate-limit safety. POST not retried (we don't do POSTs here anyway).
        retry = Retry(
            total=3,
            backoff_factor=1.5,           # 0s, 1.5s, 3s, 4.5s
            status_forcelist=(502, 503, 504, 429),
            allowed_methods=("GET",),
            raise_on_status=False,         # let us inspect the final response ourselves
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Cache of pairs we've confirmed return 401 — skip them silently after the first hit.
        self._unauthorized_pairs: set[str] = set()

        self._test_connection()

    # ---------- internal ----------

    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        """Single GET helper. Raises ConnectionError on transport failure (caller can retry)."""
        try:
            return self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.RequestException as e:
            # Convert ALL transport errors to ConnectionError so callers (and the boot
            # retry loop in main.py) can handle them uniformly. NEVER raise SystemExit
            # from here — that would bypass the retry wrapper and kill the process.
            raise ConnectionError(f"Network error contacting Oanda: {e}") from e

    def _test_connection(self):
        url = f"{self.base_url}/v3/accounts/{self.account_id}/summary"
        response = self._get(url)
        if response.status_code != 200:
            raise ConnectionError(
                f"Oanda Connection Failed! Status: {response.status_code}. "
                f"Response: {response.text[:200]}"
            )
        log.info(f"Oanda connection OK (account {self.account_id})")

    # ---------- public ----------

    def getPairs(self) -> list[str]:
        url = f"{self.base_url}/v3/accounts/{self.account_id}/instruments"
        r = self._get(url)
        if r.status_code != 200:
            # Use ConnectionError so main.py's retry wrapper catches it consistently.
            raise ConnectionError(f"Failed to fetch pairs: HTTP {r.status_code}: {r.text[:200]}")

        instruments = r.json().get("instruments", [])
        # Filter to currency pairs only — skips CFDs, metals, indices that may
        # require separate authorization (this is what's likely behind your 401s).
        pairs = [i["name"] for i in instruments if i.get("type") == "CURRENCY"]
        log.info(f"Fetched {len(pairs)} tradable currency pairs from Oanda")
        return pairs

    def get_candles(self, pair: str, granularity: str = "M", count: int = 20) -> Optional[pd.DataFrame]:
        # Skip pairs we already know the account isn't authorized for.
        if pair in self._unauthorized_pairs:
            return None

        url = f"{self.base_url}/v3/instruments/{pair}/candles"
        params = {"count": count, "granularity": granularity}

        # Let ConnectionError propagate — BaseStrategy.fetch_candles distinguishes
        # transient (raise) from permanent (return None), and we need to preserve
        # that distinction here. Returning None for transport errors would cause
        # the strategy to silently skip the cycle instead of retrying.
        response = self._get(url, params=params)

        if response.status_code == 200:
            candles = response.json().get("candles", [])
            return pd.DataFrame([{
                "Date": c["time"],
                "Open": float(c["mid"]["o"]),
                "High": float(c["mid"]["h"]),
                "Low": float(c["mid"]["l"]),
                "Close": float(c["mid"]["c"]),
                "Volume": int(c["volume"]),
                "Complete": bool(c["complete"]),
            } for c in candles])

        # Permanent failures — don't trigger backoff in the strategy
        if response.status_code in (401, 403):
            if pair not in self._unauthorized_pairs:
                log.warning(f"[{pair}] HTTP {response.status_code} — account not authorized "
                            f"for this pair. Removing from active rotation.")
                self._unauthorized_pairs.add(pair)
            return None

        if response.status_code == 404:
            log.warning(f"[{pair}] HTTP 404 — instrument not found. Skipping.")
            self._unauthorized_pairs.add(pair)
            return None

        # Transient — let the strategy's backoff handle it
        clean_error = str(response.text).replace("\n", " ").replace("\r", "")[:150]
        raise Exception(f"HTTP {response.status_code}: {clean_error}...")

    def close(self):
        """Call this on shutdown to release the connection pool cleanly."""
        try:
            self.session.close()
        except Exception:
            pass

        




