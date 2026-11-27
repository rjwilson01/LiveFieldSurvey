"""PostgreSQL persistence for survey datasets, backed by Neon."""

from pathlib import Path
import os
import time

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
DATA_CACHE_TTL_SECONDS = 120


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
        min_size=0,
        max_size=5,
        timeout=15,
        max_idle=300,
        max_lifetime=900,
        check=ConnectionPool.check_connection,
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


def _read_connection(operation):
    """Run a read-only operation, replacing a connection lost while the app slept."""
    pool = _connection_pool()
    for attempt in range(2):
        try:
            with pool.connection() as conn:
                return operation(conn)
        except psycopg.OperationalError:
            if attempt:
                raise
    raise RuntimeError("Database read retry exhausted unexpectedly.")


def _read_rows(query, params=(), *, one=False):
    def read(conn):
        cursor = conn.execute(query, params)
        return cursor.fetchone() if one else cursor.fetchall()

    return _read_connection(read)


def _read_dataset_snapshot(dataset_pk):
    def read(conn):
        info_row = conn.execute(
            "SELECT id, name, serial, dataset_id, next_tree_id, map_axis_layout, "
            "mirror_map_x, mirror_map_y, created_at FROM survey_datasets WHERE id = %s",
            (dataset_pk,),
        ).fetchone()
        info = _dataset_info_from_row(info_row)
        tree_rows = conn.execute(
            "SELECT tree_id, x, y FROM survey_trees WHERE dataset_id = %s ORDER BY tree_id",
            (dataset_pk,),
        ).fetchall()
        measurement_rows = conn.execute(
            "SELECT tree_a, tree_b, distance_mm FROM survey_measurements "
            "WHERE dataset_id = %s ORDER BY record_id",
            (dataset_pk,),
        ).fetchall()
        trees = {int(tree): (int(x), int(y)) for tree, x, y in tree_rows}
        measurements = [
            (int(a), int(b), float(distance))
            for a, b, distance in measurement_rows
            if int(a) in trees and int(b) in trees and int(a) != int(b) and float(distance) > 0
        ]
        return {"dataset_pk": dataset_pk, "info": info, "trees": trees, "measurements": measurements}

    snapshot = _read_connection(read)
    snapshot["loaded_at"] = time.monotonic()
    return snapshot


def _dataset_snapshot(dataset_pk=None, *, force=False):
    selected = _active_dataset_id(dataset_pk)
    cached = st.session_state.get("_neon_dataset_snapshot")
    if (
        not force
        and cached
        and cached.get("dataset_pk") == selected
        and time.monotonic() - cached.get("loaded_at", 0) < DATA_CACHE_TTL_SECONDS
    ):
        return cached
    snapshot = _read_dataset_snapshot(selected)
    st.session_state["_neon_dataset_snapshot"] = snapshot
    return snapshot


def _refresh_dataset_list_cache():
    st.session_state.pop("_neon_dataset_list", None)


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
    st.session_state["_neon_dataset_snapshot"] = {
        "dataset_pk": dataset_pk,
        "info": dict(info),
        "trees": {1: (0, 0), 2: (0, 1)},
        "measurements": [],
        "loaded_at": time.monotonic(),
    }
    _refresh_dataset_list_cache()
    return info


def list_datasets():
    """List datasets in the Neon database, preserving the app's selector shape."""
    cached = st.session_state.get("_neon_dataset_list")
    if cached and time.monotonic() - cached["loaded_at"] < DATA_CACHE_TTL_SECONDS:
        return [dict(dataset) for dataset in cached["datasets"]]
    rows = _read_rows(
        "SELECT id, dataset_id, name, serial "
        "FROM survey_datasets ORDER BY serial, id"
    )
    datasets = [
        {
            "dataset_pk": row[0],
            "dataset_id": row[1],
            "name": row[2],
            "serial": row[3],
        }
        for row in rows
    ]
    st.session_state["_neon_dataset_list"] = {
        "datasets": datasets,
        "loaded_at": time.monotonic(),
    }
    return [dict(dataset) for dataset in datasets]


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
    return dict(_dataset_snapshot(dataset_pk)["info"])


def load_dataset_state(dataset_pk=None, *, force=False):
    """Return one consistent in-memory view of a dataset for page rendering."""
    snapshot = _dataset_snapshot(dataset_pk, force=force)
    return {
        "dataset_pk": snapshot["dataset_pk"],
        "info": dict(snapshot["info"]),
        "trees": dict(snapshot["trees"]),
        "measurements": list(snapshot["measurements"]),
    }


def save_dataset_info(info, dataset_pk=None):
    selected = _active_dataset_id(dataset_pk or info.get("dataset_pk"))
    snapshot = _dataset_snapshot(selected)
    name = str(info.get("name", "Field Survey")).strip() or "Field Survey"
    serial = int(info["serial"])
    dataset_id = f"{name}-{serial:03d}"
    updated = {
        **snapshot["info"],
        **info,
        "dataset_pk": selected,
        "name": name,
        "dataset_id": dataset_id,
        "serial": serial,
        "next_tree_id": max(3, int(info.get("next_tree_id", 3))),
        "map_axis_layout": info.get("map_axis_layout", DEFAULT_MAP_ORIENTATION["map_axis_layout"]),
        "mirror_map_x": bool(info.get("mirror_map_x", False)),
        "mirror_map_y": bool(info.get("mirror_map_y", False)),
    }
    old = snapshot["info"]
    dataset_identity_changed = updated["name"] != old.get("name") or updated["dataset_id"] != old.get("dataset_id")
    changed = any(updated[key] != old.get(key) for key in (
        "name", "dataset_id", "next_tree_id", "map_axis_layout", "mirror_map_x", "mirror_map_y"
    ))
    if changed:
        with _connection_pool().connection() as conn:
            conn.execute(
                "UPDATE survey_datasets SET name = %s, dataset_id = %s, next_tree_id = %s, "
                "map_axis_layout = %s, mirror_map_x = %s, mirror_map_y = %s WHERE id = %s",
                (
                    updated["name"],
                    updated["dataset_id"],
                    updated["next_tree_id"],
                    updated["map_axis_layout"],
                    updated["mirror_map_x"],
                    updated["mirror_map_y"],
                    selected,
                ),
            )
        snapshot["info"] = updated
        snapshot["loaded_at"] = time.monotonic()
        if dataset_identity_changed:
            _refresh_dataset_list_cache()
    return dict(updated)


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
    snapshot = _dataset_snapshot()
    baseline = [d for a, b, d in snapshot["measurements"] if {a, b} == {1, 2}]
    current_x, current_y = snapshot["trees"].get(2, (0, 1))
    distance = (
        int(round(sum(baseline) / len(baseline)))
        if baseline
        else int(round(max(current_x, current_y)))
    )
    distance = max(distance, 1)
    position = (distance, 0) if axis == "X" else (0, distance)
    updated_trees = dict(snapshot["trees"])
    updated_trees[2] = position
    save_trees(updated_trees)
    return position


def mark_tree_id_used(tree_id):
    dataset_id = _active_dataset_id()
    snapshot = _dataset_snapshot(dataset_id)
    next_id = max(int(snapshot["info"].get("next_tree_id", 3)), int(tree_id) + 1)
    if next_id > int(snapshot["info"].get("next_tree_id", 3)):
        with _connection_pool().connection() as conn:
            conn.execute(
                "UPDATE survey_datasets SET next_tree_id = %s WHERE id = %s",
                (next_id, dataset_id),
            )
        snapshot["info"]["next_tree_id"] = next_id
        snapshot["loaded_at"] = time.monotonic()


def load_trees():
    return dict(_dataset_snapshot()["trees"])


def save_trees(trees_dict):
    dataset_id = _active_dataset_id()
    snapshot = _dataset_snapshot(dataset_id)
    normalized = {
        int(tree): (0 if int(tree) == 1 else int(round(x)), 0 if int(tree) == 1 else int(round(y)))
        for tree, (x, y) in trees_dict.items()
    }
    if 1 not in normalized:
        normalized[1] = (0, 0)
    existing = snapshot["trees"]
    removed = set(existing) - set(normalized)
    changed = {
        tree: position
        for tree, position in normalized.items()
        if tree not in existing or existing[tree] != position
    }
    if removed or changed:
        with _connection_pool().connection() as conn:
            for tree in removed:
                conn.execute(
                    "DELETE FROM survey_trees WHERE dataset_id = %s AND tree_id = %s",
                    (dataset_id, tree),
                )
            if changed:
                _executemany(
                    conn,
                    "INSERT INTO survey_trees (dataset_id, tree_id, x, y) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (dataset_id, tree_id) DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y "
                    "WHERE (survey_trees.x, survey_trees.y) IS DISTINCT FROM (EXCLUDED.x, EXCLUDED.y)",
                    [(dataset_id, tree, x, y) for tree, (x, y) in changed.items()],
                )
        snapshot["trees"] = normalized
        snapshot["loaded_at"] = time.monotonic()


def load_measurements(trees_dict):
    tree_ids = set(trees_dict)
    return [
        (a, b, distance)
        for a, b, distance in _dataset_snapshot()["measurements"]
        if a in tree_ids and b in tree_ids
    ]


def save_measurements(measurements):
    dataset_id = _active_dataset_id()
    snapshot = _dataset_snapshot(dataset_id)
    directed = {}
    for a, b, distance in measurements:
        a, b, distance = int(a), int(b), float(distance)
        if a != b and distance > 0:
            directed[(a, b)] = distance
    existing = {(a, b): distance for a, b, distance in snapshot["measurements"]}
    removed = set(existing) - set(directed)
    changed = {
        pair: distance
        for pair, distance in directed.items()
        if pair not in existing or existing[pair] != distance
    }
    if removed or changed:
        with _connection_pool().connection() as conn:
            for a, b in removed:
                conn.execute(
                    "DELETE FROM survey_measurements "
                    "WHERE dataset_id = %s AND tree_a = %s AND tree_b = %s",
                    (dataset_id, a, b),
                )
            if changed:
                _executemany(
                    conn,
                    "INSERT INTO survey_measurements (dataset_id, tree_a, tree_b, distance_mm) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (dataset_id, tree_a, tree_b) DO UPDATE "
                    "SET distance_mm = EXCLUDED.distance_mm "
                    "WHERE survey_measurements.distance_mm IS DISTINCT FROM EXCLUDED.distance_mm",
                    [(dataset_id, a, b, distance) for (a, b), distance in changed.items()],
                )
        # Keep the in-session snapshot aligned with values just written. If a
        # row was updated, retaining its prior tuple here made reruns display
        # stale measurements until the page performed a fresh database read.
        ordered = [(a, b, directed[(a, b)]) for a, b, _ in snapshot["measurements"] if (a, b) in directed]
        known = {(a, b) for a, b, _ in ordered}
        ordered.extend((a, b, d) for (a, b), d in directed.items() if (a, b) not in known)
        snapshot["measurements"] = ordered
        snapshot["loaded_at"] = time.monotonic()


def sync_anchor_baseline(dataset_pk=None):
    """Keep the two directed anchor readings and Tree 2's baseline position aligned.

    A recorded 1↔2 distance defines Tree 2's adjusted distance from the origin;
    its prior starting magnitude is ignored. The starting coordinate only
    determines whether the positive X or Y axis is used.
    """
    snapshot = _dataset_snapshot(dataset_pk)
    baseline = [distance for a, b, distance in snapshot["measurements"] if {a, b} == {1, 2}]
    if not baseline:
        return load_dataset_state(dataset_pk)

    distance = max(1, int(round(sum(baseline) / len(baseline))))
    synced = [
        (a, b, value)
        for a, b, value in snapshot["measurements"]
        if {a, b} != {1, 2}
    ]
    synced.extend(((1, 2, distance), (2, 1, distance)))
    save_measurements(synced)

    trees = dict(snapshot["trees"])
    tree2_x, tree2_y = trees.get(2, (0, 1))
    trees[2] = (distance, 0) if abs(tree2_x) > abs(tree2_y) else (0, distance)
    save_trees(trees)
    return load_dataset_state(dataset_pk)


def append_measurement(a, b, distance_mm):
    measurements = load_measurements(load_trees())
    measurements.append((int(a), int(b), float(distance_mm)))
    save_measurements(measurements)
