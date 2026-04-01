"""
Layout helpers for placing glyphs on the board: relative positions (right/left/above/below)
and row stacking with configurable horizontal and vertical gaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

# “Pillow” spacing between glyphs (side by side) and between lines (rows).
DEFAULT_HORIZONTAL_GAP = 10
DEFAULT_VERTICAL_GAP = 40
DEFAULT_MAX_RENDER_DIM = 120


@dataclass(frozen=True)
class Rect:
    """Axis-aligned rectangle (top-left origin, y grows downward)."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


def rect_from_top_left(x: float, y: float, width: float, height: float) -> Rect:
    return Rect(x=x, y=y, width=width, height=height)


def top_left_right_of(
    left: Rect,
    width: float,
    height: float,
    gap: float = DEFAULT_HORIZONTAL_GAP,
) -> Tuple[float, float]:
    """Top-left of a rect placed immediately to the right of ``left``, top-aligned."""
    return left.right + gap, left.y


def top_left_left_of(
    right: Rect,
    width: float,
    height: float,
    gap: float = DEFAULT_HORIZONTAL_GAP,
) -> Tuple[float, float]:
    """Top-left of a rect placed immediately to the left of ``right``, top-aligned."""
    return right.x - gap - width, right.y


def top_left_below(
    above: Rect,
    width: float,
    height: float,
    gap: float = DEFAULT_VERTICAL_GAP,
) -> Tuple[float, float]:
    """Top-left of a rect placed below ``above``, left-aligned."""
    return above.x, above.bottom + gap


def top_left_above(
    below: Rect,
    width: float,
    height: float,
    gap: float = DEFAULT_VERTICAL_GAP,
) -> Tuple[float, float]:
    """Top-left of a rect placed above ``below``, left-aligned."""
    return below.x, below.y - gap - height


def scaled_render_size(
    natural_width: int,
    natural_height: int,
    max_dim: float = DEFAULT_MAX_RENDER_DIM,
) -> Tuple[float, float]:
    """
    Match Konva glyph sizing, but keep *height* constant.

    The previous “fit inside square” approach used `min(wRatio, hRatio)`, which can
    shrink the rendered height for wide images. For the glyph board we want
    consistent height so side-by-side placement looks uniform.
    """
    if natural_width <= 0 or natural_height <= 0:
        return (float(max_dim), float(max_dim))

    # Scale by height only.
    scale = float(max_dim) / float(natural_height)
    rendered_height = float(natural_height) * scale  # equals max_dim
    rendered_width = float(natural_width) * scale
    return rendered_width, rendered_height


def layout_line_horizontal(
    sizes: Sequence[Tuple[float, float]],
    origin: Tuple[float, float],
    gap: float = DEFAULT_HORIZONTAL_GAP,
) -> List[Tuple[float, float]]:
    """
    Place glyphs left-to-right, top-aligned to ``origin[1]``.

    ``sizes`` are (rendered_width, rendered_height) per glyph.
    Returns top-left (x, y) for each glyph.
    """
    x0, y0 = origin
    out: List[Tuple[float, float]] = []
    x = x0
    for w, _h in sizes:
        out.append((x, y0))
        x += w + gap
    return out


def layout_horizontal_wrap(
    sizes: Sequence[Tuple[float, float]],
    origin: Tuple[float, float],
    max_row_width: float,
    horizontal_gap: float = DEFAULT_HORIZONTAL_GAP,
    vertical_gap: float = DEFAULT_VERTICAL_GAP,
) -> List[Tuple[float, float]]:
    """
    Place glyphs left-to-right, wrapping to a new row when the next glyph would
    extend past ``origin[0] + max_row_width``.

    Rows are top-aligned; after each row, ``y`` advances by that row's max height
    plus ``vertical_gap`` (same stacking spirit as ``layout_rows_sequential``).
    A glyph wider than ``max_row_width`` still occupies a full row by itself.
    """
    if max_row_width <= 0:
        raise ValueError("max_row_width must be positive")

    x0, y0 = float(origin[0]), float(origin[1])
    out: List[Tuple[float, float]] = []
    cx = x0
    cy = y0
    row_max_h = 0.0
    first_in_row = True

    for w, h in sizes:
        w = float(w)
        h = float(h)
        if not first_in_row and cx + w > x0 + max_row_width:
            cy += row_max_h + vertical_gap
            cx = x0
            row_max_h = 0.0
            first_in_row = True

        out.append((cx, cy))
        row_max_h = max(row_max_h, h)
        cx += w + horizontal_gap
        first_in_row = False

    return out


def layout_vertical_stack(
    sizes: Sequence[Tuple[float, float]],
    origin: Tuple[float, float] = (0.0, 0.0),
    horizontal_gap: float = DEFAULT_HORIZONTAL_GAP,
    vertical_gap: float = DEFAULT_VERTICAL_GAP,
) -> List[Tuple[float, float]]:
    """
    Stack glyphs vertically using the same row rules as tablet lines: each glyph
    is its own row, so spacing is ``height + vertical_gap`` between baselines.
    """
    one_glyph_rows = [[(float(w), float(h))] for w, h in sizes]
    return layout_rows_sequential(
        one_glyph_rows,
        origin,
        horizontal_gap=horizontal_gap,
        vertical_gap=vertical_gap,
    )


def layout_rows_sequential(
    rows: Sequence[Sequence[Tuple[float, float]]],
    origin: Tuple[float, float] = (0.0, 0.0),
    horizontal_gap: float = DEFAULT_HORIZONTAL_GAP,
    vertical_gap: float = DEFAULT_VERTICAL_GAP,
) -> List[Tuple[float, float]]:
    """
    Same stacking rules as ``layout_rows_top_aligned`` but returns positions in
    row-major order (entire row 1 left-to-right, then row 2, …).
    """
    x0, y0 = origin[0], origin[1]
    positions: List[Tuple[float, float]] = []
    cy = y0
    for row in rows:
        if not row:
            continue
        row_height = max(h for _w, h in row)
        line_positions = layout_line_horizontal(row, (x0, cy), gap=horizontal_gap)
        positions.extend(line_positions)
        cy += row_height + vertical_gap
    return positions
