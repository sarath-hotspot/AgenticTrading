# Domain Instructions
- Use price and volume information to find patterns before big moves.
- Prediction accuracy must exceed 70% on a held-out out-of-sample test set.
- Trade only  between 9AM and 3PM EST. So that I do not have to put lof of margin for making trades.
- in QC algo code, place orders, and collect sharpie ratio and other metrics.

# Accuracy instructions
- For accuracy calculation use all events where there is 1% up or down events, and how many times we predicted correctly. 
- For recall calculation, measure for how many events we requested trades, and out of these how many were correct predictions.

# Data granularity
- Use multiple data granularities: minute, hourly.

# Exploration notes
- Apply Digital Signal Processing (DSP) techniques (FFT, wavelet transforms,
   bandpass filters) to remove noise and isolate signal.
- Backtest must cover at least 3 years of historical data.
- Avoid look-ahead bias — all features must be computed using only past data.
- Report Sharpe ratio, max drawdown, and win rate alongside accuracy.
- Each QuantConnect algorithm must be self-contained Python using the LEAN engine.
- The algorithm must log a JSON accuracy report using self.Log() so results can be parsed.
