# Live Field Survey

A Streamlit tool for recording tree-to-tree tape measurements and calculating adjusted tree positions with a least-squares network adjustment. Survey datasets are stored in Neon PostgreSQL. Existing Google Sheets workbooks can be copied into Neon without changing the originals.

## Neon setup

The project is linked to Neon project `curly-cake-12589954`, branch `production`. PostgreSQL is included on every Neon project. `neon.ts` contains the branch policy used by `neon deploy`.

The Neon CLI writes the pooled app connection string (`DATABASE_URL`) and the direct migration connection string (`DATABASE_URL_UNPOOLED`) to `.env.local`. Keep that file private; it is ignored by Git. Local runs load it automatically. In Streamlit Community Cloud, add both values as top-level Secrets:

```toml
DATABASE_URL = "YOUR_NEON_POOLED_CONNECTION_STRING"
DATABASE_URL_UNPOOLED = "YOUR_NEON_DIRECT_CONNECTION_STRING"
```

Use the pooled URL for normal app connections. Schema migrations prefer the direct URL. The app applies the checked-in SQL migration from `migrations/` once per database schema version.

## Sign-in and Google Sheets migration

Keep the existing `[auth]` OAuth settings and `[google_sheets]` settings in Streamlit Secrets for the initial migration. Google sign-in still restricts access to the account in `google_sheets.allowed_email`. Drive and Sheets API access is retained only to copy existing workbooks into Neon. The migration button appears when the configured folder and Google API token are available. It copies each workbook's dataset metadata, starting estimates, directed measurements, and next dataset serial. It does not delete or modify source workbooks. Repeating the import skips workbooks already copied.

After the data has been copied and verified, the Google Drive and Sheets API scopes and folder settings can be removed. Google sign-in can remain for app access control.

For Streamlit Community Cloud, keep the OAuth settings in the app's **Secrets**. The OAuth client redirect URI must be the app URL followed by `/oauth2callback`. Never commit OAuth secrets or database URLs to Git.

## Run locally

Install the packages from `requirements.txt`, configure `.streamlit/secrets.toml` for Google sign-in, and ensure `.env.local` contains the Neon variables. Then run:

```bash
streamlit run app.py
```

## Field workflow

1. Sign in with the configured Google account and select a dataset from the sidebar. Copy existing Google Sheets datasets from **Data management**, or create a new dataset there.
2. Tree 1 is fixed at the origin. Tree 2 anchors either the positive X or positive Y axis; set this on the Help page. Its 1 ↔ 2 distance sets its coordinate on that axis.
3. Add trees from Tree management in the sidebar. Choose an existing tree or the next available ID, tap a placement target to set a starting estimate, then press Add or Update.
4. Record measured distances in millimetres. The live map draws each measured link and recalculates the network. Edits are written to Neon as you work.

One measurement is allowed per direction: `2 → 4` and `4 → 2` can both exist, but a second `2 → 4` updates the existing row. Measurement rows group by unordered pair while preserving direction. The short headings are `Meas`, `Adj`, and `Δ`; residuals are rounded to whole millimetres. Click a row or map line to select a record.

Each Neon dataset has a unique dataset name and serial, tree starting estimates, directed measurements, map orientation, and settings. Tree IDs are never reused; Trees 1 and 2 are protected anchors.
