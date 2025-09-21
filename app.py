# app.py — Historical MNQ=F + Random Market sims
# Neon theme (no blurry labels), roomy charts, metric cards, editable Background/About.

import inspect
import streamlit as st
import plotly.graph_objects as go

# ====== EDIT THIS: Your on-page "Background / About" text =====================
INTRO_TEXT = """
**Background / About**

Welcome to my interactive market simulation platform. My name is **Nikhil Niranjan**.
From a young age I’ve had a deep-rooted passion for financial markets. Starting with
paper trading, I got into options trading early and grew a modest account through
structured risk-taking and disciplined methodology. Today I focus on **MNQ** because
its volatility and premium dynamics fit my strategy. Explore the simulations, tweak
the parameters, and study the results — the goal is clarity, repeatability, and growth.
"""
# ==============================================================================

st.set_page_config(page_title="MNQ Strategy — Interactive", layout="wide")

# ====== Theme CSS (no global blur; glow only where we add .glow classes) ======
st.markdown(
    """
<style>
/* Base palette */
html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stHeader"], [data-testid="stSidebar"] {
  background-color: #000 !important;
  color: #b7ffcf !important;  /* soft mint for general text */
}

/* Sidebar */
[data-testid="stSidebar"] {
  background:#000 !important; color:#b7ffcf !important;
  border-right: 1px solid #0e2a0c;
}

/* Layout */
.block-container { max-width: 1500px; padding-top: 1.0rem; }
* { font-family: "Courier New", monospace; }

/* NO global glow to avoid blur on small text */
h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown, .stCaption { text-shadow: none !important; }

/* Elements that should glow explicitly */
.neon-title { color:#39ff14; text-shadow: 0 0 10px #39ff14, 0 0 20px #2be30e; }
.neon-sub   { color:#39ff14; text-shadow: 0 0 8px #39ff14; }

/* Buttons */
.stButton>button, .stDownloadButton>button {
  border-radius: 10px; border: 1px solid #39ff14;
  background: #000; color: #39ff14; font-weight: 700;
  box-shadow: 0 0 12px rgba(57,255,20,0.25);
}

/* Inputs */
input, textarea, select, .stTextInput input, .stNumberInput input,
[data-baseweb="select"] > div, .stDateInput input, .stFileUploader {
  background:#0a0a0a !important; color:#b7ffcf !important;
  border: 1px solid #135b0f !important;
}

/* Sliders */
[data-baseweb="slider"]>div>div { background:#0e1f0d !important; }
[data-baseweb="slider"]>div>div>div { background:#39ff14 !important; }
[data-baseweb="slider"] [role="slider"] { background:#39ff14 !important; border:1px solid #39ff14 !important; }

/* Metric cards */
.metric-card {
  border:1px solid #39ff14; border-radius:14px; padding:14px 16px;
  background:#050805e6; box-shadow: 0 0 18px rgba(57,255,20,0.22);
  margin-bottom: 12px;
}
.metric-card .label { color:#98ffb1; font-size:0.95rem; }
.metric-card .value { color:#39ff14; font-size:1.35rem; font-weight:800; text-shadow: 0 0 8px #39ff14; }

/* Stat grid */
.stats-grid { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:14px; }
@media (max-width: 1100px) { .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 780px)  { .stats-grid { grid-template-columns: 1fr; } }

/* Background/About neon card */
.bio-card {
  border:1px solid #39ff14; border-radius:16px; padding:14px 18px;
  background:#060a06e6; box-shadow: 0 0 20px rgba(57,255,20,0.25);
}

/* Slim divider (replaces the old fat <hr>) */
.divider { height:1px; background:#132117; margin: 18px 0 8px 0; }
</style>
""",
    unsafe_allow_html=True,
)

# ====== Engines (keep your filenames the same) ======
from mnq_sim import run_sim
from random_mnq_sim import simulate_market, run_strategy_on, SEED

# ====== Small helpers ======
def format_pct(x):
    try: return f"{float(x):.2%}"
    except: return "—"

def fmt_money(x):
    try: return f"${float(x):,.0f}"
    except: return "—"

def get_stat(stats_df, key):
    try: return stats_df.loc[key, "value"]
    except: return None

def stat_cards(stats_df):
    final_equity = get_stat(stats_df, "Final Equity")
    c1, c2 = st.columns([2.2, 1])
    with c1:
        st.markdown(
            '<div class="metric-card">'
            '<div class="label">Final Equity</div>'
            f'<div class="value">{fmt_money(final_equity)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    c2.empty()

    items = []
    cagr = get_stat(stats_df, "CAGR")
    sharpe = get_stat(stats_df, "Sharpe")
    mdd = get_stat(stats_df, "Max Drawdown")
    tot = get_stat(stats_df, "Total Trades")
    max_puts = get_stat(stats_df, "Max Open Puts")
    max_held = get_stat(stats_df, "Max Held MNQ")
    items += [("CAGR", format_pct(cagr))]
    items += [("Sharpe", f"{float(sharpe):.2f}" if sharpe is not None else "—")]
    items += [("Max Drawdown", format_pct(mdd))]
    if tot is not None: items += [("Total Trades", f"{int(tot):,}")]
    if max_puts is not None: items += [("Max Open Puts", f"{int(max_puts):,}")]
    if max_held is not None: items += [("Max Held MNQ", f"{int(max_held):,}")]

    html = '<div class="stats-grid">'
    for label, val in items:
        html += ('<div class="metric-card">'
                 f'<div class="label">{label}</div>'
                 f'<div class="value">{val}</div>'
                 '</div>')
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def plot_equity(eq_series, title):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eq_series.index, y=eq_series, mode="lines", name="Equity",
        line=dict(color="#39ff14", width=2)
    ))
    fig.update_layout(
        title=title, xaxis_title="Date", yaxis_title="$",
        height=520, margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="#000000", plot_bgcolor="#101417",
        font=dict(color="#b7ffcf"),  # crisp mint (no glow)
        xaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
        yaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
    )
    return fig

def plot_drawdown(dd_series):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd_series.index, y=dd_series, mode="lines", name="Drawdown",
        line=dict(color="#19ff74", width=1.8)
    ))
    fig.update_layout(
        title="Drawdown", xaxis_title="Date", yaxis_title="Drawdown",
        height=280, margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="#000000", plot_bgcolor="#101417",
        font=dict(color="#b7ffcf"),
        xaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
        yaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
    )
    return fig

def equity_block(out, title="Equity Curve"):
    eq_df = out["equity"]
    eq = eq_df["equity"]

    col_plot, col_stats = st.columns([7, 5])
    with col_plot:
        st.plotly_chart(plot_equity(eq, title), use_container_width=True)
    with col_stats:
        st.markdown('<h3 class="neon-sub">Key Stats</h3>', unsafe_allow_html=True)
        stat_cards(out["stats"])

    dd = (eq_df["equity"] / eq_df["equity"].cummax()) - 1.0
    st.plotly_chart(plot_drawdown(dd), use_container_width=True)

    st.markdown('<div class="neon-sub">Recent Trades</div>', unsafe_allow_html=True)
    st.dataframe(out["trades"].tail(50), use_container_width=True, height=360)

    d1, d2 = st.columns(2)
    with d1:
        st.download_button("Download trades CSV",
                           out["trades"].to_csv(index=False).encode(),
                           "trades.csv", "text/csv")
    with d2:
        st.download_button("Download equity CSV",
                           eq_df.to_csv().encode(),
                           "equity.csv", "text/csv")

# ====== Hero Title ======
st.markdown('<h1 class="neon-title">My Quant Trading Strategy App</h1>', unsafe_allow_html=True)

# ====== Background / About (no stray bar) ======
st.markdown('<div class="bio-card">', unsafe_allow_html=True)
st.markdown("### Background / About")
st.markdown(INTRO_TEXT)  # Markdown content
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ====== Historical MNQ=F ======
st.markdown('<h2 class="neon-sub">Historical MNQ=F Strategy — 20-Year Backtest</h2>', unsafe_allow_html=True)
st.caption(
    "Fetches 20y MNQ futures (Yahoo). Rules: sell puts at −0.5σ (T+1, 35% assignment), "
    "close longs at +250 points, sell covered calls at +0.75σ."
)

left, _ = st.columns([1, 5])
with left:
    seed_hist = st.number_input("Seed (optional, if supported)", value=42, step=1)
run_hist = st.button("Run Historical Simulation")

from mnq_sim import run_sim  # ensure after seed widget to avoid rerun confusion

if run_hist:
    try:
        if "seed" in inspect.signature(run_sim).parameters:
            hist_out = run_sim(seed=int(seed_hist))
        else:
            hist_out = run_sim()
        equity_block(hist_out, title="Equity Curve — Historical (MNQ=F)")
    except Exception as e:
        st.error(f"Historical run failed: {e}")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ====== Random Market ======
st.markdown('<h2 class="neon-sub">Random Market Simulator + MNQ Option Strategy</h2>', unsafe_allow_html=True)
st.caption("Generates a randomized MNQ-like path each run and applies the same option rules.")

from random_mnq_sim import simulate_market, run_strategy_on, SEED

c1, c2, c3 = st.columns(3)
with c1:
    years = st.slider("Years", 1, 20, 5)
with c2:
    sigma = st.slider("Annualized Volatility (σ)", 0.10, 0.60, 0.25, 0.01)
with c3:
    seed_rand = st.number_input("Random Seed", value=SEED, step=1)

run_rand = st.button("Run Random Simulation")

if run_rand:
    try:
        prices = simulate_market(years=years, sigma=sigma, seed=int(seed_rand))
        rand_out = run_strategy_on(prices, seed=int(seed_rand))
        equity_block(rand_out, title="Equity Curve — Random Market")
    except Exception as e:
        st.error(f"Random run failed: {e}")



