# Live Field Survey

A Streamlit tool for recording tree-to-tree tape measurements and calculating adjusted tree positions with a least-squares network adjustment. Survey data is stored directly in Google Sheets, with one spreadsheet per dataset.

## Configure Google Sheets access

The app signs in with your Google account using OAuth so newly created spreadsheets belong to you in My Drive. In the Google Cloud project, enable the Google Sheets API and Google Drive API, configure the OAuth consent screen, and create an OAuth client ID with application type **Web application**. Add the Streamlit app URL with `/oauth2callback` as an authorized redirect URI. If the consent screen is in testing mode, add your Google account as a test user.

For Streamlit Community Cloud, add these settings to the app's **Secrets**. For local development, save them in `.streamlit/secrets.toml`. Never commit OAuth secrets to Git.

```toml
[auth]
redirect_uri = "https://YOUR-APP.streamlit.app/oauth2callback"
cookie_secret = "A_LONG_RANDOM_SECRET"
client_id = "YOUR_OAUTH_CLIENT_ID"
client_secret = "YOUR_OAUTH_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
expose_tokens = ["access"]
client_kwargs = { "scope" = "openid email profile https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/spreadsheets" }

[google_sheets]
folder_id = "YOUR_DRIVE_FOLDER_ID"
allowed_email = "YOUR_GOOGLE_ACCOUNT_EMAIL"
```

Google OAuth grants the app the requested Drive scope. The app checks the signed-in email against `allowed_email` and uses the configured `folder_id` for its spreadsheet list and file operations. The Drive scope itself is broad; it is not enforced at the individual-folder permission level.

The `_LiveFieldSurvey Registry` spreadsheet in the folder tracks the next dataset serial so IDs are not reused if a dataset spreadsheet is later removed. Once OAuth is configured and working, remove the old `[gcp_service_account]` block from Streamlit Secrets and delete its unused key in Google Cloud.

## Run locally

Install the packages from `requirements.txt`, configure the OAuth secrets above, then run:

```bash
streamlit run app.py
```

## Field workflow

1. Sign in with the Google account listed in `allowed_email`. Select a dataset spreadsheet from the sidebar. Create a new dataset from **Data management**; this creates a workbook with `Trees`, `Measurements`, and `Dataset` tabs.
2. Tree 1 is fixed at the origin. Tree 2 anchors either the positive X or positive Y axis; set this on the Help page. Its 1 ↔ 2 distance is a regular measurement and sets its coordinate on that axis.
3. Add trees from Tree management in the sidebar. Choose an existing tree or the next available ID, tap a placement target to set a starting estimate, then press Add or Update.
4. Record measured distances in millimetres. The live map draws each measured link and recalculates the network. Edits are written immediately to the selected spreadsheet.
5. Review amber trees for missing links or a disconnected network. Three or more links and a path to the anchor network are used as a practical field indicator that a tree has enough ties.
6. Review distance residual warnings and large shifts from saved estimates. Both alert thresholds can be changed on the Help page.

One measurement is allowed per direction: `2 → 4` and `4 → 2` can both exist, but a second `2 → 4` updates the existing row. The review table groups records by unordered pair while preserving direction. Its short headings are `Meas`, `Adj`, and `Δ`; residuals are rounded to whole millimetres. Click a table row or map line to select a record. Measurement edits, tree estimates, and map orientation are saved directly to Google Sheets.

Each dataset workbook has a `Trees` tab for initial coordinates, a `Measurements` tab for directed distance readings, and a `Dataset` tab for its name, unique serial, next tree ID, and display settings. The app does not need an export/import CSV or a separate Save action. Google Sheets is the durable store; use Drive's own version history or file-copy features if you need a manual backup.
