import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# Import your simulation modules
from mnq_sim import run_sim
from random_mnq_sim import simulate_market, run_strategy_on, SEED

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="MNQ Strategy – Interactive", layout="wide")

# -------------------------------------------------
# Hard-force BLACK background + TURQUOISE text
# (covers modern Streamlit containers & widgets)
# -------------------------------------------------
ST_TURQ = "#40E0D0"

st.markdown(
    f"""
    <style>
    :root {{
        --turq: {ST_TURQ};
    }}

    /* kill default header bg */
    [data-testid="stHeader"] {{
        background: transparent !important;
    }}

    /* App body & main container */
    .stApp, 
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stVerticalBlock"],
    .block-container {{
        background: #000 !important;
        color: var(--turq) !important;
    }}

    /* Sidebar */
    [data-testid="stSidebar"], 
    [data-testid="stSidebar"] > div {{
        background: #000 !important;
        color: var(--turq) !important;
    }}

    /* All text defaults */
    body, p, span, div, label, li, ul, ol, 
    .stMarkdown, .stCaption, .stText, .stAlert,
    .stDataFrame, .stMetric, .stDownloadButton,
    .stRadio, .stSelectbox, .stMultiSelect,
    .stTextInput, .stNumberInput, .stSlider, .stDateInput {{
        color: var(--turq) !important;
    }}

    /* Headings */
    h1, h2, h3, h4, h5, h6 {{
        color: var(--turq) !important;
        text-shadow: none !important; /* keep crisp */
    }}

    /* Buttons */
    .stButton button {{
        background: #000 !important;
        color: var(--turq) !important;
        border: 1px solid var(--turq) !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
    }}
    .stButton button:hover {{
        background: var(--turq) !important;
        color: #000 !important;
    }}

    /* Inputs / widgets backgrounds */
    .stTextInput > div > div > input,
    .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div {{
        background: #111 !important;
        color: var(--turq) !important;
        border: 1px solid var(--turq) !important;
    }}

    /* Slider track/handle */
    .stSlider [role="slider"] {{ background: var(--turq) !important; }}
    .stSlider [data-baseweb="slider"] > div > div {{
        background: var(--turq) !important;
    }}

    /* Metric cards */
    .stMetric {{
        background: #000 !important;
        border: 2px solid var(--turq) !important;
        border-radius: 12px !important;
        padding: 12px !important;
    }}

    /* Tables */
    .stDataFrame, .stTable {{
        color: var(--turq) !important;
    }}

    /* Plotly container blend */
    .js-plotly-plot, .plotly, .user-select-none {{
        color: var(--turq) !important;
        background: #000 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Intro / About
# -------------------------------------------------
st.title("My Quant Trading Strategy App")

st.subheader("Background / About")
st.markdown(
    """
INTRO_TEXT = """
Welcome to my interactive market simulation platform.

My name is **Nikhil Niranjan**, and from a young age I’ve had a deep-rooted passion for financial markets. Starting with paper trading as a child, I ventured into options trading in middle school, successfully growing a modest account of just a few hundred dollars into **$10,000**.

My journey continued through college, where I embraced **futures options** for their capital efficiency. This strategic choice allowed me to enhance portfolio leverage dynamically. Over the last two years, I’ve applied these tactics consistently, growing my capital from **$10,000** to **$35,000**, even amidst significant market volatility.

My focus on the **MNQ index** is driven by its high volatility and premium opportunities. With careful risk management and disciplined execution, it aligns perfectly with my trading methodology.

I invite you to explore this simulation, adjust the parameters, and analyze the outcomes — with the goal of building clarity, repeatability, and long-term success in trading.
"""

"""
)

# -------------------------------------------------
# Historical MNQ=F backtest
# -------------------------------------------------
st.header("Historical MNQ=F Strategy — 20-Year Backtest")
st.caption(
    "Fetches 20y MNQ futures (Yahoo). Rules: sell puts at −0.5σ (T+1, 35% assignment), "
    "close longs at +250 points, sell covered calls at +0.75σ."
)

seed_hist = st.number_input("Seed (optional, if supported)", value=42, step=1)

if st.button("Run Historical Simulation"):
    out = run_sim()  # uses your mnq_sim.py

    eq = out["equity"]          # DataFrame
    stats = out["stats"]        # DataFrame with 'value'
    trades = out["trades"]      # DataFrame

    # Equity curve (dark-themed)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=eq.index, y=eq["equity"], mode="lines", name="Equity",
            line=dict(color=ST_TURQ, width=2)
        )
    )
    fig.update_layout(
        template="plotly_dark",
        title="Equity Curve — Historical MNQ=F",
        xaxis_title="Date", yaxis_title="$",
        plot_bgcolor="#000", paper_bgcolor="#000",
        font=dict(color=ST_TURQ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Key stats
    st.subheader("Key Stats")
    c1, c2, c3, c4 = st.columns(4)
    c5, c6, c7 = st.columns(3)

    c1.metric("Final Equity", f"${eq['equity'].iloc[-1]:,.0f}")
    c2.metric("CAGR", f"{float(stats.loc['CAGR','value']):.2%}")
    c3.metric("Sharpe", f"{float(stats.loc['Sharpe','value']):.2f}")
    c4.metric("Max Drawdown", f"{float(stats.loc['Max Drawdown','value']):.2%}")
    c5.metric("Total Trades", f"{int(stats.loc['Total Trades','value']):,}")
    if "Max Open Puts" in stats.index:
        c6.metric("Max Open Puts", f"{int(stats.loc['Max Open Puts','value'])}")
    if "Max Held MNQ" in stats.index:
        c7.metric("Max Held MNQ", f"{int(stats.loc['Max Held MNQ','value'])}")

    st.subheader("Recent Trades")
    st.dataframe(trades.tail(25))

    st.download_button(
        "Download trades CSV",
        trades.to_csv(index=False).encode(),
        "mnq_trades.csv",
        "text/csv",
    )
    st.download_button(
        "Download equity CSV",
        eq.to_csv().encode(),
        "mnq_equity.csv",
        "text/csv",
    )

# -------------------------------------------------
# Random market simulator
# -------------------------------------------------
st.header("Random Market Simulator + MNQ Option Strategy")
st.caption("Generates a randomized MNQ-like path each run and applies the same option rules.")

years = st.slider("Years", 1, 20, 5)
sigma = st.slider("Annualized Volatility (σ)", 0.10, 0.60, 0.25, 0.01)
seed = st.number_input("Random Seed", value=SEED, step=1)

if st.button("Run Random Simulation"):
    prices = simulate_market(years=years, sigma=sigma, seed=int(seed))
    out = run_strategy_on(prices, seed=int(seed))

    eq_series = out["equity"]["equity"]

    # Equity curve for random sim
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=eq_series.index, y=eq_series, mode="lines", name="Equity",
            line=dict(color=ST_TURQ, width=2)
        )
    )
    fig2.update_layout(
        template="plotly_dark",
        title="Equity Curve — Random Market",
        xaxis_title="Date", yaxis_title="$",
        plot_bgcolor="#000", paper_bgcolor="#000",
        font=dict(color=ST_TURQ),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Key stats
    st.subheader("Key Stats")
    stats2 = out["stats"]
    d1, d2, d3, d4 = st.columns(4)
    d5, d6, d7 = st.columns(3)

    d1.metric("Final Equity", f"${eq_series.iloc[-1]:,.0f}")
    d2.metric("CAGR", f"{float(stats2.loc['CAGR','value']):.2%}")
    d3.metric("Sharpe", f"{float(stats2.loc['Sharpe','value']):.2f}")
    d4.metric("Max Drawdown", f"{float(stats2.loc['Max Drawdown','value']):.2%}")
    d5.metric("Total Trades", f"{int(stats2.loc['Total Trades','value']):,}")
    if "Max Open Puts" in stats2.index:
        d6.metric("Max Open Puts", f"{int(stats2.loc['Max Open Puts','value'])}")
    if "Max Held MNQ" in stats2.index:
        d7.metric("Max Held MNQ", f"{int(stats2.loc['Max Held MNQ','value'])}")

    st.subheader("Recent Trades")
    st.dataframe(out["trades"].tail(25))

    st.download_button(
        "Download trades.csv",
        out["trades"].to_csv(index=False).encode(),
        "trades.csv",
        "text/csv",
    )

