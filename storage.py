"""CSV persistence for the tree survey."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import pandas as pd

DATA_FILE = Path("survey_data.csv")
TREES_FILE = Path("active_trees.csv")
DATASET_FILE = Path("dataset_info.json")
SERIAL_FILE = Path("dataset_serial.json")
DEFAULT_MAP_ORIENTATION = {
    "map_axis_layout": "X horizontal, Y vertical",
    "mirror_map_x": False,
    "mirror_map_y": False,
}


def init_files():
    # A blank survey is safer than silently adding example measurements.
    if not TREES_FILE.exists():
        save_trees({1: (0.0, 0.0), 2: (0.0, 1.0)})
    if not DATA_FILE.exists():
        save_measurements([])
    init_dataset_info()


def _write_json(path, content):
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


def _dataset_id(name, serial):
    return f"{name.strip()}-{int(serial):03d}"


def init_dataset_info():
    """Create current dataset identity and its next serial counter if absent."""
    if not DATASET_FILE.exists():
        existing_registry = json.loads(SERIAL_FILE.read_text(encoding="utf-8")) if SERIAL_FILE.exists() else {}
        initial_serial = max(1, int(existing_registry.get("next_serial", 1)))
        tree_frame = pd.read_csv(TREES_FILE)
        max_tree_id = int(pd.to_numeric(tree_frame["tree"], errors="coerce").max()) if not tree_frame.empty else 2
        info = {
            "name": "Field Survey",
            "serial": initial_serial,
            "dataset_id": _dataset_id("Field Survey", initial_serial),
            "next_tree_id": max(3, max_tree_id + 1),
            **DEFAULT_MAP_ORIENTATION,
            "not_downloaded": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(DATASET_FILE, info)
    info = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
    if "next_tree_id" not in info:
        tree_frame = pd.read_csv(TREES_FILE)
        max_tree_id = int(pd.to_numeric(tree_frame["tree"], errors="coerce").max()) if not tree_frame.empty else 2
        info["next_tree_id"] = max(3, max_tree_id + 1)
    else:
        info["next_tree_id"] = max(3, int(info["next_tree_id"]))
    for setting, default in DEFAULT_MAP_ORIENTATION.items():
        info.setdefault(setting, default)
    next_serial = int(info.get("serial", 0)) + 1
    if SERIAL_FILE.exists():
        registry = json.loads(SERIAL_FILE.read_text(encoding="utf-8"))
        next_serial = max(next_serial, int(registry.get("next_serial", 1)))
    _write_json(SERIAL_FILE, {"next_serial": next_serial})
    _write_json(DATASET_FILE, info)
    return info


def load_dataset_info():
    init_dataset_info()
    return json.loads(DATASET_FILE.read_text(encoding="utf-8"))


def save_dataset_info(info):
    info = dict(info)
    info["name"] = str(info.get("name", "Field Survey")).strip() or "Field Survey"
    info["serial"] = int(info["serial"])
    info["dataset_id"] = _dataset_id(info["name"], info["serial"])
    _write_json(DATASET_FILE, info)


def rename_dataset(name):
    info = load_dataset_info()
    info["name"] = str(name).strip() or info["name"]
    info["not_downloaded"] = True
    save_dataset_info(info)
    return info


def mark_dataset_dirty():
    info = load_dataset_info()
    info["not_downloaded"] = True
    save_dataset_info(info)


def mark_dataset_downloaded():
    info = load_dataset_info()
    info["not_downloaded"] = False
    info["last_downloaded_at"] = datetime.now(timezone.utc).isoformat()
    save_dataset_info(info)


def save_map_orientation(axis_layout, mirror_x, mirror_y):
    """Persist map display orientation as part of the active dataset backup."""
    info = load_dataset_info()
    info["map_axis_layout"] = axis_layout if axis_layout in (
        "X horizontal, Y vertical", "Y horizontal, X vertical"
    ) else DEFAULT_MAP_ORIENTATION["map_axis_layout"]
    info["mirror_map_x"] = bool(mirror_x)
    info["mirror_map_y"] = bool(mirror_y)
    info["not_downloaded"] = True
    save_dataset_info(info)
    return info


def mark_tree_id_used(tree_id):
    info = load_dataset_info()
    info["next_tree_id"] = max(int(info.get("next_tree_id", 3)), int(tree_id) + 1)
    info["not_downloaded"] = True
    save_dataset_info(info)


def replace_dataset(name, trees_dict, measurements, minimum_serial=None, next_tree_id=None, map_orientation=None):
    """Replace the active survey and assign a fresh, monotonically increasing serial."""
    trees_dict = dict(trees_dict)
    if 1 not in trees_dict or 2 not in trees_dict:
        raise ValueError("The uploaded dataset must include anchor trees 1 and 2.")
    save_trees(trees_dict)
    save_measurements(measurements)

    registry = json.loads(SERIAL_FILE.read_text(encoding="utf-8")) if SERIAL_FILE.exists() else {"next_serial": 1}
    serial = max(1, int(registry.get("next_serial", 1)), int(minimum_serial or 1))
    _write_json(SERIAL_FILE, {"next_serial": serial + 1})
    info = {
        "name": str(name).strip() or "Imported Survey",
        "serial": serial,
        "next_tree_id": max(max(trees_dict) + 1, int(next_tree_id or 3)),
        **{**DEFAULT_MAP_ORIENTATION, **(map_orientation or {})},
        "not_downloaded": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    save_dataset_info(info)
    return load_dataset_info()


def safe_filename(text):
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(text).strip()).strip("_")
    return name or "field_survey"


def load_trees():
    init_files()
    frame = pd.read_csv(TREES_FILE)
    trees = {}
    for row in frame.itertuples():
        tree_id = int(row.tree)
        x, y = max(0, int(round(float(row.x)))), max(0, int(round(float(row.y))))
        if tree_id == 1:
            x, y = 0, 0
        trees[tree_id] = (x, y)
    return trees


def save_trees(trees_dict):
    pd.DataFrame(
        [{"tree": int(t), "x": int(round(x)), "y": int(round(y))} for t, (x, y) in sorted(trees_dict.items())],
        columns=["tree", "x", "y"],
    ).to_csv(TREES_FILE, index=False)


def load_measurements(trees_dict):
    init_files()
    frame = pd.read_csv(DATA_FILE)
    required = {"tree_a", "tree_b", "distance_mm"}
    # Accept the earlier `distance` column, whose values were metres.
    if "distance_mm" not in frame and "distance" in frame:
        frame["distance_mm"] = pd.to_numeric(frame["distance"], errors="coerce") * 1000
    if not required.issubset(frame.columns):
        return []
    result = []
    for row in frame.itertuples():
        a, b, distance = int(row.tree_a), int(row.tree_b), float(row.distance_mm)
        if a in trees_dict and b in trees_dict and a != b and distance > 0:
            result.append((a, b, distance))
    return result


def save_measurements(measurements):
    pd.DataFrame(
        [{"tree_a": int(a), "tree_b": int(b), "distance_mm": float(d)} for a, b, d in measurements],
        columns=["tree_a", "tree_b", "distance_mm"],
    ).to_csv(DATA_FILE, index=False)


def append_measurement(a, b, distance_mm):
    measurements = load_measurements(load_trees())
    measurements.append((int(a), int(b), float(distance_mm)))
    save_measurements(measurements)
