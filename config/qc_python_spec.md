# QuantConnect LEAN Python API — Compact Reference

*Fetched from QuantConnect docs 2026-04-24. Sections marked [VERIFY] may need cross-checking against live docs or LEAN source.*

---

## 1. General Conventions

- All C# `PascalCase` methods map to Python `snake_case` (e.g., `SetStartDate` → `set_start_date`).
- All QCAlgorithm helper methods are called as `self.<method>(...)`.
- Indicators created via helper methods **auto-update** with live data; indicators created via constructors must be manually `update()`d.
- Always check `indicator.is_ready` before using `.current.value`.
- Most indicator helpers accept an optional `resolution` parameter (e.g., `Resolution.DAILY`) to control consolidation.

---

## 2. Initialization Methods (`initialize()`)

### Date & Time
```python
self.set_start_date(year: int, month: int, day: int) -> None
self.set_end_date(year: int, month: int, day: int) -> None
self.set_time_zone(timezone: str) -> None          # e.g., "America/New_York"
```

### Cash & Account
```python
self.set_cash(amount: float) -> None
self.set_cash(currency: str, amount: float) -> None   # multi-currency
self.set_account_currency(currency: str, quantity: float = 100000) -> None
```

### Brokerage & Reality Models
```python
self.set_brokerage_model(brokerage: BrokerageModel, account_type: AccountType = AccountType.MARGIN) -> None
self.set_security_initializer(func: Callable) -> None   # replaces default initializer
self.add_security_initializer(func: Callable) -> None   # extends default initializer
```

### Benchmark & Warm-Up
```python
self.set_benchmark(ticker_or_func) -> None
self.set_warm_up(period: int | timedelta, resolution: Resolution = None) -> None
# e.g., self.set_warm_up(200, Resolution.DAILY)
# e.g., self.set_warm_up(timedelta(days=200))
```

### Misc
```python
self.set_name(name: str) -> None
self.settings.automatic_indicator_warm_up = True   # auto-warm all indicators
self.universe_settings.resolution = Resolution.MINUTE
```

---

## 3. Data Subscriptions

### Equities
```python
self.add_equity(
    ticker: str,
    resolution: Resolution = Resolution.MINUTE,
    market: str = Market.USA,
    fill_forward: bool = True,
    leverage: float = None,
    extended_market_hours: bool = False,
    data_normalization_mode: DataNormalizationMode = DataNormalizationMode.ADJUSTED
) -> Equity
# Returns Equity object; use .symbol property
# symbol = self.add_equity("SPY", Resolution.DAILY).symbol
```

### Futures
```python
self.add_future(
    ticker: str,                     # e.g., Futures.Indices.SP500EMini
    resolution: Resolution = Resolution.MINUTE,
    market: str = None,
    fill_forward: bool = True,
    leverage: float = 1.0,
    extended_market_hours: bool = False,
    data_mapping_mode: DataMappingMode = None,
    data_normalization_mode: DataNormalizationMode = None,
    contract_depth_offset: int = 0   # 0=front month, 1=back month, etc.
) -> Future

self.add_future_contract(symbol: Symbol, resolution: Resolution = None) -> Future

# After add_future(), call set_filter on the returned object:
future = self.add_future(Futures.Indices.SP500EMini, Resolution.MINUTE)
future.set_filter(min_expiry: int, max_expiry: int) -> None
future.set_filter(func: Callable[[FutureFilterUniverse], FutureFilterUniverse]) -> None
# e.g., future.set_filter(0, 90)   # contracts expiring 0–90 days out
# e.g., future.set_filter(lambda u: u.front_month())
```

### Options
```python
self.add_option(
    ticker: str,
    resolution: Resolution = Resolution.MINUTE,
    market: str = Market.USA,
    fill_forward: bool = True,
    leverage: float = None
) -> Option

option.set_filter(func: Callable[[OptionFilterUniverse], OptionFilterUniverse]) -> None
# e.g., option.set_filter(lambda u: u.strikes(-5, 5).expiration(0, 30))
```

### Other Asset Classes
```python
self.add_forex(pair: str, resolution: Resolution = Resolution.MINUTE, market: str = Market.OANDA) -> Forex
self.add_crypto(ticker: str, resolution: Resolution = Resolution.MINUTE, market: str = Market.COINBASE) -> Crypto
self.add_cfd(ticker: str, resolution: Resolution = Resolution.MINUTE) -> Cfd
self.add_index(ticker: str, resolution: Resolution = Resolution.MINUTE) -> Index
self.add_data(data_type: Type, name: str, resolution: Resolution) -> Security
self.remove_security(symbol: Symbol) -> bool
```

### Universes
```python
self.add_universe(universe_selector: Universe) -> Universe
self.add_universe(func: Callable[[IEnumerable[Fundamental]], IEnumerable[Symbol]]) -> Universe
```

---

## 4. Key Properties

```python
self.time                    # datetime — current algorithm time
self.start_date              # datetime — backtest start
self.end_date                # datetime — backtest end
self.is_warming_up           # bool — True during warm-up period
self.live_mode               # bool — True in live trading
self.portfolio               # SecurityPortfolioManager
self.securities              # SecurityManager — dict-like {symbol: Security}
self.transactions            # SecurityTransactionManager
self.insights                # InsightManager [VERIFY]
self.benchmark               # IBenchmark
self.brokerage_model         # IBrokerageModel
self.date_rules              # DateRules
self.time_rules              # TimeRules
self.resolution              # Resolution (default subscription resolution) [VERIFY]
```

### Portfolio Properties (`self.portfolio`)
```python
self.portfolio.total_portfolio_value   # float — cash + holdings market value
self.portfolio.cash                    # float — available cash
self.portfolio.invested                # bool — True if any positions open
self.portfolio.total_margin_used       # float
self.portfolio.margin_remaining        # float
self.portfolio.total_net_profit        # float — realized P&L
self.portfolio.total_unrealised_profit # float — unrealized P&L
self.portfolio.total_fees              # float
self.portfolio.get_buying_power(symbol, order_direction)  # float
```

### SecurityHolding Properties (`self.portfolio[symbol]`)
```python
self.portfolio[symbol].quantity            # float — position size (+long, -short)
self.portfolio[symbol].invested            # bool
self.portfolio[symbol].is_long             # bool
self.portfolio[symbol].is_short            # bool
self.portfolio[symbol].unrealized_profit   # float
self.portfolio[symbol].holdings_cost       # float — cost basis
self.portfolio[symbol].average_price       # float — weighted average entry
self.portfolio[symbol].last_trade_profit   # float [VERIFY]
```

---

## 5. Order Methods

### Placement
```python
self.market_order(symbol, quantity: float, asynchronous: bool = False, tag: str = None) -> OrderTicket
self.limit_order(symbol, quantity: float, limit_price: float, tag: str = None) -> OrderTicket
self.stop_market_order(symbol, quantity: float, stop_price: float, tag: str = None) -> OrderTicket
self.stop_limit_order(symbol, quantity: float, stop_price: float, limit_price: float, tag: str = None) -> OrderTicket
self.market_on_open_order(symbol, quantity: float, tag: str = None) -> OrderTicket
self.market_on_close_order(symbol, quantity: float, tag: str = None) -> OrderTicket
self.trailing_stop_order(symbol, quantity: float, trailing_amount: float, trailing_as_percentage: bool = False) -> OrderTicket
self.limit_if_touched_order(symbol, quantity: float, trigger_price: float, limit_price: float) -> OrderTicket
self.buy(symbol, quantity: float) -> OrderTicket
self.sell(symbol, quantity: float) -> OrderTicket
self.order(symbol, quantity: float, tag: str = None) -> OrderTicket
```

### Position Sizing
```python
self.set_holdings(symbol, weight: float, liquidate_existing_holdings: bool = False, tag: str = "") -> None
self.set_holdings(targets: List[PortfolioTarget], liquidate_existing_holdings: bool = False) -> None
self.calculate_order_quantity(symbol, target_weight: float) -> float
self.liquidate(symbol=None, tag: str = "Liquidated") -> List[OrderTicket]
# symbol=None liquidates entire portfolio
```

### OrderTicket Properties & Methods
```python
ticket.order_id            # int
ticket.symbol              # Symbol
ticket.quantity            # float
ticket.quantity_filled     # float
ticket.average_fill_price  # float
ticket.status              # OrderStatus enum
ticket.time                # datetime
ticket.limit_price         # float (limit orders)
ticket.stop_price          # float (stop orders)
ticket.cancel(comment: str = None) -> OrderResponse
ticket.update(fields: UpdateOrderFields) -> OrderResponse
ticket.update_limit_price(limit_price: float) -> OrderResponse
ticket.update_quantity(quantity: float) -> OrderResponse
ticket.update_stop_price(stop_price: float) -> OrderResponse
ticket.update_tag(tag: str) -> OrderResponse
ticket.get_most_recent_order_response() -> OrderResponse
```

---

## 6. Scheduled Events

```python
self.schedule.on(date_rule, time_rule, callback: Callable) -> ScheduledEvent
```

### DateRules
```python
self.date_rules.every_day()
self.date_rules.every_day(symbol)
self.date_rules.every(days: int)
self.date_rules.on(year, month, day)
self.date_rules.on(dates: List[datetime])
self.date_rules.week_start(days_offset: int = 0)
self.date_rules.week_start(symbol, days_offset: int = 0)
self.date_rules.week_end(days_offset: int = 0)
self.date_rules.week_end(symbol, days_offset: int = 0)
self.date_rules.month_start(days_offset: int = 0)
self.date_rules.month_start(symbol, days_offset: int = 0)
self.date_rules.month_end(days_offset: int = 0)
self.date_rules.month_end(symbol, days_offset: int = 0)
self.date_rules.year_start(days_offset: int = 0)
self.date_rules.year_end(days_offset: int = 0)
self.date_rules.today
self.date_rules.tomorrow
```

### TimeRules
```python
self.time_rules.at(hour: int, minute: int, second: int = 0) -> TimeRule
self.time_rules.at(hour, minute, second, time_zone) -> TimeRule
self.time_rules.every(interval: timedelta) -> TimeRule
self.time_rules.after_market_open(symbol, minutes_after_open: float = 0, extended_market_open: bool = False)
self.time_rules.before_market_open(symbol, minutes_before_open: float = 0, extended_market_open: bool = False)
self.time_rules.after_market_close(symbol, minutes_after_close: float = 0, extended_market_open: bool = False)
self.time_rules.before_market_close(symbol, minutes_before_close: float = 0, extended_market_open: bool = False)
self.time_rules.midnight
self.time_rules.noon
self.time_rules.now
```

---

## 7. Historical Data

```python
# By bar count
history = self.history(TradeBar, symbol, periods: int, resolution: Resolution = None)
history = self.history(TradeBar, symbols: List[Symbol], periods: int, resolution: Resolution = None)

# By timedelta
history = self.history(TradeBar, symbol, span: timedelta, resolution: Resolution = None)

# By date range
history = self.history(TradeBar, symbol, start: datetime, end: datetime, resolution: Resolution = None)

# Advanced (all options)
history = self.history(
    symbols,
    start: datetime,
    end: datetime,
    resolution: Resolution = None,
    fill_forward: bool = True,
    extended_market_hours: bool = False,
    data_mapping_mode: DataMappingMode = None,
    data_normalization_mode: DataNormalizationMode = None,
    contract_depth_offset: int = 0
)

# Returns pandas DataFrame indexed by (symbol, time)
# Common access patterns:
closes = self.history(symbols, 252, Resolution.DAILY).close.unstack(0).dropna()
returns = closes.pct_change().dropna()

# Single symbol shorthand
bars = self.history(symbol, 20, Resolution.DAILY)   # returns DataFrame
```

---

## 8. Logging & Output

```python
self.log(message: str) -> None                      # written to log file
self.debug(message: str) -> None                    # debug output (backtest only)
self.error(message: str) -> None                    # error log [VERIFY]
self.plot(chart: str, series: str, value: float) -> None
self.plot(chart: str, indicator) -> None            # auto-plots all sub-series
self.record(key: str, value: float) -> None         # adds to chart output
self.set_runtime_statistic(key: str, value: str) -> None  # shows in summary stats
```

---

## 9. Indicator Shorthand Methods

### General Signature Pattern
```python
self.<indicator>(symbol, <period_params>, [resolution: Resolution], [field: Field]) -> IndicatorBase
```
- `resolution` — if provided, a consolidator is created automatically
- `field` — selects which price field to feed (e.g., `Field.CLOSE`, `Field.VOLUME`)
- All return auto-updating indicator objects
- Access value: `.current.value`
- Check readiness: `.is_ready`

---

### Moving Averages

| Method | Parameters | Value Access | Notes |
|--------|-----------|--------------|-------|
| `self.sma(symbol, period)` | symbol, period: int | `.current.value` | Simple MA |
| `self.ema(symbol, period, [smoothing_scale])` | symbol, period: int, smoothing_scale: float | `.current.value` | Exponential MA |
| `self.dema(symbol, period)` | symbol, period: int | `.current.value` | Double EMA |
| `self.tema(symbol, period)` | symbol, period: int | `.current.value` | Triple EMA |
| `self.hma(symbol, period)` | symbol, period: int | `.current.value` | Hull MA |
| `self.kama(symbol, period)` | symbol, period: int | `.current.value` | Kaufman Adaptive MA |
| `self.lwma(symbol, period)` | symbol, period: int | `.current.value` | Linear Weighted MA |
| `self.alma(symbol, period, sigma, offset)` | symbol, period, sigma, offset | `.current.value` | Arnaud Legoux MA |
| `self.mama(symbol, fast_limit, slow_limit)` | symbol, fast_limit, slow_limit | `.current.value` | Mesa Adaptive MA |
| `self.tma(symbol, period)` | symbol, period: int | `.current.value` | Triangular MA |
| `self.vwma(symbol, period)` | symbol, period: int | `.current.value` | Volume Weighted MA |
| `self.wilder_moving_average(symbol, period)` | symbol, period: int | `.current.value` | Wilder Smoothed MA |
| `self.zema(symbol, period)` | symbol, period: int | `.current.value` | Zero-Lag EMA |
| `self.frama(symbol, period)` | symbol, period: int | `.current.value` | Fractal Adaptive MA |
| `self.t3(symbol, period, volume_factor)` | symbol, period, volume_factor | `.current.value` | T3 MA |
| `self.vidya(symbol, period, slow_period)` | symbol, period, slow_period | `.current.value` | Variable Index Dynamic Avg |
| `self.trix(symbol, period)` | symbol, period: int | `.current.value` | Triple EMA oscillator |
| `self.lsma(symbol, period)` | symbol, period: int | `.current.value` | Least Squares MA |

---

### Momentum & Oscillators

#### RSI
```python
self.rsi(symbol, period: int) -> RelativeStrengthIndex
# Access:
indicator.current.value                  # RSI value (0–100)
indicator.average_gain.current.value
indicator.average_loss.current.value
```

#### MACD
```python
self.macd(symbol, fast_period: int, slow_period: int, signal_period: int,
          moving_average_type: MovingAverageType = MovingAverageType.EXPONENTIAL) -> MovingAverageConvergenceDivergence
# Access:
indicator.current.value                  # MACD line (fast - slow)
indicator.fast.current.value             # fast MA
indicator.slow.current.value             # slow MA
indicator.signal.current.value           # signal line
indicator.histogram.current.value        # MACD - signal
```

#### Stochastic
```python
self.sto(symbol, k_period: int, k_slowing_period: int, d_period: int) -> Stochastic
# Access:
indicator.stoch_k.current.value          # slow %K
indicator.stoch_d.current.value          # slow %D
indicator.fast_stoch.current.value       # fast %K
```

#### Other Momentum Indicators

| Method | Parameters | Value Access |
|--------|-----------|--------------|
| `self.mom(symbol, period)` | symbol, period: int | `.current.value` — n-period price change |
| `self.roc(symbol, period)` | symbol, period: int | `.current.value` — (v0-vn)/vn |
| `self.rocp(symbol, period)` | symbol, period: int | `.current.value` — ROC percent |
| `self.rocr(symbol, period)` | symbol, period: int | `.current.value` — ROC ratio |
| `self.momp(symbol, period)` | symbol, period: int | `.current.value` |
| `self.willr(symbol, period)` | symbol, period: int | `.current.value` (-100 to 0) |
| `self.wilr(symbol, period)` | symbol, period: int | `.current.value` (alias) |
| `self.cci(symbol, period, moving_average_type)` | symbol, period, MAType | `.current.value` |
| `self.cmo(symbol, period)` | symbol, period: int | `.current.value` |
| `self.uo(symbol, period1, period2, period3)` | symbol, 3 periods | `.current.value` |
| `self.ao(symbol)` | symbol | `.current.value` — Awesome Oscillator |
| `self.bop(symbol)` | symbol | `.current.value` — Balance of Power |
| `self.demarker(symbol, period)` | symbol, period: int | `.current.value` |
| `self.dpo(symbol, period)` | symbol, period: int | `.current.value` |
| `self.kst(symbol, ...)` | symbol, multiple periods | `.current.value` |
| `self.stoch_rsi(symbol, period, rsi_period, k_period, d_period)` | symbol, periods | `.k.current.value`, `.d.current.value` [VERIFY] |
| `self.rvi(symbol, period)` | symbol, period: int | `.current.value` — Relative Vigor Index |
| `self.pso(symbol, period)` | symbol, period: int | `.current.value` — Premier Stochastic |
| `self.apo(symbol, fast_period, slow_period, moving_average_type)` | symbol, periods, MAType | `.current.value` |
| `self.ppo(symbol, fast_period, slow_period, moving_average_type)` | symbol, periods, MAType | `.current.value` |
| `self.momersion(symbol, min_period, full_period)` | symbol, periods | `.current.value` |

---

### Volatility Indicators

#### Bollinger Bands
```python
self.bb(symbol, period: int, standard_deviations: float,
        moving_average_type: MovingAverageType = MovingAverageType.SIMPLE) -> BollingerBands
# Access:
indicator.upper_band.current.value
indicator.middle_band.current.value
indicator.lower_band.current.value
indicator.bandwidth.current.value        # (upper - lower) / middle [VERIFY]
indicator.percent_b.current.value        # (price - lower) / (upper - lower) [VERIFY]
```

#### ATR
```python
self.atr(symbol, period: int,
         moving_average_type: MovingAverageType = MovingAverageType.SIMPLE) -> AverageTrueRange
# Access:
indicator.current.value                  # ATR value
indicator.true_range.current.value       # raw True Range
```

#### Keltner Channels
```python
self.kch(symbol, period: int, offset_multiplier: float,
         moving_average_type: MovingAverageType = MovingAverageType.SIMPLE) -> KeltnerChannels
# Access:
indicator.upper_band.current.value
indicator.middle_band.current.value
indicator.lower_band.current.value
indicator.average_true_range.current.value
```

#### Donchian Channel
```python
self.dch(symbol, period_high: int, period_low: int) -> DonchianChannel
# Access:
indicator.upper_band.current.value       # highest high over period_high
indicator.lower_band.current.value       # lowest low over period_low
indicator.current.value                  # midpoint (mean of upper & lower)
```

#### Other Volatility

| Method | Parameters | Value Access |
|--------|-----------|--------------|
| `self.natr(symbol, period)` | symbol, period: int | `.current.value` |
| `self.std_dev(symbol, period)` | symbol, period: int | `.current.value` |
| `self.rs_volatility(symbol, period)` | symbol, period: int | `.current.value` — Rogers-Satchell |
| `self.chop(symbol, period)` | symbol, period: int | `.current.value` — Choppiness Index |
| `self.variance(symbol, period)` | symbol, period: int | `.current.value` |

---

### Trend Indicators

#### ADX
```python
self.adx(symbol, period: int) -> AverageDirectionalIndex
# Access:
indicator.current.value                              # ADX strength (0–100)
indicator.positive_directional_index.current.value   # +DI
indicator.negative_directional_index.current.value   # -DI
```

#### Aroon
```python
self.aroon(symbol, period1: int, period2: int) -> AroonOscillator
# Access:
indicator.aroon_up.current.value
indicator.aroon_down.current.value
indicator.current.value                  # oscillator (up - down)
```

#### Other Trend

| Method | Parameters | Value Access |
|--------|-----------|--------------|
| `self.psar(symbol, af_start, af_increment, af_max)` | symbol, floats | `.current.value` — Parabolic SAR |
| `self.ichimoku(symbol, tenkan, kijun, senkou_a_max, senkou_b_max, senkou_a_period, senkou_b_period)` | symbol, periods | see sub-properties [VERIFY] |
| `self.supertrend(symbol, period, multiplier)` | symbol, period, float | `.current.value` |
| `self.vortex(symbol, period)` | symbol, period: int | `.vortex_movement_positive.current.value`, `.vortex_movement_negative.current.value` |
| `self.schaff_trend_cycle(symbol, period, fast_period, slow_period)` | symbol, periods | `.current.value` |

---

### Volume Indicators

| Method | Parameters | Value Access |
|--------|-----------|--------------|
| `self.obv(symbol)` | symbol | `.current.value` — On Balance Volume |
| `self.ad(symbol)` | symbol | `.current.value` — Accumulation/Distribution |
| `self.adosc(symbol, fast_period, slow_period)` | symbol, periods | `.current.value` — AD Oscillator |
| `self.cmf(symbol, period)` | symbol, period: int | `.current.value` — Chaikin Money Flow |
| `self.mfi(symbol, period)` | symbol, period: int | `.current.value` — Money Flow Index |
| `self.force_index(symbol, period)` | symbol, period: int | `.current.value` |
| `self.eom(symbol, period)` | symbol, period: int | `.current.value` — Ease of Movement |
| `self.kvo(symbol, fast_period, slow_period)` | symbol, periods | `.current.value` — Klinger Volume Oscillator |
| `self.sobv(symbol, period)` | symbol, period: int | `.current.value` — Smoothed OBV |
| `self.vp(symbol, period)` | symbol, period: int | `.current.value` — Volume Profile [VERIFY] |
| `self.intraday_vwap(symbol)` | symbol | `.current.value` — intraday VWAP only |

---

### Statistical Indicators

| Method | Parameters | Value Access |
|--------|-----------|--------------|
| `self.correlation(symbol1, symbol2, period)` | 2 symbols, period | `.current.value` |
| `self.covariance(symbol1, symbol2, period)` | 2 symbols, period | `.current.value` |
| `self.beta(symbol, reference, period)` | target, reference symbols, period | `.current.value` |
| `self.alpha(symbol, reference, period, risk_free_rate)` | symbols, period, float | `.current.value` |
| `self.sharpe_ratio(symbol, period, risk_free_rate)` | symbol, period, float | `.current.value` |
| `self.sortino_ratio(symbol, period, risk_free_rate)` | symbol, period, float | `.current.value` |
| `self.var(symbol, period, confidence)` | symbol, period, float | `.current.value` — Value at Risk |
| `self.tdd(symbol, period, minimum_acceptable_return)` | symbol, period, float | `.current.value` — Target Downside Deviation |
| `self.mad(symbol, period)` | symbol, period: int | `.current.value` — Mean Absolute Deviation |
| `self.hurst_exponent(symbol, period)` | symbol, period: int | `.current.value` |

---

### Price / Math Indicators

| Method | Parameters | Value Access |
|--------|-----------|--------------|
| `self.true_range(symbol)` | symbol | `.current.value` |
| `self.midpoint(symbol, period)` | symbol, period: int | `.current.value` |
| `self.mid_price(symbol, period)` | symbol, period: int | `.current.value` |
| `self.maximum(symbol, period)` | symbol, period: int | `.current.value` |
| `self.minimum(symbol, period)` | symbol, period: int | `.current.value` |
| `self.sum(symbol, period)` | symbol, period: int | `.current.value` |
| `self.log_return(symbol, period)` | symbol, period: int | `.current.value` |
| `self.rdv(symbol, period)` | symbol, period: int | `.current.value` — Relative Daily Volume |
| `self.ibs(symbol)` | symbol | `.current.value` — Internal Bar Strength |
| `self.identity(symbol)` | symbol | `.current.value` |
| `self.ha(symbol)` | symbol | Heikin-Ashi bars [VERIFY access pattern] |
| `self.ker(symbol, period)` | symbol, period: int | `.current.value` — Kaufman Efficiency Ratio |
| `self.mass_index(symbol, em_period, sum_period)` | symbol, 2 periods | `.current.value` |
| `self.tsf(symbol, period)` | symbol, period: int | `.current.value` — Time Series Forecast |
| `self.arima(symbol, ar_order, d_order, ma_order, period)` | symbol, orders, period | `.current.value` |
| `self.regression_channel(symbol, period)` | symbol, period: int | `.upper_channel.current.value`, `.lower_channel.current.value` [VERIFY] |
| `self.fisher_transform(symbol, period)` | symbol, period: int | `.current.value` |
| `self.hilbert_transform(symbol)` | symbol | `.current.value` |
| `self.coppock_curve(symbol, roc1_period, roc2_period, wma_period)` | symbol, 3 periods | `.current.value` |
| `self.aps(symbol, period)` | symbol, period: int | `.current.value` — Augen Price Spike |
| `self.zigzag(symbol, low_tolerance, high_tolerance)` | symbol, 2 floats | `.current.value` |
| `self.pivot_points(symbol, period)` | symbol, period: int | see sub-properties [VERIFY] |

---

### Options Greeks [VERIFY — requires option subscription]

| Method | Parameters | Value Access |
|--------|-----------|--------------|
| `self.delta(symbol, risk_free_rate, dividend_yield)` | symbol, floats | `.current.value` |
| `self.gamma(symbol, risk_free_rate, dividend_yield)` | symbol, floats | `.current.value` |
| `self.vega(symbol, risk_free_rate, dividend_yield)` | symbol, floats | `.current.value` |
| `self.theta(symbol, risk_free_rate, dividend_yield)` | symbol, floats | `.current.value` |
| `self.rho(symbol, risk_free_rate, dividend_yield)` | symbol, floats | `.current.value` |
| `self.iv(symbol, risk_free_rate, dividend_yield)` | symbol, floats | `.current.value` — Implied Volatility |

---

### Indicator Warm-Up Helpers
```python
self.warm_up_indicator(symbol: Symbol, indicator: IndicatorBase, resolution: Resolution = None) -> None
# Primes a manually-created indicator with historical data before live trading
```

---

## 10. Slice Object (on_data parameter)

```python
def on_data(self, slice: Slice) -> None:
    # Trade bars (OHLCV)
    bar = slice.bars.get(symbol)          # TradeBar or None
    if bar:
        bar.open; bar.high; bar.low; bar.close; bar.volume; bar.time

    # Quote bars
    qbar = slice.quote_bars.get(symbol)   # QuoteBar or None
    if qbar:
        qbar.ask.close; qbar.bid.close
        qbar.ask.open; qbar.bid.open

    # Ticks
    ticks = slice.ticks.get(symbol)       # List[Tick] or None

    # Futures chains
    chain = slice.futures_chains.get(canonical_symbol)
    if chain:
        for contract_symbol, contract in chain.contracts.items():
            contract.last_price
            contract.open_interest
            contract.expiry

    # Options chains
    chain = slice.option_chains.get(canonical_symbol)
    if chain:
        for contract in chain:
            contract.strike; contract.expiry; contract.right  # OptionRight.CALL / .PUT
            contract.implied_volatility
            contract.greeks.delta

    # Generic access
    data = slice[symbol]                  # dynamic — returns bar/tick/etc.
    slice.contains_key(symbol)            # bool
```

---

## 11. Key Enumerations

```python
# Resolution
Resolution.TICK
Resolution.SECOND
Resolution.MINUTE
Resolution.HOUR
Resolution.DAILY

# MovingAverageType
MovingAverageType.SIMPLE
MovingAverageType.EXPONENTIAL
MovingAverageType.DOUBLE_EXPONENTIAL
MovingAverageType.TRIPLE_EXPONENTIAL
MovingAverageType.WILDERS

# DataNormalizationMode
DataNormalizationMode.RAW
DataNormalizationMode.ADJUSTED
DataNormalizationMode.SPLIT_ADJUSTED
DataNormalizationMode.TOTAL_RETURN

# DataMappingMode (Futures)
DataMappingMode.LAST_TRADING_DAY
DataMappingMode.FIRST_DAY_MONTH
DataMappingMode.OPEN_INTEREST

# OrderStatus
OrderStatus.SUBMITTED
OrderStatus.PARTIALLY_FILLED
OrderStatus.FILLED
OrderStatus.CANCELED
OrderStatus.INVALID

# Market
Market.USA
Market.OANDA
Market.COINBASE
Market.CME
Market.NYMEX
Market.CBOT

# Field (price field selector for indicators)
Field.OPEN
Field.HIGH
Field.LOW
Field.CLOSE
Field.VOLUME
Field.BID_PRICE
Field.ASK_PRICE

# AccountType
AccountType.CASH
AccountType.MARGIN
```

---

## 12. Common Algorithm Lifecycle Methods (override these)

```python
def initialize(self) -> None: ...           # Required — set up everything here

def on_data(self, slice: Slice) -> None: ... # Called on each data update

def on_order_event(self, order_event: OrderEvent) -> None: ...
# order_event.order_id, order_event.symbol, order_event.status,
# order_event.fill_price, order_event.fill_quantity

def on_end_of_day(self, symbol: Symbol = None) -> None: ...  # EOD callback

def on_end_of_algorithm(self) -> None: ...   # Final cleanup / logging

def on_securities_changed(self, changes: SecurityChanges) -> None: ...
# changes.added_securities — list of newly added Security objects
# changes.removed_securities — list of removed Security objects

def on_margin_call(self, requests: List[SubmitOrderRequest]) -> List[SubmitOrderRequest]: ...

def on_assignment_order_event(self, assignment_event: OrderEvent) -> None: ...  # options
```

---

## 13. Indicator Usage Example

```python
class MyAlgorithm(QCAlgorithm):
    def initialize(self) -> None:
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2023, 1, 1)
        self.set_cash(100000)
        self.set_warm_up(200, Resolution.DAILY)

        self._symbol = self.add_equity("SPY", Resolution.DAILY).symbol

        # Single-value indicators
        self._rsi  = self.rsi(self._symbol, 14)
        self._ema  = self.ema(self._symbol, 20)
        self._atr  = self.atr(self._symbol, 14, MovingAverageType.SIMPLE)

        # Multi-value indicators
        self._macd = self.macd(self._symbol, 12, 26, 9, MovingAverageType.EXPONENTIAL)
        self._bb   = self.bb(self._symbol, 20, 2)
        self._sto  = self.sto(self._symbol, 14, 3, 3)
        self._adx  = self.adx(self._symbol, 14)

    def on_data(self, slice: Slice) -> None:
        if self.is_warming_up:
            return
        if not all([self._rsi.is_ready, self._macd.is_ready, self._bb.is_ready]):
            return

        rsi_val   = self._rsi.current.value
        macd_val  = self._macd.current.value
        signal    = self._macd.signal.current.value
        upper     = self._bb.upper_band.current.value
        lower     = self._bb.lower_band.current.value
        stoch_k   = self._sto.stoch_k.current.value
        adx_val   = self._adx.current.value
        plus_di   = self._adx.positive_directional_index.current.value
        minus_di  = self._adx.negative_directional_index.current.value

        price = slice.bars[self._symbol].close if self._symbol in slice.bars else None
        if price is None:
            return

        if rsi_val < 30 and price < lower:
            self.set_holdings(self._symbol, 1.0)
        elif rsi_val > 70 and price > upper:
            self.liquidate(self._symbol)
```

---

*Sources: QuantConnect docs v2 (writing-algorithms/indicators, initialization, scheduled-events, historical-data, trading-and-orders), LEAN engine class reference. Fetched 2026-04-24.*
*Sections marked [VERIFY] should be cross-checked against https://www.lean.io/docs/v2/lean-engine/class-reference/ or LEAN source.*
