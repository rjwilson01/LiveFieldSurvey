# Live Field Survey

A Streamlit tool for recording tree-to-tree tape measurements and calculating adjusted tree positions with a least-squares network adjustment.

## Run locally

Install the packages from `requirements.txt`, then run:

```bash
streamlit run app.py
```

## Field workflow

1. Tree 1 is shown at the bottom-left origin `(0, 0)`. Tree 2 is above it on the positive Y axis. Record a measurement between them to establish the network scale and baseline.
2. Add trees from the Tree management section. Tap a grid point on the map to place the selected tree's rough initial position; tap an existing tree to load its ID and estimate for updating or deleting. Estimates are saved as whole millimetres and remain visible when adjusted positions move.
3. Record measured distances in millimetres. The live map draws each measured link and recalculates the network.
4. Review amber trees for missing links or a disconnected network. Three or more links and a path to the anchor network are used as a practical field indicator that a tree has enough ties.
5. Review distance residual warnings and large shifts from saved estimates. Both alert thresholds can be changed in the sidebar. Measurement distances can be edited or deleted.
6. Download the combined tree and measurement CSV, or a separate measurement ledger.

## Dataset backup and replacement

The Dataset panel assigns an ID in the form `Name-001`. Each confirmed ZIP upload receives the next serial number and replaces the active trees and measurements. The ZIP includes a manifest plus `trees.csv` and `measurements.csv`; those two CSVs retain starting estimates and all directed measurement records. The app validates the archive before showing a replacement confirmation. The Dataset panel marks the active set **Not downloaded** whenever its data or name changes and clears that flag when the ZIP download is requested. Download the ZIP before replacing a set that matters to you.

Repeated measurements are kept as separate observations, including reverse-direction readings such as `2 → 4` and `4 → 2`; the review table groups them under the same unordered tree pair while preserving the From/To direction. Its short headings are `Meas`, `Adj`, and `Δ`; residuals are rounded to whole millimetres. Click a table row to edit or delete that observation. On the map, tap two adjusted tree markers to prefill a new measurement, or tap a measurement line to highlight all observations for that pair. Tree 2 can be selected and its Y estimate edited; its X coordinate stays fixed at zero.

Trees 1 and 2 are protected anchors. Other trees and their associated measurements can be deleted from the sidebar. Deleted tree numbers are retired; the next tree number is saved in the dataset ZIP so it is not reused when that dataset is restored. Each successful edit is written immediately to `active_trees.csv`, `survey_data.csv`, and the dataset metadata files in the app's working directory, so there is no separate Save button. On Streamlit Community Cloud these local files are not a durable backup; download the ZIP before a reboot or any operation that might reset app storage. For unattended durable saving, the app needs a persistent external database.
