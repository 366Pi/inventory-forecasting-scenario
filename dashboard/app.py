import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from services.data_loader import load_all_demand_data, get_available_items
from services.forecasting import train_and_forecast, calculate_accuracy
from services.pm_engine import load_pm_demand, combine_forecast_with_pm
from services.inventory_engine import run_inventory_planning
from services.alert_engine import run_alert_engine
from services.stock_movement import (
    load_monthly_movement, load_movement_summary,
    get_top_consuming_items, get_overall_stats
)
from main import run_pipeline

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PE Inventory Forecasting",
    page_icon="📦",
    layout="wide"
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("📦 PE Inventory System")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Forecasting",
    "Inventory Planning",
    "Risk Dashboard",
    "Procurement",
    "Stock Movement"
])

st.sidebar.markdown("---")
horizon = st.sidebar.selectbox("Forecast Horizon", [30, 60, 90], index=0)
scenario = st.sidebar.selectbox("Scenario", [
    "Normal",
    "+20% Demand",
    "+50% PM Activity"
])

scenario_map = {
    "Normal":           {"demand_multiplier": 1.0, "pm_multiplier": 1.0},
    "+20% Demand":      {"demand_multiplier": 1.2, "pm_multiplier": 1.0},
    "+50% PM Activity": {"demand_multiplier": 1.0, "pm_multiplier": 1.5},
}
multipliers = scenario_map[scenario]

max_items = st.sidebar.number_input("Max Items to Process", min_value=5, max_value=200, value=20, step=5)

run_btn = st.sidebar.button("Run Pipeline", type="primary")

# ── Pipeline cache ────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Running pipeline...")
def get_pipeline_data(horizon, scenario, max_items):
    return run_pipeline(
        horizon_days=horizon,
        max_items=max_items,
        scenario_name=scenario,
        demand_multiplier=scenario_map[scenario]["demand_multiplier"],
        pm_multiplier=scenario_map[scenario]["pm_multiplier"]
    )

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None

if run_btn:
    st.session_state.pipeline_result = get_pipeline_data(horizon, scenario, max_items)

df = st.session_state.pipeline_result

# ── Helper ────────────────────────────────────────────────────────────────────
def no_data():
    st.info("Click **Run Pipeline** in the sidebar to load data.")
    st.stop()

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Overview
# ═════════════════════════════════════════════════════════════════════════════
if page == "Overview":
    st.title("📦 Inventory Forecasting — Overview")

    if df is None or df.empty:
        no_data()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Parts",          len(df))
    col2.metric("Critical Items",       int((df["risk_indicator"] == "CRITICAL").sum()))
    col3.metric("High Risk Items",      int((df["risk_indicator"] == "HIGH").sum()))
    col4.metric("Total Forecast Demand", f"{df['combined_projected_demand'].sum():,.0f}")

    st.markdown("---")

    # Risk breakdown pie chart
    risk_counts = df["risk_indicator"].value_counts().reset_index()
    risk_counts.columns = ["Risk Level", "Count"]
    color_map = {"CRITICAL": "#d62728", "HIGH": "#ff7f0e", "WARNING": "#f0c419", "NORMAL": "#2ca02c"}

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Risk Distribution")
        fig = px.pie(
            risk_counts, names="Risk Level", values="Count",
            color="Risk Level", color_discrete_map=color_map
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Procurement Priority")
        prio_counts = df["procurement_priority"].value_counts().reset_index()
        prio_counts.columns = ["Priority", "Count"]
        fig2 = px.bar(prio_counts, x="Priority", y="Count",
                    color="Priority",
                    color_discrete_map={"HIGH": "#d62728", "MEDIUM": "#ff7f0e", "LOW": "#2ca02c"})
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("All Items Summary")
    st.dataframe(df[[
        "item", "available_stock", "combined_projected_demand",
        "projected_shortfall", "risk_indicator", "procurement_priority"
    ]].sort_values("projected_shortfall"), use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Forecasting
# ═════════════════════════════════════════════════════════════════════════════
elif page == "Forecasting":
    st.title("📈 Demand Forecasting")

    items = get_available_items()
    selected_item = st.selectbox("Select Item", items)

    if st.button("Generate Forecast"):
        with st.spinner("Training Prophet model..."):
            forecast_df = train_and_forecast(item=selected_item, horizon_days=horizon)
            hist_df     = load_all_demand_data()
            hist_item   = hist_df[hist_df["item"] == selected_item].copy()
            metrics     = calculate_accuracy(item=selected_item)

        if forecast_df.empty:
            st.warning("Not enough data to forecast this item (need at least 10 data points).")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("MAE",  metrics["MAE"]  if metrics["MAE"]  is not None else "N/A")
            col2.metric("RMSE", metrics["RMSE"] if metrics["RMSE"] is not None else "N/A")
            col3.metric("MAPE", f"{metrics['MAPE']}%" if metrics["MAPE"] is not None else "N/A")

            if all(v is None for v in metrics.values()):
                st.info(
                    "Accuracy metrics are not available for this item. "
                    "This is normal for items with limited history or infrequent demand. "
                    "The forecast is still generated using all available data."
                )

            # Historical demand chart
            st.subheader("Historical Demand")
            fig_hist = px.line(hist_item, x="date", y="demand", title=f"{selected_item} — Historical")
            st.plotly_chart(fig_hist, use_container_width=True)

            # Forecast chart with confidence interval
            st.subheader(f"Forecast — Next {horizon} Days")
            fig_fc = go.Figure()
            fig_fc.add_trace(go.Scatter(
                x=forecast_df["forecast_date"], y=forecast_df["max_expected_demand"],
                fill=None, mode="lines", line_color="lightblue", name="Upper Bound"
            ))
            fig_fc.add_trace(go.Scatter(
                x=forecast_df["forecast_date"], y=forecast_df["min_expected_demand"],
                fill="tonexty", mode="lines", line_color="lightblue", name="Lower Bound"
            ))
            fig_fc.add_trace(go.Scatter(
                x=forecast_df["forecast_date"], y=forecast_df["predicted_demand"],
                mode="lines+markers", line_color="royalblue", name="Predicted"
            ))
            fig_fc.update_layout(title=f"{selected_item} — {horizon}-Day Forecast")
            st.plotly_chart(fig_fc, use_container_width=True)

            st.subheader("Forecast Data")
            st.dataframe(forecast_df, use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Inventory Planning
# ═════════════════════════════════════════════════════════════════════════════
elif page == "Inventory Planning":
    st.title("🗂 Inventory Planning")

    if df is None or df.empty:
        no_data()

    st.dataframe(df[[
        "item", "available_stock", "forecast_demand",
        "pm_demand", "combined_projected_demand",
        "safety_stock", "recommended_reorder_qty", "final_reorder_qty",
        "stock_coverage_days"
    ]].sort_values("stock_coverage_days"), use_container_width=True)

    st.subheader("Stock Coverage Distribution")
    coverage = df[df["stock_coverage_days"] < 9999].copy()
    fig = px.histogram(coverage, x="stock_coverage_days", nbins=20,
                        title="Days of Stock Coverage per Item",
                        labels={"stock_coverage_days": "Coverage Days"})
    st.plotly_chart(fig, use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Risk Dashboard
# ═════════════════════════════════════════════════════════════════════════════
elif page == "Risk Dashboard":
    st.title("🚨 Risk Dashboard")

    if df is None or df.empty:
        no_data()

    risk_colors = {"CRITICAL": "🔴", "HIGH": "🟠", "WARNING": "🟡", "NORMAL": "🟢"}

    for level in ["CRITICAL", "HIGH", "WARNING", "NORMAL"]:
        subset = df[df["risk_indicator"] == level]
        icon   = risk_colors[level]
        with st.expander(f"{icon} {level} — {len(subset)} items", expanded=(level == "CRITICAL")):
            if subset.empty:
                st.write("No items at this level.")
            else:
                st.dataframe(subset[[
                    "item", "available_stock", "combined_projected_demand",
                    "projected_shortfall", "stock_coverage_days", "action_status"
                ]], use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 5 — Procurement
# ═════════════════════════════════════════════════════════════════════════════
elif page == "Procurement":
    st.title("🛒 Procurement Recommendations")

    if df is None or df.empty:
        no_data()

    order_df = df[df["final_reorder_qty"] > 0].sort_values(
        ["procurement_priority", "final_reorder_qty"],
        ascending=[True, False]
    )

    st.metric("Items Requiring Reorder", len(order_df))

    for priority in ["HIGH", "MEDIUM", "LOW"]:
        subset = order_df[order_df["procurement_priority"] == priority]
        if not subset.empty:
            st.subheader(f"{'🔴' if priority == 'HIGH' else '🟠' if priority == 'MEDIUM' else '🟢'} {priority} Priority")
            st.dataframe(subset[[
                "item", "available_stock", "combined_projected_demand",
                "projected_shortfall", "final_reorder_qty", "risk_indicator"
            ]], use_container_width=True)

    st.markdown("---")
    st.subheader("Export")
    csv = order_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Procurement List (CSV)", csv, "procurement_list.csv", "text/csv")

    excel_path = "outputs/procurement_list.xlsx"
    os.makedirs("outputs", exist_ok=True)
    order_df.to_excel(excel_path, index=False)
    with open(excel_path, "rb") as f:
        st.download_button("Download Procurement List (Excel)", f, "procurement_list.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6 — Stock Movement Analysis
# ═════════════════════════════════════════════════════════════════════════════
elif page == "Stock Movement":
    st.title("📊 Stock Movement Analysis")
    st.markdown("Historical **stock-in vs stock-out** patterns from the Stock Register — 2018 to present.")

    # ── Overall KPI cards ────────────────────────────────────────────────────
    with st.spinner("Loading stock movement data..."):
        stats = get_overall_stats()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Unique Items Tracked",    stats["unique_items"])
    col2.metric("Total OUT Transactions",  f"{stats['total_out_transactions']:,}")
    col3.metric("Total IN Transactions",   f"{stats['total_in_transactions']:,}")
    col4.metric("Data Range",              f"{pd.to_datetime(stats['earliest']).year} → {pd.to_datetime(stats['latest']).year}"
)

    st.markdown("---")

    # ── Section 1: Item-level monthly IN vs OUT chart ────────────────────────
    st.subheader("📦 Monthly IN vs OUT — Item Deep Dive")

    all_items = get_available_items()
    selected  = st.selectbox("Select Item", all_items, key="mv_item")

    monthly_df = load_monthly_movement(item=selected)

    if monthly_df.empty:
        st.warning("No movement data found for this item.")
    else:
        # Grouped bar chart — IN vs OUT per month
        fig_bar = px.bar(
            monthly_df,
            x="month",
            y=["total_in", "total_out"],
            barmode="group",
            title=f"{selected} — Monthly Stock IN vs OUT",
            labels={"month": "Month", "value": "Quantity", "variable": "Movement"},
            color_discrete_map={"total_in": "#2ca02c", "total_out": "#d62728"},
        )
        fig_bar.update_layout(xaxis_tickangle=-45, legend_title="Type")
        st.plotly_chart(fig_bar, use_container_width=True)

        # Net movement line chart
        fig_net = px.line(
            monthly_df,
            x="month",
            y="net_movement",
            title=f"{selected} — Net Movement per Month  (IN minus OUT)",
            labels={"month": "Month", "net_movement": "Net Movement (units)"},
            markers=True,
        )
        fig_net.add_hline(y=0, line_dash="dash", line_color="gray",
                          annotation_text="Break-even", annotation_position="top right")
        fig_net.update_traces(line_color="#2e75b6")
        st.plotly_chart(fig_net, use_container_width=True)

        # Summary metrics for this item
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Monthly IN",  f"{monthly_df['total_in'].mean():.1f}")
        c2.metric("Avg Monthly OUT", f"{monthly_df['total_out'].mean():.1f}")
        c3.metric("Total IN",        f"{monthly_df['total_in'].sum():,.1f}")
        c4.metric("Total OUT",       f"{monthly_df['total_out'].sum():,.1f}")

        st.subheader("Monthly Breakdown Table")
        st.dataframe(
            monthly_df[["month","total_in","total_out","net_movement","replenishment_ratio"]]
            .sort_values("month", ascending=False),
            use_container_width=True
        )

    st.markdown("---")

    # ── Section 2: Top consuming items ──────────────────────────────────────
    st.subheader("🔥 Top 15 Most Consumed Items (All Time)")

    top_df = get_top_consuming_items(top_n=15)
    fig_top = px.bar(
        top_df,
        x="total_out",
        y="part_name",
        orientation="h",
        title="Top 15 Items by Total Stock-Out Quantity",
        labels={"total_out": "Total OUT Quantity", "part_name": "Item"},
        color="total_out",
        color_continuous_scale="Reds",
    )
    fig_top.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
    st.plotly_chart(fig_top, use_container_width=True)

    st.markdown("---")

    # ── Section 3: Replenishment health summary ──────────────────────────────
    st.subheader("⚖️ Replenishment Health — All Items")
    st.caption("Is stock being replenished fast enough to keep up with consumption?")

    with st.spinner("Loading summary..."):
        summary_df = load_movement_summary()

    # Replenishment status distribution
    status_counts = summary_df["consumption_status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    status_colors = {
        "BALANCED":                    "#2ca02c",
        "OVERSTOCKED":                 "#2e75b6",
        "UNDER-REPLENISHED":           "#ff7f0e",
        "CRITICALLY LOW REPLENISHMENT":"#d62728",
        "NO CONSUMPTION":              "#aaaaaa",
    }

    fig_status = px.pie(
        status_counts,
        names="Status",
        values="Count",
        title="Replenishment Health Distribution",
        color="Status",
        color_discrete_map=status_colors,
    )
    st.plotly_chart(fig_status, use_container_width=True)

    # Filter by status
    status_filter = st.selectbox(
        "Filter by replenishment status",
        ["All"] + list(status_colors.keys()),
        key="status_filter"
    )

    display_df = summary_df if status_filter == "All" else summary_df[summary_df["consumption_status"] == status_filter]

    st.dataframe(
        display_df[[
            "part_name", "avg_monthly_in", "avg_monthly_out",
            "avg_net_movement", "replenishment_ratio", "consumption_status"
        ]],
        use_container_width=True
    )
