"""
Verification Dashboard for Qingsong UI.
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

setup_page("Verification")
render_sidebar()

def main():
    core = get_core()
    st.markdown('<div class="main-header">✅ Verification Dashboard</div>', unsafe_allow_html=True)
    
    summary = core.get_verification_summary()
    
    if summary["total"] == 0:
        st.warning("No requirements found.")
        return

    # Hero metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Requirements", summary["total"])
    with col2:
        st.metric("Verified", summary["verified"])
    with col3:
        st.metric("Progress", f"{summary['percent']:.1f}%")
        
    st.progress(summary["percent"] / 100)
    
    st.divider()
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("By Method")
        m_df = pd.DataFrame([{"Method": m, "Count": c} for m, c in summary["by_method"].items()])
        st.bar_chart(m_df.set_index("Method"))
        
    with col_right:
        st.subheader("By System")
        s_data = []
        for s, stats in summary["by_system"].items():
            s_data.append({
                "System": s,
                "Verified": stats["verified"],
                "Total": stats["total"],
                "Percent": (stats["verified"] / stats["total"]) * 100
            })
        st.dataframe(pd.DataFrame(s_data), hide_index=True, use_container_width=True)

if __name__ == "__main__":
    main()
