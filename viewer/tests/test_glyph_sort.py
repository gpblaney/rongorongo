import unittest
from unittest.mock import patch

from viewer.glyph_sort import (
    CRITERION_CONNECTIONS,
    CRITERION_ORDER,
    CRITERION_TRANSLITERATION,
    reverse_token_sort_key,
    sort_glyph_addresses,
    transliteration_sort_key,
)


class TransliterationKeyTests(unittest.TestCase):
    def test_natural_numeric_chunks(self):
        self.assertLess(transliteration_sort_key("2.10"), transliteration_sort_key("10.2"))

    def test_reverse_token_key(self):
        # Right-to-left comparison of dot tokens
        a = reverse_token_sort_key("1.2.3")
        b = reverse_token_sort_key("1.2.4")
        self.assertLess(a, b)

    def test_mixed_digit_letter_no_typeerror(self):
        """Keys must compare without int/str TypeError (regression for /api/sort-layout)."""
        keys = sorted(
            [transliteration_sort_key("1a"), transliteration_sort_key("a1"), transliteration_sort_key("2")]
        )
        self.assertEqual(len(keys), 3)




class SortGlyphAddressesTests(unittest.TestCase):
    def test_order_uses_corpus_index(self):
        out = sort_glyph_addresses(
            ["Z2", "A1"],
            CRITERION_ORDER,
            corpus_index={"A1": 0, "Z2": 5},
        )
        self.assertEqual(out, ["A1", "Z2"])

    def test_stable_duplicates(self):
        out = sort_glyph_addresses(
            ["B", "A", "A"],
            CRITERION_ORDER,
            corpus_index={"A": 0, "B": 1},
        )
        self.assertEqual(out, ["A", "A", "B"])

    @patch("viewer.glyph_sort.get_transliteration_meta")
    def test_transliteration_sort(self, mock_meta):
        def meta(addr):
            return {
                "x": {"transliteration": "10"},
                "y": {"transliteration": "2"},
            }[addr]

        mock_meta.side_effect = meta
        out = sort_glyph_addresses(["x", "y"], CRITERION_TRANSLITERATION, corpus_index={})
        self.assertEqual(out, ["y", "x"])

    def test_connections_chain(self):
        # A — B — C
        addrs = ["A", "B", "C"]
        links = {"A": ["B"], "B": ["A", "C"], "C": ["B"]}
        out = sort_glyph_addresses(addrs, CRITERION_CONNECTIONS, links=links)
        self.assertEqual(set(out), {"A", "B", "C"})
        self.assertEqual(len(out), 3)
        # All three in one component; BFS from lowest index (0 = A) visits A then ordered neighbors by degree
        self.assertEqual(out[0], "A")


if __name__ == "__main__":
    unittest.main()
