"""PostgreSQL persistence for survey datasets, backed by Neon."""

from pathlib import Path
import os

import streamlit as st
import psycopg
from psycopg.rows import tuple_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"), override=False)
load_dotenv(Path(__file__).with_name(".env.local"), override=False)

DEFAULT_MAP_ORIENTATION = {
    "map_axis_layout": "X horizontal, Y vertical",
    "mirror_map_x": False,
    "mirror_map_y": False,
}
MIGRATION_VERSION = "001_initial"


class StorageConfigurationError(RuntimeError):
    """Raised when the Neon PostgreSQL connection is not configured."""


def _configured_value(name):
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value).strip() if value else os.getenv(name, "").strip()


def _database_url():
    value = _configured_value("DATABASE_URL")
    if not value:
        raise StorageConfigurationError(
            "Neon PostgreSQL is not configured. Add DATABASE_URL to .env.local "
            "or Streamlit Secrets."
        )
    return value


def _run_migrations():
    app_url = _database_url()
    migration_url = _configured_value("DATABASE_URL_UNPOOLED") or app_url
    migration_path = Path(__file__).with_name("migrations") / "001_initial.sql"
    if not migration_path.exists():
        raise StorageConfigurationError(f"Database migration file is missing: {migration_path.name}")

    with psycopg.connect(migration_url, connect_timeout=15, row_factory=tuple_row) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = %s", (MIGRATION_VERSION,)
        ).fetchone()
        if applied:
            return
        for statement in migration_path.read_text(encoding="utf-8").split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
        conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (MIGRATION_VERSION,))


@st.cache_resource(show_spinner=False)
def _connection_pool():
    _run_migrations()
    return ConnectionPool(
        conninfo=_database_url(),
        min_size=1,
        max_size=5,
        timeout=15,
        open=True,
        kwargs={"connect_timeout": 15},
    )


def init_files():
    """Compatibility entry point; initialize the Neon schema and connection pool."""
    _connection_pool()


def _active_dataset_id(dataset_id=None):
    selected = dataset_id or st.session_state.get("active_dataset_pk")
    if not selected:
        raise StorageConfigurationError("Select or create a dataset before editing survey data.")
    try:
        return int(selected)
    except (TypeError, ValueError) as exc:
        raise StorageConfigurationError("The selected dataset is invalid. Select a dataset again.") from exc


def _executemany(conn, query, params):
    """Execute a batch using psycopg's cursor API."""
    with conn.cursor() as cursor:
        cursor.executemany(query, params)


def _next_serial(conn, preferred=None):
    conn.execute(
        "INSERT INTO dataset_serial_counters (singleton, next_serial) VALUES (TRUE, 1) "
        "ON CONFLICT (singleton) DO NOTHING"
    )
    counter = conn.execute(
        "SELECT next_serial FROM dataset_serial_counters WHERE singleton = TRUE FOR UPDATE"
    ).fetchone()[0]
    observed = conn.execute("SELECT COALESCE(MAX(serial), 0) + 1 FROM survey_datasets").fetchone()[0]
    candidate = max(int(counter), int(observed), 1)
    if preferred is not None:
        preferred = max(int(preferred), 1)
        exists = conn.execute("SELECT 1 FROM survey_datasets WHERE serial = %s", (preferred,)).fetchone()
        if not exists:
            candidate = preferred
    conn.execute(
        "UPDATE dataset_serial_counters SET next_serial = %s WHERE singleton = TRUE",
        (max(int(counter), int(observed), candidate) + (1 if candidate >= max(int(counter), int(observed)) else 0),),
    )
    return candidate


def create_dataset(name):
    """Create a dataset with protected anchor trees and a never-reused serial."""
    name = str(name).strip() or "Field Survey"
    with _connection_pool().connection() as conn:
        serial = _next_serial(conn)
        dataset_id = f"{name}-{serial:03d}"
        row = conn.execute(
            "INSERT INTO survey_datasets (name, serial, dataset_id, next_tree_id) "
            "VALUES (%s, %s, %s, 3) RETURNING id, created_at",
            (name, serial, dataset_id),
        ).fetchone()
        dataset_pk, created_at = row
        _executemany(conn,
            "INSERT INTO survey_trees (dataset_id, tree_id, x, y) VALUES (%s, %s, %s, %s)",
            [(dataset_pk, 1, 0, 0), (dataset_pk, 2, 0, 1)],
        )
    info = {
        "name": name,
        "serial": serial,
        "dataset_id": dataset_id,
        "next_tree_id": 3,
        **DEFAULT_MAP_ORIENTATION,
        "created_at": created_at.isoformat(),
        "dataset_pk": dataset_pk,
    }
    st.session_state["active_dataset_pk"] = dataset_pk
    return info


def list_datasets():
    """List datasets in the Neon database, preserving the app's selector shape."""
    with _connection_pool().connection() as conn:
        rows = conn.execute(
            "SELECT id, dataset_id, name, serial "
            "FROM survey_datasets ORDER BY serial, id"
        ).fetchall()
    return [
        {
            "dataset_pk": row[0],
            "dataset_id": row[1],
            "name": row[2],
            "serial": row[3],
        }
        for row in rows
    ]


def _dataset_info_from_row(row):
    if not row:
        raise ValueError("The selected dataset was not found in Neon.")
    return {
        "dataset_pk": row[0],
        "name": row[1],
        "serial": int(row[2]),
        "dataset_id": row[3],
        "next_tree_id": int(row[4]),
        "map_axis_layout": row[5] or DEFAULT_MAP_ORIENTATION["map_axis_layout"],
        "mirror_map_x": bool(row[6]),
        "mirror_map_y": bool(row[7]),
        "created_at": row[8].isoformat() if row[8] else None,
    }


def load_dataset_info(dataset_pk=None):
    selected = _active_dataset_id(dataset_pk)
    with _connection_pool().connection() as conn:
        row = conn.execute(
            "SELECT id, name, serial, dataset_id, next_tree_id, map_axis_layout, "
            "mirror_map_x, mirror_map_y, created_at "
            "FROM survey_datasets WHERE id = %s",
            (selected,),
        ).fetchone()
    return _dataset_info_from_row(row)


def save_dataset_info(info, dataset_pk=None):
    selected = _active_dataset_id(dataset_pk or info.get("dataset_pk"))
    name = str(info.get("name", "Field Survey")).strip() or "Field Survey"
    serial = int(info["serial"])
    dataset_id = f"{name}-{serial:03d}"
    with _connection_pool().connection() as conn:
        conn.execute(
            "UPDATE survey_datasets SET name = %s, dataset_id = %s, next_tree_id = %s, "
            "map_axis_layout = %s, mirror_map_x = %s, mirror_map_y = %s WHERE id = %s",
            (
                name,
                dataset_id,
                max(3, int(info.get("next_tree_id", 3))),
                info.get("map_axis_layout", DEFAULT_MAP_ORIENTATION["map_axis_layout"]),
                bool(info.get("mirror_map_x", False)),
                bool(info.get("mirror_map_y", False)),
                selected,
            ),
        )
    return {**info, "name": name, "dataset_id": dataset_id, "serial": serial}


def rename_dataset(name):
    info = load_dataset_info()
    info["name"] = str(name).strip() or info["name"]
    return save_dataset_info(info)


def save_map_orientation(axis_layout, mirror_x, mirror_y):
    info = load_dataset_info()
    info["map_axis_layout"] = axis_layout if axis_layout in (
        "X horizontal, Y vertical", "Y horizontal, X vertical"
    ) else DEFAULT_MAP_ORIENTATION["map_axis_layout"]
    info["mirror_map_x"] = bool(mirror_x)
    info["mirror_map_y"] = bool(mirror_y)
    return save_dataset_info(info)


def set_tree2_reference_axis(axis):
    """Place Tree 2 on the selected positive axis using its baseline distance."""
    axis = str(axis).upper()
    if axis not in ("X", "Y"):
        raise ValueError("Tree 2 reference axis must be X or Y.")
    dataset_id = _active_dataset_id()
    with _connection_pool().connection() as conn:
        baseline = conn.execute(
            "SELECT distance_mm FROM survey_measurements WHERE dataset_id = %s "
            "AND ((tree_a = 1 AND tree_b = 2) OR (tree_a = 2 AND tree_b = 1))",
            (dataset_id,),
        ).fetchall()
        row = conn.execute(
            "SELECT x, y FROM survey_trees WHERE dataset_id = %s AND tree_id = 2",
            (dataset_id,),
        ).fetchone()
        current_x, current_y = row if row else (0, 1)
        distance = (
            int(round(sum(float(item[0]) for item in baseline) / len(baseline)))
            if baseline
            else int(round(max(current_x, current_y)))
        )
        distance = max(distance, 1)
        position = (distance, 0) if axis == "X" else (0, distance)
        conn.execute(
            "INSERT INTO survey_trees (dataset_id, tree_id, x, y) VALUES (%s, 2, %s, %s) "
            "ON CONFLICT (dataset_id, tree_id) DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y",
            (dataset_id, *position),
        )
    return position


def mark_tree_id_used(tree_id):
    dataset_id = _active_dataset_id()
    with _connection_pool().connection() as conn:
        conn.execute(
            "UPDATE survey_datasets SET next_tree_id = GREATEST(next_tree_id, %s) WHERE id = %s",
            (int(tree_id) + 1, dataset_id),
        )


def load_trees():
    dataset_id = _active_dataset_id()
    with _connection_pool().connection() as conn:
        rows = conn.execute(
            "SELECT tree_id, x, y FROM survey_trees WHERE dataset_id = %s ORDER BY tree_id",
            (dataset_id,),
        ).fetchall()
    return {int(tree): (int(x), int(y)) for tree, x, y in rows}


def save_trees(trees_dict):
    dataset_id = _active_dataset_id()
    normalized = {
        int(tree): (0 if int(tree) == 1 else int(round(x)), 0 if int(tree) == 1 else int(round(y)))
        for tree, (x, y) in trees_dict.items()
    }
    if 1 not in normalized:
        normalized[1] = (0, 0)
    with _connection_pool().connection() as conn:
        existing = {
            int(row[0]) for row in conn.execute(
                "SELECT tree_id FROM survey_trees WHERE dataset_id = %s", (dataset_id,)
            ).fetchall()
        }
        for tree in existing - normalized.keys():
            conn.execute(
                "DELETE FROM survey_trees WHERE dataset_id = %s AND tree_id = %s",
                (dataset_id, tree),
            )
        _executemany(conn,
            "INSERT INTO survey_trees (dataset_id, tree_id, x, y) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (dataset_id, tree_id) DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y",
            [(dataset_id, tree, x, y) for tree, (x, y) in normalized.items()],
        )


def load_measurements(trees_dict):
    dataset_id = _active_dataset_id()
    tree_ids = set(trees_dict)
    with _connection_pool().connection() as conn:
        rows = conn.execute(
            "SELECT tree_a, tree_b, distance_mm FROM survey_measurements "
            "WHERE dataset_id = %s ORDER BY record_id",
            (dataset_id,),
        ).fetchall()
    return [
        (int(a), int(b), float(distance))
        for a, b, distance in rows
        if int(a) in tree_ids and int(b) in tree_ids and int(a) != int(b) and float(distance) > 0
    ]


def save_measurements(measurements):
    dataset_id = _active_dataset_id()
    directed = {}
    for a, b, distance in measurements:
        a, b, distance = int(a), int(b), float(distance)
        if a != b and distance > 0:
            directed[(a, b)] = distance
    with _connection_pool().connection() as conn:
        conn.execute("DELETE FROM survey_measurements WHERE dataset_id = %s", (dataset_id,))
        _executemany(conn,
            "INSERT INTO survey_measurements (dataset_id, tree_a, tree_b, distance_mm) "
            "VALUES (%s, %s, %s, %s)",
            [(dataset_id, a, b, distance) for (a, b), distance in directed.items()],
        )


def append_measurement(a, b, distance_mm):
    measurements = load_measurements(load_trees())
    measurements.append((int(a), int(b), float(distance_mm)))
    save_measurements(measurements)
