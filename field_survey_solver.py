"""Least-squares adjustment of tree positions from tape distances."""

import numpy as np
from scipy.optimize import least_squares


def run_network_adjustment(trees_dict, measurements):
    """Return adjusted coordinates (mm), starting guesses, and solver metadata.

    Tree 1 defines the origin. Tree 2 defines either the positive X or positive
    Y axis, based on its starting estimate, with its position set by their
    measured baseline when one is recorded. Remaining
    estimates are retained as the solver's starting point and constrained to
    the positive quadrant to keep the chosen orientation stable.
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
        for a, b, measured_mm in measurements:
            if a in trees_dict and b in trees_dict:
                result.append(np.linalg.norm(xy(a, values) - xy(b, values)) - measured_mm)
        return np.asarray(result, dtype=float)

    if measurements and free_ids:
        fit = least_squares(residuals, initial, bounds=(0.0, np.inf), method="trf", ftol=1e-10, xtol=1e-10, gtol=1e-10)
        values = fit.x
        success = bool(fit.success)
        message = fit.message
    else:
        values = initial
        success = False
        message = "Add distance measurements to calculate positions."

    coords = {1: (0.0, 0.0), 2: tuple(map(float, anchor_position))}
    coords.update({t: tuple(map(float, xy(t, values))) for t in free_ids})
    return coords, {"success": success, "message": str(message), "baseline_measured": bool(baseline)}


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
