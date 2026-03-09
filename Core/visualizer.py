import mplfinance as mpf

class Visualizer:

    @staticmethod
    def plot_stoch(df, pair, granularity):
       
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
       
        apds= [
        mpf.make_addplot(df['STOCHk_14_3_3'], panel=1, color='green', ylabel='Stoch (14,3,3)'),
        mpf.make_addplot(df['STOCHd_14_3_3'], panel=1, color='red')
        ]

        pf.plot(
        df, 
         type='candle', 
         style='charles', 
         addplot=apds,
         title=f'{pair} {granularity} Stochastic',
         panel_ratios=(3, 1), # Makes the Candle chart 3 times taller than the Stochastic chart
         figratio=(12, 8),    # Overall window size
         tight_layout=True
    )

    @staticmethod
    def plot_bollinger(df, pair, granularity):
        
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)

        apds = [
        # Layer 1: Bollinger Bands (On top of the candles, Panel 0)
        mpf.make_addplot(df['BBU_20_2.0_2.0'], color='blue', width=2, linestyle='dashed'),
        mpf.make_addplot(df['BBM_20_2.0_2.0'], color='blue', width=2, linestyle='dotted'),
        mpf.make_addplot(df['BBL_20_2.0_2.0'], color='blue', width=2, linestyle='dashed')
        ]

        mpf.plot(
        df, 
         type='candle', 
         style='charles', 
         addplot=apds,
         title=f'{pair} {granularity} Bollinger Graph',
         figratio=(12, 8),    # Overall window size
         tight_layout=True
    )



