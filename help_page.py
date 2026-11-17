import streamlit as st

st.title("Field survey help")
st.caption("How to record a tree network, place starting estimates, and review the least-squares adjustment.")

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
    - The CSV exports are convenient for spreadsheet review. Use the ZIP to restore a survey in this app.
    """)
