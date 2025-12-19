"""
Streamlit UI for Qingsong.

A simple GUI for browsing/filtering items, viewing details, and showing connected items.

Launch with: qingsong ui
Or directly: streamlit run tools/qingsong/ui/app_streamlit.py
"""

import sys
from pathlib import Path

# Add tools/ directory to path for imports when run directly
# This allows both `qingsong ui` (installed) and direct `streamlit run` to work
_tools_dir = Path(__file__).parent.parent.parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

import streamlit as st
import pandas as pd

from qingsong.core import QingsongCore
from qingsong.models import ItemType


# Page config
st.set_page_config(
    page_title="Qingsong - MUST Project Management",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
    }
    .item-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #667eea;
        margin-bottom: 1rem;
    }
    .status-draft { color: #FFA500; }
    .status-active { color: #28A745; }
    .status-retired { color: #6C757D; }
    .status-superseded { color: #007BFF; }
    .type-req { background-color: #4CAF50; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; }
    .type-rsk { background-color: #F44336; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; }
    .type-ifc { background-color: #2196F3; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; }
    .type-doc { background-color: #9C27B0; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; }
    .type-dat { background-color: #FF9800; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; }
    .type-note { background-color: #607D8B; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_core():
    """Load QingsongCore (cached)."""
    return QingsongCore.load()


def main():
    # Header
    st.markdown('<div class="main-header">🔭 Qingsong</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Project Management Engine for MUST Telescope</div>', unsafe_allow_html=True)

    # Load data
    try:
        core = load_core()
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.info("Make sure you're running from the project root directory.")
        return

    # Sidebar filters
    st.sidebar.title("Filters")

    # Type filter
    type_options = ["All"] + [t.value for t in ItemType]
    selected_type = st.sidebar.selectbox("Item Type", type_options)

    # System filter
    system_options = ["All"] + (core.metadata.valid_system_paths if core.metadata else [])
    selected_system = st.sidebar.selectbox("System", system_options)

    # Status filter
    status_options = ["All", "draft", "active", "retired", "superseded"]
    selected_status = st.sidebar.selectbox("Status", status_options)

    # Owner filter
    owner_options = ["All"] + (core.metadata.valid_person_ids if core.metadata else [])
    selected_owner = st.sidebar.selectbox("Owner", owner_options)

    # Search
    search_query = st.sidebar.text_input("Search", placeholder="Search items...")

    # Apply filters
    items = list(core.items.values())

    if selected_type != "All":
        items = [i for i in items if i.type.value == selected_type]

    if selected_system != "All":
        items = [i for i in items if i.system_path == selected_system]

    if selected_status != "All":
        items = [i for i in items if i.status.value == selected_status]

    if selected_owner != "All":
        items = [i for i in items if i.owner == selected_owner]

    if search_query:
        query_lower = search_query.lower()
        items = [i for i in items if
                 query_lower in i.id_full.lower() or
                 query_lower in i.title.lower() or
                 query_lower in i.text.lower()]

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Items", "📊 Dashboard", "🔗 Links", "ℹ️ About"])

    with tab1:
        render_items_tab(core, items)

    with tab2:
        render_dashboard_tab(core)

    with tab3:
        render_links_tab(core)

    with tab4:
        render_about_tab(core)


def render_items_tab(core: QingsongCore, items: list):
    """Render the items list and detail view."""
    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader(f"Items ({len(items)})")

        if not items:
            st.info("No items match the current filters.")
            return

        # Items list
        for item in sorted(items, key=lambda x: x.id_full):
            type_class = f"type-{item.type.value.lower()}"
            status_class = f"status-{item.status.value}"

            with st.container():
                col_id, col_btn = st.columns([4, 1])
                with col_id:
                    st.markdown(f"""
                    <span class="{type_class}">{item.type.value}</span>
                    <strong>{item.id_full}</strong><br>
                    <small>{item.title[:50]}{'...' if len(item.title) > 50 else ''}</small><br>
                    <small class="{status_class}">{item.status.value}</small>
                    """, unsafe_allow_html=True)
                with col_btn:
                    if st.button("View", key=f"view_{item.id_full}"):
                        st.session_state.selected_item = item.id_full

                st.divider()

    with col2:
        # Detail view
        selected_id = st.session_state.get("selected_item")
        if selected_id and selected_id in core.items:
            render_item_detail(core, selected_id)
        else:
            st.info("Select an item to view details.")


def render_item_detail(core: QingsongCore, item_id: str):
    """Render detailed view of a single item."""
    item = core.items[item_id]

    st.subheader(f"📄 {item.id_full}")

    # Basic info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Type", item.type.value)
    with col2:
        st.metric("Status", item.status.value)
    with col3:
        st.metric("Owner", item.owner)

    st.markdown(f"**Title:** {item.title}")
    st.markdown(f"**System:** {item.system_path}")
    if item.l3:
        st.markdown(f"**L3 Task:** {item.l3}")

    # Description
    st.markdown("**Description:**")
    st.markdown(item.text)

    # Type-specific fields
    if item.type == ItemType.REQ:
        st.markdown("---")
        st.markdown("**Requirement Details:**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"- Category: {getattr(item, 'category_path', 'N/A')}")
            st.markdown(f"- Priority: {getattr(item, 'priority', 'N/A')}")
        with col2:
            st.markdown(f"- Verification: {getattr(item, 'verification_method', 'N/A')}")
            st.markdown(f"- Verified: {'✅' if getattr(item, 'verified', False) else '❌'}")

    elif item.type == ItemType.RSK:
        st.markdown("---")
        st.markdown("**Risk Assessment:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Likelihood", getattr(item, 'likelihood', 'N/A'))
        with col2:
            st.metric("Consequence", getattr(item, 'consequence', 'N/A'))
        with col3:
            score = getattr(item, 'risk_score', 0) or 0
            st.metric("Risk Score", score)

        if hasattr(item, 'mitigation_strategy') and item.mitigation_strategy:
            st.markdown("**Mitigation Strategy:**")
            st.markdown(item.mitigation_strategy)

    elif item.type == ItemType.IFC:
        st.markdown("---")
        st.markdown("**Interface Details:**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"- Provider: {getattr(item, 'provider_system', 'N/A')}")
            st.markdown(f"- Status: {getattr(item, 'interface_status', 'N/A')}")
        with col2:
            st.markdown(f"- Consumer: {getattr(item, 'consumer_system', 'N/A')}")

        params = getattr(item, 'parameters', {})
        if params:
            st.markdown("**Parameters:**")
            for key, value in params.items():
                st.markdown(f"- {key}: {value}")

    # Links
    st.markdown("---")
    st.markdown("**Links:**")

    linked = core.get_linked_items(item_id)

    if item.links:
        st.markdown("*Outgoing:*")
        for link in item.links:
            st.markdown(f"  → **{link.link_type}**: {link.target_id}")

    if linked["incoming"]:
        st.markdown("*Incoming:*")
        for other in linked["incoming"]:
            # Find the link type
            for other_link in other.links:
                if other_link.target_id == item_id:
                    st.markdown(f"  ← **{other_link.link_type}**: {other.id_full}")
                    break

    # Metadata
    st.markdown("---")
    with st.expander("Metadata"):
        st.markdown(f"- Created: {item.created_at}")
        st.markdown(f"- Updated: {item.updated_at}")
        if item.tags:
            st.markdown(f"- Tags: {', '.join(item.tags)}")
        if item.references:
            st.markdown(f"- References: {', '.join(item.references)}")
        if item.collaborators:
            st.markdown(f"- Collaborators: {', '.join(item.collaborators)}")


def render_dashboard_tab(core: QingsongCore):
    """Render the dashboard with summary statistics."""
    st.subheader("📊 Repository Dashboard")

    summary = core.summary()

    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", summary["total_items"])
    with col2:
        st.metric("Active Items", summary["items_by_status"].get("active", 0))
    with col3:
        st.metric("Draft Items", summary["items_by_status"].get("draft", 0))
    with col4:
        st.metric("Systems", len(summary["systems"]))

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Items by Type**")
        type_data = pd.DataFrame([
            {"Type": t, "Count": c}
            for t, c in summary["items_by_type"].items()
            if c > 0
        ])
        if not type_data.empty:
            st.bar_chart(type_data.set_index("Type"))

    with col2:
        st.markdown("**Items by Status**")
        status_data = pd.DataFrame([
            {"Status": s, "Count": c}
            for s, c in summary["items_by_status"].items()
            if c > 0
        ])
        if not status_data.empty:
            st.bar_chart(status_data.set_index("Status"))

    # Items by system
    st.markdown("---")
    st.markdown("**Items by System**")

    system_counts = {}
    for item in core.items.values():
        system_counts[item.system_path] = system_counts.get(item.system_path, 0) + 1

    if system_counts:
        system_df = pd.DataFrame([
            {"System": s, "Count": c}
            for s, c in sorted(system_counts.items())
        ])
        st.dataframe(system_df, use_container_width=True)


def render_links_tab(core: QingsongCore):
    """Render the links view."""
    st.subheader("🔗 Item Links")

    links_df = core.links_to_dataframe()

    if links_df.empty:
        st.info("No links found in the repository.")
        return

    # Summary
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Links", len(links_df))
    with col2:
        st.metric("Unique Link Types", links_df["link_type"].nunique())

    # Links by type
    st.markdown("**Links by Type**")
    type_counts = links_df["link_type"].value_counts()
    st.bar_chart(type_counts)

    # Link table
    st.markdown("**All Links**")
    st.dataframe(
        links_df,
        use_container_width=True,
        column_config={
            "source_id": st.column_config.TextColumn("Source"),
            "target_id": st.column_config.TextColumn("Target"),
            "link_type": st.column_config.TextColumn("Type"),
            "description": st.column_config.TextColumn("Description"),
        }
    )


def render_about_tab(core: QingsongCore):
    """Render the about/help tab."""
    st.subheader("ℹ️ About Qingsong")

    st.markdown("""
    **Qingsong** is a lightweight project management system for the MUST Telescope project.

    Named after the Chinese astronomer **Yu Qingsong (余青松)**, a Tsinghua alumnus.

    ### Features
    - 📋 **Requirements Management**: Track and trace requirements
    - ⚠️ **Risk Management**: Identify and mitigate project risks
    - 🔗 **Interface Control**: Define system interfaces
    - 📄 **Document Tracking**: Reference project documents
    - 📊 **Data Records**: Track test data and results
    - 📝 **Technical Notes**: Capture decisions and analyses

    ### Architecture
    - **Doorstop**: File-based item storage
    - **Pydantic**: Schema validation
    - **SQLite**: Query cache
    - **Streamlit**: Web UI

    ### Quick Start
    ```bash
    # Validate metadata
    qingsong meta validate

    # Validate all items
    qingsong validate

    # Build cache
    qingsong cache build

    # Query items
    qingsong query "SELECT * FROM items LIMIT 10"

    # Launch UI
    qingsong ui
    ```
    """)

    # Current state
    st.markdown("---")
    st.markdown("**Current Repository State:**")

    if core.metadata:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"- Project: {core.metadata.project_name}")
            st.markdown(f"- Systems: {len(core.metadata.systems)}")
        with col2:
            st.markdown(f"- People: {len(core.metadata.people)}")
            st.markdown(f"- Total Items: {len(core.items)}")


if __name__ == "__main__":
    main()

