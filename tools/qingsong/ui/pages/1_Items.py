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

    # Header with Edit Toggle
    col_h, col_edit = st.columns([4, 1])
    with col_h:
        st.subheader(f"📄 {item.id_full}")
    with col_edit:
        edit_mode = st.toggle("Edit Mode", key=f"edit_toggle_{item_id}")

    if item.has_placeholders:
        st.warning("⚠️ This item contains **TBD** or **TBC** placeholders and is considered unstable.")

    if edit_mode:
        render_edit_form(core, item)
    else:
        render_view_mode(core, item)

def render_view_mode(core, item):
    item_id = item.id_full
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Type", item.type.value)
    with col2: st.metric("Status", item.status.value)
    with col3: st.metric("Owner", item.owner)

    st.markdown(f"**Title:** {item.title}")
    st.markdown(f"**System:** {item.system_path}")
    
    # Collaborators
    if item.collaborators:
        st.write(f"**Collaborators:** {', '.join(item.collaborators)}")
    
    with st.expander("👥 Manage Collaborators"):
        all_people = core.metadata.valid_person_ids if core.metadata else []
        new_collabs = st.multiselect("Update Collaborators", all_people, default=item.collaborators)
        if st.button("Save Collaborators"):
            try:
                core.update_item(item_id, collaborators=new_collabs)
                st.success("Collaborators updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Update failed: {e}")

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

    # Impact Analysis
    st.divider()
    st.subheader("💥 Impact Analysis (Transitive)")
    
    with st.expander("Analyze Change Ripple Effect"):
        direction = st.radio("Impact Direction", ["both", "downward", "upward"], horizontal=True, key=f"impact_dir_{item_id}")
        if st.button("Run Analysis", key=f"run_impact_{item_id}"):
            report = core.get_impact_analysis(item_id, direction=direction)
            if report["impacted_count"] == 0:
                st.success("No transitive dependencies found. This item is an leaf node.")
            else:
                st.warning(f"Changing this item potentially impacts **{report['impacted_count']}** other items.")
                impact_df = pd.DataFrame([
                    {
                        "ID": tid,
                        "Type": i.type.value,
                        "Title": i.title,
                        "System": i.system_path
                    }
                    for tid, i in report["items"].items()
                ])
                st.dataframe(impact_df, width="stretch", hide_index=True)

    # Discussions
    st.divider()
    st.subheader("💬 Discussions")
    
    if item.discussions:
        for comment in item.discussions:
            with st.chat_message("user", avatar="👤"):
                st.write(f"**{comment.author}** ({comment.timestamp.strftime('%Y-%m-%d %H:%M')})")
                st.write(comment.text)
    else:
        st.info("No discussions yet.")

    # Add comment form
    with st.expander("➕ Add Comment"):
        with st.form(f"comment_form_{item_id}", clear_on_submit=True):
            author = st.selectbox("Commenter", core.metadata.valid_person_ids if core.metadata else [], key=f"auth_{item_id}")
            comment_text = st.text_area("Your comment", key=f"text_{item_id}")
            if st.form_submit_button("Post Comment"):
                if comment_text:
                    try:
                        core.add_comment(item_id, author, comment_text)
                        st.success("Comment staged!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to add comment: {e}")
                else:
                    st.error("Comment cannot be empty.")

def render_edit_form(core, item):
    """Form to edit an existing item."""
    item_id = item.id_full
    
    with st.form(f"edit_form_{item_id}"):
        st.write("**Core Content**")
        new_title = st.text_input("Title", value=item.title)
        new_text = st.text_area("Description / Text", value=item.text, height=200)
        
        col1, col2 = st.columns(2)
        with col1:
            new_status = st.selectbox("Status", ["draft", "active", "retired"], index=["draft", "active", "retired"].index(item.status.value))
        with col2:
            new_owner = st.selectbox("Owner", core.metadata.valid_person_ids if core.metadata else [], index=(core.metadata.valid_person_ids.index(item.owner) if core.metadata and item.owner in core.metadata.valid_person_ids else 0))

        st.divider()
        st.write("**Relationship Management**")
        
        # Display current links with delete option
        updated_links = list(item.links)
        for idx, link in enumerate(item.links):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"🔗 `{link.link_type}`: **{link.target_id}**")
            if c2.checkbox("Remove", key=f"del_link_{item_id}_{idx}"):
                updated_links.remove(link)
        
        st.write("➕ Add Link")
        lx1, lx2 = st.columns(2)
        target_id = lx1.text_input("Target ID", key=f"new_link_target_{item_id}")
        link_type = lx2.selectbox("Link Type", core.metadata.valid_link_types if core.metadata else ["related_to"], key=f"new_link_type_{item_id}")
        
        if st.form_submit_button("Stage Changes", type="primary"):
            try:
                updates = {
                    "title": new_title,
                    "text": new_text,
                    "status": new_status,
                    "owner": new_owner,
                    "links": updated_links
                }
                
                # Add new link if provided
                if target_id:
                    from qingsong.models.common import Link
                    updates["links"].append(Link(target_id=target_id, link_type=link_type))
                
                core.update_item(item_id, **updates)
                st.success("Changes staged! Flush in the sidebar to save.")
                st.rerun()
            except Exception as e:
                st.error(f"Update failed: {e}")

    # Migration (Separate because it changes ID)
    st.divider()
    with st.expander("🛠️ Advanced: Migrate Item"):
        st.info("Migration moves the item to a new system and updates its ID and all incoming links.")
        new_sys = st.selectbox("New System", core.metadata.valid_system_paths if core.metadata else [], key=f"mig_sys_{item_id}")
        new_l3 = st.selectbox("New L3 (Optional)", ["None"] + (core.metadata.valid_l3_codes if core.metadata else []), key=f"mig_l3_{item_id}")
        
        if st.button("Migrate Item"):
            try:
                l3_val = None if new_l3 == "None" else new_l3
                migrated = core.migrate_item(item_id, new_sys, l3_val)
                st.success(f"Migrated to {migrated.id_full}! Staged.")
                st.session_state.selected_item = migrated.id_full
                st.rerun()
            except Exception as e:
                st.error(f"Migration failed: {e}")

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
        
        submitted = st.form_submit_button("Create Item (Stage)")
        
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
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                sel_type = st.selectbox("Type", ["All"] + [t.value for t in ItemType])
            with col2:
                sel_system = st.selectbox("System", ["All"] + (core.metadata.valid_system_paths if core.metadata else []))
            with col3:
                query = st.text_input("Search", placeholder="Keywords...")
            with col4:
                tbd_only = st.checkbox("TBD/TBC Only")
    
        # Filter items
        items = list(core.items.values())
        if sel_type != "All":
            items = [i for i in items if i.type.value == sel_type]
        if sel_system != "All":
            items = [i for i in items if i.system_path == sel_system]
        if tbd_only:
            items = [i for i in items if i.has_placeholders]
        if query:
            q = query.lower()
            items = [i for i in items if q in i.title.lower() or q in i.text.lower() or q in i.id_full.lower()]
    
        # Layout
        col_list, col_detail = st.columns([2, 3])
    
        with col_list:
            st.subheader(f"Results ({len(items)})")
            
            # If search was performed via FTS5, we might have snippets
            fts_results = {}
            if query:
                try:
                    # Use the core search which returns dicts with snippets
                    search_data = core.search(query)
                    fts_results = {r["id_full"]: r.get("snippet") for r in search_data}
                except:
                    pass
    
            for i in sorted(items, key=lambda x: x.id_full):
                label = f"{i.id_full}: {i.title[:40]}..."
                if i.has_placeholders:
                    label = "⚠️ " + label
                
                with st.container():
                    if st.button(label, key=f"btn_{i.id_full}", width="stretch"):
                        st.session_state.selected_item = i.id_full
                    
                    # Show snippet if this was a search result
                    if i.id_full in fts_results and fts_results[i.id_full]:
                        st.caption(f"...{fts_results[i.id_full]}...")
                    
                    st.write("") # Spacer
                
        with col_detail:
            sel_id = st.session_state.get("selected_item")
            if sel_id:
                render_item_detail(core, sel_id)
            else:
                st.info("Select an item to view details.")

if __name__ == "__main__":
    main()
