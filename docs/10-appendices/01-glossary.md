# THE ETERNAL ENGINE
## Appendix A: Glossary of Terms

---

## A

**ADX (Average Directional Index)**  
A technical indicator developed by J. Welles Wilder to quantify trend strength. Values above 25 indicate a strong trend; values below 20 indicate a weak trend or ranging market. Calculated using +DI and -DI components.

**All-Time High (ATH)**  
The highest price ever reached by an asset. Used in The Eternal Engine to calculate drawdowns and trigger tactical deployment.

**Alpha**  
Excess return relative to a benchmark. In The Eternal Engine, alpha comes from rebalancing premium, trend capture, and funding arbitrage.

**Annualized Return**  
The geometric average amount of money earned by an investment each year over a given time period. Calculated as: `(Ending Value / Beginning Value)^(1/years) - 1`

**Anti-Martingale**  
A position sizing approach that increases position size after wins and decreases after losses. The Eternal Engine uses inverse-Martingale (reduce size during drawdowns).

**Arbitrage**  
The simultaneous purchase and sale of an asset to profit from a difference in the price. In The Eternal Engine, funding rate arbitrage exploits the difference between spot and perpetual funding rates.

**Asset Allocation**  
The implementation of an investment strategy that attempts to balance risk versus reward by adjusting the percentage of each asset in an investment portfolio.

**ATR (Average True Range)**  
A volatility indicator developed by J. Welles Wilder. Calculated as the 14-period moving average of the True Range. Used for stop loss placement and position sizing.

---

## B

**Backtest**  
The process of testing a trading strategy on historical data to see how it would have performed. The Eternal Engine requires 5+ years of backtest data before live deployment.

**Basis**  
The difference between the spot price and the futures/perpetual price of an asset. In funding arbitrage, basis risk is the primary concern.

**Bear Market**  
A market condition in which prices fall 20% or more from recent highs amid widespread pessimism and negative investor sentiment.

**Beta**  
A measure of an asset's volatility in relation to the overall market. Beta of 1.0 means the asset moves with the market. The Eternal Engine targets low-beta strategies during crises.

**Bid-Ask Spread**  
The difference between the highest price a buyer is willing to pay (bid) and the lowest price a seller is willing to accept (ask). Important for slippage calculations.

**Bollinger Bands**  
A technical analysis tool defined by a set of trendlines plotted two standard deviations away from a simple moving average (SMA).

**Bull Market**  
A financial market of a group of securities in which prices are rising or are expected to rise. Typically defined as 20% rise from recent lows.

---

## C

**CAGR (Compound Annual Growth Rate)**  
The mean annual growth rate of an investment over a specified period of time longer than one year. Formula: `(Ending Value / Beginning Value)^(1/n) - 1`

**Calendar Rebalancing**  
Rebalancing a portfolio at predetermined time intervals (e.g., monthly, quarterly). The Eternal Engine uses quarterly calendar rebalancing with threshold triggers.

**Calmar Ratio**  
A comparison of the average annual compounded rate of return and the maximum drawdown risk. Calculated as: `CAGR / Max Drawdown`

**CAPE Ratio (Cyclically Adjusted PE)**  
A valuation measure that uses real earnings per share over a 10-year period. Developed by Robert Shiller. Used for long-term market valuation assessment.

**Capital Preservation**  
An investment strategy that prioritizes preventing losses over achieving gains. First tenet of The Eternal Engine.

**Circuit Breaker**  
An automatic trading halt designed to curb panic-selling on stock exchanges. The Eternal Engine implements four levels of circuit breakers at 10%, 15%, 20%, and 25% drawdowns.

**Compound Interest**  
Interest calculated on the initial principal and also on the accumulated interest of previous periods. "Interest on interest."

**Conditional Value at Risk (CVaR)**  
Also known as Expected Shortfall (ES), the average of the worst-case losses beyond the VaR threshold.

**Correlation**  
A statistic that measures the degree to which two securities move in relation to each other. Range from -1 (perfect negative) to +1 (perfect positive).

**Correlation Matrix**  
A table showing correlation coefficients between variables. Used in The Eternal Engine to monitor diversification breakdown.

**Counterparty Risk**  
The risk that the other party in an investment, credit, or trading transaction may not fulfill its part of the deal and may default on the contractual obligations.

**Cross-Collateral**  
A margin mode where multiple assets can be used as collateral for trading positions. Feature of Bybit UTA.

---

## D

**DCA (Dollar-Cost Averaging)**  
An investment strategy in which an investor divides up the total amount to be invested across periodic purchases of a target asset in an effort to reduce the impact of volatility.

**Delta**  
The ratio comparing the change in the price of an asset to the corresponding change in the price of its derivative. Delta-neutral means zero exposure to price movements.

**Delta-Neutral**  
A portfolio strategy utilizing multiple positions with balancing positive and negative deltas so that the overall delta of the assets in question totals zero.

**Demarker Indicator**  
A technical analysis tool that compares the most recent maximum and minimum prices to the previous period's equivalent prices.

**Derivatives**  
Financial securities whose value relies on or is derived from an underlying asset or group of assets. Includes futures, options, and perpetuals.

**Donchian Channel**  
A technical indicator developed by Richard Donchian. Forms a band with upper band = highest high of N periods, lower band = lowest low of N periods.

**Drawdown**  
The peak-to-trough decline during a specific recorded period of an investment, fund, or commodity. A 20% drawdown means a 20% decline from the peak.

**Dual Momentum**  
An investment strategy combining relative strength momentum (asset selection) and absolute momentum (trend following). Developed by Gary Antonacci.

---

## E

**EMA (Exponential Moving Average)**  
A type of moving average that places a greater weight and significance on the most recent data points. The Eternal Engine uses 50-period and 200-period EMAs.

**Equity Curve**  
A graphical representation of the change in value of a trading account over a time period.

**EV (Expected Value)**  
The anticipated value for a given investment. Calculated as: `Σ(Probability × Outcome)`

**Exchange Broker**  
A feature on Bybit that allows management of multiple subaccounts with custom rate limits and permissions.

---

## F

**Fat Tail**  
A statistical phenomenon where the probability of extreme outcomes is higher than what would be predicted by a normal distribution. Common in crypto markets.

**Fiat**  
Government-issued currency that is not backed by a physical commodity, such as gold or silver, but rather by the government that issued it.

**Fixed Fractional Position Sizing**  
A money management technique where the position size is based on a fixed percentage of the account equity. The Eternal Engine uses 1% risk per trade.

**FOK (Fill or Kill)**  
An order type that must be executed immediately in its entirety or not at all.

**FOMO (Fear of Missing Out)**  
A behavioral phenomenon where investors buy assets due to fear of missing potential gains. The Eternal Engine eliminates FOMO through systematic execution.

**Funding Rate**  
Periodic payments made to or by traders based on the difference between the perpetual contract price and the spot price. Paid every 8 hours on Bybit.

**Futures**  
A legal agreement to buy or sell a particular commodity or asset at a predetermined price at a specified time in the future.

---

## G

**GTC (Good Till Canceled)**  
An order to buy or sell a security that remains in effect until either the order is filled or the investor cancels it.

---

## H

**HODL**  
A term derived from a misspelling of "hold" that refers to buy-and-hold strategies in cryptocurrency. Core philosophy of the CORE-HODL engine.

---

## I

**Iceberg Order**  
A large single order that has been divided into smaller limit orders, usually through the use of an automated program, for the purpose of hiding the actual order quantity.

**IMR (Initial Margin Rate)**  
The minimum amount of equity required to open a leveraged position. On Bybit, 100% IMR means no new positions can be opened.

**Index Price**  
The aggregate price of an asset derived from multiple exchanges. Used for mark price calculations and funding rates.

**IOC (Immediate or Cancel)**  
An order to buy or sell that must be executed immediately. Any portion of the order that cannot be filled immediately is canceled.

---

## K

**Kelly Criterion**  
A mathematical formula for bet sizing: `f = (bp - q) / b` where f is the fraction of capital, b is odds, p is win probability, q is loss probability. The Eternal Engine uses 1/8 Kelly for safety.

**Kill Switch**  
An emergency shutdown mechanism that immediately halts all trading activity. Activated at Circuit Breaker Level 4.

---

## L

**Latency**  
The time delay between the initiation of a request and the response. Critical for high-frequency strategies; less critical for The Eternal Engine's longer timeframes.

**Layer 1 (Blockchain)**  
The base network or blockchain itself (e.g., Bitcoin, Ethereum). The Eternal Engine's CORE-HODL focuses on major Layer 1 assets.

**Leverage**  
The use of borrowed capital to increase the potential return of an investment. The Eternal Engine limits leverage to 2x maximum.

**Limit Order**  
An order to buy or sell a security at a specific price or better.

**Liquidity**  
The degree to which an asset can be quickly bought or sold without affecting its price. Essential for position entry and exit.

---

## M

**Maker Fee**  
The fee paid by traders who add liquidity to the order book by placing limit orders. Lower than taker fees on Bybit (0.01% vs 0.06%).

**Mark Price**  
The price used for unrealized P&L calculations and liquidation triggers. Derived from index price to prevent manipulation.

**Market Order**  
An order to buy or sell immediately at the best available current price.

**Market Regime**  
The current state of the market (trending up, trending down, ranging, volatile). The Eternal Engine detects regimes to adjust allocations.

**Maximum Drawdown (MDD)**  
The maximum observed loss from a peak to a trough of a portfolio, before a new peak is attained. The Eternal Engine limits MDD to 35%.

**MMR (Maintenance Margin Rate)**  
The minimum equity required to maintain an open position. When MMR reaches 100%, liquidation occurs.

**Monte Carlo Simulation**  
A method of estimating the probability of different outcomes by running multiple trials using random variables. Used for projection validation.

**Moving Average**  
A calculation to analyze data points by creating a series of averages of different subsets of the full data set.

**Multi-Strategy**  
An approach that combines multiple trading strategies to achieve better risk-adjusted returns. The Eternal Engine uses four distinct strategies.

---

## O

**Open Interest**  
The total number of outstanding derivative contracts, such as options or futures, that have not been settled.

**Order Book**  
An electronic list of buy and sell orders for a specific security or financial instrument, organized by price level.

---

## P

**Perpetual Futures**  
A type of futures contract without an expiration date. Uses funding rates to keep price anchored to spot. Primary instrument for The Eternal Engine's TREND engine.

**Position Sizing**  
The process of determining how much capital to allocate to a specific trade. Critical for risk management.

**Post-Only**  
An order type that ensures the order adds liquidity to the order book (maker) and does not execute immediately against existing orders (taker).

**Profit Factor**  
A trading metric calculated as: `Gross Profit / Gross Loss`. Values above 1.5 indicate profitable strategies.

---

## R

**R-Multiple**  
A way to express profit or loss as a multiple of the initial risk (R). A 3R winner made 3 times the amount risked.

**Rate Limit**  
The maximum number of API requests allowed in a time period. Bybit allows 120 requests per minute by default.

**Rebalancing**  
The process of realigning the weightings of a portfolio of assets by buying or selling assets to maintain a desired asset allocation.

**Regime Detection**  
Identifying the current market state (trending, ranging, volatile) to adjust strategy parameters.

**REST API**  
Representational State Transfer Application Programming Interface. A standard way for systems to communicate over HTTP.

**Risk Parity**  
An approach to investment management that focuses on allocation of risk rather than allocation of capital.

**Risk-Adjusted Return**  
A calculation of the return on an investment that takes into account the degree of risk that must be accepted to achieve that return. Measured by Sharpe ratio.

**ROI (Return on Investment)**  
A performance measure used to evaluate the efficiency of an investment. Calculated as: `(Current Value - Cost) / Cost`

**RSI (Relative Strength Index)**  
A momentum oscillator that measures the speed and change of price movements. Range 0-100; typically 70 = overbought, 30 = oversold.

---

## S

**Sharpe Ratio**  
A measure of risk-adjusted return. Calculated as: `(Return - Risk Free Rate) / Standard Deviation`. The Eternal Engine targets Sharpe > 1.3.

**Slippage**  
The difference between the expected price of a trade and the actual price at which the trade is executed. Target <0.3%.

**SMA (Simple Moving Average)**  
An arithmetic moving average calculated by adding recent prices and then dividing that figure by the number of time periods in the calculation average.

**Sortino Ratio**  
A variation of the Sharpe ratio that differentiates harmful volatility from total overall volatility. Uses downside deviation only.

**Spot Market**  
A market where financial instruments or commodities are traded for immediate delivery.

**Stablecoin**  
A type of cryptocurrency designed to maintain a stable value relative to a fiat currency (usually USD). USDT and USDC are examples.

**Standard Deviation**  
A measure of the amount of variation or dispersion of a set of values. Used to quantify volatility.

**Stop Loss**  
An order placed with a broker to buy or sell once the stock reaches a certain price. Designed to limit an investor's loss.

**Strategy Decay**  
The phenomenon where a trading strategy's performance degrades over time as market conditions change or more participants exploit the same edge.

**Subaccount**  
A separate account under a master account, used for isolating risk and organizing trading activities.

---

## T

**Taker Fee**  
The fee paid by traders who remove liquidity from the order book by executing against existing orders. Higher than maker fees.

**Tactical Asset Allocation**  
An active management portfolio strategy that shifts the percentage of assets held in various categories to take advantage of market pricing anomalies or strong market sectors.

**Technical Analysis**  
A trading discipline employed to evaluate investments and identify trading opportunities by analyzing statistical trends gathered from trading activity.

**Threshold Rebalancing**  
Rebalancing triggered when an asset's allocation drifts beyond a predetermined percentage from its target allocation.

**Time-Weighted Average Price (TWAP)**  
The average price of a security over a specified time. Used for large order execution.

**Trend Following**  
A trading strategy that attempts to capture gains through the analysis of an asset's momentum in a particular direction.

**True Range**  
The greatest of: (current high - current low), |current high - previous close|, |current low - previous close|. Used in ATR calculation.

---

## U

**UTA (Unified Trading Account)**  
Bybit's account system that allows trading spot, derivatives, and options from a single account with shared margin.

---

## V

**Value at Risk (VaR)**  
A statistic that quantifies the extent of possible financial losses within a firm, portfolio, or position over a specific time frame.

**Volatility**  
A statistical measure of the dispersion of returns for a given security or market index. Usually measured by standard deviation.

**Volatility Targeting**  
Adjusting position sizes based on current market volatility to maintain consistent portfolio risk.

---

## W

**WebSocket**  
A computer communications protocol providing full-duplex communication channels over a single TCP connection. Used for real-time market data.

**Whipsaw**  
A condition where a security's price heads in one direction, but then is followed quickly by a movement in the opposite direction.

**Win Rate**  
The percentage of trades that are profitable. The Eternal Engine's trend following targets 35-40% win rate with high risk/reward ratios.

---

## Y

**Yield**  
The income return on an investment. In The Eternal Engine, yield comes from funding rates, staking, and Bybit Earn.

---

# FORMULA REFERENCE

## Position Sizing

**Kelly Criterion (Full):**
```
f = (bp - q) / b

f = fraction of capital to risk
b = average win / average loss (odds)
p = win probability
q = loss probability (1 - p)
```

**Fractional Kelly (The Eternal Engine):**
```
Position Size = (Account × Kelly Fraction × Kelly) / Stop Distance

Kelly Fraction = 0.125 (1/8)
Max Risk = 1% of account per trade
```

## Risk Metrics

**Sharpe Ratio:**
```
Sharpe = (Rp - Rf) / σp

Rp = Portfolio return
Rf = Risk-free rate
σp = Standard deviation of portfolio return
```

**Maximum Drawdown:**
```
MDD = (Trough Value - Peak Value) / Peak Value
```

**Value at Risk (Parametric):**
```
VaR = Portfolio Value × (μ - zσ)

μ = Expected return
z = Z-score for confidence level (1.65 for 95%)
σ = Standard deviation
```

**Calmar Ratio:**
```
Calmar = CAGR / Max Drawdown
```

## Technical Indicators

**EMA (Exponential Moving Average):**
```
EMA_t = (Close_t × k) + (EMA_{t-1} × (1 - k))

k = 2 / (N + 1)
N = Period
```

**ATR (Average True Range):**
```
TR = max[(High - Low), |High - Close_{t-1}|, |Low - Close_{t-1}|]
ATR = SMA(TR, 14)
```

**ADX (Average Directional Index):**
```
+DM = Current High - Previous High (if positive, else 0)
-DM = Previous Low - Current Low (if positive, else 0)
+DI = 100 × EMA(+DM, 14) / ATR
-DI = 100 × EMA(-M, 14) / ATR
DX = 100 × |+DI - -DI| / (+DI + -DI)
ADX = EMA(DX, 14)
```

## Portfolio Math

**Compound Annual Growth Rate:**
```
CAGR = (Ending Value / Beginning Value)^(1/years) - 1
```

**Portfolio Return with Contributions:**
```
FV = P(1 + r)^n + PMT × [((1 + r)^n - 1) / r]

P = Principal
PMT = Periodic contribution
r = Periodic return rate
n = Number of periods
```

**Correlation:**
```
ρ(X,Y) = Cov(X,Y) / (σX × σY)
```

---

*This glossary provides standardized definitions for all terms used in The Eternal Engine documentation. Terms are cross-referenced across all documents for consistency.*
