"""Streamlit dashboard for Day 13 observability lab.

Reads data/logs.jsonl and renders the six panels defined by the
grading contract in config/dashboard.yaml (source of truth for
thresholds/units — do not hardcode numbers here).

Run with: streamlit run scripts/dashboard.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DASHBOARD_CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"


def load_config() -> dict:
    payload = yaml.safe_load(DASHBOARD_CONFIG_PATH.read_text(encoding="utf-8"))
    return payload["dashboard"]


def panel_by_id(config: dict, panel_id: str) -> dict:
    return next(p for p in config["panels"] if p["id"] == panel_id)


@st.cache_data(ttl=5)
def load_records(_mtime: float) -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df


def in_window(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if df.empty:
        return df
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return df[df["ts"] >= cutoff]


def threshold_badge(value: float | None, threshold: dict) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    op = threshold["operator"]
    limit = threshold["value"]
    ok = value <= limit if op == "lte" else value >= limit
    return "PASS" if ok else "FAIL"


def rule_layer(value: float, color: str = "red") -> alt.Chart:
    return (
        alt.Chart(pd.DataFrame({"y": [value]}))
        .mark_rule(color=color, strokeDash=[4, 4])
        .encode(y="y:Q")
    )


def render_latency(config: dict, df: pd.DataFrame) -> None:
    panel = panel_by_id(config, "latency")
    st.subheader(panel["title"])
    events = df[(df["event"] == "response_sent") & df["latency_ms"].notna()]
    if events.empty:
        st.info("Chưa có dữ liệu response_sent trong cửa sổ hiện tại.")
        return
    p50, p95, p99 = events["latency_ms"].quantile([0.5, 0.95, 0.99])
    threshold = panel["threshold"]
    cols = st.columns(4)
    cols[0].metric("P50 (ms)", f"{p50:.0f}")
    cols[1].metric("P95 (ms)", f"{p95:.0f}")
    cols[2].metric("P99 (ms)", f"{p99:.0f}")
    cols[3].metric(f"SLO {threshold['aggregation']} {threshold['operator']} {threshold['value']}{panel['unit']}", threshold_badge(p95, threshold))

    events = events.copy()
    events["minute"] = events["ts"].dt.floor("min")
    per_min = events.groupby("minute")["latency_ms"].quantile(0.95).reset_index(name="p95_latency_ms")
    chart = (
        alt.Chart(per_min)
        .mark_line(point=True)
        .encode(x="minute:T", y="p95_latency_ms:Q")
    )
    st.altair_chart(chart + rule_layer(threshold["value"]), use_container_width=True)


def render_traffic(config: dict, df: pd.DataFrame) -> None:
    panel = panel_by_id(config, "traffic")
    st.subheader(panel["title"])
    events = df[df["event"] == "request_received"]
    threshold = panel["threshold"]
    if events.empty:
        st.info("Chưa có request nào trong cửa sổ hiện tại.")
        cols = st.columns(2)
        cols[0].metric("Total requests", 0)
        cols[1].metric(f"SLO rate {threshold['operator']} {threshold['value']} {panel['unit']}", "n/a")
        return
    events = events.copy()
    events["minute"] = events["ts"].dt.floor("min")
    per_min = events.groupby("minute").size().reset_index(name="requests")
    current_rate = per_min["requests"].iloc[-1] if not per_min.empty else 0
    cols = st.columns(2)
    cols[0].metric("Total requests (window)", len(events))
    cols[1].metric(f"SLO rate {threshold['operator']} {threshold['value']} {panel['unit']}", threshold_badge(current_rate, threshold))
    chart = alt.Chart(per_min).mark_bar().encode(x="minute:T", y="requests:Q")
    st.altair_chart(chart + rule_layer(threshold["value"]), use_container_width=True)


def render_errors(config: dict, df: pd.DataFrame) -> None:
    panel = panel_by_id(config, "errors")
    st.subheader(panel["title"])
    threshold = panel["threshold"]
    received = (df["event"] == "request_received").sum()
    failed_df = df[df["event"] == "request_failed"]
    failed = len(failed_df)
    error_rate = (failed / received * 100) if received else 0.0
    cols = st.columns(2)
    cols[0].metric("Error rate (%)", f"{error_rate:.2f}")
    cols[1].metric(f"SLO {threshold['operator']} {threshold['value']}{panel['unit']}", threshold_badge(error_rate, threshold))
    if not failed_df.empty:
        breakdown = failed_df["error_type"].value_counts().reset_index()
        breakdown.columns = ["error_type", "count"]
        st.altair_chart(
            alt.Chart(breakdown).mark_bar().encode(x="error_type:N", y="count:Q"),
            use_container_width=True,
        )
    else:
        st.caption("Không có request_failed trong cửa sổ hiện tại.")


def render_cost(config: dict, df: pd.DataFrame) -> None:
    panel = panel_by_id(config, "cost")
    st.subheader(panel["title"])
    events = df[(df["event"] == "response_sent") & df["cost_usd"].notna()]
    threshold = panel["threshold"]
    total = events["cost_usd"].sum() if not events.empty else 0.0
    cols = st.columns(2)
    cols[0].metric("Total cost (USD)", f"{total:.4f}")
    cols[1].metric(f"SLO {threshold['aggregation']} {threshold['operator']} {threshold['value']}{panel['unit']}", threshold_badge(total, threshold))
    if not events.empty:
        events = events.copy()
        events["minute"] = events["ts"].dt.floor("min")
        per_min = events.groupby("minute")["cost_usd"].sum().reset_index()
        st.altair_chart(
            alt.Chart(per_min).mark_bar().encode(x="minute:T", y="cost_usd:Q"),
            use_container_width=True,
        )


def render_tokens(config: dict, df: pd.DataFrame) -> None:
    panel = panel_by_id(config, "tokens")
    st.subheader(panel["title"])
    events = df[df["event"] == "response_sent"]
    threshold = panel["threshold"]
    tokens_in = events["tokens_in"].sum() if not events.empty else 0
    tokens_out = events["tokens_out"].sum() if not events.empty else 0
    total = tokens_in + tokens_out
    cols = st.columns(3)
    cols[0].metric("Tokens in", int(tokens_in))
    cols[1].metric("Tokens out", int(tokens_out))
    cols[2].metric(f"SLO total {threshold['operator']} {threshold['value']}", threshold_badge(total, threshold))
    chart_df = pd.DataFrame({"field": ["tokens_in", "tokens_out"], "value": [tokens_in, tokens_out]})
    st.altair_chart(
        alt.Chart(chart_df).mark_bar().encode(x="field:N", y="value:Q"),
        use_container_width=True,
    )


def render_quality(config: dict, df: pd.DataFrame) -> None:
    panel = panel_by_id(config, "quality")
    st.subheader(panel["title"])
    events = df[(df["event"] == "response_sent") & df["quality_score"].notna()]
    threshold = panel["threshold"]
    mean_score = events["quality_score"].mean() if not events.empty else None
    cols = st.columns(2)
    cols[0].metric("Mean quality score", f"{mean_score:.2f}" if mean_score is not None else "n/a")
    cols[1].metric(f"SLO {threshold['aggregation']} {threshold['operator']} {threshold['value']}", threshold_badge(mean_score, threshold))
    if not events.empty:
        events = events.copy()
        events["minute"] = events["ts"].dt.floor("min")
        per_min = events.groupby("minute")["quality_score"].mean().reset_index()
        chart = alt.Chart(per_min).mark_line(point=True).encode(x="minute:T", y="quality_score:Q")
        st.altair_chart(chart + rule_layer(threshold["value"], color="orange"), use_container_width=True)


def main() -> None:
    config = load_config()
    st.set_page_config(page_title=config["title"], layout="wide")

    refresh_seconds = config["refresh_seconds"]
    st.markdown(f'<meta http-equiv="refresh" content="{refresh_seconds}">', unsafe_allow_html=True)

    st.title(config["title"])
    st.caption(
        f"Time range: last {config['time_range_minutes']} min | "
        f"Refresh: {refresh_seconds}s | Source: data/logs.jsonl"
    )

    mtime = LOG_PATH.stat().st_mtime if LOG_PATH.exists() else 0.0
    df = load_records(mtime)
    df = in_window(df, config["time_range_minutes"])

    if df.empty:
        st.warning(
            "Không có log trong cửa sổ thời gian hiện tại. "
            "Chạy `python scripts/load_test.py` trong khi API đang bật."
        )
        return

    render_latency(config, df)
    render_traffic(config, df)
    render_errors(config, df)
    render_cost(config, df)
    render_tokens(config, df)
    render_quality(config, df)


if __name__ == "__main__":
    main()
