import streamlit as st

st.title("My Quant Trading Strategy App")

st.write("👋 Welcome! This is a starter Streamlit app.")
st.write("I’ll use this space to showcase my trading strategy, backtests, and interactive simulations.")



import plotly.graph_objects as go
import pandas as pd

# IMPORTANT: this must match the file name exactly (mnq_sim.py)
from mnq_sim import run_sim

st.set_page_config(page_title="MNQ Strategy – Interactive", layout="wide")
st.title("MNQ Put/Call Strategy — 20-Year Simulation")

st.markdown(
    "Press **Run Simulation** to fetch 20y MNQ data, sell puts at −0.5σ, "
    "simulate assignments (35%), close longs at +250 pts, and sell covered calls at +0.75σ."
)

if st.button("Run Simulation"):
    out = run_sim()  # <- runs your code in mnq_sim.py

    eq = out["equity"]            # DataFrame indexed by date
    stats = out["stats"]          # DataFrame with 'value' column
    trades = out["trades"]        # DataFrame

    # Equity curve
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq.index, y=eq["equity"], mode="lines", name="Equity"))
    fig.update_layout(title="Equity Curve", xaxis_title="Date", yaxis_title="$")
    st.plotly_chart(fig, use_container_width=True)

    # Drawdown
    dd = (eq["equity"] / eq["equity"].cummax()) - 1.0
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=dd.index, y=dd, mode="lines", name="Drawdown"))
    fig2.update_layout(title="Drawdown", xaxis_title="Date", yaxis_title="Drawdown")
    st.plotly_chart(fig2, use_container_width=True)

    # Headline stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Equity", f"${eq['equity'].iloc[-1]:,.0f}")
    c2.metric("CAGR", f"{float(stats.loc['CAGR','value']):.2%}")
    c3.metric("Sharpe", f"{float(stats.loc['Sharpe','value']):.2f}")
    c4.metric("Max DD", f"{float(stats.loc['Max Drawdown','value']):.2%}")

    st.markdown("### Recent Trades")
    st.dataframe(trades.tail(50))

    st.download_button("Download trades CSV", trades.to_csv(index=False).encode(), "mnq_trades.csv", "text/csv")
    st.download_button("Download equity CSV", eq.to_csv().encode(), "mnq_equity.csv", "text/csv")
else:
    st.info("Click **Run Simulation** to generate results.")




from random_mnq_sim import simulate_market, run_strategy_on, SEED

st.set_page_config(page_title="Random MNQ Strategy Simulator", layout="wide")
st.title("Random Market Simulator + MNQ Option Strategy")

with st.sidebar:
    years = st.slider("Years", 1, 20, 5)
    sigma = st.slider("Annualized Volatility (σ)", 0.10, 0.60, 0.25, 0.01)
    seed = st.number_input("Random Seed", value=SEED, step=1)
    run_btn = st.button("Run Simulation")

st.markdown("Simulates a MNQ-like market randomly each run and applies your option strategy.")

if run_btn:
    prices = simulate_market(years=years, sigma=sigma, seed=int(seed))
    out = run_strategy_on(prices, seed=int(seed))

    eq = out["equity"]["equity"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq.index, y=eq, mode="lines", name="Equity"))
    fig.update_layout(title="Equity Curve", xaxis_title="Date", yaxis_title="$")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Stats")
    st.dataframe(out["stats"])

    st.subheader("Recent Trades")
    st.dataframe(out["trades"].tail(50))

    st.download_button("Download trades.csv",
                       out["trades"].to_csv(index=False).encode(),
                       "trades.csv", "text/csv")
else:
    st.info("Use the sidebar to set parameters and click **Run Simulation**.")


