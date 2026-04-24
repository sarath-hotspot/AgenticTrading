# Domain Knowledge

---

## Energy Futures Basics

### QuantConnect setup
- Quant connect is a back testing engine, it sends data simulating the real timeline, this avoids algorithm from accessing future data and look ahead bias. 
- If algorithm want to keep track of 
- For front-month rolling use `DataNormalizationMode.BackwardsPanamaCanal`.
- Resolution options: Minute, Hour, Daily.
- Refer to https://www.quantconnect.com/docs/v2/writing-algorithms documentation for specs on how to write algorithm.


### Seasonality
- Natural gas prices tend to spike in winter (heating demand) and summer (power generation).
- Crude oil is sensitive to OPEC announcements and geopolitical events.

### Known signals to explore
- Volume spikes preceding large moves are documented in academic literature.
- RSI divergence at 30/70 levels has shown predictive value in commodities.
- Bollinger Band squeeze (low volatility) often precedes breakouts.
- EIA inventory reports (Wednesdays for crude, Thursdays for gas) drive 1%+ moves.
- Order flow gives signals about how market participants are responding to new events. 

### DSP techniques
- Apply FFT to identify dominant price cycles.
- Use a bandpass filter to isolate the 5-20 day cycle component.
- Wavelet transforms can separate signal from noise across multiple timescales.

---

## Your Notes
<!-- Add your own domain knowledge below this line -->
