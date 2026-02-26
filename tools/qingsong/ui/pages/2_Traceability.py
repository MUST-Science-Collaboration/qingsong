"""
Traceability Matrix view for Qingsong UI.
"""

import sys
from pathlib import Path

# Add tools/ directory to path for imports
_tools_dir = Path(__file__).parent.parent.parent.parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

import streamlit as st
import pandas as pd
from qingsong.ui.common import setup_page, get_core, render_sidebar

setup_page("Traceability")
render_sidebar()

def main():
    core = get_core()
    st.markdown('<div class="main-header">🔗 Traceability Matrix</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        direction = st.selectbox("Direction", ["downward", "upward"], help="Downward: find children. Upward: find parents.")
    with col2:
        # Simple search filter for the matrix
        filter_text = st.text_input("Filter IDs", placeholder="Filter by requirement ID...")

    matrix = core.get_traceability_matrix(direction=direction)
    
    if not matrix:
        st.warning("No traceability data found.")
        return

    # Flatten matrix for display
    display_data = []
    for row in matrix:
        if filter_text and filter_text.lower() not in row["id"].lower():
            continue
            
        links = row["links"]
        if not links:
            display_data.append({
                "Requirement": row["id"],
                "Title": row["title"],
                "Linked ID": "None",
                "Link Type": "N/A"
            })
        else:
            for l in links:
                display_data.append({
                    "Requirement": row["id"],
                    "Title": row["title"],
                    "Linked ID": l["id"],
                    "Link Type": l["type"]
                })

    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.download_button(
        "Download Matrix (CSV)",
        df.to_csv(index=False),
        f"traceability_{direction}.csv",
        "text/csv"
    )

if __name__ == "__main__":
    main()
