"""
Shared UI components and logic for Qingsong Streamlit app.
"""

import os
import sys
from pathlib import Path
import streamlit as st

# Add tools/ directory to path for imports
_tools_dir = Path(__file__).parent.parent.parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

from qingsong.core import QingsongCore

def setup_page(title: str):
    """Common page configuration and styling."""
    st.set_page_config(
        page_title=f"Qingsong - {title}",
        page_icon="🔭",
        layout="wide",
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: 700;
            color: #1E3A5F;
            margin-bottom: 0.5rem;
        }
        .status-draft { color: #FFA500; font-weight: 600; }
        .status-active { color: #28A745; font-weight: 600; }
        .status-retired { color: #6C757D; font-weight: 600; }
        .type-req { background-color: #4CAF50; color: white; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.8rem; }
        .type-rsk { background-color: #F44336; color: white; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.8rem; }
        .type-ifc { background-color: #2196F3; color: white; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def get_core() -> QingsongCore:
    """Load QingsongCore, respecting QINGSONG_ROOT if set."""
    root = os.environ.get("QINGSONG_ROOT")
    try:
        return QingsongCore.load(project_root=root)
    except Exception as e:
        st.error(f"Failed to load project: {e}")
        st.info("Check your project root directory.")
        st.stop()

def render_sidebar():
    """Render common sidebar info."""
    core = get_core()
    st.sidebar.title("🔭 Qingsong")
    st.sidebar.info(f"**Vault:** {core.project_root.name}\n\n**Items:** {len(core.items)}")
    
    # Staged changes info
    staged_count = len(core.staged_changes)
    if staged_count > 0:
        st.sidebar.warning(f"⚠️ {staged_count} staged changes")
        if st.sidebar.button("Flush Changes to Disk", type="primary"):
            try:
                count = core.flush()
                st.sidebar.success(f"Successfully wrote {count} items.")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Flush failed: {e}")
        if st.sidebar.button("Discard Changes"):
            core.discard_changes()
            st.rerun()

    if st.sidebar.button("Reload Data"):
        st.cache_resource.clear()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("Advanced Insights")
    if st.sidebar.button("💡 View System Insights", width="stretch"):
        st.switch_page("pages/6_Insights.py")
