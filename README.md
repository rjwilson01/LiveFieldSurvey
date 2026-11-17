# Live Field Survey

A Streamlit tool for recording tree-to-tree tape measurements and calculating adjusted tree positions with a least-squares network adjustment.

## Run locally

Install the packages from `requirements.txt`, then run:

```bash
streamlit run app.py
```

## Field workflow

1. Tree 1 is shown at the bottom-left origin `(0, 0)`. Tree 2 is above it on the positive Y axis. Record a measurement between them to establish the network scale and baseline.
2. Add trees from Tree management in the sidebar. Select an existing tree or the next available ID, tap a grid point to set its starting estimate, then press Add or Update. Tree 1 and Tree 2 are protected anchors. Use the map toggle to show or hide initial estimates.
3. Record measured distances in millimetres. The live map draws each measured link and recalculates the network.
4. Review amber trees for missing links or a disconnected network. Three or more links and a path to the anchor network are used as a practical field indicator that a tree has enough ties.
5. Review distance residual warnings and large shifts from saved estimates. Both alert thresholds can be changed in the sidebar. Measurement distances can be edited or deleted.
6. Download the complete dataset ZIP from the Dataset section in the sidebar for backup and restore. Download the combined tree and measurement CSV, or a separate measurement ledger, from Export survey.

## Dataset backup and replacement

The Dataset panel assigns an ID in the form `Name-001`. Each confirmed ZIP upload receives the next serial number and replaces the active trees and measurements. The ZIP includes a manifest plus `trees.csv` and `measurements.csv`; those two CSVs retain starting estimates and all directed measurement records. The app validates the archive before showing a replacement confirmation. The Dataset panel marks the active set **Not downloaded** whenever its data or name changes and clears that flag when the ZIP download is requested. Download the ZIP before replacing a set that matters to you.

One measurement is allowed per direction: `2 → 4` and `4 → 2` can both exist, but a second `2 → 4` must update the existing row. The review table groups records by unordered pair while preserving From/To direction. Its short headings are `Meas`, `Adj`, and `Δ`; residuals are rounded to whole millimetres. Click a table row to load it into the sidebar for update or deletion. On the map, successive tree taps alternate the From and To fields; tapping a currently selected endpoint keeps it and directs the next tap to the other field. Tree 2 can be selected and its Y estimate edited; its X coordinate stays fixed at zero.

Trees 1 and 2 are protected anchors. Other trees and their associated measurements can be deleted from the sidebar. Deleted tree numbers are retired; the next tree number is saved in the dataset ZIP so it is not reused when that dataset is restored. Each successful edit is written immediately to `active_trees.csv`, `survey_data.csv`, and the dataset metadata files in the app's working directory, so there is no separate Save button. On Streamlit Community Cloud these local files are not a durable backup; download the ZIP before a reboot or any operation that might reset app storage. For unattended durable saving, the app needs a persistent external database.
