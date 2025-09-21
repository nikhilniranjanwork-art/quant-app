# app.py — Historical MNQ=F + Random Market sims
# Neon-green theme, roomy charts, metric cards, optional background image

import base64
import inspect
import io
from typing import Optional

import streamlit as st
import plotly.graph_objects as go

# Engines (keep filenames the same)
from mnq_sim import run_sim
from random_mnq_sim import simulate_market, run_strategy_on, SEED


# ======================== Page Config ========================
st.set_page_config(page_title="MNQ Strategy — Interactive", layout="wide")


# ======================== Background Helpers ========================
def css_background(url: Optional[str] = None, b64: Optional[str] = None, opacity: float = 0.12):
    """
    Inject CSS to set a global page background image.
    - Provide either a URL or a base64 string (b64) from an uploaded file.
    - `opacity` controls a dark overlay so neon text remains readable.
    """
    if url:
        bg_src = f"url('{url}')"
    elif b64:
        bg_src = f"url('data:image/png;base64,{b64}')"
    else:
        bg_src = "none"

    st.markdown(
        f"""
<style>
/* Global page background (image + dark overlay) */
html, body, .stApp, [data-testid="stAppViewContainer"] {{
  background-color: #000 !important;
  color: #39ff14 !important;
  background-image: {bg_src};
  background-size: cover;
  background-position: center center;
  background-attachment: fixed;
}}
/* Dark overlay for readability */
.stApp::before {{
  content: "";
  position: fixed; inset: 0;
  background: rgba(0,0,0,{opacity});
  pointer-events: none;
  z-index: 0;
}}
/* Bring main content above overlay */
.block-container, [data-testid="stSidebar"], [data-testid="stHeader"] {{
  position: relative; z-index: 1;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def file_to_base64(file) -> str:
    return base64.b64encode(file.read()).decode("utf-8")


# ======================== Neon Hacker Theme CSS ========================
st.markdown(
    """
<style>
/* Content width + base colors */
.block-container { max-width: 1500px; padding-top: 1.2rem; }
* { font-family: "Courier New", monospace; }
h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown, .stCaption {
  color: #39ff14 !important; text-shadow: 0 0 8px #39ff14;
}
hr { border:0; height:1px; background:#222; margin: 1.2rem 0; }

/* Buttons */
.stButton>button, .stDownloadButton>button {
  border-radius: 10px; border: 1px solid #39ff14;
  background: #000; color: #39ff14; font-weight: 700;
  text-shadow: 0 0 6px #39ff14;
}

/* Inputs/Sliders */
.stSlider>div>div>div>div { background: #39ff14 !important; }
.stNumberInput>div>div>input, .stTextInput>div>div>input {
  color:#39ff14 !important; background:#0a0a0a !important; border:1px solid #135b0f !important;
}

/* Metric Cards */
.metric-card {
  border:1px solid #39ff14; border-radius:14px; padding:14px 16px;
  background:#070707cc; box-shadow: 0 0 18px rgba(57,255,20,0.25);
  margin-bottom: 10px;
}
.metric-card .label { font-size:0.95rem; opacity:0.9; }
.metric-card .value { font-size:1.35rem; font-weight:800; }

/* Stat grid wrapper */
.stats-grid { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:14px; }
@media (max-width: 1100px) { .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 780px)  { .stats-grid { grid-template-columns: 1fr; } }
</style>
""",
    unsafe_allow_html=True,
)

# ======================== Sidebar: Background Controls ========================
with st.sidebar:
    st.subheader("Background Image")
    bg_url = st.text_input("Paste image URL (optional)")
    upload = st.file_uploader("…or upload an image", type=["png", "jpg", "jpeg"])
    bg_b64 = file_to_base64(upload) if upload else None
    bg_opacity = st.slider("Background dim (overlay)", 0.00, 0.50, 0.12, 0.01)

# Apply background CSS now
css_background(url=bg_url if bg_url else None, b64=bg_b64, opacity=bg_opacity)


# ======================== Intro ========================
st.title("My Quant Trading Strategy App")
st.caption("Two live sims: historical MNQ=F backtest + random market simulator (same rules).")
st.markdown("---")


# ======================== Helpers ========================
def format_pct(x):
    try:
        return f"{float(x):.2%}"
    except Exception:
        return "—"


def fmt_money(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return "—"


def get_stat(stats_df, key):
    try:
        return stats_df.loc[key, "value"]
    except Exception:
        return None


def stat_cards(stats_df):
    """Render pretty metric cards (Final Equity big; others in a responsive grid)."""
    # Final equity prominent
    final_equity = get_stat(stats_df, "Final Equity")
    c1, c2 = st.columns([2.2, 1])
    with c1:
        st.markdown(
            '<div class="metric-card">'
            f'<div class="label">Final Equity</div>'
            f'<div class="value">{fmt_money(final_equity)}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    # Other stats
    c2.empty()
    container = st.container()
    with container:
        items = []
        cagr = get_stat(stats_df, "CAGR")
        sharpe = get_stat(stats_df, "Sharpe")
        mdd = get_stat(stats_df, "Max Drawdown")
        tot = get_stat(stats_df, "Total Trades")
        max_puts = get_stat(stats_df, "Max Open Puts")
        max_held = get_stat(stats_df, "Max Held MNQ")
        items.append(("CAGR", format_pct(cagr)))
        items.append(("Sharpe", f"{float(sharpe):.2f}" if sharpe is not None else "—"))
        items.append(("Max Drawdown", format_pct(mdd)))
        if tot is not None:
            items.append(("Total Trades", f"{int(tot):,}"))
        if max_puts is not None:
            items.append(("Max Open Puts", f"{int(max_puts):,}"))
        if max_held is not None:
            items.append(("Max Held MNQ", f"{int(max_held):,}"))

        html = '<div class="stats-grid">'
        for label, val in items:
            html += (
                '<div class="metric-card">'
                f'<div class="label">{label}</div>'
                f'<div class="value">{val}</div>'
                "</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)


def plot_equity(eq_series, title):
    """Plotly chart with dark gray plot area + visible gridlines."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=eq_series.index,
            y=eq_series,
            mode="lines",
            name="Equity",
            line=dict(color="#39ff14", width=2),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="$",
        height=520,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="#000000",     # frame
        plot_bgcolor="#101417",      # dark gray plot area (not black)
        font=dict(color="#39ff14"),
        xaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
        yaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
    )
    return fig


def plot_drawdown(dd_series):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dd_series.index,
            y=dd_series,
            mode="lines",
            name="Drawdown",
            line=dict(color="#19ff74", width=1.8),
        )
    )
    fig.update_layout(
        title="Drawdown",
        xaxis_title="Date",
        yaxis_title="Drawdown",
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="#000000",
        plot_bgcolor="#101417",
        font=dict(color="#39ff14"),
        xaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
        yaxis=dict(gridcolor="#1d2a2f", zerolinecolor="#24343b", showgrid=True),
    )
    return fig


def equity_block(out, title="Equity Curve"):
    """Wide chart + compact metric cards + drawdown + downloads."""
    eq_df = out["equity"]
    eq = eq_df["equity"]

    col_plot, col_stats = st.columns([7, 5])
    with col_plot:
        st.plotly_chart(plot_equity(eq, title), use_container_width=True)

    with col_stats:
        st.subheader("Key Stats")
        stat_cards(out["stats"])

    dd = (eq_df["equity"] / eq_df["equity"].cummax()) - 1.0
    st.plotly_chart(plot_drawdown(dd), use_container_width=True)

    st.markdown("### Recent Trades")
    st.dataframe(out["trades"].tail(50), use_container_width=True, height=360)

    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Download trades CSV",
            out["trades"].to_csv(index=False).encode(),
            "trades.csv",
            "text/csv",
        )
    with d2:
        st.download_button(
            "Download equity CSV",
            eq_df.to_csv().encode(),
            "equity.csv",
            "text/csv",
        )


# ======================== Historical MNQ=F ========================
st.header("Historical MNQ=F Strategy — 20-Year Backtest")
st.caption(
    "Fetches 20y MNQ futures (Yahoo). Rules: sell puts at −0.5σ (T+1, 35% assignment), "
    "close longs at +250 points, sell covered calls at +0.75σ."
)

left, _ = st.columns([1, 5])
with left:
    seed_hist = st.number_input("Seed (optional, if supported)", value=42, step=1)
run_hist = st.button("Run Historical Simulation")

if run_hist:
    try:
        if "seed" in inspect.signature(run_sim).parameters:
            hist_out = run_sim(seed=int(seed_hist))
        else:
            hist_out = run_sim()
        equity_block(hist_out, title="Equity Curve — Historical (MNQ=F)")
    except Exception as e:
        st.error(f"Historical run failed: {e}")

st.markdown("---")


# ======================== Random Market ========================
st.header("Random Market Simulator + MNQ Option Strategy")
st.caption("Generates a randomized MNQ-like path each run and applies the same option rules.")

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



