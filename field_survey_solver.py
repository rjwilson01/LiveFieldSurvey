"""Least-squares adjustment of tree positions from tape distances."""

import numpy as np
from scipy.optimize import least_squares


from itertools import combinations
import numpy as np
from scipy.optimize import least_squares


def run_network_adjustment(trees_dict, measurements, anchor_weight=1e-3):
    """Return adjusted coordinates (mm), solver metadata, and geometry warnings.

    anchor_weight=1e-3 corresponds to a 1000 mm map-click prior vs 1 mm tape
    weight (1,000,000 : 1 squared error ratio). Keeps unconstrained chains from
    wildly drifting without biasing constrained triangles.
    """
    ids = sorted(trees_dict)
    if 1 not in trees_dict or 2 not in trees_dict or len(ids) < 2:
        return {}, None

    guesses = {t: np.asarray(trees_dict[t], dtype=float) for t in ids}
    baseline = [d for a, b, d in measurements if {a, b} == {1, 2}]
    anchor_axis = 0 if abs(guesses[2][0]) > abs(guesses[2][1]) else 1
    anchor_distance = float(np.mean(baseline)) if baseline else max(abs(guesses[2][anchor_axis]), 1.0)
    anchor_distance = max(anchor_distance, 1e-6)
    anchor_position = np.zeros(2, dtype=float)
    anchor_position[anchor_axis] = anchor_distance

    free_ids = [t for t in ids if t not in (1, 2)]
    initial = np.concatenate([np.maximum(guesses[t], 0.0) for t in free_ids]) if free_ids else np.array([])
    index = {tree: i for i, tree in enumerate(free_ids)}

    def xy(tree, values):
        if tree == 1:
            return np.array([0.0, 0.0])
        if tree == 2:
            return anchor_position
        return values[2 * index[tree]:2 * index[tree] + 2]

    def residuals(values):
        result = []
        # 1. Primary distance residuals (weight = 1.0)
        for a, b, measured_mm in measurements:
            if a in trees_dict and b in trees_dict:
                result.append(np.linalg.norm(xy(a, values) - xy(b, values)) - measured_mm)
        # 2. Weak map-click anchors so unconstrained traverse chains stay near clicks
        if free_ids and anchor_weight > 0:
            result.extend((values - initial) * anchor_weight)
        return np.asarray(result, dtype=float)

    if measurements and free_ids:
        fit = least_squares(
            residuals,
            initial,
            bounds=(0.0, np.inf),
            method="trf",
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        values = fit.x
        success = bool(fit.success)
        message = fit.message
    else:
        values = initial
        success = False
        message = "Add distance measurements to calculate positions."

    coords = {1: (0.0, 0.0), 2: tuple(map(float, anchor_position))}
    coords.update({t: tuple(map(float, xy(t, values))) for t in free_ids})

    # Run geometry diagnostics
    unfixed = underconstrained_tree_ids(trees_dict, measurements, coords)
    warnings = diagnose_geometry(guesses, coords, measurements, unfixed)

    return coords, {
        "success": success,
        "message": str(message),
        "baseline_measured": bool(baseline),
        "unfixed_ids": unfixed,
        "warnings": warnings,
    }

def diagnose_geometry(guesses, coords, measurements, unfixed_ids, min_area_mm2=5000.0):
    """Detect fold-over local minima and gross initial-estimate errors on fixed nodes."""
    warnings = []

    # Build adjacency from measured edges
    adj = {t: set() for t in coords}
    for a, b, _ in measurements:
        if a in adj and b in adj and a != b:
            adj[a].add(b)
            adj[b].add(a)

    # 1. Triangle Chirality Flip (catches Node 10 folding onto Node 11)
    triangles = set()
    for u in adj:
        for v, w in combinations(adj[u], 2):
            if w in adj[v]:
                triangles.add(tuple(sorted((u, v, w))))

    for a, b, c in sorted(triangles):
        g_a, g_b, g_c = guesses[a], guesses[b], guesses[c]
        s_a, s_b, s_c = np.asarray(coords[a]), np.asarray(coords[b]), np.asarray(coords[c])

        area2_init = (g_b[0] - g_a[0]) * (g_c[1] - g_a[1]) - (g_b[1] - g_a[1]) * (g_c[0] - g_a[0])
        area2_solv = (s_b[0] - s_a[0]) * (s_c[1] - s_a[1]) - (s_b[1] - s_a[1]) * (s_c[0] - s_a[0])

        if abs(area2_init) >= 2 * min_area_mm2 and abs(area2_solv) >= 2 * min_area_mm2:
            if np.sign(area2_init) != np.sign(area2_solv):
                warnings.append({
                    "type": "chirality_flip",
                    "trees": (a, b, c),
                    "message": f"Triangle {a}-{b}-{c} flipped orientation (possible fold-over).",
                })

    # 2. Gross Initial Estimate Outlier (only on FIXED nodes, ignoring unbraced traverses)
    # Compare initial-to-solved shift against the median shift of all fixed nodes
    fixed_ids = [t for t in coords if t not in unfixed_ids and t not in (1, 2)]
    if len(fixed_ids) >= 3:
        shifts = {
            t: float(np.linalg.norm(np.asarray(coords[t]) - guesses[t]))
            for t in fixed_ids
        }
        median_shift = float(np.median(list(shifts.values())))
        for t, shift in shifts.items():
            # Flag only if a fixed node jumped > 500 mm AND > 3x the typical click error
            if shift > max(500.0, 3.0 * median_shift):
                warnings.append({
                    "type": "gross_initial_error",
                    "trees": (t,),
                    "shift_mm": round(shift, 1),
                    "message": f"Tree {t} moved {shift:.0f} mm from initial click (check for mistyped digit).",
                })

    return warnings



def underconstrained_tree_ids(trees_dict, measurements, coords):
    """Return trees with coordinate motion left in the network Jacobian null space.

    A point can be fixed by two well-placed distances, or remain movable despite
    several readings that constrain the same direction. The Jacobian rank tests
    the actual local geometry instead of counting links.
    """
    ids = sorted(tree for tree in trees_dict if tree not in (1, 2))
    if not ids:
        return set()

    has_baseline = any({a, b} == {1, 2} for a, b, _ in measurements)
    if not has_baseline or any(tree not in coords for tree in trees_dict):
        return set(ids)

    index = {tree: position for position, tree in enumerate(ids)}
    jacobian_rows = []
    for a, b, _ in measurements:
        if a not in coords or b not in coords or a == b:
            continue
        delta = np.asarray(coords[a], dtype=float) - np.asarray(coords[b], dtype=float)
        length = float(np.linalg.norm(delta))
        if length <= 1e-9:
            continue
        unit = delta / length
        row = np.zeros(2 * len(ids), dtype=float)
        if a in index:
            offset = 2 * index[a]
            row[offset:offset + 2] += unit
        if b in index:
            offset = 2 * index[b]
            row[offset:offset + 2] -= unit
        jacobian_rows.append(row)

    if not jacobian_rows:
        return set(ids)
    jacobian = np.vstack(jacobian_rows)
    _, singular_values, right_vectors = np.linalg.svd(jacobian, full_matrices=True)
    largest = float(singular_values[0]) if singular_values.size else 0.0
    # Treat near-singular directions as poorly fixed too; a tiny singular value
    # can represent substantial position uncertainty even when it is nonzero.
    relative_tolerance = max(max(jacobian.shape) * np.finfo(float).eps, 1e-6)
    tolerance = relative_tolerance * max(largest, 1.0)
    rank = int(np.count_nonzero(singular_values > tolerance))
    null_vectors = right_vectors[rank:, :]
    if not null_vectors.size:
        return set()

    unfixed = set()
    for tree, position in index.items():
        offset = 2 * position
        motion = float(np.linalg.norm(null_vectors[:, offset:offset + 2]))
        if motion > 1e-7:
            unfixed.add(tree)
    return unfixed
