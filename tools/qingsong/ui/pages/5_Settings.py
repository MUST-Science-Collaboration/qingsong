"""
Settings and Vault Management for Qingsong UI.
"""

import sys
import os
from pathlib import Path

# Add tools/ directory to path for imports
_tools_dir = Path(__file__).parent.parent.parent.parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

import streamlit as st
from qingsong.ui.common import setup_page, get_core, render_sidebar

setup_page("Settings")
render_sidebar()

def main():
    core = get_core()
    st.markdown('<div class="main-header">⚙️ Settings</div>', unsafe_allow_html=True)
    
    st.subheader("Vault Management")
    st.info(f"Current project root: `{core.project_root.resolve()}`")
    
    new_root = st.text_input("Switch Vault (Path)", placeholder="/path/to/another/vault")
    if st.button("Switch"):
        if os.path.exists(new_root):
            os.environ["QINGSONG_ROOT"] = str(Path(new_root).resolve())
            st.cache_resource.clear()
            st.success(f"Switched to {new_root}")
            st.rerun()
        else:
            st.error("Path does not exist.")

    st.divider()
    st.subheader("Metadata Integrity")
    if st.button("Run Meta Validate"):
        errors = core.validate_metadata()
        if not errors:
            st.success("Metadata is valid!")
        else:
            for e in errors:
                st.error(e)

    st.divider()
    st.subheader("Search Cache")
    if st.button("Rebuild SQLite Cache"):
        with st.spinner("Building..."):
            core.build_cache()
            st.success("Cache rebuilt successfully.")

if __name__ == "__main__":
    main()
