# Live Field Survey

A Streamlit tool for recording tree-to-tree tape measurements and calculating adjusted tree positions with a least-squares network adjustment. Survey datasets are stored in Neon PostgreSQL.

## Neon setup

The project is linked to Neon project `curly-cake-12589954`, branch `production`. PostgreSQL is included on every Neon project. `neon.ts` contains the branch policy used by `neon deploy`.

The app can use a single set of database credentials and derive the pooled and direct Neon URLs. Set the direct endpoint host (without `-pooler`) once. Streamlit Community Cloud Secrets:

```toml
[database]
user = "YOUR_NEON_DATABASE_ROLE"
password = "YOUR_NEON_ROLE_PASSWORD"
host = "ep-example.region.aws.neon.tech"
name = "neondb"
port = 5432
```

The app adds `-pooler` to the endpoint host for normal app connections and uses the direct host for schema migrations. The app applies the checked-in SQL migration from `migrations/` once per database schema version.

For local runs, `.env.local` uses the equivalent flat environment variables:

```dotenv
DB_USER=YOUR_NEON_DATABASE_ROLE
DB_PASSWORD=YOUR_NEON_ROLE_PASSWORD
DB_HOST=ep-example.region.aws.neon.tech
DB_NAME=neondb
DB_PORT=5432
```

`.env.local` is a private local configuration file, not a notes file; it is ignored by Git. Use the same values as Streamlit Secrets if local development should connect to the same Neon branch. You can use different values to keep local testing on another database. Existing `DATABASE_URL` and `DATABASE_URL_UNPOOLED` settings remain supported as a fallback.

## Sign-in

The app uses Google OAuth for sign-in and restricts access to the email in `app.allowed_email`. No Google Drive or Sheets API settings are used.

In Streamlit Secrets, keep your existing `[auth]` OAuth block and set the allowed account separately:

```toml
[app]
allowed_email = "your-sign-in-account@example.com"
```

The old `[google_sheets]` block can be removed.

For Streamlit Community Cloud, keep the OAuth settings in the app's **Secrets**. The OAuth client redirect URI must be the app URL followed by `/oauth2callback`. Never commit OAuth secrets or database URLs to Git.

## Run locally

Install the packages from `requirements.txt`, configure `.streamlit/secrets.toml` for Google sign-in, and ensure `.env.local` contains the Neon variables. Then run:

```bash
streamlit run app.py
```

## Field workflow

1. Sign in with the configured Google account and select a dataset from the sidebar. Create a new dataset from **Data management** when needed.
2. Tree 1 is fixed at the origin. Tree 2 anchors either the positive X or positive Y axis; set this on the Help page. Its 1 ↔ 2 distance sets its coordinate on that axis.
3. Add trees from Tree management in the sidebar. Choose an existing tree or the next available ID, tap a placement target to set a starting estimate, then press Add or Update.
4. Record measured distances in millimetres. The live map draws each measured link and recalculates the network. Edits are written to Neon as you work.

One measurement is allowed per direction: `2 → 4` and `4 → 2` can both exist, but a second `2 → 4` updates the existing row. Measurement rows group by unordered pair while preserving direction. The short headings are `Meas`, `Adj`, and `Δ`; residuals are rounded to whole millimetres. Click a row or map line to select a record.

Each Neon dataset has a unique dataset name and serial, tree starting estimates, directed measurements, map orientation, and settings. Tree IDs are never reused; Trees 1 and 2 are protected anchors.
