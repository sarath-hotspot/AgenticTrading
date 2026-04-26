# QuantConnect Code Instructions

Instructions for the experiment agent when writing and fixing QC Python algorithms.
Edit this file to add your own patterns, gotchas, and preferred coding style.

---
## High level algorithm structure 


from AlgorithmImports import *

class <AlgoName>(QCAlgorithm):
    def initialize(self):
        // start date and end date 
        // set cash
        // Add instruments 
        // Indicator initialization
        // Other initialization. 

    

## Common Errors and Fixes

- **`object has no attribute 'stoch'` or `'stochastic'`** → The Stochastic helper is `self.sto()`, NOT `self.stoch()` or `self.stochastic()`. Use `self.sto(sym, period, kPeriod, dPeriod, Resolution.Daily)`

- **`set_warm_up_period` does not exist** → use `self.set_warm_up(n)`
- **`'NoneType' object has no attribute 'close'`** → guard with `if sym not in data or data[sym] is None: return`
- **`'QuoteBar' object has no attribute 'volume'`** → QuoteBars don't have volume; use `Resolution.Daily` which gives TradeBars, or use `self.securities[sym].volume`
- **`on_hourly_data() takes 2 positional arguments but 3 were given`** → consolidator handlers need `def on_hourly_data(self, consolidator, bar):`
- **`File already exist in this project`** → retry with `is_update=True` on the upload
- **Indicators not updating** → make sure resolution passed to indicator matches the data resolution added to the algorithm

## Futures Gotchas

- Never pass `Futures.Energy.CrudeOilWTI` directly to an indicator — always use the symbol returned by `add_future`.
- The continuous contract (canonical symbol) is what LEAN feeds to attached indicators automatically.
- `self.securities[self.cl_sym].price` gives the front-month price at all times.
- Use `DataNormalizationMode.BackwardsPanamaCanal` if you need adjusted prices for indicators:
  ```python
  cl = self.add_future(Futures.Energy.CrudeOilWTI, dataNormalizationMode=DataNormalizationMode.BackwardsPanamaCanal)
  ```
