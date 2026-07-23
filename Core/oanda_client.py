
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
        url = f"{self.base_url}/v3/instruments/{pair}/candles"
        params = {"count": count, "granularity": granularity}

        # Let ConnectionError propagate — BaseStrategy.fetch_candles handles retries.
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

        # Anything non-200 is a problem — raise and let the strategy's backoff retry.
        clean = str(response.text).replace("\n", " ").replace("\r", "")[:150]
        raise Exception(f"HTTP {response.status_code} for {pair}: {clean}")

    def close(self):
        """Call this on shutdown to release the connection pool cleanly."""
        try:
            self.session.close()
        except Exception:
            pass

        




