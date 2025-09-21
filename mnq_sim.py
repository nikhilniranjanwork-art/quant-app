# mnq_sim.py
# MNQ strategy simulation (robust Yahoo fetch)

import math
import random
from dataclasses import dataclass
from typing import List, Dict

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

# ---------- utils ----------
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

# ---------- robust Yahoo fetch ----------
def fetch_mnq_20y() -> pd.DataFrame:
    """
    Fetch 20 years of MNQ=F daily bars.
    Handles both single-level and MultiIndex columns, and falls back to Adj Close.
    """
    df = yf.download(
        "MNQ=F",
        period="20y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="column",
    )

    if df is None or len(df) == 0:
        raise RuntimeError("No data returned for MNQ=F. Try again or adjust period/interval.")

    # If MultiIndex (e.g., columns like ('Open','MNQ=F')), reduce to single frame
    if isinstance(df.columns, pd.MultiIndex):
        # common patterns: level 0 is OHLCV, level 1 is ticker
        # Bring it to single-level by selecting the ticker if present
        tickers = set(df.columns.get_level_values(-1))
        if "MNQ=F" in tickers:
            df = df.xs("MNQ=F", axis=1, level=-1, drop_level=True)

    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Some futures return 'adj close' but not 'close' when auto_adjust=False
    if "close" not in df.columns and "adj close" in df.columns:
        df["close"] = df["adj close"]

    # Minimal validation
    required = {"open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        raise RuntimeError(f"Expected columns {required}, got {set(df.columns)}")

    if "volume" not in df.columns:
        df["volume"] = np.nan

    df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    df.index.name = "date"
    return df

def add_zscores(df: pd.DataFrame, window: int = ROLL_WINDOW) -> pd.DataFrame:
    out = df.copy()
    out["ma"] = out["close"].rolling(window).mean()
    out["sd"] = out["close"].rolling(window).std(ddof=0)
    out["z"] = (out["close"] - out["ma"]) / out["sd"]
    return out

# ---------- main sim ----------
def run_sim() -> Dict[str, pd.DataFrame]:
    data = fetch_mnq_20y()
    df = add_zscores(data)

    cash = START_EQUITY
    equity_curve = []
    positions: List[LongMNQ] = []       # open MNQ longs (from assignments)
    open_puts: List[PutTicket] = []
    open_calls: List[CallTicket] = []
    trade_log_rows = []

    def used_notional() -> int:
        open_put_contracts = sum(t.contracts for t in open_puts)
        held_contracts = sum(p.contracts for p in positions)
        return (open_put_contracts + held_contracts) * CONTRACT_NOTIONAL

    dates = df.index.to_list()

    for i, day in enumerate(dates):
        row = df.loc[day]
        price = float(row["close"])

        # 1) Expirations (puts T+1, calls T+2)
        if open_puts:
            still_open_puts = []
            for t in open_puts:
                if day >= t.expires_on:
                    if t.assigned_contracts > 0:
                        positions.append(LongMNQ(entry_day=day, entry_price=price, contracts=t.assigned_contracts))
                        trade_log_rows.append({
                            "date": day, "type": "ASSIGN_PUT",
                            "contracts": t.assigned_contracts, "price": price,
                            "cash_change": 0.0, "note": f"Assigned out of {t.contracts} puts"
                        })
                else:
                    still_open_puts.append(t)
            open_puts = still_open_puts

        if open_calls:
            open_calls = [t for t in open_calls if day < t.expires_on]  # calls simply expire; premium was collected

        # 2) Manage open longs: close at +250 pts
        still_positions: List[LongMNQ] = []
        for p in positions:
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

        # 3) Signals
        z = row["z"]
        current_notional = used_notional()

        # (a) Put-selling trigger
        if not math.isnan(z) and z <= PUT_Z:
            max_contracts = max(0, (RISK_CAP - current_notional) // CONTRACT_NOTIONAL)
            n = min(random.choice([1, 2]), max_contracts)
            if n > 0:
                prem = clipped_normal(PUT_MEAN, PUT_SIGMA, PUT_MIN, PUT_MAX)
                assigned = sum(1 for _ in range(n) if random.random() < ASSIGN_PROB)
                cash_change = prem * n
                cash += cash_change
                exp_day = dates[i + 1] if (i + 1) < len(dates) else day  # last day safety
                open_puts.append(PutTicket(day, n, prem, exp_day, assigned))
                trade_log_rows.append({
                    "date": day, "type": "SELL_PUT",
                    "contracts": n, "premium_per_contract": prem,
                    "cash_change": cash_change, "note": f"assigned_prob={ASSIGN_PROB}, assigned={assigned}"
                })

        # (b) Covered call trigger
        if not math.isnan(z) and z >= CALL_Z and positions:
            n_cc = sum(p.contracts for p in positions)
            if n_cc > 0:
                prem = clipped_normal(CALL_MEAN, CALL_SIGMA, CALL_MIN, CALL_MAX)
                cash_change = prem * n_cc
                cash += cash_change
                exp_idx = min(i + 2, len(dates) - 1)
                open_calls.append(CallTicket(day, n_cc, prem, dates[exp_idx]))
                trade_log_rows.append({
                    "date": day, "type": "SELL_COVERED_CALL",
                    "contracts": n_cc, "premium_per_contract": prem,
                    "cash_change": cash_change
                })

        # 4) Mark-to-market
        unreal = sum((price - p.entry_price) * POINT_VALUE * p.contracts for p in positions)
        equity = cash + unreal
        equity_curve.append({
            "date": day, "equity": equity, "cash": cash, "unrealized": unreal,
            "held_contracts": sum(p.contracts for p in positions),
            "open_puts": sum(t.contracts for t in open_puts),
            "open_calls": sum(t.contracts for t in open_calls),
        })

    eq_df = pd.DataFrame(equity_curve).set_index("date")
    ret = eq_df["equity"].pct_change().fillna(0.0)
    stats = pd.Series({
        "Final Equity": eq_df["equity"].iloc[-1],
        "CAGR": cagr(eq_df["equity"]),
        "Sharpe": sharpe(ret),
        "Max Drawdown": max_drawdown(eq_df["equity"]),
        "Total Trades": len(trade_log_rows),
    })

    trades = pd.DataFrame(trade_log_rows).sort_values("date").reset_index(drop=True)
    return {
        "equity": eq_df,
        "returns": ret.to_frame("ret"),
        "trades": trades,
        "stats": stats.to_frame("value"),
    }

if __name__ == "__main__":
    out = run_sim()
    out["equity"].to_csv("mnq_equity.csv")
    out["returns"].to_csv("mnq_returns.csv")
    out["trades"].to_csv("mnq_trades.csv", index=False)
    out["stats"].to_csv("mnq_stats.csv")
    print("\n=== Summary ===")
    print(out["stats"])
    print("\nSaved: mnq_equity.csv, mnq_returns.csv, mnq_trades.csv, mnq_stats.csv")
