"""Google Sheets persistence for survey datasets."""

from datetime import datetime, timezone
import re

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


DEFAULT_MAP_ORIENTATION = {
    "map_axis_layout": "X horizontal, Y vertical",
    "mirror_map_x": False,
    "mirror_map_y": False,
}
SHEETS_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
DATASET_SHEETS = ("Trees", "Measurements", "Dataset")
REGISTRY_TITLE = "_LiveFieldSurvey Registry"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class StorageConfigurationError(RuntimeError):
    """Raised when the Google Sheets connection is not configured."""


def _google_services():
    try:
        folder_id = str(st.secrets["google_sheets"]["folder_id"]).strip()
    except (KeyError, FileNotFoundError) as exc:
        raise StorageConfigurationError(
            "Google Sheets storage is not configured. Add the [auth] Google OAuth settings "
            "and google_sheets.folder_id to Streamlit secrets."
        ) from exc
    if not folder_id:
        raise StorageConfigurationError("Set google_sheets.folder_id to the Drive folder for survey spreadsheets.")

    try:
        access_token = st.user.tokens["access"]
    except (AttributeError, KeyError, TypeError) as exc:
        raise StorageConfigurationError("Sign in with Google and grant Drive and Sheets access to continue.") from exc
    cached = st.session_state.get("_google_sheets_services")
    if cached and cached.get("access_token") == access_token:
        return cached["sheets"], cached["drive"], folder_id

    credentials = Credentials(token=access_token, scopes=SCOPES)
    sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    st.session_state["_google_sheets_services"] = {
        "access_token": access_token,
        "sheets": sheets,
        "drive": drive,
    }
    return sheets, drive, folder_id


def init_files():
    """Compatibility entry point; data is now read and written directly to Sheets."""
    _google_services()


def _active_spreadsheet_id(spreadsheet_id=None):
    selected = spreadsheet_id or st.session_state.get("active_spreadsheet_id")
    if not selected:
        raise StorageConfigurationError("Select or create a Google Sheets dataset before editing survey data.")
    return str(selected)


def _get_values(spreadsheet_id, worksheet, cell_range="A1:Z"):
    sheets, _, _ = _google_services()
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{worksheet}'!{cell_range}",
    ).execute()
    return result.get("values", [])


def _write_values(spreadsheet_id, worksheet, values):
    sheets, _, _ = _google_services()
    sheets.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{worksheet}'!A:Z",
        body={},
    ).execute()
    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{worksheet}'!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def _list_drive_files():
    _, drive, folder_id = _google_services()
    files = []
    page_token = None
    while True:
        result = drive.files().list(
            q=f"'{folder_id}' in parents and mimeType = '{SHEETS_MIME_TYPE}' and trashed = false",
            pageSize=1000,
            pageToken=page_token,
            orderBy="name",
            fields="nextPageToken,files(id,name,mimeType,webViewLink,modifiedTime)",
        ).execute()
        files.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return files


def _dataset_title_parts(title):
    match = re.match(r"^(.*)-(\d{3,})$", str(title))
    if not match:
        return None
    return match.group(1), int(match.group(2))


def list_datasets():
    """List survey workbooks in the configured Drive folder."""
    datasets = []
    for file in _list_drive_files():
        if file.get("name") == REGISTRY_TITLE:
            continue
        parts = _dataset_title_parts(file.get("name", ""))
        if not parts:
            continue
        name, serial = parts
        datasets.append({
            "spreadsheet_id": file["id"],
            "dataset_id": file["name"],
            "name": name,
            "serial": serial,
            "url": file.get("webViewLink", f"https://docs.google.com/spreadsheets/d/{file['id']}/edit"),
        })
    return datasets


def _move_to_dataset_folder(spreadsheet_id):
    _, drive, folder_id = _google_services()
    current = drive.files().get(fileId=spreadsheet_id, fields="parents").execute()
    parents = current.get("parents", [])
    kwargs = {"fileId": spreadsheet_id, "addParents": folder_id, "fields": "id,parents"}
    if parents:
        kwargs["removeParents"] = ",".join(parents)
    drive.files().update(**kwargs).execute()


def _create_spreadsheet(title, worksheet_titles):
    sheets, _, _ = _google_services()
    created = sheets.spreadsheets().create(
        body={
            "properties": {"title": title},
            "sheets": [{"properties": {"title": name}} for name in worksheet_titles],
        },
        fields="spreadsheetId,spreadsheetUrl",
    ).execute()
    _move_to_dataset_folder(created["spreadsheetId"])
    return created


def _registry_spreadsheet_id(existing_files=None):
    existing_files = existing_files if existing_files is not None else _list_drive_files()
    registry = next((file for file in existing_files if file.get("name") == REGISTRY_TITLE), None)
    if registry:
        return registry["id"]
    return _create_spreadsheet(REGISTRY_TITLE, ["Registry"])["spreadsheetId"]


def _allocate_serial():
    files = _list_drive_files()
    registry_id = _registry_spreadsheet_id(files)
    rows = _get_values(registry_id, "Registry")
    current_serial = None
    for row in rows[1:]:
        if len(row) > 1 and row[0] == "next_serial":
            try:
                current_serial = int(row[1])
            except (TypeError, ValueError):
                current_serial = None
            break
    observed_next = max(
        (parts[1] + 1 for file in files if (parts := _dataset_title_parts(file.get("name", "")))),
        default=1,
    )
    if current_serial is None:
        current_serial = observed_next
    current_serial = max(current_serial, observed_next, 1)
    _write_values(registry_id, "Registry", [["key", "value"], ["next_serial", current_serial + 1]])
    return current_serial


def create_dataset(name):
    """Create a new spreadsheet dataset and initialize its three data tabs."""
    name = str(name).strip() or "Field Survey"
    serial = _allocate_serial()
    dataset_id = f"{name}-{serial:03d}"
    created = _create_spreadsheet(dataset_id, DATASET_SHEETS)
    spreadsheet_id = created["spreadsheetId"]
    info = {
        "name": name,
        "serial": serial,
        "dataset_id": dataset_id,
        "next_tree_id": 3,
        **DEFAULT_MAP_ORIENTATION,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_values(spreadsheet_id, "Trees", [["tree", "x", "y"], [1, 0, 0], [2, 0, 1]])
    _write_values(spreadsheet_id, "Measurements", [["tree_a", "tree_b", "distance_mm"]])
    save_dataset_info(info, spreadsheet_id=spreadsheet_id)
    info["spreadsheet_id"] = spreadsheet_id
    st.session_state["active_spreadsheet_id"] = spreadsheet_id
    return info


def _parse_dataset_info(rows):
    if not rows:
        raise ValueError("This spreadsheet has no Dataset tab metadata. Create datasets with this app.")
    values = {str(row[0]): row[1] for row in rows[1:] if len(row) > 1 and row[0]}
    if "dataset_id" not in values or "serial" not in values:
        raise ValueError("This spreadsheet is missing required survey dataset metadata.")
    info = dict(values)
    for key in ("serial", "next_tree_id"):
        if key in info:
            info[key] = int(info[key])
    for key in ("mirror_map_x", "mirror_map_y"):
        info[key] = str(info.get(key, "false")).lower() in ("true", "1", "yes")
    info["name"] = info.get("name", info["dataset_id"])
    info["map_axis_layout"] = info.get("map_axis_layout", DEFAULT_MAP_ORIENTATION["map_axis_layout"])
    return info


def load_dataset_info(spreadsheet_id=None):
    spreadsheet_id = _active_spreadsheet_id(spreadsheet_id)
    try:
        return _parse_dataset_info(_get_values(spreadsheet_id, "Dataset"))
    except Exception as exc:
        if isinstance(exc, (StorageConfigurationError, ValueError)):
            raise
        raise RuntimeError(f"Could not read dataset metadata from Google Sheets: {exc}") from exc


def save_dataset_info(info, spreadsheet_id=None):
    spreadsheet_id = _active_spreadsheet_id(spreadsheet_id)
    info = dict(info)
    info["name"] = str(info.get("name", "Field Survey")).strip() or "Field Survey"
    info["serial"] = int(info["serial"])
    info["dataset_id"] = f"{info['name']}-{info['serial']:03d}"
    values = [["key", "value"]]
    for key, value in info.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        values.append([str(key), str(value)])
    _write_values(spreadsheet_id, "Dataset", values)
    return info


def rename_dataset(name):
    info = load_dataset_info()
    info["name"] = str(name).strip() or info["name"]
    save_dataset_info(info)
    _, drive, _ = _google_services()
    drive.files().update(fileId=_active_spreadsheet_id(), body={"name": info["dataset_id"]}, fields="id,name").execute()
    return info


def save_map_orientation(axis_layout, mirror_x, mirror_y):
    info = load_dataset_info()
    info["map_axis_layout"] = axis_layout if axis_layout in (
        "X horizontal, Y vertical", "Y horizontal, X vertical"
    ) else DEFAULT_MAP_ORIENTATION["map_axis_layout"]
    info["mirror_map_x"] = bool(mirror_x)
    info["mirror_map_y"] = bool(mirror_y)
    save_dataset_info(info)
    return info


def set_tree2_reference_axis(axis):
    """Move Tree 2 onto the selected positive axis while preserving its distance."""
    axis = str(axis).upper()
    if axis not in ("X", "Y"):
        raise ValueError("Tree 2 reference axis must be X or Y.")
    trees = load_trees()
    measurements = load_measurements(trees)
    baseline = [d for a, b, d in measurements if {a, b} == {1, 2}]
    current_x, current_y = trees.get(2, (0, 1))
    distance = int(round(sum(baseline) / len(baseline))) if baseline else int(round(max(current_x, current_y)))
    distance = max(distance, 1)
    trees[2] = (distance, 0) if axis == "X" else (0, distance)
    save_trees(trees)
    return trees[2]


def mark_tree_id_used(tree_id):
    info = load_dataset_info()
    info["next_tree_id"] = max(int(info.get("next_tree_id", 3)), int(tree_id) + 1)
    save_dataset_info(info)


def load_trees():
    spreadsheet_id = _active_spreadsheet_id()
    rows = _get_values(spreadsheet_id, "Trees")
    if not rows:
        return {}
    columns = {str(name).strip().lower(): index for index, name in enumerate(rows[0])}
    if not {"tree", "x", "y"}.issubset(columns):
        raise ValueError("Trees tab must have tree, x, and y columns.")
    trees = {}
    for row in rows[1:]:
        if len(row) <= max(columns.values()):
            continue
        tree_id = int(float(row[columns["tree"]]))
        x = max(0, int(round(float(row[columns["x"]]))))
        y = max(0, int(round(float(row[columns["y"]]))))
        if tree_id == 1:
            x, y = 0, 0
        trees[tree_id] = (x, y)
    return trees


def save_trees(trees_dict):
    rows = [["tree", "x", "y"]]
    rows.extend([[int(tree), int(round(x)), int(round(y))] for tree, (x, y) in sorted(trees_dict.items())])
    _write_values(_active_spreadsheet_id(), "Trees", rows)


def load_measurements(trees_dict):
    rows = _get_values(_active_spreadsheet_id(), "Measurements")
    if not rows:
        return []
    columns = {str(name).strip().lower(): index for index, name in enumerate(rows[0])}
    required = {"tree_a", "tree_b", "distance_mm"}
    if not required.issubset(columns):
        raise ValueError("Measurements tab must have tree_a, tree_b, and distance_mm columns.")
    measurements = []
    for row in rows[1:]:
        if len(row) <= max(columns.values()):
            continue
        a = int(float(row[columns["tree_a"]]))
        b = int(float(row[columns["tree_b"]]))
        distance = float(row[columns["distance_mm"]])
        if a in trees_dict and b in trees_dict and a != b and distance > 0:
            measurements.append((a, b, distance))
    return measurements


def save_measurements(measurements):
    rows = [["tree_a", "tree_b", "distance_mm"]]
    rows.extend([[int(a), int(b), float(distance)] for a, b, distance in measurements])
    _write_values(_active_spreadsheet_id(), "Measurements", rows)


def append_measurement(a, b, distance_mm):
    measurements = load_measurements(load_trees())
    measurements.append((int(a), int(b), float(distance_mm)))
    save_measurements(measurements)
