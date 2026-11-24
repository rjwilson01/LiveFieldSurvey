# Live Field Survey

A Streamlit tool for recording tree-to-tree tape measurements and calculating adjusted tree positions with a least-squares network adjustment. Survey data is stored directly in Google Sheets, with one spreadsheet per dataset.

## Configure Google Sheets storage

The app uses a Google Cloud service account. Enable the Google Sheets API and Google Drive API in the Cloud project, create a service account key, and create a Drive folder for survey spreadsheets. Share that folder with the service account email as an editor. The app creates each dataset spreadsheet in that folder and lists those spreadsheets in the sidebar.

For local development, add the following to `.streamlit/secrets.toml`. For Streamlit Community Cloud, add the same TOML structure in the app's Secrets settings. Never commit the service account key or `secrets.toml` to Git.

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = """-----BEGIN PRIVATE KEY-----
REPLACE_WITH_PRIVATE_KEY
-----END PRIVATE KEY-----
"""
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
token_uri = "https://oauth2.googleapis.com/token"

[google_sheets]
folder_id = "your-shared-drive-folder-id"
```

`folder_id` is the ID in the Google Drive folder URL. A hidden `_LiveFieldSurvey Registry` spreadsheet in that folder tracks the next dataset serial so IDs are not reused if a dataset spreadsheet is later removed.

## Run locally

Install the packages from `requirements.txt`, configure the secrets above, then run:

```bash
streamlit run app.py
```

## Field workflow

1. Select a dataset spreadsheet from the sidebar. Create a new dataset from **Data management**; this creates a workbook with `Trees`, `Measurements`, and `Dataset` tabs.
2. Tree 1 is fixed at the origin. Tree 2 anchors either the positive X or positive Y axis; set this on the Help page. Its 1 ↔ 2 distance is a regular measurement and sets its coordinate on that axis.
3. Add trees from Tree management in the sidebar. Choose an existing tree or the next available ID, tap a placement target to set a starting estimate, then press Add or Update.
4. Record measured distances in millimetres. The live map draws each measured link and recalculates the network. Edits are written immediately to the selected spreadsheet.
5. Review amber trees for missing links or a disconnected network. Three or more links and a path to the anchor network are used as a practical field indicator that a tree has enough ties.
6. Review distance residual warnings and large shifts from saved estimates. Both alert thresholds can be changed on the Help page.

One measurement is allowed per direction: `2 → 4` and `4 → 2` can both exist, but a second `2 → 4` updates the existing row. The review table groups records by unordered pair while preserving direction. Its short headings are `Meas`, `Adj`, and `Δ`; residuals are rounded to whole millimetres. Click a table row or map line to select a record. Measurement edits, tree estimates, and map orientation are saved directly to Google Sheets.

Each dataset workbook has a `Trees` tab for initial coordinates, a `Measurements` tab for directed distance readings, and a `Dataset` tab for its name, unique serial, next tree ID, and display settings. The app does not need an export/import CSV or a separate Save action. Google Sheets is the durable store; use Drive's own version history or file-copy features if you need a manual backup.
