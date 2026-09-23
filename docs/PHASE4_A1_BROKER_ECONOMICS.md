# Phase 4A.1 — Broker economics calibration

This phase attaches to the existing USD DEMO terminal, reads current quotes and
metadata, calls only the two authorized calculation methods, and reads the
preserved Phase 4A observations in a PostgreSQL read-only transaction. It creates
no broker request, trade, accounting posting, or persistent risk reservation.

The Phase 4A checkpoint is `c1e354c`. The only checkpoint modifications are the
account `currency_digits` observation field and the explicit calculation-method
safety guard. All accounting, portfolio and risk implementations remain unchanged.

## Architecture and admission

`calculations.py` separates observation methods from calculation methods. The
existing native loader remains the sole MetaTrader5 import. SDK `None` and error
responses fail closed with sanitized messages; numeric responses cross through
finite Decimal conversion. Only the SDK argument boundary uses floats.

`calibration_economics.py` keeps independent evidence dimensions and an explicit
`BrokerEconomicsEvidence -> Economics` admission adapter. Missing required
commission, swap, margin or stop evidence blocks admission. Observed metadata
does not prove executable stop constraints; no order-check operation is allowed.
Overall PARTIAL preserves the Phase 4A enum. Qualification remains false.

The separate conditional experiment supplies explicit synthetic fees of $1 per
lot per side plus $0.01 per side. These are test assumptions, not observed or
contractual broker rates. No default-zero costs are supplied. Swap is unknown and
outside this instantaneous stop-loss experiment. Synthetic complete health and
cash histories are used solely to exercise the unchanged pure Risk Engine in
BACKTEST mode. Nothing changes the actual account balance or readiness state.

## Preregistered finite coverage

- All three explicit discovered aliases; BUY and SELL.
- Volumes: minimum, minimum + one step, minimum + ten steps, and one lot when valid.
- Profit movements: -100, -10, -1, +1, +10, +100 ticks.
- Risk stops: 100, 10,000, 200,000 and 500,000 ticks.
- Simulated equity: $300, $3,000 and $30,000; V0 and HR_DEMO_5PCT.

The wider fourth stop was added during fake testing to cover feasible HR sizing
under the existing gross-notional cap, before the real calibration. No strategy
parameters are optimized. V0 SELL correctly rejects V0_LONG_ONLY. HR retains its
existing risk-sized-then-other-limits rejection behavior.

144 price-P/L rows use the original portfolio marking function, 24 margin rows
check local linearity, and 144 risk scenarios use the original `evaluate`.
Accepted volumes are compared with calculator P/L at the stop and margin at entry.
Rejected scenarios retain minimum-lot calculator loss. Risk output includes the
engine's two-tick buffer and the explicit synthetic fees, so it intentionally
differs from fee-exclusive price P/L.

## Monetary rounding and tolerance

The initial half-cent assumption failed on BTC: broker -$0.01 versus unrounded
domain -$0.00110. The run stopped. Preserved probes of 84 cases each for BTC and
gold matched separately rounded opening and closing monetary legs; USTEC showed
net-P/L rounding in cases that differed from that model. This is sample evidence,
not a claim about undocumented implementation internals or future behavior.

The error bound is two half-units of account currency, plus four binary ULPs per
price propagated through volume and contract size. With USD precision two this
is $0.01 plus microscopic floating-point error. Each profit row must additionally
match either net rounding or the difference of rounded legs; only binary-near-tie
alternatives are accepted. Errors inside the bound without an explained rounding
candidate still fail. Tick movements remain exact multiples of tick size.

Relative errors for sub-cent P/L can be large: report them without interpreting
currency quantization as an economic-model percentage failure. Asymmetric tick
values are examined separately and cannot silently enter the symmetric frozen
Phase 3.4 model. Incompatible contracts fail admission rather than being replaced
with a hardcoded broker formula.

## Margin and costs

Margin is a proposed-operation estimate under current account/environment
conditions. It is not total portfolio margin and never overwrites observed used
or free margin. The finite volume grid checks linear representability within
propagated monetary rounding. The conditional engine model uses the maximum
per-lot upper rounding bound of sampled margins. Each accepted candidate is
checked again with the calculator, simulated free margin and the unchanged 20%
cap, and separately against actual observed free margin.

The historical profiler groups immutable tickets by symbol and native entry/exit
code. Identical tickets deduplicate; conflicting contents fail. Missing costs
remain unknown, and zero-volume nontrade records have no per-lot statistic.
Signed commission, fee and swap per-lot min/median/max describe only the bounded
sample. Observed zero does not establish a future zero schedule.

Quote distributions use Decimal ask minus bid over distinct retained observations,
midpoint median and nearest-rank p90/p95. They are neither time-weighted nor a
historical backtest spread model. Stop/freeze points are converted to price
distances, while executable acceptance remains untested.

## Evidence and reproduction

Full immutable calculation answers and domain identities:
`.local/phase4_a1/calibration-20260922-complete.json`. Local accepted SHA-256 manifest:
`.local/phase4_a1/accepted-hashes.json`. The tracked presentation is
`reports/mt5_broker_economics_calibration.json`; internal hashes remain in ignored
proof so the existing secret scanner requires no exceptions or weaker rules.
Original Phase 4A report and economics JSON are preserved.

The evidence verifier checks file hashes, reloads answers into a recorded
calculator, reruns the unchanged domain on the same inputs, compares every
generated row and decision identity, and rechecks retained PostgreSQL hashes and
descriptive profiles. It never reruns historical research or calls MT5.

```powershell
# TE_DATABASE_URL: existing local Phase 4A observation database.
# TE_TEST_DATABASE_URL: disposable PostgreSQL regression target.
.\scripts\verify_phase4_a1.ps1
```

A new explicitly requested calibration uses a new output path; the CLI refuses
to overwrite an existing output. The final gate validates the accepted capture.

## Official API semantics

- [Profit calculator](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py):
  estimated P/L in account currency for supplied prices and volume.
- [Margin calculator](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcmargin_py):
  current-environment operation estimate without existing positions or orders.

Completion stops before execution and before Phase 4B. The next separately
reviewed proposal is External EA Observer, not an execution gateway.
