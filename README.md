# Forex: Quantitative Forex Trading Engine

A fully automated, multi-threaded algorithmic trading engine built in Python. Designed to interface directly with the Oanda v3 REST API, this system dynamically scans available forex pairs, processes historical market data, and executes a custom Stochastic Bollinger Band strategy across dozens of concurrent threads.

## 🚀 System Architecture & Key Features

* **Concurrent Execution:** Utilizes memory-isolated OS-level threads to monitor up to 70+ currency pairs simultaneously without blocking the main execution loop.
* **API Resilience & Rate Limit Handling:** Implements exponential backoff and randomized execution jitter to gracefully handle HTTP 429 (Too Many Requests) errors and prevent "Thundering Herd" API bottlenecks.
* **Dynamic Market Scanning:** Automatically queries the broker on boot to map available instruments, adapting instantly to broker-side additions or removals.
* **Precision Time Synchronization:** UTC-anchored sleep scheduling ensures the engine idles efficiently and wakes up at the exact millisecond of the 4-Hour candle close.
* **Asynchronous SMS Broadcasting:** Built-in SMTP notification system to broadcast real-time buy/sell signals and technical breakouts to an array of target phone numbers.
* **Stateless Actuators:** Database and notification clients are engineered as strictly stateless services, completely eliminating the need for thread-locking mechanisms (Mutexes).

## 📁 Directory Structure

    Forex/
    │
    ├── Core/
    │   ├── indicator.py        # Mathematical formulation for Bollinger Bands & Stochastics
    │   ├── oanda_client.py     # Resilient HTTP client for the Oanda v3 API
    │   ├── smsNotifier.py      # Multi-target SMTP broadcast engine
    │   └── visualizer.py       # Data visualization and charting tools
    │
    ├── strategies/
    │   ├── base_strategy.py    # Abstract base class for strategy inheritance
    │   └── stoch_bollinger.py  # Primary state-machine trading logic
    │
    ├── tests/                  # Unit tests and API connection verifications
    ├── main.py                 # The Thread Spawner and main application loop
    ├── .gitignore              # Security and environment exclusions
    └── README.md


## ⚙️ Installation & Setup

**1. Clone the repository**
```bash
git clone [https://github.com/JackShkifati28/Forex_Trading_Strategies.git](https://github.com/JackShkifati28/Forex_Trading_Strategies.git)
cd Forex_Trading_Strategies

**2. Create a virtual environment and install dependencies**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install requests pandas python-dotenv
```

**3. Environment Variable Configuration**
Create a `.env` file in the root directory. This file is explicitly ignored by Git to protect your API keys.

```text
# .env
API_TOKEN=your_oanda_v3_api_token
ACCOUNT_ID=your_oanda_account_id

# SMS Broadcasting Setup
GMAIL_ADDRESS=your.bot.email@gmail.com
GMAIL_APP_PASSWORD=your_16_digit_app_password
TARGET_PHONE_EMAILS=5551234567@vtext.com,5559876543@txt.att.net
```

## 📈 The Strategy: Stochastic Bollinger Ping-Pong

This engine currently runs a custom state-machine strategy designed to filter out market noise during heavy trends. 

1. **The Setup:** The engine monitors the Monthly timeframe for macro momentum direction.
2. **The Trigger:** On the 4-Hour timeframe, the bot tracks complete traversals of the Bollinger Band channel. 
3. **The Execution:** It strictly executes on the *first touch* of the opposing band that aligns with the macro momentum, inherently ignoring subsequent touches (market "hugging") until the price physically resets by crossing the entire channel again.

## ⚠️ Disclaimer

**This software is for educational and research purposes only.** Do not risk money which you are afraid to lose. USE AT YOUR OWN RISK. The authors and contributors assume no responsibility for your trading results. Always test algorithmic strategies on a paper-trading/demo account before deploying live capital.
