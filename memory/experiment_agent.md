# QC Experiment Agent Learnings

## Seed — Always use snake_case (CRITICAL)
- LEAN Python fully supports snake_case aliases for all methods and properties.
- Use: `initialize`, `on_data`, `on_end_of_algorithm`, `set_start_date`, `set_end_date`, `set_cash`,
  `add_future`, `set_filter`, `set_warm_up`, `set_runtime_statistic`, `is_warming_up`,
  `is_ready`, `current.value`, `upper_band`, `lower_band`, `middle_band`, `signal`, `histogram`,
  `self.time`, `self.start_date`, `self.end_date`, `self.securities`, `self.log`
- Enums/constants stay as-is: `Resolution.Daily`, `Futures.Energy.CrudeOilWTI`
- NEVER use PascalCase method names like SetStartDate, AddFuture, OnData, IsWarmingUp, etc.

## Seed — Stochastic indicator method name
- Error: `object has no attribute 'stoch'` or `object has no attribute 'stochastic'`
- Fix: The LEAN snake_case helper is `self.sto()`, NOT `self.stoch()` or `self.stochastic()`.
- Correct usage: `self.cl_stoch = self.sto(self.cl_sym, 14, 3, 3, Resolution.Daily)`
- Value access: `.stoch_k.current.value` (fast %K) and `.stoch_d.current.value` (slow %D)

## Seed — set_warm_up method name
- Error: `'QCAlgorithm' object has no attribute 'set_warm_up_period'`
- Fix: The correct LEAN method is `self.set_warm_up(period)`, NOT `self.set_warm_up_period(period)`.
- Always use: `self.set_warm_up(50)` in initialize().

## Seed — QuoteBar has no Volume or IsReady
- Error: `'QuoteBar' object has no attribute 'Volume'` or `'QuoteBar' object has no attribute 'IsReady'`
- Cause: Futures OnData receives QuoteBars by default, not TradeBars. QuoteBar doesn't have .Volume or .IsReady.
- Fix: Use `data.Bars` to get TradeBars, or check `if symbol in data.Bars: bar = data.Bars[symbol]`.
  For futures with daily resolution, use `if self.cl_sym in data and data[self.cl_sym] is not None`.
  Alternatively subscribe with `Resolution.Daily` and access `data[self.cl_sym]` which gives a TradeBar.

## Seed — NoneType has no attribute Close
- Error: `'NoneType' object has no attribute 'Close'`
- Cause: `data[symbol]` returns None when that symbol has no data for the current bar.
- Fix: Always guard: `bar = data.get(self.cl_sym); if bar is None: return`

## Seed — Futures symbol usage
- Wrong: Passing `Futures.Energy.CrudeOilWTI` directly to indicators or AddConsolidator.
- Fix: Call `cl = self.add_future(Futures.Energy.CrudeOilWTI); cl.set_filter(0, 90)` then use `cl.symbol`
  everywhere. Example: `self.sma = self.sma(cl.symbol, 20, Resolution.Daily)`

## Seed — Consolidator callback signature
- Error: `on_hourly_data() takes 2 positional arguments but 3 were given`
- Cause: LEAN passes (consolidator, bar) to consolidator callbacks, not just (bar).
- Fix: Always define consolidator handlers as: `def on_hourly_data(self, consolidator, bar):`

## Seed — Do not create a new project for runtime error fixes
- Pattern: After getting a runtime error, agent creates a new project instead of fixing the existing one.
- Fix: When fixing a runtime error, always reuse the SAME project_id with `is_update=True`.
  Creating a new project wastes compile attempts and creates clutter.

## Seed — File already exists on first upload
- Error: `QC API error on /files/create: ['File already exist in this project']`
- Cause: QC auto-creates a main.py stub when a new project is created.
- Fix: Use `is_update=True` for the very first upload, or catch and retry with is_update=True.

## Seed — Continuous futures contract access
- The continuous futures symbol returned by add_future is a CANONICAL symbol.
- `self.securities[cl.symbol].price` gives the current price of the active front-month contract.
- Indicators attached to `cl.symbol` automatically receive continuous bar data.
- Do NOT try to look up individual expiry contracts like `CL 2021M21` — use the canonical symbol only.

## Seed — Accuracy reporting (REQUIRED pattern)
- At the end of the backtest in `on_end_of_algorithm`, ALWAYS call BOTH:
    self.set_runtime_statistic("accuracy_pct", str(round(accuracy_pct, 2)))
    self.log(f'{{"metric": "out_of_sample_accuracy", "accuracy_pct": {accuracy_pct}, "total_predictions": {total_predictions}}}')
- `set_runtime_statistic` puts the value in the API response so the engine can read it.
- `self.log` provides a fallback for the log-based extraction.

## Seed — Keep signal conditions simple (≤2 conditions)
- Complex multi-condition signals (3+ simultaneous conditions) almost never fire in historical data.
- Result: 0 trades, 0 predictions, accuracy = None.
- Fix: Use at most 2 conditions. Single-condition signals (RSI < 30, SMA crossover) work best.
- Aim for at least 15 signal events per year in the out-of-sample period.


## 2026-04-24 21:30 UTC — Runtime Error fix (attempt 1)
Error: [ERROR] FATAL UNHANDLED EXCEPTION:Engine.Run(): During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'Quant

Fix applied (see code diff).


## 2026-04-24 21:30 UTC — Runtime Error fix (attempt 2)
Error: [ERROR] FATAL UNHANDLED EXCEPTION:Engine.Run(): During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'Quant

Fix applied (see code diff).


## 2026-04-24 21:33 UTC — Runtime Error fix (attempt 1)
Error: During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'QuantConnect.Resolution'>) method. Please checkout th

Fix applied (see code diff).


## 2026-04-24 21:34 UTC — Runtime Error fix (attempt 2)
Error: During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'QuantConnect.Resolution'>) method. Please checkout th

Fix applied (see code diff).


## 2026-04-24 22:21 UTC — Runtime Error fix (attempt 1)
Error: During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'QuantConnect.Resolution'>) method. Please checkout th

Fix applied (see code diff).


## 2026-04-24 22:22 UTC — Runtime Error fix (attempt 2)
Error: During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'QuantConnect.Resolution'>) method. Please checkout th

Fix applied (see code diff).


## 2026-04-24 22:24 UTC — Runtime Error fix (attempt 1)
Error: During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'QuantConnect.Resolution'>) method. Please checkout th

Fix applied (see code diff).


## 2026-04-24 22:25 UTC — Runtime Error fix (attempt 2)
Error: During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'int'>) method. Please checkout the API documentation.

Fix applied (see code diff).


## 2026-04-24 22:26 UTC — Runtime Error fix (attempt 3)
Error: During the algorithm initialization, the following exception has occurred: Trying to dynamically access a method that does not exist throws a TypeError exception. To prevent the exception, ensure each parameter type matches those required by the 'QuantConnect.Resolution'>) method. Please checkout th

Fix applied (see code diff).
