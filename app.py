import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from mnq_sim import run_sim
from random_mnq_sim import simulate_market, run_strategy_on, SEED

# Page config
st.set_page_config(page_title="Quant Trading Strategy App", layout="wide")

# Global turquoise hacker theme
st.markdown("""
    <style>
    /* Set the whole page background */
    html, body, [class*="css"]  {
        background-color: black !important;
        color: #40E0D0 !important;
    }

    /* Sidebar background */
    section[data-testid="stSidebar"] {
        background-color: black !important;
    }

    /* Make text turquoise everywhere */
    .stMarkdown, .stMetric, .stDataFrame, .stDownloadButton,
    .stTextInput, .stNumberInput, .stSlider label, .stButton button,
    .stCaption, .stSubheader, .stHeader, .stTitle {
        color: #40E0D0 !important;
    }

    /* Button styling */
    .stButton button {
        background-color: black !important;
        color: #40E0D0 !important;
        border: 1px solid #40E0D0 !important;
        border-radius: 6px;
        padding: 0.5em 1em;
    }
    .stButton button:hover {
        background-color: #40E0D0 !important;
        color: black !important;
    }

    /* Slider knobs and bars */
    .stSlider > div > div > div {
        background: #40E0D0 !important;
    }

    /* Metrics */
    .stMetric {
        border: 2px solid #40E0D0;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        color: #40E0D0 !important;
        background-color: black !important;
    }

    /* Headings */
    h1, h2, h3, h4 {
        color: #40E0D0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Title
st.title("My Quant Trading Strategy App")

# Background/About Section (clean, no duplicates)
st.header("Background / About")
st.write("""
Welcome to my interactive market simulation platform. My name is **Nikhil Niranjan**. 
From a young age I’ve had a deep-rooted passion for financial markets. Starting with paper trading, 
I got into options trading early and grew a modest account through structured risk-taking and disciplined methodology. 
Today I focus on **MNQ** because its volatility and premium dynamics fit my strategy. 

Explore the simulations, tweak the parameters, and study the results — the goal is clarity, repeatability, and growth.
""")

# --- Historical Simulation Section ---
st.subheader("Historical MNQ=F Strategy — 20-Year Backtest")
st.caption("Fetches 20y MNQ futures (Yahoo). Rules: sell puts at −0.5σ (T+1, 35% assignment), close longs at +250 points, sell covered calls at +0.75σ.")

seed_hist = st.number_input("Seed (optional, if supported)", value=42, step=1, key="hist_seed")
if st.button("Run Historical Simulation"):
    out = run_sim()
    eq = out["equity"]
    stats = out["stats"]
    trades = out["trades"]

    # Equity curve
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq.index, y=eq["equity"], mode="lines", line=dict(color="#40E0D0")))
    fig.update_layout(
        title="Equity Curve — Historical",
        xaxis_title="Date",
        yaxis_title="$",
        paper_bgcolor="black",
        plot_bgcolor="black",
        font=dict(color="#40E0D0")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Key stats
    st.subheader("Key Stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Equity", f"${eq['equity'].iloc[-1]:,.0f}")
    c2.metric("CAGR", f"{float(stats.loc['CAGR','value']):.2%}")
    c3.metric("Sharpe", f"{float(stats.loc['Sharpe','value']):.2f}")
    c4.metric("Max Drawdown", f"{float(stats.loc['Max Drawdown','value']):.2%}")

    st.download_button("Download trades CSV", trades.to_csv(index=False).encode(), "mnq_trades.csv", "text/csv")

# --- Random Market Simulation Section ---
st.subheader("Random Market Simulator + MNQ Option Strategy")
st.caption("Generates a randomized MNQ-like path each run and applies the same option rules.")

col1, col2, col3 = st.columns(3)
with col1:
    years = st.slider("Years", 1, 20, 5)
with col2:
    sigma = st.slider("Annualized Volatility (σ)", 0.10, 0.60, 0.25, 0.01)
with col3:
    seed = st.number_input("Random Seed", value=SEED, step=1)

if st.button("Run Random Simulation"):
    prices = simulate_market(years=years, sigma=sigma, seed=int(seed))
    out = run_strategy_on(prices, seed=int(seed))
    eq = out["equity"]["equity"]

    # Equity curve
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=eq.index, y=eq, mode="lines", line=dict(color="#40E0D0")))
    fig2.update_layout(
        title="Equity Curve — Random Market",
        xaxis_title="Date",
        yaxis_title="$",
        paper_bgcolor="black",
        plot_bgcolor="black",
        font=dict(color="#40E0D0")
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Key stats
    st.subheader("Key Stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Equity", f"${eq.iloc[-1]:,.0f}")
    c2.metric("CAGR", f"{float(out['stats'].loc['CAGR','value']):.2%}")
    c3.metric("Sharpe", f"{float(out['stats'].loc['Sharpe','value']):.2f}")
    c4.metric("Max Drawdown", f"{float(out['stats'].loc['Max Drawdown','value']):.2%}")

    st.download_button("Download trades CSV", out["trades"].to_csv(index=False).encode(), "random_trades.csv", "text/csv")




