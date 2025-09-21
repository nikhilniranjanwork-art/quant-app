# app.py — Two sims (Historical MNQ=F + Random Market) with dark/turquoise/green theme

import inspect
import streamlit as st
import plotly.graph_objects as go

# --- Import your engines ---
from mnq_sim import run_sim                                # historical MNQ=F
from random_mnq_sim import simulate_market, run_strategy_on, SEED  # random market


# ===================== Page / Theme =====================
st.set_page_config(page_title="MNQ Strategy — Interactive", layout="wide")

# Inline CSS (black background + turquoise + green)
st.markdown(
    """
<style>
:root{
  --teal:#2dd4bf; --green:#22c55e; --bg:#0b0f14; --bg2:#0f172a; --text:#e5f3f1;
}
html, body, [data-testid="stAppViewContainer"] { background-color: var(--bg); color: var(--text); }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.2rem; }
hr { border:0; height:1px; background:#1f2937; margin: 1.2rem 0; }
.stButton>button {
  border-radius: 12px; border: 1px solid var(--teal);
  background: linear-gradient(90deg, #064e3b 0%, #065f46 55%, #0d9488 100%);
  color: white; padding: 0.5rem 1rem;
}
.stDownloadButton>button { border-radius: 12px; border: 1px solid var(--green); }
.stSlider>div>div>div>div { background: var(--teal) !important; }
[data-testid="stMarkdown"] p { color: var(--text); }
</style>
""",
    unsafe_allow_html=True,
)

# ===================== Header / Intro =====================
st.title("My Quant Trading Strategy App")

st.markdown(
    """
<b>Welcome!</b> This app showcases two interactive simulations:
1) a **historical MNQ=F** strategy backtest and 2) a **random market** simulator that
mimics MNQ behavior. Use each section below to run and explore the results.
""",
    unsafe_allow_html=True,
)

st.markdown("---")


# ===================== Helper to draw results =====================
def render_block(out, title="Equity Curve"):
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
        st.dataframe(out["stats"], use_container_width=True, height=280)

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


# ===================== Historical MNQ=F Simulation =====================
st.header("Historical MNQ=F Strategy — 20-Year Backtest")
st.caption(
    "Fetches 20y MNQ futures (Yahoo), sells puts at −0.5σ (T+1, 35% assignment), "
    "closes longs at +250 pts, and sells covered calls at +0.75σ."
)

colH1, colH2 = st.columns([1, 3])
with colH1:
    # Optional reproducibility: only passed if your run_sim supports it
    seed_hist = st.number_input("Seed (optional, if supported)", value=42, step=1)
    run_hist_btn = st.button("Run Historical Simulation")

if run_hist_btn:
    try:
        if "seed" in inspect.signature(run_sim).parameters:
            hist_out = run_sim(seed=int(seed_hist))
        else:
            hist_out = run_sim()
        render_block(hist_out, title="Equity Curve — Historical (MNQ=F)")
    except Exception as e:
        st.error(f"Historical run failed: {e}")

st.markdown("---")


# ===================== Random Market Simulation =====================
st.header("Random Market Simulator + MNQ Option Strategy")
st.caption("Simulates a MNQ-like market randomly each run and applies the same options strategy.")

colR1, colR2, colR3 = st.columns(3)
with colR1:
    years = st.slider("Years", 1, 20, 5)
with colR2:
    sigma = st.slider("Annualized Volatility (σ)", 0.10, 0.60, 0.25, 0.01)
with colR3:
    seed_rand = st.number_input("Random Seed", value=SEED, step=1)

run_rand_btn = st.button("Run Random Simulation")

if run_rand_btn:
    try:
        prices = simulate_market(years=years, sigma=sigma, seed=int(seed_rand))
        rand_out = run_strategy_on(prices, seed=int(seed_rand))
        render_block(rand_out, title="Equity Curve — Random Market")
    except Exception as e:
        st.error(f"Random run failed: {e}")



