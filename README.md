# Live Field Survey

A Streamlit tool for recording tree-to-tree tape measurements and calculating adjusted tree positions with a least-squares network adjustment.

## Run locally

Install the packages from `requirements.txt`, then run:

```bash
streamlit run app.py
```

## Field workflow

1. Tree 1 is the origin `(0, 0)`. Tree 2 defines the positive Y axis. Record a measurement between them to establish the network scale and baseline.
2. Add trees in the sidebar and enter rough initial X/Y estimates in millimetres. Estimates are saved separately and remain visible when the adjusted positions move.
3. Record measured distances in millimetres. The live map draws each measured link and recalculates the network.
4. Review amber trees for missing links or a disconnected network. Three or more links and a path to the anchor network are used as a practical field indicator that a tree has enough ties.
5. Review distance residual warnings and large shifts from saved estimates. Both alert thresholds can be changed in the sidebar. Measurement distances can be edited or deleted.
6. Download the combined tree and measurement CSV, or a separate measurement ledger.

Repeated measurements are kept as separate observations, including reverse-direction readings such as `2 → 4` and `4 → 2`; the review table groups them under the same unordered tree pair while preserving the From/To direction. Residuals are rounded to whole millimetres. Click a table row to edit or delete that observation. On the map, tap two adjusted tree markers to prefill a new measurement, or tap a measurement line to highlight all observations for that pair.

Trees 1 and 2 are protected anchors. Other trees and their associated measurements can be deleted from the sidebar. Survey data is stored in `active_trees.csv` and `survey_data.csv` in the app's working directory; back these files up when hosting on an ephemeral service.
