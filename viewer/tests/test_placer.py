import unittest

from viewer.placer import (
    DEFAULT_HORIZONTAL_GAP,
    DEFAULT_VERTICAL_GAP,
    layout_horizontal_wrap,
    layout_vertical_stack,
)


class LayoutHorizontalWrapTests(unittest.TestCase):
    def test_single_glyph(self):
        pos = layout_horizontal_wrap([(50, 120)], (0, 0), max_row_width=1000)
        self.assertEqual(pos, [(0.0, 0.0)])

    def test_two_fit_one_row(self):
        # 50 + 10 gap + 50 = 110 <= 200
        pos = layout_horizontal_wrap([(50, 120), (50, 120)], (0, 0), max_row_width=200)
        self.assertEqual(pos[0], (0.0, 0.0))
        self.assertEqual(pos[1], (50.0 + DEFAULT_HORIZONTAL_GAP, 0.0))

    def test_wrap_second_to_new_row(self):
        # First at 0, second would start at 60+10=70, 70+60=130 > 100
        pos = layout_horizontal_wrap([(60, 50), (60, 80)], (0, 0), max_row_width=100)
        self.assertEqual(pos[0], (0.0, 0.0))
        self.assertEqual(
            pos[1],
            (0.0, 50.0 + DEFAULT_VERTICAL_GAP),
        )

    def test_variable_row_heights(self):
        pos = layout_horizontal_wrap([(10, 30), (10, 100)], (5, 7), max_row_width=15)
        self.assertEqual(pos[0], (5.0, 7.0))
        # Row 1 max height is 30; next row starts after vertical gap.
        self.assertEqual(pos[1], (5.0, 7.0 + 30.0 + DEFAULT_VERTICAL_GAP))

    def test_oversized_glyph_starts_row(self):
        pos = layout_horizontal_wrap([(200, 40), (10, 40)], (0, 0), max_row_width=100)
        self.assertEqual(pos[0], (0.0, 0.0))
        self.assertEqual(pos[1], (0.0, 40.0 + DEFAULT_VERTICAL_GAP))

    def test_max_row_width_positive(self):
        with self.assertRaises(ValueError):
            layout_horizontal_wrap([(1, 1)], (0, 0), max_row_width=0)


class LayoutVerticalStackTests(unittest.TestCase):
    def test_matches_rows_sequential_single_columns(self):
        pos = layout_vertical_stack([(40, 120), (40, 60)], (0, 0))
        self.assertEqual(pos[0], (0.0, 0.0))
        self.assertEqual(pos[1], (0.0, 120.0 + DEFAULT_VERTICAL_GAP))


if __name__ == "__main__":
    unittest.main()
