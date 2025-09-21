# app.py — Historical MNQ=F + Random Market sims with neon-green hacker theme

import inspect
import streamlit as st
import plotly.graph_objects as go

# Engines
from mnq_sim import run_sim
from random_mnq_sim import simulate_market, run_strategy_on, SEED

# ---------------- Page Config ----------------
st.set_page_config(page_title="MNQ Strategy — Interactive", layout="wide")

# ---------------- Neon Hacker Theme CSS ----------------
st.markdown(
    """
<style>
/* Force full background to black */
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {
    background-color: #000000 !important;
    color: #39ff14 !important;
}
.block-container {
    background-color: #000000 !important;
    padding-top: 1.2rem;
    color: #39ff14 !important;
}
* {
    font-family: "Courier New", monospace;
}
h1, h2, h3, h4, h5, h6, p, span, div, label {
    color: #39ff14 !important;
    text-shadow: 0 0 10px #39ff14;
}
hr {
    border: 0;
    height: 1px;
    background: #222;
    margin: 1.2rem 0;
}
.stButton>button, .stDownloadButton>button {
    border-radius: 10px;
    border: 1px solid #39ff14;
    background: #000000;
    color: #39ff14;
    font-weight: 700;
    text-shadow: 0 0 6px #39ff14;
}
.stSlider>div>div>div>div {
    background: #39ff14 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- Intro ----------------
st.title("My Quant Trading Strategy App")

st.markdown(
    """
Welcome! This app includes **two** interactive simulations:

• A historical **MNQ=F** strategy backtest using Yahoo Finance  
• A **random market** simulator that mimics MNQ behavior and applies the same rules
"""
)

st.markdown("---")

# ---------------- Helper to render result block ----------------
def render_block(out, title="Equity Curve"):
    eq_df = out["equity"]
    eq = eq_df["equity"]

    c1, c2 = st.columns([2, 1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=eq.index, y=eq, mode="lines", name="Equity"))
        fig.update_layout(title=title, xaxis_title="Date", yaxis_title="$",
                          margin=dict(l=10, r=10, t=40, b=10),
                          paper_bgcolor="#000000", plot_bgcolor="#000000",
                          font=dict(color="#39ff14"))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Key Stats")
        st.dataframe(out["stats"], use_container_width=True, height=280)

    # Drawdown
    dd = (eq_df["equity"] / eq_df["equity"].cummax()) - 1.0
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=dd.index, y=dd, mode="lines", name="Drawdown"))
    fig2.update_layout(title="Drawdown", xaxis_title="Date", yaxis_title="Drawdown",
                       paper_bgcolor="#000000", plot_bgcolor="#000000",
                       font=dict(color="#39ff14"))
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

# ---------------- Historical MNQ=F ----------------
st.header("Historical MNQ=F Strategy — 20-Year Backtest")
st.caption(
    "Fetches 20y MNQ futures (Yahoo). Rules: sell puts at −0.5σ (T+1, 35% assignment), "
    "close longs at +250 points, sell covered calls at +0.75σ."
)

left, right = st.columns([1, 3])
with left:
    seed_hist = st.number_input("Seed (optional, if supported)", value=42, step=1)
    if st.button("Run Historical Simulation"):
        try:
            if "seed" in inspect.signature(run_sim).parameters:
                hist_out = run_sim(seed=int(seed_hist))
            else:
                hist_out = run_sim()
            render_block(hist_out, title="Equity Curve — Historical (MNQ=F)")
        except Exception as e:
            st.error(f"Historical run failed: {e}")

st.markdown("---")

# ---------------- Random Market ----------------
st.header("Random Market Simulator + MNQ Option Strategy")
st.caption("Generates a randomized MNQ-like path each run and applies the same option rules.")

c1, c2, c3 = st.columns(3)
with c1:
    years = st.slider("Years", 1, 20, 5)
with c2:
    sigma = st.slider("Annualized Volatility (σ)", 0.10, 0.60, 0.25, 0.01)
with c3:
    seed_rand = st.number_input("Random Seed", value=SEED, step=1)

if st.button("Run Random Simulation"):
    try:
        prices = simulate_market(years=years, sigma=sigma, seed=int(seed_rand))
        rand_out = run_strategy_on(prices, seed=int(seed_rand))
        render_block(rand_out, title="Equity Curve — Random Market")
    except Exception as e:
        st.error(f"Random run failed: {e}")


