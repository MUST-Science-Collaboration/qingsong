"""
Items Explorer for Qingsong UI.
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
from qingsong.models import ItemType

setup_page("Items Explorer")
render_sidebar()

def render_item_detail(core, item_id):
    item = core.get_item(item_id)
    if not item:
        st.error(f"Item {item_id} not found.")
        return

    st.subheader(f"📄 {item.id_full}")
    
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Type", item.type.value)
    with col2: st.metric("Status", item.status.value)
    with col3: st.metric("Owner", item.owner)

    st.markdown(f"**Title:** {item.title}")
    st.markdown(f"**System:** {item.system_path}")
    
    st.markdown("**Description:**")
    st.info(item.text)

    # Links
    st.divider()
    st.subheader("🔗 Traceability")
    linked = core.get_linked_items(item_id)
    
    col_out, col_in = st.columns(2)
    with col_out:
        st.write("**Outgoing (Target):**")
        for link in item.links:
            st.markdown(f"→ `{link.link_type}`: **{link.target_id}**")
    with col_in:
        st.write("**Incoming (Source):**")
        for other in linked["incoming"]:
            st.markdown(f"← **{other.id_full}**")

def render_new_item_form(core):
    """Render a form to create a new item."""
    st.subheader("🆕 Create New Item")
    
    with st.form("new_item_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            item_type = st.selectbox("Type", [t.value for t in ItemType])
            system = st.selectbox("System", core.metadata.valid_system_paths if core.metadata else [])
        with col2:
            title = st.text_input("Title")
            owner = st.selectbox("Owner", core.metadata.valid_person_ids if core.metadata else [])
            
        text = st.text_area("Description / Text")
        
        # Optional L3
        l3 = st.selectbox("L3 Task (Optional)", ["None"] + (core.metadata.valid_l3_codes if core.metadata else []))
        
        submitted = st.form_submit_state = st.form_submit_button("Create Item (Stage)")
        
        if submitted:
            if not title or not text:
                st.error("Title and Text are required.")
            else:
                try:
                    l3_val = None if l3 == "None" else l3
                    item = core.create_item(
                        item_type=item_type,
                        system_path=system,
                        title=title,
                        text=text,
                        owner=owner,
                        l3=l3_val
                    )
                    st.success(f"Item {item.id_full} staged! Don't forget to 'Flush' in the sidebar.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create item: {e}")

def main():
    core = get_core()
    st.markdown('<div class="main-header">📋 Items Explorer</div>', unsafe_allow_html=True)

    # Main layout with tabs for View vs Create
    tab_view, tab_create = st.tabs(["🔍 Browse Items", "➕ New Item"])
    
    with tab_create:
        render_new_item_form(core)

    with tab_view:
        # Filters
        with st.expander("Filter & Search", expanded=False):
            col1, col2, col3 = st.columns(3)
        with col1:
            sel_type = st.selectbox("Type", ["All"] + [t.value for t in ItemType])
        with col2:
            sel_system = st.selectbox("System", ["All"] + (core.metadata.valid_system_paths if core.metadata else []))
        with col3:
            query = st.text_input("Search", placeholder="Keywords...")

    # Filter items
    items = list(core.items.values())
    if sel_type != "All":
        items = [i for i in items if i.type.value == sel_type]
    if sel_system != "All":
        items = [i for i in items if i.system_path == sel_system]
    if query:
        q = query.lower()
        items = [i for i in items if q in i.title.lower() or q in i.text.lower() or q in i.id_full.lower()]

    # Layout
    col_list, col_detail = st.columns([2, 3])

    with col_list:
        st.subheader(f"Results ({len(items)})")
        for i in sorted(items, key=lambda x: x.id_full):
            if st.button(f"{i.id_full}: {i.title[:40]}...", key=f"btn_{i.id_full}", width="stretch"):
                st.session_state.selected_item = i.id_full
            
    with col_detail:
        sel_id = st.session_state.get("selected_item")
        if sel_id:
            render_item_detail(core, sel_id)
        else:
            st.info("Select an item to view details.")

if __name__ == "__main__":
    main()
