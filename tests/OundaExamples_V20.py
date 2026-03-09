# get a list of trades
from oandapyV20 import API
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.instruments as instruments
import json

api = API(access_token="7efba9fb830aaa1178b54bf4b2899e4c-63d7c62edd2278c34e520190019add55")
accountID = "101-001-38676409-001"


""" --------------------------------------------------------------- """
# Example get the trade list

r = trades.TradesList(accountID)
# show the endpoint as it is constructed for this call
# print("REQUEST:{}".format(r))
rv = api.request(r)
# print("RESPONSE:\n{}".format(json.dumps(rv, indent=2)))

""" --------------------------------------------------------------- """

# Getting Prices 

params ={"instruments": "EUR_USD,EUR_JPY"}
p = pricing.PricingInfo(accountID=accountID, params=params)
rp = api.request(p)
# print(type(rp))
# print("Price:\n{}".format(json.dumps(rp, indent=2)))

""" --------------------------------------------------------------- """

params2 = {"count":30, "granularity": "M2"}
c= instruments.InstrumentsCandles(instrument="AUD_CAD", params=params2)
rc=api.request(c)
print("Feb Candles:\n{}".format(json.dumps(rp, indent=2)))
