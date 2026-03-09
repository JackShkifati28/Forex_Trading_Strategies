
import pandas_ta as ta

class Indicator:

    @staticmethod
    def stocastic(df, length = 14, d =3, k= 3):
        df.ta.stoch(high=df['High'], low=df['Low'], close=df['Close'], k=length, d=d, smooth_k =k, append=True)
        df.dropna(inplace=True)
        return df

    
    @staticmethod
    def bollinger(df,length =20, std=2 ):
        df.ta.bbands(close='Close', length=length, std=std, append=True)
        df.dropna(inplace=True)
        return df

