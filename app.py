import streamlit as st

st.set_page_config(
    page_title="Live Field Survey Network",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure data arrays survive page-swaps in global context memory
if "survey_ledger" not in st.session_state:
    st.session_state["survey_ledger"] = []

if "tree_estimates" not in st.session_state:
    st.session_state["tree_estimates"] = {}

# Set up routing mapping
data_entry_page = st.Page(
    page="data_entry.py", 
    title="Data Entry & Mapping", 
    icon="📝", 
    default=True
)

pg = st.navigation([data_entry_page])
pg.run()
