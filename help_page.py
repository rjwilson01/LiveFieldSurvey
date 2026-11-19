import streamlit as st
import plotly.graph_objects as go
from page_navigation import render_page_title_selector

render_page_title_selector("Help")
st.caption("Record tree-to-tree tape distances and adjust the map with least squares. Enter coordinates and distances in millimetres.")

with st.expander("Map orientation and deviation alerts", expanded=True):
    st.selectbox(
        "Map axes",
        ("X horizontal, Y vertical", "Y horizontal, X vertical"),
        key="map_axis_layout",
        help="Changes the map display only. Tree coordinates remain in their original X and Y fields.",
    )
    mirror_col_x, mirror_col_y = st.columns(2)
    with mirror_col_x:
        st.checkbox("Mirror X", key="mirror_map_x", help="Show positive X toward the opposite side of the map.")
    with mirror_col_y:
        st.checkbox("Mirror Y", key="mirror_map_y", help="Show positive Y toward the opposite side of the map.")

    swap_axes = st.session_state.get("map_axis_layout", "X horizontal, Y vertical") == "Y horizontal, X vertical"
    mirror_x = bool(st.session_state.get("mirror_map_x", False))
    mirror_y = bool(st.session_state.get("mirror_map_y", False))
    horizontal_axis = "Y" if swap_axes else "X"
    vertical_axis = "X" if swap_axes else "Y"
    horizontal_mirrored = mirror_y if swap_axes else mirror_x
    vertical_mirrored = mirror_x if swap_axes else mirror_y
    horizontal_sign = -1 if horizontal_mirrored else 1
    vertical_sign = -1 if vertical_mirrored else 1

    orientation_diagram = go.Figure()
    orientation_diagram.add_shape(
        type="rect",
        x0=0 if horizontal_sign > 0 else -1,
        x1=1 if horizontal_sign > 0 else 0,
        y0=0 if vertical_sign > 0 else -1,
        y1=1 if vertical_sign > 0 else 0,
        fillcolor="rgba(34,197,94,0.22)",
        line={"color": "rgba(34,197,94,0.55)", "width": 1},
        layer="below",
    )
    orientation_diagram.add_trace(go.Scatter(x=[-1.05, 1.05], y=[0, 0], mode="lines", line={"color": "#64748b", "width": 2}, hoverinfo="skip", showlegend=False))
    orientation_diagram.add_trace(go.Scatter(x=[0, 0], y=[-1.05, 1.05], mode="lines", line={"color": "#64748b", "width": 2}, hoverinfo="skip", showlegend=False))
    orientation_diagram.add_annotation(x=horizontal_sign * 0.77, y=0.08, text=f"+{horizontal_axis}", showarrow=False, font={"color": "#166534", "size": 13})
    orientation_diagram.add_annotation(x=-horizontal_sign * 0.77, y=0.08, text=f"−{horizontal_axis}", showarrow=False, font={"color": "#64748b", "size": 12})
    orientation_diagram.add_annotation(x=0.12, y=vertical_sign * 0.78, text=f"+{vertical_axis}", showarrow=False, font={"color": "#166534", "size": 13})
    orientation_diagram.add_annotation(x=0.12, y=-vertical_sign * 0.78, text=f"−{vertical_axis}", showarrow=False, font={"color": "#64748b", "size": 12})
    orientation_diagram.update_layout(
        height=250,
        margin={"l": 20, "r": 20, "t": 15, "b": 15},
        xaxis={"range": [-1.1, 1.1], "showgrid": False, "showticklabels": False, "zeroline": False, "title": None},
        yaxis={"range": [-1.1, 1.1], "showgrid": False, "showticklabels": False, "zeroline": False, "title": None, "scaleanchor": "x", "scaleratio": 1},
        showlegend=False,
    )
    st.plotly_chart(orientation_diagram, config={"displayModeBar": False, "responsive": True})
    st.caption("Green shading marks the active positive-coordinate area. Mirroring or swapping changes the map view, not the stored estimates.")

    st.subheader("Deviation alerts")
    st.number_input("Moderate distance residual (mm)", min_value=0.0, value=50.0, step=10.0, key="distance_tolerance")
    st.number_input("Large shift from estimate (mm)", min_value=0.0, value=1000.0, step=100.0, key="estimate_tolerance")

with st.expander("Set the map reference", expanded=True):
    st.markdown("""
    - Tree 1 is fixed at **(0, 0)**.
    - Tree 2 lies on the positive **Y axis**. Its X coordinate is fixed at zero.
    - Record a Tree 1 ↔ Tree 2 baseline distance to establish the map scale. Choose which direction to record based on how the tape or laser was read.
    - The map keeps a small negative margin so the origin markers and axis remain visible.
    - Gray lines show recorded measurements. Amber trees need more links or a connection to the anchored network.
    """)

with st.expander("Add trees and set starting positions", expanded=True):
    st.markdown("""
    1. In **Tree management** on the sidebar, choose the next available Tree ID.
    2. Tap one of the faint grid points on the map. The X and Y estimate fields update; the tree is not saved yet.
    3. Edit either estimate if needed, then press **Add tree**. For an existing tree, select its ID and press **Update tree**.
    4. Select an existing tree ID to view its calculated location when the measurement network can be adjusted.

    Tree 1 and Tree 2 are protected anchors. Deleted IDs are retired and are not offered again. The starting estimates guide the solver; they are approximate positions and may shift substantially after measurements are added.

    **Tree ID cases:** Tree 1 is fixed at the origin and both coordinates are disabled. Tree 2 stays on the Y axis, so X is disabled and Y can be set. Other existing trees can have both starting estimates edited or be deleted. The final option in the ID list is the next unused ID, ready to add.
    """)

with st.expander("Record and edit measurements", expanded=True):
    st.markdown("""
    - Tap a tree marker to fill the highlighted **From** or **To** field. The next map pick alternates between these fields. Tapping the current endpoint keeps it and moves the next pick to the other field; a tree cannot measure to itself.
    - You may enter the two IDs with the dropdowns and type-to-search instead.
    - Tree 1 is at the lower-left origin and Tree 2 is above it on the Y axis. Tap a grid point to set the selected tree's starting estimate; then Add or Update in the sidebar.
    - Choosing From and To fills the distance from an existing directed record when present. Otherwise, it estimates the distance from calculated positions where available, falling back to starting estimates. The distance remains editable.
    - If the chosen From → To record already exists, the app loads it and changes the action to **Update measurement**. The table's **Select** checkboxes allow only one active record; choosing another clears the previous selection.
    - Enter a distance in millimetres and press **Add measurement**. One record is allowed per direction for each pair, so A → B and B → A can both be stored.
    - Edit **Meas** directly in the table. Use the **Select** checkbox to load a record into the sidebar, where you can press **Update measurement** or **Delete measurement**. A line tap highlights all records for that pair.
    - Selecting a row shows its From and To trees, their initial coordinates, and their calculated coordinates in the sidebar. Edit the initial coordinates there and press **Update starting estimates** to adjust the solver's starting positions.
    - Rows are grouped by tree pair. **Δ** is adjusted distance minus measured distance, rounded to whole millimetres. Red rows exceed the editable residual threshold. All table fields except **Meas** and **Select** are read only.
    """)

with st.expander("Understand map colours and calculated locations"):
    st.markdown("""
    - Blue marks Trees 1 and 2; green marks other trees; amber marks trees that need more links or a connection to the anchored network.
    - The least-squares adjustment uses the recorded distances and starting estimates. A calculated location appears in Tree management once available. “Adjusted location so far” means the network is still incomplete, so treat that position as provisional.
    - A large shift warning means a tree moved farther than the editable estimate threshold. This can be expected when a rough map tap is replaced by stronger measurement evidence.
    - Use **Show initial estimates** above the map to compare the saved starting positions with adjusted positions. It stays in the selected state across map clicks.
    """)

with st.expander("Back up and transfer a dataset"):
    st.markdown("""
    - Choose **Start a new dataset** in the sidebar to finish the current survey and start fresh with Trees 1 and 2 as anchors. Its first available tree ID is 3, and the dataset receives a new serial number.
    - The sidebar shows whether changes have been included in a requested backup. Download the complete dataset ZIP regularly; it preserves the dataset identity, tree estimates, measurements, and retired Tree ID sequence.
    - Upload a saved ZIP in the sidebar to replace the active dataset. The app shows a replacement warning and requires confirmation before loading it.
    - Open **Data management** to rename, back up, upload, or start a dataset. The CSV exports there are convenient for spreadsheet review; use the ZIP to restore a survey in this app.
    """)
