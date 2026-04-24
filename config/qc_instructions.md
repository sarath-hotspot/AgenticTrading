# QuantConnect Code Instructions

Instructions for the experiment agent when writing and fixing QC Python algorithms.
Edit this file to add your own patterns, gotchas, and preferred coding style.

---

## Project Setup

```python
from AlgorithmImports import *
from datetime import timedelta

class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2024, 6, 30)
        self.set_cash(100000)

        # Futures — always use the returned symbol, not the constant
        # Add futures here

        # Attach indicators to the continuous symbol
        # Add indicators. 

        self.set_warm_up(20)

        # Train/test split
        total_days = (self.end_date - self.start_date).days
        self.train_end = self.start_date + timedelta(days=int(total_days * 0.7))
        self.predictions = []
```

## OnData Pattern

```python
def on_data(self, data):
    if self.is_warming_up:
        return
    if not self.rsi.is_ready:
        return
    # Always guard — data[sym] can be None
    if self.cl_sym not in data or data[self.cl_sym] is None:
        return
    price = self.securities[self.cl_sym].price
    if price == 0:
        return
    # Only record signals in out-of-sample period
    if self.time < self.train_end:
        return
    # Signal logic here
```

## Accuracy Reporting (required)

```python
def on_end_of_algorithm(self):
    correct = 0
    for pred in self.predictions:
        # Check if price moved >=1% in predicted direction within 60 bars
        # Use pred["price"] as baseline; pred["direction"] = 1 (long) or -1 (short)
        pass  # implement evaluation logic

    total = len(self.predictions)
    accuracy_pct = (correct / total * 100) if total > 0 else 0.0

    # REQUIRED — both lines
    self.set_runtime_statistic("accuracy_pct", str(round(accuracy_pct, 2)))
    self.set_runtime_statistic("total_predictions", str(total))
    self.log(f'{{"metric": "out_of_sample_accuracy", "accuracy_pct": {accuracy_pct}, "total_predictions": {total}}}')
```

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
