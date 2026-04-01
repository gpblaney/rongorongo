"""
Sort glyph addresses for board reflow (Tkinter GlyphEditorWindow parity).

Criteria match the old app's ``sort_glyphs_by_criterion`` except Visual Embedding,
which is not implemented here.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Tuple

from viewer.corpus.kohau_code import get_transliteration_meta, load_corpus_transliterations

CRITERION_ORDER = "Order"
CRITERION_TRANSLITERATION = "Transliteration"
CRITERION_REVERSE_TRANSLITERATION = "Reverse Transliteration"
CRITERION_TOKEN_COUNT = "Token Count"
CRITERION_CONFIDENCE = "Confidence"
CRITERION_CONNECTIONS = "Connections"

KNOWN_CRITERIA = frozenset(
    {
        CRITERION_ORDER,
        CRITERION_TRANSLITERATION,
        CRITERION_REVERSE_TRANSLITERATION,
        CRITERION_TOKEN_COUNT,
        CRITERION_CONFIDENCE,
        CRITERION_CONNECTIONS,
    }
)


def _natsorted_keys(keys: Sequence[str]) -> List[str]:
    try:
        from natsort import natsorted

        return list(natsorted(keys))
    except ImportError:
        return sorted(keys)


def corpus_address_order_index() -> Dict[str, int]:
    """Natsorted corpus keys -> 0..n-1; used for Order criterion."""
    corpus = load_corpus_transliterations()
    ordered = _natsorted_keys([k for k in corpus.keys() if isinstance(k, str)])
    return {addr: i for i, addr in enumerate(ordered)}


def _typed_segment(part: str) -> Tuple[int, Any]:
    """
    One segment of a transliteration sort key: comparable in Python 3.

    Digit runs use (0, int); other text uses (1, str). Comparing (0, n) with
    (1, s) is always defined (0 < 1), unlike raw int vs str in the same tuple
    position (which raises TypeError).
    """
    if part.isdigit():
        return (0, int(part))
    return (1, part)


def transliteration_sort_key(translit: str) -> Tuple[Tuple[int, Any], ...]:
    """
    Natural-ish order over the full transliteration string (Tk ``re.split(r'(\\d+)', ...)``).

    Same alternating digit / non-digit structure as the old app, but each piece
    is tagged so keys never mix bare int and str in one comparison step.
    """
    if not translit:
        return ()
    parts = re.split(r"(\d+)", translit)
    out: List[Tuple[int, Any]] = []
    for part in parts:
        if part == "":
            continue
        out.append(_typed_segment(part))
    return tuple(out)


def reverse_token_sort_key(translit: str) -> Tuple[Tuple[int, Any], ...]:
    """Dot-separated tokens, right-to-left, with typed segments (Tk parity, Py3-safe)."""
    if not translit:
        return ()
    tokens = translit.split(".")
    out: List[Tuple[int, Any]] = []
    for t in reversed(tokens):
        out.append(_typed_segment(t))
    return tuple(out)


def num_tokens_sort_key(translit: str) -> int:
    if not translit.strip():
        return 0
    return len(translit.split("."))


def _find(parent: Dict[int, int], x: int) -> int:
    if parent[x] != x:
        parent[x] = _find(parent, parent[x])
    return parent[x]


def _union(parent: Dict[int, int], rank: Dict[int, int], x: int, y: int) -> None:
    root_x = _find(parent, x)
    root_y = _find(parent, y)
    if root_x == root_y:
        return
    if rank[root_x] < rank[root_y]:
        parent[root_x] = root_y
    elif rank[root_x] > rank[root_y]:
        parent[root_y] = root_x
    else:
        parent[root_y] = root_x
        rank[root_x] += 1


def _cuthill_mckee_order(graph: Dict[int, List[int]], indices: List[int]) -> List[int]:
    """BFS-like order; neighbors visited in increasing degree (within ``indices`` subgraph)."""
    n = len(indices)
    if n == 0:
        return []
    local_index = {idx: i for i, idx in enumerate(indices)}
    subgraph = {i: [] for i in range(n)}
    for i, gi in enumerate(indices):
        for neighbor in graph.get(gi, []):
            if neighbor in local_index:
                j = local_index[neighbor]
                if j not in subgraph[i]:
                    subgraph[i].append(j)
                if i not in subgraph[j]:
                    subgraph[j].append(i)

    visited = [False] * n
    order: List[int] = []

    def bfs(start: int) -> List[int]:
        q: deque[int] = deque([start])
        visited[start] = True
        comp: List[int] = []
        while q:
            current = q.popleft()
            comp.append(current)
            for neighbor in sorted(subgraph[current], key=lambda x: len(subgraph[x])):
                if not visited[neighbor]:
                    visited[neighbor] = True
                    q.append(neighbor)
        return comp

    for i in range(n):
        if not visited[i]:
            mapped = bfs(i)
            order.extend(indices[j] for j in mapped)
    return order


def _group_and_sort_by_connections(graph: Dict[int, List[int]], n: int) -> List[int]:
    """Union–find on 0..n-1; multi-vertex components first (by size), CM order inside."""
    if n == 0:
        return []
    parent = {i: i for i in range(n)}
    rank = {i: 0 for i in range(n)}
    for i in range(n):
        for j in graph.get(i, []):
            if 0 <= j < n:
                _union(parent, rank, i, j)

    groups_dict: Dict[int, List[int]] = {}
    for i in range(n):
        root = _find(parent, i)
        groups_dict.setdefault(root, []).append(i)
    groups = list(groups_dict.values())

    groups_mult = [g for g in groups if len(g) > 1]
    groups_single = [g for g in groups if len(g) == 1]

    groups_mult.sort(key=lambda g: (-len(g), min(g)))

    sorted_groups: List[List[int]] = []
    for group in groups_mult:
        sorted_groups.append(_cuthill_mckee_order(graph, group))
    groups_single.sort(key=lambda g: g[0])
    sorted_groups.extend(groups_single)

    return [idx for group in sorted_groups for idx in group]


def _build_graph_from_links(addresses: Sequence[str], links: Optional[Dict[str, Sequence[str]]]) -> Dict[int, List[int]]:
    n = len(addresses)
    graph: Dict[int, List[int]] = {i: [] for i in range(n)}
    if not links:
        return graph

    addr_to_indices: Dict[str, List[int]] = {}
    for i, a in enumerate(addresses):
        addr_to_indices.setdefault(a, []).append(i)

    seen_edges = set()
    for i, a in enumerate(addresses):
        for nbr in links.get(a, ()) or ():
            if not isinstance(nbr, str):
                continue
            for j in addr_to_indices.get(nbr, []):
                if i == j:
                    continue
                pair = (i, j) if i < j else (j, i)
                if pair in seen_edges:
                    continue
                seen_edges.add(pair)
                graph[i].append(j)
                graph[j].append(i)
    return graph


def sort_glyph_addresses(
    addresses: Sequence[str],
    criterion: str,
    *,
    links: Optional[Dict[str, Sequence[str]]] = None,
    corpus_index: Optional[Dict[str, int]] = None,
) -> List[str]:
    """
    Return a new list of addresses sorted by ``criterion``.

    Sort is stable for duplicate addresses: ties keep the relative order from
    ``addresses``. ``links`` is only used for Connections (edges between
    addresses in the selection).
    """
    if criterion not in KNOWN_CRITERIA:
        raise ValueError(f"Unknown criterion {criterion!r}; expected one of {sorted(KNOWN_CRITERIA)}")

    addrs = list(addresses)
    if len(addrs) <= 1:
        return addrs

    if criterion == CRITERION_CONNECTIONS:
        ordered_idx = _group_and_sort_by_connections(_build_graph_from_links(addrs, links), len(addrs))
        # Connections reorder is global; stabilize duplicates by input index order within same key?
        # Tk replaces full list order — apply permutation.
        return [addrs[i] for i in ordered_idx]

    if corpus_index is None:
        corpus_index = corpus_address_order_index()

    def order_key(addr: str) -> Tuple:
        return (corpus_index.get(addr, 999_999),)

    def translit_key(addr: str) -> Tuple:
        meta = get_transliteration_meta(addr)
        t = meta.get("transliteration", "") or ""
        return (transliteration_sort_key(t),)

    def reverse_key(addr: str) -> Tuple:
        meta = get_transliteration_meta(addr)
        t = meta.get("transliteration", "") or ""
        return (reverse_token_sort_key(t),)

    def token_count_key(addr: str) -> Tuple:
        meta = get_transliteration_meta(addr)
        t = meta.get("transliteration", "") or ""
        return (num_tokens_sort_key(t),)

    def confidence_key(addr: str) -> Tuple:
        meta = get_transliteration_meta(addr)
        c = meta.get("confidence", None)
        if c is None:
            return (0,)  # Tk get_confidence returned 0 when missing
        try:
            return (int(c),)
        except (TypeError, ValueError):
            return (0,)

    key_funcs = {
        CRITERION_ORDER: order_key,
        CRITERION_TRANSLITERATION: translit_key,
        CRITERION_REVERSE_TRANSLITERATION: reverse_key,
        CRITERION_TOKEN_COUNT: token_count_key,
        CRITERION_CONFIDENCE: confidence_key,
    }

    key_fn = key_funcs[criterion]
    decorated = [(key_fn(a), i, a) for i, a in enumerate(addrs)]
    decorated.sort(key=lambda t: (t[0], t[1]))
    return [a for _k, _i, a in decorated]
