"""Least-squares adjustment of tree positions from tape distances."""

import numpy as np
from scipy.optimize import least_squares


def run_network_adjustment(trees_dict, measurements):
    """Return adjusted coordinates (mm), starting guesses, and solver metadata.

    Tree 1 defines the origin. Tree 2 defines the positive Y axis, with its
    position set by their measured baseline when one is recorded. Remaining
    estimates are retained as the solver's starting point and constrained to
    the positive quadrant to keep the chosen orientation stable.
    """
    ids = sorted(trees_dict)
    if 1 not in trees_dict or 2 not in trees_dict or len(ids) < 2:
        return {}, None

    guesses = {t: np.asarray(trees_dict[t], dtype=float) for t in ids}
    baseline = [d for a, b, d in measurements if {a, b} == {1, 2}]
    anchor_y = float(np.mean(baseline)) if baseline else max(abs(guesses[2][1]), 1.0)
    anchor_y = max(anchor_y, 1e-6)
    free_ids = [t for t in ids if t not in (1, 2)]
    initial = np.concatenate([np.maximum(guesses[t], 0.0) for t in free_ids]) if free_ids else np.array([])
    index = {tree: i for i, tree in enumerate(free_ids)}

    def xy(tree, values):
        if tree == 1:
            return np.array([0.0, 0.0])
        if tree == 2:
            return np.array([0.0, anchor_y])
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

    coords = {1: (0.0, 0.0), 2: (0.0, anchor_y)}
    coords.update({t: tuple(map(float, xy(t, values))) for t in free_ids})
    return coords, {"success": success, "message": str(message), "baseline_measured": bool(baseline)}
