# Quality Management Plan
## NewTradingOS v14.0

**PMBOK Knowledge Area:** Quality Management  
**Process Group:** Planning → Monitoring & Controlling  
**Document Version:** 3.0  
**Date:** 2026-05-30

---

## 1. Quality Objectives

| ID | Quality Objective | Metric | Target | Current |
|---|---|---|---|---|
| QO-1 | All core logic is unit-tested and passing | Test pass rate | 100% | 237/237 ✅ |
| QO-2 | Scoring performance meets latency SLA | Tickers scored per second | 60 tickers < 2s | 1.04s ✅ |
| QO-3 | World market data retrieval meets latency SLA | Fetch wall-clock time | < 3s | ~2s ✅ |
| QO-4 | No unhandled exceptions during normal use | Error rate | 0 in happy path | ✅ |
| QO-5 | Audit log never loses events | JSONL integrity | Append-only, no drops | ✅ |
| QO-6 | Indicator outputs are deterministic | Repeatability | Same result on re-run | Enforced by tests |
| QO-7 | Score breakdown sums to total score | Integrity | |sum − score| < 0.5 | Tested ✅ |

---

## 2. Test Strategy

### 2.1 Test Infrastructure

| Item | Value |
|---|---|
| Framework | `pytest` 9.0.2 |
| Config file | `pytest.ini` at project root |
| Command | `python -m pytest` or `python -m pytest -v` |
| Total tests | **299** |
| Typical run time | ~550 seconds (9m 10s) |
| Test data | Synthetic DataFrames generated in fixtures; no live API calls in tests |

### 2.2 Test Files and Coverage

| File | Tests | Module Covered | Focus |
|---|---|---|---|
| `tests/test_indicators.py` | ~50 | `core/indicators.py` | Each indicator function; compute_all column presence; no-NaN on sufficient data; VN-specific formulas (CMF, SuperTrend ratchet, Streak counter); Wilder ADX smoothing; exchange-aware Streak (HNX ±10%, UPCoM ±15%); ATC manipulation bonus |
| `tests/test_scoring.py` | ~30 | `core/scoring.py` | Score range [0,100]; breakdown sum; regime downgrade; manipulation downgrade; stop/target formula; batch_score performance; `exchange_map` routing; `foreign_flow_net_20d` usage |
| `tests/test_macro_data.py` | ~17 | `core/macro_data.py` | `get_macro_score()` 3-tuple return; score range [0,10]; label thresholds; stale field detection; `fetch_foreign_flow_ticker()` session-only snapshot contract (`session_net_proxy`, `session_trend`, neutral `net_20d`) |
| `tests/test_macro_tab.py` | 4 | `ui/macro_tab.py` | Macro Pulse tri-state stale handling; missing DXY/VIX/foreign flow no longer appears favorable; timeframe scorecard shows `Thiếu dữ liệu` when macro components are stale |
| `tests/test_scanner_wiring.py` | 15 | `ui/scanner_tab.py`, `core/scoring.py`, `app.py` | `render_scanner_tab()` signature has `exchange_map`; HNX ticker routed with `exchange='HNX'`; proxy `net_20d` ignored in scoring; scanner audit emits summary + per-symbol events into the main audit log |
| `tests/test_audit.py` | 5 | `core/audit.py`, `ui/audit_tab.py` | Batch audit writes; scan summary/result subtype inference; filter_events detail-kind filtering; Audit tab labels scan summaries vs per-symbol signals |
| `tests/test_ml_tab.py` | 3 | `ui/ml_tab.py` | ML trust-state helper; Holt-only fallback warning path; degraded-model detection; as-of/source metadata |
| `tests/test_portfolio.py` | ~25 | `portfolio/tracker.py` | Lot-size calculation; P&L net of fees; T+2 pending state; JSON round-trip persistence; audit event fired on open/close |
| `tests/test_backtest.py` | ~20 | `backtest/engine.py` | VN cost model; CAGR formula; Sharpe ratio; Max Drawdown; trade entry/exit simulation |
| `tests/test_data_fetcher.py` | ~15 | `core/data_fetcher.py` | Fallback chain (mock APIs); timeout handling; output schema validation |
| `tests/test_ensemble.py` | ~22 | `ml/ensemble.py` | Forecast not NaN; LSTM fallback without TensorFlow; ensemble weight sum = 1.0; walk-forward 80/20 train/test split; `_walk_forward_mape()` non-negative and finite |
| `tests/test_regime.py` | 21 | `core/regime.py` | HMM label output (bull/sideways/bear); macro score range [0,10]; parallel world market fetch; `detect_market_regime` alias; VNI uptrend/downtrend detection; history length/label validity |

### 2.3 Test Categories

| Category | Description | Marker |
|---|---|---|
| Unit | Single function, mocked dependencies | default |
| Integration | Multiple modules working together | `@pytest.mark.integration` |
| Performance | Timing-based assertions | `@pytest.mark.slow` |
| Regression | Tests added after bug fixes | default (named `test_regression_*`) |

### 2.4 Test Design Principles

1. **No live API calls in tests** — all external data mocked with synthetic DataFrames.
2. **Deterministic** — tests use fixed random seeds where stochastic logic is involved.
3. **Independent** — tests must not depend on execution order; each uses fresh fixtures.
4. **Fast failure** — unit tests should complete in < 1s each; slow tests marked `@pytest.mark.slow`.
5. **Edge cases** — all boundary conditions tested: empty DataFrame, single-row DataFrame, all-zero volume, ATR = 0.

---

## 3. Code Quality Standards

### 3.1 Coding Conventions

| Standard | Rule |
|---|---|
| Python style | PEP 8; 4-space indentation; max line length 120 |
| Type hints | Required for all public function signatures |
| Docstrings | Required for all public functions (`"""One-line summary.\n\nExtended description."""`) |
| Variable naming | `snake_case` for variables/functions; `PascalCase` for classes; `ALL_CAPS` for constants |
| Error handling | Use explicit `except ExceptionType`; never bare `except:` |
| Logging | Use Python `logging` module; never `print()` in library code |

### 3.2 Security Coding Standards

Following OWASP Top 10 mitigations:

| OWASP | Rule |
|---|---|
| A01 Broken Access Control | N/A (single-user local app) |
| A02 Crypto Failures | No sensitive data encrypted (local file; document not to push `data/`) |
| A03 Injection | Validate all ticker symbols against whitelist before URL construction |
| A04 Insecure Design | No user-supplied values interpolated into shell commands |
| A05 Security Misconfiguration | No default credentials; no API keys stored in code |
| A07 Auth Failures | N/A (single-user) |
| A09 Logging Failures | Audit log captures all business events |

### 3.3 Financial Calculation Rules

1. **Never use floating point for shares** — always `int(floor(...))` for lot sizes.
2. **Round monetary values to 0 decimal places VND** after computation; never mid-calculation.
3. **Fee constants from `config.py`** — never hardcode fee values in scoring or portfolio modules.
4. **ATR = 0 guard** — stop/target calculation must default to 1% buffer if ATR equals zero.

---

## 4. Performance KPIs

| KPI | Measurement Method | Target | Alert Threshold |
|---|---|---|---|
| Scan latency | `time.perf_counter()` around `batch_score()` | 60 tickers < 2s | > 5s |
| World market fetch | `time.perf_counter()` around `fetch_world_markets()` | < 3s | > 8s |
| Test suite run time | `pytest --tb=short` exit timing | < 10 min | > 20 min |
| ML forecast latency | Per-ticker ensemble time | < 5s per ticker | > 15s |
| App startup time | Streamlit first render | < 5s | > 15s |

---

## 5. Quality Assurance Activities

### 5.1 Pre-Commit Checklist

- [ ] `python -m pytest` passes with 0 failures
- [ ] New functions have docstrings and type hints
- [ ] No hardcoded ticker symbols, fees, or API URLs in non-config modules
- [ ] No API credentials in source code
- [ ] `data/` folder not included in commit

### 5.2 Release Checklist

- [ ] All 299 tests pass on clean environment
- [ ] Backtesting regression report compared against v13.0 baseline
- [ ] Scan performance benchmark run (60 tickers < 2s)
- [ ] PMBOK docs updated for any scope changes
- [ ] `requirements.txt` reflects actual dependencies
- [ ] `GUIDE.md` updated with any new features

### 5.3 Defect Management

| Severity | Definition | Target Resolution |
|---|---|---|
| P1 — Critical | Application crashes or data loss | Same session |
| P2 — High | Incorrect score calculation; portfolio P&L wrong | Next release |
| P3 — Medium | UI display issue; minor miscalculation | Backlog |
| P4 — Low | Cosmetic; documentation gap | Backlog |

**Defect tracking:** GitHub Issues or equivalent; label by P1–P4.

---

## 6. Test Configuration

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

### 6.1 Running Specific Test Groups

```bash
# All tests
python -m pytest

# Single module
python -m pytest tests/test_scoring.py -v

# Performance tests only
python -m pytest -m slow -v

# Stop on first failure
python -m pytest -x

# With timing
python -m pytest --durations=10
```

---

## 7. Continuous Improvement

| Practice | Frequency |
|---|---|
| Backtesting vs benchmark comparison | Quarterly |
| Indicator relevance review (VN market changes) | Semi-annually |
| Risk register review | Monthly |
| Test suite coverage gap analysis | Each release |
| Performance benchmark regression check | Each release |
