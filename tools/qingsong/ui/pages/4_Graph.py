"""
Graph Visualizer for Qingsong UI.
"""

import sys
from pathlib import Path

# Add tools/ directory to path for imports
_tools_dir = Path(__file__).parent.parent.parent.parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

import streamlit as st
import streamlit.components.v1 as components
import os
import tempfile
from qingsong.ui.common import setup_page, get_core, render_sidebar
from qingsong.graph import build_graph, get_neighborhood, export_graph_html

setup_page("Graph Visualizer")
render_sidebar()

def main():
    core = get_core()
    st.markdown('<div class="main-header">🕸️ Graph Visualizer</div>', unsafe_allow_html=True)
    
    # Options
    col1, col2 = st.columns(2)
    with col1:
        mode = st.radio("Mode", ["Full Graph", "Neighborhood"], horizontal=True)
    with col2:
        item_id = st.text_input("Center Item ID", placeholder="MUST-...", disabled=(mode == "Full Graph"))

    # Generate graph
    with st.spinner("Generating graph..."):
        try:
            if mode == "Full Graph":
                G = build_graph(core.items)
                title = "Full Link Graph"
            else:
                if not item_id:
                    st.info("Enter an Item ID to view its neighborhood.")
                    return
                G = get_neighborhood(core.items, item_id, depth=2)
                title = f"Neighborhood of {item_id}"

            # Export to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                export_graph_html(G, Path(tmp.name), title=title)
                with open(tmp.name, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                os.unlink(tmp.name)

            # Render
            components.html(html_content, height=600, scrolling=True)
            
        except Exception as e:
            st.error(f"Failed to generate graph: {e}")

if __name__ == "__main__":
    main()
