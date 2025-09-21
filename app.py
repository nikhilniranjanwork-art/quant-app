# app.py — MNQ historical & random simulators with controls at the bottom

import streamlit as st
import plotly.graph_objects as go
from pathlib import Path
import pandas as pd

# Historical simulator (Yahoo MNQ=F)
from mnq_sim import run_sim

# Random-market simulator
from random_mnq_sim import simulate_market, run_strategy_on, SEED

# ---------------- Page / Theme ----------------
st.set_page_config(page_title="Random Market Simulator + MNQ Options", layout="wide")

# Optional extra CSS (rounded buttons, sliders, etc.)
css_path = Path("assets/custom.css")
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# ---------------- Intro ----------------
st.title("Random Market Simulator + MNQ Option Strategy")

st.markdown(
    """
<div style="font-size:1.05rem; line-height:1.75;">
<b>Welcome to my interactive market simulation platform.</b> My name is <b>Nikhil Niranjan</b>, and from a young age, I’ve had a deep-rooted passion for financial markets.
Starting with paper trading as a child, I ventured into options trading in middle school, successfully transforming a modest account into <b>$10,000</b>.
My journey continued through college, where I embraced <b>futures options</b> for their capital efficiency—allowing dynamic leverage with tight, rules-based risk controls.
Over the last two years, I’ve applied these tactics, growing capital from <b>$10,000</b> to <b>$35,000</b> through varying market regimes.
<br><br>
I focus on the <b>MNQ</b> micro Nasdaq because its volatility and premium structure align with my methodology. This app lets you explore that approach:
sell puts on downside dislocations, write covered calls on strength, and manage positions systematically.
Use the tools below to simulate behavior, review outcomes, and iterate like a quant.
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("---")

# Keep latest results so controls can live at the bottom
if "hist_out" not in st.session_state:
    st.session_state.hist_out = None
if "rand_out" not in st.session_state:
    st.session_state.rand_out = None

# ---------------- Helper to render result blocks ----------------
def render_equity_block(out, title="Equity Curve"):
    eq_df = out["equity"]
    eq = eq_df["equity"]

    c1, c2 = st.columns([2, 1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=eq.index, y=eq, mode="lines", name="Equity"))
        fig.update_layout(title=title, xaxis_title="Date", yaxis_title="$",
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Key Stats")
        st.dataframe(out["stats"])

    # Drawdown
    dd = (eq_df["equity"] / eq_df["equity"].cummax()) - 1.0
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=dd.index, y=dd, mode="lines", name="Drawdown"))
    fig2.update_layout(title="Drawdown", xaxis_title="Date", yaxis_title="Drawdown")
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### Recent Trades")
    st.dataframe(out["trades"].tail(50), use_container_width=True, height=320)

    d1, d2 = st.columns(2)
    with d1:
        st.download_button("Download trades CSV",
                           out["trades"].to_csv(index=False).encode(),
                           "trades.csv", "text/csv")
    with d2:
        st.download_button("Download equity CSV",
                           eq_df.to_csv().encode(),
                           "equity.csv", "text/csv")

# ---------------- Results (TOP) ----------------
top_container = st.container()

with top_container:
    # Historical results (if any)
    if st.session_state.hist_out is not None:
        st.header("Historical MNQ=F Strategy Results")
        render_equity_block(st.session_state.hist_out, title="Equity Curve — Historical (MNQ=F)")

    # Random results (if any)
    if st.session_state.rand_out is not None:
        st.header("Random Market Strategy Results")
        render_equity_block(st.session_state.rand_out, title="Equity Curve — Random Market")

    if st.session_state.hist_out is None and st.session_state.rand_out is None:
        st.info("Run a simulation using the controls below to see results here.")

st.markdown("---")

# ---------------- Controls (BOTTOM) ----------------
st.markdown("## Simulation Controls")
st.caption("All controls live here. Results appear above.")

# Parameters for the RANDOM simulator
cA, cB, cC = st.columns([1, 1, 1])
with cA:
    years = st.slider("Years (Random Market)", 1, 20, 5)
with cB:
    sigma = st.slider("Annualized Volatility σ (Random Market)", 0.10, 0.60, 0.25, 0.01)
with cC:
    seed = st.number_input("Random Seed", value=SEED, step=1)

col_run1, col_run2 = st.columns([1, 1])
with col_run1:
    run_hist = st.button("Run Historical Simulation (MNQ=F)", type="primary")
with col_run2:
    run_rand = st.button("Run Random Simulation", type="secondary")

# Execute — reseed inside your functions for reproducibility
if run_hist:
    st.session_state.hist_out = run_sim(seed=42)  # pass a seed if your run_sim accepts it
    st.experimental_rerun()

if run_rand:
    prices = simulate_market(years=years, sigma=sigma, seed=int(seed))
    st.session_state.rand_out = run_strategy_on(prices, seed=int(seed))
    st.experimental_rerun()



