import streamlit as st

# 1. Page Configuration (Must run before any other Streamlit command)
st.set_page_config(
    page_title="Live Field Survey Network",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Global State Initialization (Session Memory Management)
# Ensure variables are initialized cleanly here so they persist across pages
if "survey_ledger" not in st.session_state:
    # Example placeholder: Initialize with whatever storage.py or solver.py expects
    st.session_state["survey_ledger"] = [] 

if "calculated_coords" not in st.session_state:
    st.session_state["calculated_coords"] = None

# 3. Modular Architecture Routing
# Point your navigation pages to their standalone implementation files
data_entry_page = st.Page(
    page="data_entry.py", 
    title="Data Entry & Mapping", 
    icon="📝", 
    default=True
)

# Optional: If you want exporter to be its own visual subpage later instead of a footer widget
# export_page = st.Page("exporter.py", title="Export Data Packages", icon="💾")

# 4. Fire Up the Navigation Controller
pg = st.navigation([data_entry_page])
pg.run()
