"""Run isolated CRUD checks against the temporary Neon verification branch."""

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage


EXPECTED_BRANCH = "codex-verification"


def main():
    branch = os.getenv("NEON_BRANCH", "")
    if branch != EXPECTED_BRANCH:
        raise SystemExit(
            f"Refusing to write test data: expected Neon branch {EXPECTED_BRANCH!r}, got {branch!r}."
        )

    storage.init_files()
    created_ids = []
    try:
        first = storage.create_dataset("Codex Verification")
        first_id = first["dataset_pk"]
        created_ids.append(first_id)
        st.session_state["active_dataset_pk"] = first_id

        assert storage.load_trees() == {1: (0, 0), 2: (0, 1)}
        storage.save_trees({1: (0, 0), 2: (0, 1), 3: (300, 400)})
        storage.mark_tree_id_used(3)
        storage.save_measurements([(1, 2, 1000), (2, 1, 1002), (1, 3, 500)])
        assert storage.load_measurements(storage.load_trees()) == [
            (1, 2, 1000.0), (2, 1, 1002.0), (1, 3, 500.0)
        ]

        assert storage.set_tree2_reference_axis("X") == (1001, 0)
        storage.save_map_orientation("Y horizontal, X vertical", True, False)
        info = storage.load_dataset_info(first_id)
        assert info["next_tree_id"] == 4
        assert info["map_axis_layout"] == "Y horizontal, X vertical"
        assert info["mirror_map_x"] is True and info["mirror_map_y"] is False

        storage.save_measurements([(1, 2, 1005), (2, 1, 1007), (1, 3, 500)])
        assert storage.load_measurements(storage.load_trees()) == [
            (1, 2, 1005.0), (2, 1, 1007.0), (1, 3, 500.0)
        ]

        storage.save_trees({1: (0, 0), 2: (1001, 0)})
        storage.save_measurements([(1, 2, 1005), (2, 1, 1007)])
        assert storage.load_measurements(storage.load_trees()) == [
            (1, 2, 1005.0), (2, 1, 1007.0)
        ]

        renamed = storage.rename_dataset("Codex Verification Renamed")
        assert renamed["dataset_id"].startswith("Codex Verification Renamed-")
        assert any(item["dataset_pk"] == first_id for item in storage.list_datasets())

        second = storage.create_dataset("Codex Verification Second")
        second_id = second["dataset_pk"]
        created_ids.append(second_id)
        assert second["serial"] == first["serial"] + 1
        print("Neon smoke check passed: dataset CRUD, serials, estimates, directed measurements, orientation, and cascade delete.")
    finally:
        with storage._connection_pool().connection() as conn:
            for dataset_id in created_ids:
                conn.execute("DELETE FROM survey_datasets WHERE id = %s", (dataset_id,))
        storage._connection_pool().close()


if __name__ == "__main__":
    main()
