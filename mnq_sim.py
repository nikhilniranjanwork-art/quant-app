"""
MNQ strategy simulation
-----------------------
Data: 20y MNQ futures from Yahoo Finance ("MNQ=F"), daily OHLC.
Signals:
  - Sell 1–2 puts when close is < (mean - 1.5*std) on a rolling window.
    * Premium ~ Normal(105, σ≈10) clipped to [80, 130] USD per contract.
    * 35% of sold puts are assigned (≈ 0.30 delta). Assignment opens 1 MNQ long.
    * Puts expire in 1 trading day.
  - If we hold any MNQ long and z-score > +2.0, sell a 2-day covered call
    * Premium ~ Normal(135, σ≈12) clipped to [100, 170] USD per contract.
    * For simplicity, calls are covered and expire after 2 days (no extra payoff modeled).
Portfolio:
  - Start equity: $1,000,000.
  - Risk cap: (open puts + held MNQ) * $60,000 ≤ $1,200,000  (≈ 20 contracts of MNQ).
MNQ tick value note: MNQ is $2 per index point. We realize $500 per contract
once price rises +250 points from the MNQ long entry; then we close that long.

Outputs:
  - Daily equity curve and key stats (CAGR, Sharpe, max drawdown)
  - CSVs for equity curve and trade log

Requires: pandas, numpy, yfinance, plotly (optional for charts)
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf

# ----------- Configs you may tweak ----------
SEED = 42
ROLL_WINDOW = 20            # rolling window for mean/std
PUT_Z = -1.5                # 1.5 stdev below mean triggers put sell
CALL_Z = +2.0               # 2.0 stdev above mean triggers covered call
START_EQUITY = 1_000_000.0
CONTRACT_NOTIONAL = 60_000  # approximate MNQ notional per contract
RISK_CAP = 1_200_000        # cap on (open puts + held contracts) notional
POINT_VALUE = 2.0           # USD per MNQ point
TARGET_POINTS = 250         # +250 points = +$500 per MNQ
PUT_MEAN, PUT_MIN, PUT_MAX, PUT_SIGMA = 105, 80, 130, 10
CALL_MEAN, CALL_MIN, CALL_MAX, CALL_SIGMA = 135, 100, 170, 12
ASSIGN_PROB = 0.35          # 35% assignment for sold puts
# --------------------------------------------

random.seed(SEED)
np.random.seed(SEED)

@dataclass
class PutTicket:
    open_day: pd.Timestamp
    contracts: int
    premium_per_contract: float
    expires_on: pd.Timestamp     # T+1
    # whether this ticket was assigned (decided at open)
    assigned_contracts: int      # 0..contracts

@dataclass
class CallTicket:
    open_day: pd.Timestamp
    contracts: int
    premium_per_contract: float
    expires_on: pd.Timestamp     # T+2

@dataclass
class LongMNQ:
    entry_day: pd.Timestamp
    entry_price: float           # index level
    contracts: int               # positive count

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
    years = len(equity) / periods_per_year
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)

def fetch_mnq_20y() -> pd.DataFrame:
    """
    Fetch 20 years of MNQ=F daily bars (multiple data points per day = OHLC/Volume).
    """
    df = yf.download("MNQ=F", period="20y", interval="1d", auto_adjust=False, progress=False)
    if df.empty:
        raise RuntimeError("No data returned for MNQ=F. Try a VPN or different interval.")
    df = df.rename(columns=str.lower)
    df = df.dropna(subset=["close"])
    df = df[["open", "high", "low", "close", "volume"]]
    df.index.name = "date"
    return df

def add_zscores(df: pd.DataFrame, window: int = ROLL_WINDOW) -> pd.DataFrame:
    out = df.copy()
    out["ma"] = out["close"].rolling(window).mean()
    out["sd"] = out["close"].rolling(window).std(ddof=0)
    out["z"] = (out["close"] - out["ma"]) / out["sd"]
    return out

def run_sim() -> Dict[str, pd.DataFrame]:
    data = fetch_mnq_20y()
    df = add_zscores(data)

    cash = START_EQUITY
    equity_curve = []
    positions: List[LongMNQ] = []       # open MNQ longs (from assignments)
    open_puts: List[PutTicket] = []
    open_calls: List[CallTicket] = []
    trade_log_rows = []

    # helper to compute remaining notional
    def used_notional() -> int:
        open_put_contracts = sum(t.contracts for t in open_puts)
        held_contracts = sum(p.contracts for p in positions)
        return (open_put_contracts + held_contracts) * CONTRACT_NOTIONAL

    dates = df.index.to_list()

    for i, day in enumerate(dates):
        row = df.loc[day]
        price = float(row["close"])

        # 1) Expirations (puts T+1, calls T+2)
        #    Puts: if assigned at open, convert to MNQ long at current price (assignment).
        if open_puts:
            still_open_puts = []
            for t in open_puts:
                if day >= t.expires_on:
                    # Put expires today. Assignment already decided up front.
                    if t.assigned_contracts > 0:
                        # Open new MNQ longs at today's close price
                        positions.append(LongMNQ(entry_day=day, entry_price=price, contracts=t.assigned_contracts))
                        trade_log_rows.append({
                            "date": day, "type": "ASSIGN_PUT",
                            "contracts": t.assigned_contracts, "price": price,
                            "cash_change": 0.0, "note": f"Assigned out of {t.contracts} puts"
                        })
                    # Premium was collected at sale time (already in cash).
                    # Put ticket is gone after expiry.
                else:
                    still_open_puts.append(t)
            open_puts = still_open_puts

        if open_calls:
            open_calls = [t for t in open_calls if day < t.expires_on]  # calls simply expire; premium was collected

        # 2) Manage open MNQ longs: close any that hit +250 points from entry
        still_positions: List[LongMNQ] = []
        for p in positions:
            # unrealized move
            points_up = price - p.entry_price
            if points_up >= TARGET_POINTS:
                realized = points_up * POINT_VALUE * p.contracts
                cash += realized
                trade_log_rows.append({
                    "date": day, "type": "CLOSE_LONG",
                    "contracts": p.contracts, "entry_price": p.entry_price, "exit_price": price,
                    "points": points_up, "pnl_usd": realized, "cash_change": realized
                })
            else:
                still_positions.append(p)
        positions = still_positions

        # 3) New signals
        z = row["z"]
        current_notional = used_notional()

        # (a) Put-selling trigger: z < -1.5
        if not math.isnan(z) and z <= PUT_Z:
            # decide to sell 1 or 2 puts, respecting notional cap
            max_contracts = max(0, (RISK_CAP - current_notional) // CONTRACT_NOTIONAL)
            n = min(random.choice([1, 2]), max_contracts)
            if n > 0:
                prem = clipped_normal(PUT_MEAN, PUT_SIGMA, PUT_MIN, PUT_MAX)
                assigned = sum(1 for _ in range(n) if random.random() < ASSIGN_PROB)
                # collect premium now
                cash_change = prem * n
                cash += cash_change
                t = PutTicket(
                    open_day=day,
                    contracts=n,
                    premium_per_contract=prem,
                    expires_on=dates[i+1] if i+1 < len(dates) else day,  # expire next bar if possible
                    assigned_contracts=assigned
                )
                open_puts.append(t)
                trade_log_rows.append({
                    "date": day, "type": "SELL_PUT",
                    "contracts": n, "premium_per_contract": prem,
                    "cash_change": cash_change, "note": f"assigned_prob={ASSIGN_PROB}, assigned={assigned}"
                })

        # (b) Covered call trigger: z > +2.0 and we hold longs
        if not math.isnan(z) and z >= CALL_Z and positions:
            # sell 1 covered call per held contract, expiring T+2 (or as far as data allows)
            n_cc = sum(p.contracts for p in positions)
            if n_cc > 0:
                prem = clipped_normal(CALL_MEAN, CALL_SIGMA, CALL_MIN, CALL_MAX)
                cash_change = prem * n_cc
                cash += cash_change
                exp_idx = min(i + 2, len(dates) - 1)
                open_calls.append(CallTicket(open_day=day, contracts=n_cc,
                                             premium_per_contract=prem, expires_on=dates[exp_idx]))
                trade_log_rows.append({
                    "date": day, "type": "SELL_COVERED_CALL",
                    "contracts": n_cc, "premium_per_contract": prem,
                    "cash_change": cash_change
                })

        # 4) Mark portfolio value end of day
        #    Unrealized P&L from open longs:
        unreal = sum((price - p.entry_price) * POINT_VALUE * p.contracts for p in positions)
        #    Options are modeled premium-only (already in cash).
        equity = cash + unreal
        equity_curve.append({"date": day, "equity": equity, "cash": cash,
                             "unrealized": unreal,
                             "held_contracts": sum(p.contracts for p in positions),
                             "open_puts": sum(t.contracts for t in open_puts),
                             "open_calls": sum(t.contracts for t in open_calls)})

    eq_df = pd.DataFrame(equity_curve).set_index("date")
    ret = eq_df["equity"].pct_change().fillna(0.0)
    stats = pd.Series({
        "Final Equity": eq_df["equity"].iloc[-1],
        "CAGR": cagr(eq_df["equity"]),
        "Sharpe": sharpe(ret),
        "Max Drawdown": max_drawdown(eq_df["equity"]),
        "Total Put Premium": sum(t.premium_per_contract * t.contracts for t in []),  # kept for structure
    })

    trades = pd.DataFrame(trade_log_rows).sort_values("date").reset_index(drop=True)
    return {"equity": eq_df, "returns": ret.to_frame("ret"), "trades": trades, "stats": stats.to_frame("value")}

if __name__ == "__main__":
    out = run_sim()
    # Save artifacts
    out["equity"].to_csv("mnq_equity.csv")
    out["returns"].to_csv("mnq_returns.csv")
    out["trades"].to_csv("mnq_trades.csv", index=False)
    out["stats"].to_csv("mnq_stats.csv")

    # Pretty print summary
    print("\n=== Summary ===")
    print(out["stats"])
    print("\nSaved: mnq_equity.csv, mnq_returns.csv, mnq_trades.csv, mnq_stats.csv")
