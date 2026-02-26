"""
SQLite cache builder for Qingsong.

Generates a SQLite database for unified querying across all items.
The cache includes:
- Items table with all item data
- Links table for relationships
- Metadata tables for hierarchy, people, vocabularies
- Full-text search (FTS5) for item content
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import get_project_root
from .doorstop_io import load_all_items
from .load_meta import Metadata, load_metadata
from .models import BaseItem


def get_cache_path() -> Path:
    """Get the default cache database path."""
    return get_project_root() / "index" / "qingsong.sqlite"


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create database schema."""
    cursor = conn.cursor()

    # Items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id_full TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            system_path TEXT NOT NULL,
            l3 TEXT,
            category_path TEXT,
            owner TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT,
            likelihood INTEGER,
            consequence INTEGER,
            risk_score INTEGER,
            created_at TEXT,
            updated_at TEXT,
            tags TEXT,  -- JSON array
            references_json TEXT,  -- JSON array (renamed to avoid SQLite keyword)
            collaborators TEXT,  -- JSON array
            discussions TEXT,  -- JSON array
            extra_data TEXT  -- JSON for type-specific fields
        )
    """)

    # Links table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            link_type TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (source_id) REFERENCES items(id_full),
            UNIQUE(source_id, target_id, link_type)
        )
    """)

    # Metadata: Hierarchy
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meta_hierarchy (
            system_path TEXT PRIMARY KEY,
            l1 TEXT NOT NULL,
            l2 TEXT NOT NULL,
            l1_name TEXT,
            l2_name TEXT,
            owner TEXT
        )
    """)

    # Metadata: People
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meta_people (
            person_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT,
            organization TEXT,
            systems TEXT,  -- JSON array
            active INTEGER
        )
    """)

    # Metadata: Vocabularies
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meta_vocab (
            vocab_name TEXT NOT NULL,
            value TEXT NOT NULL,
            label TEXT,
            description TEXT,
            PRIMARY KEY (vocab_name, value)
        )
    """)

    # Cache metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # FTS5 for full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
            id_full,
            title,
            text,
            tags,
            discussions,
            content='items',
            content_rowid='rowid'
        )
    """)

    # Triggers to keep FTS in sync
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
            INSERT INTO items_fts(rowid, id_full, title, text, tags, discussions)
            VALUES (NEW.rowid, NEW.id_full, NEW.title, NEW.text, NEW.tags, NEW.discussions);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
            INSERT INTO items_fts(items_fts, rowid, id_full, title, text, tags, discussions)
            VALUES('delete', OLD.rowid, OLD.id_full, OLD.title, OLD.text, OLD.tags, OLD.discussions);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
            INSERT INTO items_fts(items_fts, rowid, id_full, title, text, tags, discussions)
            VALUES('delete', OLD.rowid, OLD.id_full, OLD.title, OLD.text, OLD.tags, OLD.discussions);
            INSERT INTO items_fts(rowid, id_full, title, text, tags, discussions)
            VALUES (NEW.rowid, NEW.id_full, NEW.title, NEW.text, NEW.tags, NEW.discussions);
        END
    """)

    # Indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_type ON items(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_system_path ON items(system_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_status ON items(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_owner ON items(owner)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_type ON links(link_type)")

    conn.commit()


def _insert_item(cursor: sqlite3.Cursor, item: BaseItem) -> None:
    """Insert an item into the database."""
    # Extract common fields
    data = item.model_dump(mode="json")

    # Extract type-specific fields into extra_data
    common_fields = {
        "id_full", "type", "title", "text", "system_path", "l3",
        "category_path", "owner", "status", "created_at", "updated_at",
        "tags", "references", "collaborators", "links", "retirement",
        "uid", "active", "derived", "normative", "reviewed",
    }

    # Some types have additional common fields
    extra_common = {"priority", "likelihood", "consequence", "risk_score"}

    extra_data = {k: v for k, v in data.items()
                  if k not in common_fields and k not in extra_common}

    cursor.execute("""
        INSERT OR REPLACE INTO items (
            id_full, type, title, text, system_path, l3, category_path,
            owner, status, priority, likelihood, consequence, risk_score,
            created_at, updated_at, tags, references_json, collaborators, discussions, extra_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item.id_full,
        item.type.value,
        item.title,
        item.text,
        item.system_path,
        item.l3,
        getattr(item, "category_path", None),
        item.owner,
        item.status.value,
        getattr(item, "priority", None),
        getattr(item, "likelihood", None),
        getattr(item, "consequence", None),
        getattr(item, "risk_score", None),
        item.created_at.isoformat() if item.created_at else None,
        item.updated_at.isoformat() if item.updated_at else None,
        json.dumps(item.tags),
        json.dumps(item.references),
        json.dumps(item.collaborators),
        json.dumps([c.model_dump(mode="json") for c in item.discussions]),
        json.dumps(extra_data),
    ))


def _insert_links(cursor: sqlite3.Cursor, item: BaseItem) -> None:
    """Insert links for an item."""
    for link in item.links:
        cursor.execute("""
            INSERT OR IGNORE INTO links (source_id, target_id, link_type, description)
            VALUES (?, ?, ?, ?)
        """, (
            item.id_full,
            link.target_id,
            link.link_type,
            link.description,
        ))


def _insert_metadata(cursor: sqlite3.Cursor, metadata: Metadata) -> None:
    """Insert metadata into the database."""
    # Hierarchy
    for sys_id, system in metadata.systems.items():
        for sub_id, subsystem in system.subsystems.items():
            cursor.execute("""
                INSERT OR REPLACE INTO meta_hierarchy
                (system_path, l1, l2, l1_name, l2_name, owner)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                f"{sys_id}/{sub_id}",
                sys_id,
                sub_id,
                system.name,
                subsystem.name,
                subsystem.owner,
            ))

    # People
    for person_id, person in metadata.people.items():
        cursor.execute("""
            INSERT OR REPLACE INTO meta_people
            (person_id, name, email, role, organization, systems, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            person_id,
            person.name,
            person.email,
            person.role,
            person.organization,
            json.dumps(person.systems),
            1 if person.active else 0,
        ))

    # Vocabularies
    for item in metadata.status_vocab.items:
        cursor.execute("""
            INSERT OR REPLACE INTO meta_vocab (vocab_name, value, label, description)
            VALUES (?, ?, ?, ?)
        """, ("status", item.value, item.label, item.description))

    for item in metadata.req_category_vocab.items:
        cursor.execute("""
            INSERT OR REPLACE INTO meta_vocab (vocab_name, value, label, description)
            VALUES (?, ?, ?, ?)
        """, ("req_category", item.value, item.label, item.description))

    for item in metadata.risk_category_vocab.items:
        cursor.execute("""
            INSERT OR REPLACE INTO meta_vocab (vocab_name, value, label, description)
            VALUES (?, ?, ?, ?)
        """, ("risk_category", item.value, item.label, item.description))

    for item in metadata.ifc_type_vocab.items:
        cursor.execute("""
            INSERT OR REPLACE INTO meta_vocab (vocab_name, value, label, description)
            VALUES (?, ?, ?, ?)
        """, ("ifc_type", item.value, item.label, item.description))

    # Link types as vocab
    for lt_name in metadata.valid_link_types:
        lt_def = metadata.link_types.get(lt_name)
        cursor.execute("""
            INSERT OR REPLACE INTO meta_vocab (vocab_name, value, label, description)
            VALUES (?, ?, ?, ?)
        """, (
            "link_type",
            lt_name,
            lt_def.label if lt_def else lt_name,
            lt_def.description if lt_def else "",
        ))


def build_cache(
    output_path: Path | None = None,
    doorstop_dir: Path | None = None,
    meta_dir: Path | None = None,
) -> Path:
    """
    Build the SQLite cache from Doorstop items and metadata.

    Args:
        output_path: Path for the SQLite database. Defaults to index/qingsong.sqlite.
        doorstop_dir: Doorstop base directory.
        meta_dir: Metadata directory.

    Returns:
        Path to the created database.
    """
    if output_path is None:
        output_path = get_cache_path()

    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database
    if output_path.exists():
        output_path.unlink()

    # Load data
    metadata = load_metadata(meta_dir, force_reload=True)
    items = load_all_items(doorstop_dir)

    # Create database
    conn = sqlite3.connect(output_path)

    try:
        _create_schema(conn)
        cursor = conn.cursor()

        # Insert metadata
        _insert_metadata(cursor, metadata)

        # Insert items and links
        for item in items.values():
            _insert_item(cursor, item)
            _insert_links(cursor, item)

        # Store cache metadata
        cursor.execute("""
            INSERT OR REPLACE INTO cache_meta (key, value)
            VALUES ('built_at', ?), ('item_count', ?), ('version', ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            str(len(items)),
            "1.0",
        ))

        conn.commit()

    finally:
        conn.close()

    return output_path


def query_cache(
    sql: str,
    params: tuple[Any, ...] | None = None,
    cache_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Execute a SQL query on the cache.

    Args:
        sql: SQL query string.
        params: Query parameters.
        cache_path: Path to cache database.

    Returns:
        List of result dictionaries.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    if not cache_path.exists():
        raise FileNotFoundError(
            f"Cache not found at {cache_path}. Run 'qingsong cache build' first."
        )

    conn = sqlite3.connect(cache_path)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        return results

    finally:
        conn.close()


def search_items(
    query: str,
    cache_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Full-text search items with snippet generation.

    Args:
        query: Search query (FTS5 syntax supported).
        cache_path: Path to cache database.

    Returns:
        List of matching items with 'snippet' field.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    if not cache_path.exists():
        raise FileNotFoundError(
            f"Cache not found at {cache_path}. Run 'qingsong cache build' first."
        )

    conn = sqlite3.connect(cache_path)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        # Use snippet() to get relevant context
        cursor.execute("""
            SELECT items.*, snippet(items_fts, 2, '...', '...', '...', 20) as snippet
            FROM items_fts
            JOIN items ON items_fts.id_full = items.id_full
            WHERE items_fts MATCH ?
            ORDER BY rank
        """, (query,))

        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        return results

    finally:
        conn.close()


def get_cache_stats(cache_path: Path | None = None) -> dict[str, Any]:
    """
    Get statistics about the cache.

    Args:
        cache_path: Path to cache database.

    Returns:
        Dictionary with cache statistics.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    if not cache_path.exists():
        return {"exists": False}

    conn = sqlite3.connect(cache_path)

    try:
        cursor = conn.cursor()

        stats: dict[str, Any] = {"exists": True, "path": str(cache_path)}

        # Get cache metadata
        cursor.execute("SELECT key, value FROM cache_meta")
        for row in cursor.fetchall():
            stats[row[0]] = row[1]

        # Count by type
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM items
            GROUP BY type
            ORDER BY type
        """)
        stats["items_by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Count links
        cursor.execute("SELECT COUNT(*) FROM links")
        stats["link_count"] = cursor.fetchone()[0]

        # Count by system path
        cursor.execute("""
            SELECT system_path, COUNT(*) as count
            FROM items
            GROUP BY system_path
            ORDER BY system_path
        """)
        stats["items_by_system"] = {row[0]: row[1] for row in cursor.fetchall()}

        return stats

    finally:
        conn.close()

