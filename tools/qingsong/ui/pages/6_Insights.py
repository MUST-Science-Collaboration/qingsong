"""
System Insights dashboard for Qingsong UI.
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

setup_page("System Insights")
render_sidebar()

def main():
    core = get_core()
    st.markdown('<div class="main-header">💡 System Insights</div>', unsafe_allow_html=True)
    
    # 1. Coverage Metrics
    st.subheader("📊 System Maturity & Coverage")
    stats = core.get_coverage_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Traceability Coverage**")
        st.metric("Linked to Parents", f"{stats['traceability_percent']:.1f}%", 
                  help="Requirements that have a parent (derives_from) link.")
        st.progress(stats['traceability_percent'] / 100)
        st.caption(f"{stats['traceability_count']} of {stats['total_requirements']} items")
        
    with col2:
        st.write("**Verification Coverage**")
        st.metric("Linked to Evidence", f"{stats['verification_percent']:.1f}%",
                  help="Requirements linked to implementation/verification items.")
        st.progress(stats['verification_percent'] / 100)
        st.caption(f"{stats['verification_count']} of {stats['total_requirements']} items")

    st.divider()

    # 2. Design Gaps (Orphans)
    st.subheader("🔍 Design Gap Analysis (Orphans)")
    report = core.get_orphan_report()
    
    tab_root, tab_leaf, tab_unver = st.tabs([
        "🌳 Root Orphans", 
        "🍂 Leaf Orphans", 
        "❌ Unverified Gaps"
    ])
    
    with tab_root:
        st.write("Requirements with **no parent**. These may be disconnected project goals.")
        if not report["root_orphans"]:
            st.success("No root orphans found.")
        else:
            root_df = pd.DataFrame([
                {"ID": tid, "Title": core.items[tid].title}
                for tid in report["root_orphans"]
            ])
            st.dataframe(root_df, width="stretch", hide_index=True)
            
    with tab_leaf:
        st.write("Items with **no children**. These items currently satisfy no downstream needs.")
        if not report["leaf_orphans"]:
            st.success("No leaf orphans found.")
        else:
            leaf_df = pd.DataFrame([
                {"ID": tid, "Type": core.items[tid].type.value, "Title": core.items[tid].title}
                for tid in report["leaf_orphans"]
            ])
            st.dataframe(leaf_df, width="stretch", hide_index=True)
            
    with tab_unver:
        st.write("Requirements with **no verification links**. These requirements have no proof of implementation.")
        if not report["unverified_requirements"]:
            st.success("No unverified requirements found.")
        else:
            unver_df = pd.DataFrame([
                {"ID": tid, "Title": core.items[tid].title}
                for tid in report["unverified_requirements"]
            ])
            st.dataframe(unver_df, width="stretch", hide_index=True)

if __name__ == "__main__":
    main()
