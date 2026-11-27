import math
import numpy as np
import plotly.graph_objects as go


def survey_to_map(x, y, axis_layout, mirror_x, mirror_y):
    swap_axes = axis_layout == "Y horizontal, X vertical"
    signed_x = -x if mirror_x else x
    signed_y = -y if mirror_y else y
    return (signed_y, signed_x) if swap_axes else (signed_x, signed_y)


def map_to_survey(map_x, map_y, axis_layout, mirror_x, mirror_y):
    swap_axes = axis_layout == "Y horizontal, X vertical"
    signed_x, signed_y = (map_y, map_x) if swap_axes else (map_x, map_y)
    x = -signed_x if mirror_x else signed_x
    y = -signed_y if mirror_y else signed_y
    return (x, y)


def build_survey_map(
    trees,
    measurements,
    coords,
    underconstrained,
    axis_layout="X horizontal, Y vertical",
    mirror_x=False,
    mirror_y=False,
    show_initial_estimates=False,
    show_starting_targets=True,
    include_target_trace=True,
    highlight_pair=None,
):
    """Build the shared map; target dots can be omitted for the read-only view."""
    swap_axes = axis_layout == "Y horizontal, X vertical"
    horizontal_axis_name = "Y" if swap_axes else "X"
    vertical_axis_name = "X" if swap_axes else "Y"
    horizontal_sign = -1 if (mirror_y if swap_axes else mirror_x) else 1
    vertical_sign = -1 if (mirror_x if swap_axes else mirror_y) else 1

    fig = go.Figure()
    if coords:
        extent_points = [
            survey_to_map(*point, axis_layout, mirror_x, mirror_y)
            for point in list(trees.values()) + list(coords.values())
        ]
        max_x = max(1000, max(abs(point[0]) for point in extent_points) + 1000)
        max_y = max(1000, max(abs(point[1]) for point in extent_points) + 1000)
        x_padding = max(100, int(max_x * 0.03))
        y_padding = max(100, int(max_y * 0.03))
        fig.add_shape(
            type="rect",
            x0=0 if horizontal_sign > 0 else -max_x,
            x1=max_x if horizontal_sign > 0 else 0,
            y0=0 if vertical_sign > 0 else -max_y,
            y1=max_y if vertical_sign > 0 else 0,
            fillcolor="rgba(34,197,94,0.045)",
            line={"width": 0},
            layer="below",
        )

        if include_target_trace:
            grid_x = np.linspace(0, max_x, 25) * horizontal_sign
            grid_y = np.linspace(0, max_y, 25) * vertical_sign
            grid_points = [(float(x), float(y)) for x in grid_x for y in grid_y]
            tap_points = [
                map_to_survey(x, y, axis_layout, mirror_x, mirror_y)
                for x, y in grid_points
            ]
            fig.add_trace(
                go.Scatter(
                    x=[point[0] for point in grid_points],
                    y=[point[1] for point in grid_points],
                    customdata=tap_points,
                    mode="markers",
                    marker={"size": 18, "color": "rgba(100,116,139,0.20)"},
                    hovertemplate=(
                        "Tap to set starting estimate<br>Survey X"
                        " %{customdata[0]:.0f} mm<br>Survey Y"
                        " %{customdata[1]:.0f} mm<extra></extra>"
                    ),
                    showlegend=False,
                    visible=show_starting_targets,
                    name="Starting estimate targets",
                )
            )

        # Track seen undirected pairs so reciprocal shots (a->b and b->a) separate cleanly
        seen_pairs = set()

        for record_index, (a, b, distance) in enumerate(measurements):
            if a not in coords or b not in coords:
                continue
            xa, ya = survey_to_map(*coords[a], axis_layout, mirror_x, mirror_y)
            xb, yb = survey_to_map(*coords[b], axis_layout, mirror_x, mirror_y)

            pair_key = tuple(sorted((a, b)))
            is_highlighted = highlight_pair == pair_key
            color = "#f97316" if is_highlighted else "#191c1f"
            has_arrow = {a, b} != {1, 2}

            dx, dy = xb - xa, yb - ya
            length = math.hypot(dx, dy)

            # Place arrow near the start node (a), outside the node's marker radius,
            # while capping at 22% of the line so short segments still look balanced.
            if length > 1e-9:
                clearance = max(max_x, max_y) * 0.025
                t = min(0.22, max(0.06, clearance / length))
            else:
                t = 0.1

            arrow_x = xa + dx * t
            arrow_y = ya + dy * t
            mid_x, mid_y = (xa + xb) / 2, (ya + yb) / 2

            # 4 points: [start, near-start arrow, invisible midpoint tap target, end]
            # angleref="previous" points the arrow from (xa, ya) -> (arrow_x, arrow_y) (away from a)
            fig.add_trace(
                go.Scatter(
                    x=[xa, arrow_x, mid_x, xb],
                    y=[ya, arrow_y, mid_y, yb],
                    mode="lines+markers",
                    line={"color": color, "width": 3 if is_highlighted else 2},
                    marker={
                        "symbol": [
                            "circle",
                            "arrow" if has_arrow else "circle",
                            "circle",
                            "circle",
                        ],
                        "size": [1, 13 if has_arrow else 1, 18, 1],
                        "angleref": "previous",
                        "color": [
                            color,
                            color if has_arrow else "rgba(0,0,0,0)",
                            "rgba(100,116,139,0.015)",  # Preserves your center tap/hover target
                            color,
                        ],
                    },
                    customdata=[[record_index, a, b]] * 4,
                    hovertemplate=(
                        f"{a} → {b}: {distance:.0f} mm<extra></extra>"
                    ),
                    showlegend=False,
                )
            )

        estimate_points = [
            survey_to_map(*trees[tree], axis_layout, mirror_x, mirror_y)
            for tree in sorted(trees)
        ]
        fig.add_trace(
            go.Scatter(
                x=[point[0] for point in estimate_points],
                y=[point[1] for point in estimate_points],
                customdata=[trees[tree] for tree in sorted(trees)],
                mode="markers",
                name="Initial estimates",
                visible=show_initial_estimates,
                showlegend=False,
                marker={
                    "symbol": "circle-open",
                    "size": 13,
                    "color": "#64748b",
                    "line": {"width": 2},
                },
                text=[str(tree) for tree in sorted(trees)],
                hovertemplate=(
                    "Initial estimate · Tree %{text}<br>Survey X"
                    " %{customdata[0]:.0f} mm<br>Survey Y %{customdata[1]:.0f}"
                    " mm<extra></extra>"
                ),
            )
        )

        neighbors = {tree: set() for tree in trees}
        for a, b, _ in measurements:
            if a in neighbors and b in neighbors:
                neighbors[a].add(b)
                neighbors[b].add(a)
        colors = [
            "#2563eb"
            if tree in (1, 2)
            else ("#f59e0b" if tree in underconstrained else "#15803d")
            for tree in sorted(trees)
        ]
        adjusted_points = [
            survey_to_map(*coords[tree], axis_layout, mirror_x, mirror_y)
            for tree in sorted(trees)
        ]
        fig.add_trace(
            go.Scatter(
                x=[point[0] for point in adjusted_points],
                y=[point[1] for point in adjusted_points],
                mode="markers+text",
                name="Adjusted positions",
                showlegend=False,
                text=[str(tree) for tree in sorted(trees)],
                textposition="top center",
                marker={
                    "size": 15,
                    "color": colors,
                    "line": {"color": "white", "width": 1},
                },
                customdata=[
                    [
                        len(neighbors[tree]),
                        tree in underconstrained,
                        tree,
                        coords[tree][0],
                        coords[tree][1],
                    ]
                    for tree in sorted(trees)
                ],
                hovertemplate=(
                    "Tree %{text}<br>Survey X %{customdata[3]:.0f} mm<br>Survey"
                    " Y %{customdata[4]:.0f} mm<br>Distinct links:"
                    " %{customdata[0]}<extra></extra>"
                ),
            )
        )
    else:
        max_x = max_y = 1000
        x_padding = y_padding = 100

    x_range = [-x_padding, max_x] if horizontal_sign > 0 else [-max_x, x_padding]
    y_range = [-y_padding, max_y] if vertical_sign > 0 else [-max_y, y_padding]
    fig.update_layout(
        height=620,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        xaxis={
            "title": f"{horizontal_axis_name} (mm)",
            "range": x_range,
            "zeroline": True,
            "scaleanchor": "y",
            "scaleratio": 1,
            "constrain": "domain",
            "constraintoward": "left",
        },
        yaxis={
            "title": f"{vertical_axis_name} (mm)",
            "range": y_range,
            "zeroline": True,
            "constrain": "domain",
            "constraintoward": "bottom",
        },
        showlegend=False,
        autosize=True,
        uirevision=f"survey-map-{swap_axes}-{mirror_x}-{mirror_y}",
    )
    return fig
