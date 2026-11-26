"""Tablet map page for a read-only, independently refreshable survey view."""

import streamlit as st

import solver
import storage
from map_view import build_survey_map
from page_navigation import render_page_title_selector


render_page_title_selector("Map")
state = storage.load_dataset_state()
info = state["info"]
st.caption(f"Active dataset: {info['dataset_id']}")

left, right = st.columns([1, 1])
with left:
    show_estimates = st.checkbox(
        "Show initial estimates",
        value=bool(st.session_state.get("map_page_show_estimates", False)),
        key="map_page_show_estimates",
    )
with right:
    auto_refresh = st.checkbox(
        "Auto-refresh map",
        value=bool(st.session_state.get("map_page_auto_refresh", True)),
        key="map_page_auto_refresh",
        help="Only the map page refreshes automatically; edits on the Data Entry page are left untouched.",
    )
interval_col, refresh_col = st.columns([1, 1])
with interval_col:
    interval = st.selectbox(
        "Refresh interval",
        options=(5, 10, 15, 30, 60),
        index=2,
        format_func=lambda seconds: f"{seconds} seconds",
        disabled=not auto_refresh,
        key="map_page_refresh_interval",
    )
with refresh_col:
    st.write("")
    manual_refresh = st.button("Refresh map", width="stretch", key="map_page_manual_refresh")


@st.fragment(run_every=interval if auto_refresh else None)
def render_map():
    snapshot = storage.load_dataset_state(force=True)
    trees = snapshot["trees"]
    measurements = snapshot["measurements"]
    coords, _ = solver.run_network_adjustment(trees, measurements)
    underconstrained = solver.underconstrained_tree_ids(trees, measurements, coords)
    latest_info = snapshot["info"]
    fig = build_survey_map(
        trees,
        measurements,
        coords,
        underconstrained,
        axis_layout=latest_info.get("map_axis_layout", storage.DEFAULT_MAP_ORIENTATION["map_axis_layout"]),
        mirror_x=latest_info.get("mirror_map_x", False),
        mirror_y=latest_info.get("mirror_map_y", False),
        show_initial_estimates=st.session_state.get("map_page_show_estimates", False),
        show_starting_targets=False,
        include_target_trace=False,
    )
    st.plotly_chart(
        fig,
        key="tablet_map_figure",
        config={"responsive": True, "scrollZoom": False, "displayModeBar": False},
        width="stretch",
    )


if manual_refresh:
    st.rerun()
render_map()
