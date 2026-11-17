from datetime import datetime, timezone
from io import BytesIO
import json
import math
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

import pandas as pd
import streamlit as st

import storage


def build_dataset_bundle(dataset_info, trees, measurements):
    """Build a round-trippable ZIP containing identity, estimates, and observations."""
    manifest = {
        "format": "live-field-survey",
        "format_version": 1,
        "dataset_name": dataset_info["name"],
        "dataset_id": dataset_info["dataset_id"],
        "serial": int(dataset_info["serial"]),
        "next_tree_id": int(dataset_info.get("next_tree_id", max(trees, default=2) + 1)),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "distance_unit": "mm",
        "coordinate_unit": "mm",
    }
    tree_frame = pd.DataFrame(
        [{"tree": t, "x": int(round(x)), "y": int(round(y))} for t, (x, y) in sorted(trees.items())],
        columns=["tree", "x", "y"],
    )
    measurement_frame = pd.DataFrame(
        [{"tree_a": a, "tree_b": b, "distance_mm": d} for a, b, d in measurements],
        columns=["tree_a", "tree_b", "distance_mm"],
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("trees.csv", tree_frame.to_csv(index=False))
        archive.writestr("measurements.csv", measurement_frame.to_csv(index=False))
    return buffer.getvalue()


def parse_dataset_bundle(upload_bytes):
    """Validate a survey ZIP completely before any active data is changed."""
    try:
        with ZipFile(BytesIO(upload_bytes)) as archive:
            required_files = {"manifest.json", "trees.csv", "measurements.csv"}
            if not required_files.issubset(archive.namelist()):
                raise ValueError("ZIP must contain manifest.json, trees.csv, and measurements.csv.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest.json must contain a JSON object.")
            if manifest.get("format") != "live-field-survey" or manifest.get("format_version") != 1:
                raise ValueError("This ZIP is not a supported Live Field Survey dataset.")
            if manifest.get("distance_unit") != "mm" or manifest.get("coordinate_unit") != "mm":
                raise ValueError("This dataset does not use the supported millimetre units.")
            tree_frame = pd.read_csv(BytesIO(archive.read("trees.csv")))
            measurement_frame = pd.read_csv(BytesIO(archive.read("measurements.csv")))
    except (OSError, KeyError, BadZipFile, UnicodeDecodeError, json.JSONDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not read dataset ZIP: {exc}") from exc

    if not {"tree", "x", "y"}.issubset(tree_frame.columns):
        raise ValueError("trees.csv needs tree, x, and y columns.")
    if not {"tree_a", "tree_b", "distance_mm"}.issubset(measurement_frame.columns):
        raise ValueError("measurements.csv needs tree_a, tree_b, and distance_mm columns.")
    if tree_frame.empty:
        raise ValueError("The uploaded dataset has no trees.")
    if tree_frame["tree"].isna().any() or tree_frame["tree"].duplicated().any():
        raise ValueError("Tree IDs must be present and unique.")

    trees = {}
    for row in tree_frame.itertuples(index=False):
        try:
            tree_number = float(row.tree)
            tree_id = int(tree_number)
            x, y = float(row.x), float(row.y)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Tree IDs and coordinates must be numeric.") from exc
        if not tree_number.is_integer() or tree_id < 1 or not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Tree IDs must be positive and coordinates must be finite.")
        trees[tree_id] = (max(0, int(round(x))), max(0, int(round(y))))
    if 1 not in trees or 2 not in trees:
        raise ValueError("The uploaded dataset must include anchor trees 1 and 2.")
    trees[1] = (0, 0)
    trees[2] = (0, trees[2][1])

    measurements = []
    for row in measurement_frame.itertuples(index=False):
        try:
            a_number, b_number = float(row.tree_a), float(row.tree_b)
            a, b = int(a_number), int(b_number)
            distance = float(row.distance_mm)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Measurement tree IDs and distances must be numeric.") from exc
        if not a_number.is_integer() or not b_number.is_integer() or a not in trees or b not in trees or a == b:
            raise ValueError(f"Measurement {a} → {b} refers to an invalid tree pair.")
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError(f"Measurement {a} → {b} must have a positive finite distance.")
        measurements.append((a, b, distance))

    name = str(manifest.get("dataset_name", "Imported Survey")).strip() or "Imported Survey"
    source_serial = manifest.get("serial")
    if source_serial is not None:
        try:
            source_serial = int(source_serial)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("The manifest serial must be a positive integer.") from exc
        if source_serial < 1:
            raise ValueError("The manifest serial must be a positive integer.")
    try:
        source_next_tree_id = int(manifest.get("next_tree_id", max(trees) + 1))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("The manifest next_tree_id must be a positive integer.") from exc
    source_next_tree_id = max(max(trees) + 1, 3, source_next_tree_id)
    return {
        "name": name,
        "source_id": str(manifest.get("dataset_id", "Unknown dataset")),
        "source_serial": source_serial,
        "next_tree_id": source_next_tree_id,
        "trees": trees,
        "measurements": measurements,
    }


def export_survey(df_trees, df_measurements, dataset_info, trees, measurements, on_download=None):
    dataset_slug = storage.safe_filename(dataset_info["name"])
    serial = int(dataset_info["serial"])
    st.download_button(
        "Download complete dataset (ZIP)",
        data=build_dataset_bundle(dataset_info, trees, measurements),
        file_name=f"{dataset_slug}-{serial:03d}.zip",
        mime="application/zip",
        key="download_dataset_bundle",
        on_click=on_download,
        help="Includes the dataset identity, all tree estimates, and every directed measurement for later upload.",
    )
    st.download_button(
        "Download trees and measurements CSV",
        data=df_trees.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{dataset_slug}-{serial:03d}-tree_survey.csv",
        mime="text/csv",
        key="download_tree_survey",
        help="Tree estimates, least-squares adjusted positions, link counts, and measured distances with adjusted residuals.",
    )
    st.download_button(
        "Download measurements only CSV",
        data=df_measurements.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{dataset_slug}-{serial:03d}-measurements.csv",
        mime="text/csv",
        key="download_tree_measurements",
    )
