"""
Main Dashboard for Qingsong Streamlit UI.
"""

import sys
from pathlib import Path

# Add tools/ directory to path for imports
_tools_dir = Path(__file__).parent.parent.parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

import streamlit as st
import pandas as pd
from qingsong.ui.common import setup_page, get_core, render_sidebar

setup_page("Dashboard")
render_sidebar()

def main():
    core = get_core()
    
    st.markdown('<div class="main-header">📊 Project Dashboard</div>', unsafe_allow_html=True)
    
    summary = core.summary()
    
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", summary["total_items"])
    with col2:
        st.metric("Active Items", summary["items_by_status"].get("active", 0))
    with col3:
        st.metric("Staged Changes", summary["staged_changes"])
    with col4:
        st.metric("Systems", len(summary["systems"]))
        
    st.divider()
    
    # Visual breakdowns
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Items by Type")
        type_data = pd.DataFrame([
            {"Type": t, "Count": c}
            for t, c in summary["items_by_type"].items()
            if c > 0
        ])
        if not type_data.empty:
            st.bar_chart(type_data.set_index("Type"))
            
    with col2:
        st.subheader("Items by Status")
        status_data = pd.DataFrame([
            {"Status": s, "Count": c}
            for s, c in summary["items_by_status"].items()
            if c > 0
        ])
        if not status_data.empty:
            st.bar_chart(status_data.set_index("Status"))

    # System breakdown
    st.subheader("Items by System")
    system_counts = {}
    for item in core.items.values():
        system_counts[item.system_path] = system_counts.get(item.system_path, 0) + 1
        
    if system_counts:
        sys_df = pd.DataFrame([
            {"System": s, "Count": c}
            for s, c in sorted(system_counts.items())
        ])
        st.dataframe(sys_df, width="stretch", hide_index=True)

    # TBD/TBC Watchlist
    st.divider()
    st.subheader("⚠️ Stability Watchlist (TBD/TBC)")
    tbd_items = [i for i in core.items.values() if i.has_placeholders]
    
    if tbd_items:
        st.warning(f"Found {len(tbd_items)} items with TBD/TBC placeholders.")
        tbd_df = pd.DataFrame([
            {
                "ID": i.id_full,
                "Type": i.type.value,
                "Title": i.title,
                "Status": i.status.value,
                "Owner": i.owner
            }
            for i in sorted(tbd_items, key=lambda x: x.id_full)
        ])
        st.dataframe(tbd_df, width="stretch", hide_index=True)
    else:
        st.success("No items with TBD/TBC placeholders found.")

if __name__ == "__main__":
    main()
