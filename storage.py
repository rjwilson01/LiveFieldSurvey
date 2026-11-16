"""CSV persistence for the tree survey."""

from pathlib import Path
import pandas as pd

DATA_FILE = Path("survey_data.csv")
TREES_FILE = Path("active_trees.csv")


def init_files():
    # A blank survey is safer than silently adding example measurements.
    if not TREES_FILE.exists():
        save_trees({1: (0.0, 0.0), 2: (0.0, 1.0)})
    if not DATA_FILE.exists():
        save_measurements([])


def load_trees():
    init_files()
    frame = pd.read_csv(TREES_FILE)
    return {int(row.tree): (float(row.x), float(row.y)) for row in frame.itertuples()}


def save_trees(trees_dict):
    pd.DataFrame(
        [{"tree": int(t), "x": float(x), "y": float(y)} for t, (x, y) in sorted(trees_dict.items())],
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
