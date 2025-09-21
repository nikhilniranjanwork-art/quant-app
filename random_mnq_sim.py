"""
Random MNQ-like market simulator + your option strategy
-------------------------------------------------------
- Market: geometric Brownian motion (GBM) with optional jumps, daily steps.
- Strategy:
    * Sell 5–7 puts when z <= -0.5 (1-day expiry), 35% per-put assignment.
    * If holding MNQ longs and z >= +0.75, sell 2-day covered calls (premium-only).
    * Close each MNQ long at +250 index points (+$500/contract since MNQ $2/pt).
    * Notional cap: (open puts + held MNQ) * $60k <= $1.35M.
- Outputs:
    * Equity curve, trades, stats CSVs to ./out/
- CLI examples:
    python random_mnq_sim.py
    python random_mnq_sim.py --years 3 --sigma 0.28 --paths 20
"""

from dataclasses import dataclass
from typing import List, Dict
import argparse, math, random, os

import numpy as np
import pandas as pd
import plotly.graph_objects as go


# ----------- Strategy Config -----------
SEED = 42
START_EQUITY = 1_000_000.0
CONTRACT_NOTIONAL = 60_000
RISK_CAP = 1_350_000                 # portfolio notional cap
POINT_VALUE = 2.0                    # $ per MNQ point
TARGET_POINTS = 250                  # close long at +250 pts
# Z-score triggers
ROLL_WINDOW = 20
PUT_Z = -0.5
CALL_Z = +0.75
# Premium models (USD/contract)
PUT_MEAN, PUT_MIN, PUT_MAX, PUT_SIGMA = 105, 80, 130, 10
CALL_MEAN, CALL_MIN, CALL_MAX, CALL_SIGMA = 135, 100, 170, 12
ASSIGN_PROB = 0.35
# --------------------------------------


@dataclass
class PutTicket:
    open_day: pd.Timestamp
    contracts: int
    premium_per_contract: float
    expires_on: pd.Timestamp       # T+1
    assigned_contracts: int


@dataclass
class CallTicket:
    open_day: pd.Timestamp
    contracts: int
    premium_per_contract: float
    expires_on: pd.Timestamp       # T+2


@dataclass
class LongMNQ:
    entry_day: pd.Timestamp
    entry_price: float
    contracts: int


def clipped_normal(mean: float, sigma: float, low: float, high: float) -> float:
    x = np.random.normal(mean, sigma)
    return float(np.clip(x, low, high))


def sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    r = returns.dropna()
    if r.std() == 0:
        return float("nan")
    return float(np.sqrt(periods_per_year) * r.mean() / (r.std() + 1e-12))


def max_drawdown(series: pd.Series) -> float:
    roll_max = series.cummax()
    dd = series / roll_max - 1.0
    return float(dd.min())


def cagr(equity: pd.Series, periods_per_year: int = 252) -> float:
    if len(equity) < 2:
        return float("nan")
    yrs = len(equity) / periods_per_year
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / yrs) - 1)


# ---------- Random market generator ----------
def simulate_market(
    years: int = 5,
    s0: float = 15000.0,              # MNQ-like index level
    mu: float = 0.07,                 # annual drift
    sigma: float = 0.25,              # annual vol
    jump_prob: float = 0.02,          # optional downward jumps (crisis flavor)
    jump_mean: float = -0.03,
    jump_std: float = 0.03,
    seed: int = SEED,
) -> pd.DataFrame:
    """
    GBM with optional jumps. Returns DataFrame with daily open/high/low/close.
    """
    np.random.seed(seed)
    n = int(252 * years)
    dt = 1 / 252
    # GBM increments
    z = np.random.normal(0, 1, size=n)
    # daily returns
    rets = (mu - 0.5 * sigma * sigma) * dt + sigma * np.sqrt(dt) * z

    # occasional jumps
    jumps = np.random.rand(n) < jump_prob
    jump_sizes = np.random.normal(jump_mean, jump_std, size=n)
    rets += jumps * jump_sizes

    # price path
    prices = [s0]
    for r in rets:
        prices.append(prices[-1] * math.exp(r))
    prices = np.array(prices)
    # create simple OHLC from close + noise
    close = prices[1:]  # n days
    open_ = np.concatenate([[s0], prices[:-1]])[1:]
    high = np.maximum(open_, close) * (1 + np.abs(np.random.normal(0, 0.002, n)))
    low  = np.minimum(open_, close) * (1 - np.abs(np.random.normal(0, 0.002, n)))
    vol  = np.abs(np.random.normal(0, 1, n)) * 1e3

    idx = pd.date_range("2000-01-01", periods=n, freq="B")
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)
    df.index.name = "date"
    return df


def add_zscores(df: pd.DataFrame, window: int = ROLL_WINDOW) -> pd.DataFrame:
    out = df.copy()
    out["ma"] = out["close"].rolling(window).mean()
    out["sd"] = out["close"].rolling(window).std(ddof=0)
    out["z"] = (out["close"] - out["ma"]) / out["sd"]
    return out


# ---------- Strategy on simulated market ----------
def run_strategy_on(df_prices: pd.DataFrame, seed: int = SEED) -> Dict[str, pd.DataFrame]:
    random.seed(seed)
    np.random.seed(seed)

    df = add_zscores(df_prices, ROLL_WINDOW)
    dates = df.index.to_list()

    cash = START_EQUITY
    equity_curve = []
    positions: List[LongMNQ] = []
    open_puts: List[PutTicket] = []
    open_calls: List[CallTicket] = []
    trade_log_rows = []

    def used_notional() -> int:
        return (sum(t.contracts for t in open_puts) + sum(p.contracts for p in positions)) * CONTRACT_NOTIONAL

    for i, day in enumerate(dates):
        row = df.loc[day]
        price = float(row["close"])

        # ---- expiries ----
        if open_puts:
            still = []
            for t in open_puts:
                if day >= t.expires_on:
                    if t.assigned_contracts > 0:
                        positions.append(LongMNQ(day, price, t.assigned_contracts))
                        trade_log_rows.append({"date": day, "type": "ASSIGN_PUT",
                                               "contracts": t.assigned_contracts, "price": price,
                                               "cash_change": 0.0, "note": f"assigned out of {t.contracts}"})
                else:
                    still.append(t)
            open_puts = still

        if open_calls:
            open_calls = [t for t in open_calls if day < t.expires_on]  # premium-only in cash

        # ---- manage longs: take +250 pts ----
        still_pos = []
        for p in positions:
            pts = price - p.entry_price
            if pts >= TARGET_POINTS:
                realized = pts * POINT_VALUE * p.contracts
                cash += realized
                trade_log_rows.append({"date": day, "type": "CLOSE_LONG",
                                       "contracts": p.contracts, "entry_price": p.entry_price,
                                       "exit_price": price, "points": pts, "pnl_usd": realized,
                                       "cash_change": realized})
            else:
                still_pos.append(p)
        positions = still_pos

        # ---- signals ----
        z = row["z"]
        current_notional = used_notional()

        # Put sell @ z <= -0.5 (random 5–7, cap-aware)
        if not math.isnan(z) and z <= PUT_Z:
            max_contracts = max(0, (RISK_CAP - current_notional) // CONTRACT_NOTIONAL)
            n = min(random.choice([5, 6, 7]), max_contracts)
            if n > 0:
                prem = clipped_normal(PUT_MEAN, PUT_SIGMA, PUT_MIN, PUT_MAX)
                assigned = sum(1 for _ in range(n) if random.random() < ASSIGN_PROB)
                cash_change = prem * n
                cash += cash_change
                exp_day = dates[i + 1] if (i + 1) < len(dates) else day
                open_puts.append(PutTicket(day, n, prem, exp_day, assigned))
                trade_log_rows.append({"date": day, "type": "SELL_PUT", "contracts": n,
                                       "premium_per_contract": prem, "cash_change": cash_change,
                                       "note": f"assigned_prob={ASSIGN_PROB}, assigned={assigned}"})
            else:
                trade_log_rows.append({"date": day, "type": "SKIP_PUT_CAP", "contracts": 0,
                                       "premium_per_contract": 0.0, "cash_change": 0.0,
                                       "note": f"cap hit; notional={current_notional:,.0f}"})

        # Covered call @ z >= +0.75 (premium-only)
        if not math.isnan(z) and z >= CALL_Z and positions:
            n_cc = sum(p.contracts for p in positions)
            if n_cc > 0:
                prem = clipped_normal(CALL_MEAN, CALL_SIGMA, CALL_MIN, CALL_MAX)
                cash_change = prem * n_cc
                cash += cash_change
                exp_idx = min(i + 2, len(dates) - 1)
                open_calls.append(CallTicket(day, n_cc, prem, dates[exp_idx]))
                trade_log_rows.append({"date": day, "type": "SELL_COVERED_CALL",
                                       "contracts": n_cc, "premium_per_contract": prem,
                                       "cash_change": cash_change})

        # ---- mark-to-market ----
        unreal = sum((price - p.entry_price) * POINT_VALUE * p.contracts for p in positions)
        equity = cash + unreal
        equity_curve.append({
            "date": day, "equity": equity, "cash": cash, "unrealized": unreal,
            "held_contracts": sum(p.contracts for p in positions),
            "open_puts": sum(t.contracts for t in open_puts),
            "open_calls": sum(t.contracts for t in open_calls),
            "z": float(z) if not math.isnan(z) else np.nan,
        })

    eq = pd.DataFrame(equity_curve).set_index("date")
    ret = eq["equity"].pct_change().fillna(0.0)
    trades = pd.DataFrame(trade_log_rows).sort_values("date").reset_index(drop=True)
    stats = pd.Series({
        "Final Equity": eq["equity"].iloc[-1],
        "CAGR": cagr(eq["equity"]),
        "Sharpe": sharpe(ret),
        "Max Drawdown": max_drawdown(eq["equity"]),
        "Max Open Puts": int(eq["open_puts"].max()),
        "Max Held MNQ": int(eq["held_contracts"].max()),
        "Total Trades": len(trades),
    })
    return {"equity": eq, "returns": ret.to_frame("ret"), "trades": trades, "stats": stats.to_frame("value")}


# ---------- CLI ----------
def run_once(years=5, sigma=0.25, seed=SEED, show_plot=True, out_dir="out"):
    prices = simulate_market(years=years, sigma=sigma, seed=seed)
    out = run_strategy_on(prices, seed=seed)

    os.makedirs(out_dir, exist_ok=True)
    out["equity"].to_csv(f"{out_dir}/equity.csv")
    out["returns"].to_csv(f"{out_dir}/returns.csv")
    out["trades"].to_csv(f"{out_dir}/trades.csv", index=False)
    out["stats"].to_csv(f"{out_dir}/stats.csv")

    # quick plotly chart
    if show_plot:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=out["equity"].index, y=out["equity"]["equity"],
                                 mode="lines", name="Equity"))
        fig.update_layout(title="Equity Curve (Random Market)", xaxis_title="Date", yaxis_title="$")
        fig.show()

    print("\n=== Summary ===")
    print(out["stats"])
    return out


def run_paths(paths=10, years=5, sigma=0.25, seed=SEED):
    rows = []
    for p in range(paths):
        out = run_once(years=years, sigma=sigma, seed=seed + p, show_plot=False, out_dir=f"out/path_{p}")
        s = out["stats"]["value"]
        rows.append({"path": p, "Final Equity": s.loc["Final Equity"], "CAGR": s.loc["CAGR"],
                     "Sharpe": s.loc["Sharpe"], "Max DD": s.loc["Max Drawdown"]})
    df = pd.DataFrame(rows)
    print("\n=== Monte Carlo Summary ===")
    print(df.describe(percentiles=[0.1, 0.5, 0.9]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=5, help="Number of years to simulate")
    parser.add_argument("--sigma", type=float, default=0.25, help="Annualized volatility")
    parser.add_argument("--paths", type=int, default=1, help="Run N randomized paths")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    args = parser.parse_args()

    if args.paths <= 1:
        run_once(years=args.years, sigma=args.sigma, seed=args.seed)
    else:
        run_paths(paths=args.paths, years=args.years, sigma=args.sigma, seed=args.seed)
