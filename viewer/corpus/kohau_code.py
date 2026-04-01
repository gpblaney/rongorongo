import json
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import AbstractSet, Any, Dict, List, Optional, Tuple

# This module is a Django-safe wrapper around your original KohauCode.py.
# Key goals:
# - No heavy work at import time (KohauCode defers corpus filesystem scan).
# - Deterministic, repository-relative paths (so it works under runserver).
# - Lazy, cached access to transliterations and (optionally) corpus files.

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]  # glyphboard_test/

_repo_root_str = str(REPO_ROOT)
if _repo_root_str not in sys.path:
    sys.path.insert(0, _repo_root_str)

from KohauCode import (
    adjacent_address_in_same_tablet,
    infer_tablet_layout_from_addresses,
    transliteration_search,
)  # noqa: E402

DEFAULT_CORPUS_DATA_ROOT = REPO_ROOT / "data" / "RRC-64%"
DEFAULT_TRANSLITERATIONS_PATH = REPO_ROOT / "data" / "corpus_transliterations.json"


def _get_corpus_data_root() -> Path:
    """
    Returns the root folder that contains tablet subfolders for the corpus.

    You can override with env var:
      GLYPHBOARD_CORPUS_DATA_ROOT=/full/path/to/data/RRC-64%
    """

    override = os.environ.get("GLYPHBOARD_CORPUS_DATA_ROOT")
    if override:
        return Path(override)
    return DEFAULT_CORPUS_DATA_ROOT


@lru_cache(maxsize=1)
def load_corpus_transliterations() -> Dict[str, Dict[str, Any]]:
    """
    Loads viewer/static/corpus_transliterations.json.
    Cached for the lifetime of the process.
    """

    path = DEFAULT_TRANSLITERATIONS_PATH
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_corpus_transliterations(transliterations: Dict[str, Dict[str, Any]]) -> None:
    """
    Saves transliterations to DEFAULT_TRANSLITERATIONS_PATH.
    Creates a timestamped backup next to it (mirrors the behavior in KohauCode.py).
    """

    path = DEFAULT_TRANSLITERATIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    import shutil
    from datetime import datetime

    if path.exists():
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = path.parent / f"transliterations_backup_{timestamp}.json"
        shutil.copy(str(path), str(backup_filename))

    with open(path, "w", encoding="utf-8") as f:
        json.dump(transliterations, f, indent=2)


def update_transliteration_meta(
    address: str,
    transliteration: str,
    labels_str: Optional[str] = None,
    comments_str: Optional[str] = None,
    confidence: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Updates transliteration/confidence/labels/comments for a single address and persists to disk.

    - If confidence is 0..4, it is stored as-is.
    - If confidence is None, confidence key is removed (optional behavior).
    """

    translits = load_corpus_transliterations()
    if address not in translits or not isinstance(translits.get(address), dict):
        translits[address] = {}

    entry = translits[address]
    entry["transliteration"] = str(transliteration)

    if labels_str is None:
        entry.pop("labels_str", None)
    else:
        entry["labels_str"] = str(labels_str)

    if comments_str is None:
        entry.pop("comments_str", None)
    else:
        entry["comments_str"] = str(comments_str)

    if confidence is None:
        entry.pop("confidence", None)
    else:
        # UI uses 0..4. Clamp so legacy value 5 becomes 4.
        entry["confidence"] = max(0, min(4, int(confidence)))

    save_corpus_transliterations(translits)
    load_corpus_transliterations.cache_clear()
    return entry


def split_transliteration_signs(transliteration: Any) -> List[str]:
    """
    Split transliteration into signs using '.' separator.
    Empty chunks are ignored and signs are trimmed.
    """

    if transliteration is None:
        return []
    text = str(transliteration).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(".") if part.strip()]


def transliteration_sign_occurrences() -> Dict[str, int]:
    """
    Returns sign -> occurrence count across corpus transliterations.
    """

    out: Dict[str, int] = {}
    corpus = load_corpus_transliterations()
    for row in corpus.values():
        if not isinstance(row, dict):
            continue
        signs = split_transliteration_signs(row.get("transliteration", ""))
        for sign in signs:
            out[sign] = out.get(sign, 0) + 1
    return out


def single_sign_glyph_addresses(sign: str, *, limit: int = 100) -> List[str]:
    """
    Addresses whose transliteration is exactly one sign, matching ``sign`` (trimmed, exact).
    Sorted lexicographically by address; at most ``limit`` entries.
    """

    want = str(sign).strip()
    if not want:
        return []

    limit_int = max(1, min(200, int(limit)))

    corpus = load_corpus_transliterations()
    matches: List[str] = []
    for address, row in corpus.items():
        if not isinstance(row, dict):
            continue
        signs = split_transliteration_signs(row.get("transliteration", ""))
        if len(signs) == 1 and signs[0] == want:
            matches.append(str(address))

    matches.sort()
    return matches[:limit_int]


def compound_glyph_addresses_containing_sign(
    sign: str,
    *,
    limit: int,
    exclude: Optional[AbstractSet[str]] = None,
) -> List[str]:
    """
    Addresses whose transliteration has more than one sign and includes ``sign``
    as one token (exact match after trim). Sorted by address; at most ``limit``.
    """

    want = str(sign).strip()
    if not want:
        return []

    limit_int = max(0, min(200, int(limit)))
    if limit_int == 0:
        return []

    skip = exclude if exclude is not None else set()
    corpus = load_corpus_transliterations()
    matches: List[str] = []
    for address, row in corpus.items():
        addr_s = str(address)
        if addr_s in skip:
            continue
        if not isinstance(row, dict):
            continue
        signs = split_transliteration_signs(row.get("transliteration", ""))
        if len(signs) > 1 and want in signs:
            matches.append(addr_s)

    matches.sort()
    return matches[:limit_int]


def replace_transliteration_sign(old_sign: str, new_sign: str) -> Dict[str, Any]:
    """
    Replace one sign with another in corpus transliterations and persist.
    Matching is exact sign equality after trim, using '.' tokenization.
    """

    old_s = str(old_sign).strip()
    new_s = str(new_sign).strip()
    if not old_s:
        raise ValueError("old_sign is required")
    if not new_s:
        raise ValueError("new_sign is required")

    translits = load_corpus_transliterations()
    changed_addresses: List[str] = []
    replaced_occurrences = 0

    for address, row in translits.items():
        if not isinstance(row, dict):
            continue
        signs = split_transliteration_signs(row.get("transliteration", ""))
        if not signs:
            continue
        changed = False
        for i, sign in enumerate(signs):
            if sign == old_s:
                signs[i] = new_s
                replaced_occurrences += 1
                changed = True
        if changed:
            row["transliteration"] = ".".join(signs)
            changed_addresses.append(address)

    if changed_addresses:
        save_corpus_transliterations(translits)
        load_corpus_transliterations.cache_clear()

    return {
        "old_sign": old_s,
        "new_sign": new_s,
        "changed_addresses": changed_addresses,
        "changed_address_count": len(changed_addresses),
        "replaced_occurrences": replaced_occurrences,
    }


def run_transliteration_search(
    query: str,
    *,
    exact_match: bool = False,
    include_letters: bool = True,
    search_labels: bool = True,
) -> Dict[str, Any]:
    """Runs KohauCode.transliteration_search on the cached corpus JSON."""

    corpus = load_corpus_transliterations()
    return transliteration_search(
        corpus,
        query,
        exact_match=exact_match,
        include_letters=include_letters,
        search_labels=search_labels,
    )


def get_tablet_layout_from_corpus() -> Dict[str, Dict[str, Any]]:
    """
    Sides and line counts inferred from corpus address keys (see KohauCode.infer_tablet_layout_from_addresses).
    """

    corpus = load_corpus_transliterations()
    return infer_tablet_layout_from_addresses(corpus.keys())


def step_adjacent_glyph_address(address: str, *, direction: int) -> Optional[str]:
    """
    Uses KohauCode's address stepping rules to get the adjacent glyph address
    within the same tablet.
    """
    corpus = load_corpus_transliterations()
    return adjacent_address_in_same_tablet(corpus, address, direction)


def address_prefix_for_tablet_line(letter: str, side: str, line: int) -> str:
    """
    Address keys for a tablet line: ``{L}{side}{line}-*`` or ``X{face}{line}-*`` for tablet X.
    """

    L = letter.strip().upper()
    s = side.strip().lower()
    n = int(line)
    if L == "X":
        return f"X{s}{n}-"
    return f"{L}{s}{n}-"


def tablet_line_selection_sort_key(letter: str, side: str, line: int) -> Tuple[Any, ...]:
    """Stable ordering for loading multiple lines (letter, side order, line number)."""

    L = letter.upper()
    s = side.lower()
    if L == "X":
        face_order = {c: i for i, c in enumerate("abcdefgh")}
        return (L, face_order.get(s, 99), int(line))
    pref = {"r": 0, "v": 1, "a": 2, "b": 3}
    return (L, pref.get(s, 50), int(line))


def list_addresses_for_tablet_line(letter: str, side: str, line: int) -> List[str]:
    """All corpus addresses on one tablet line, natural-sorted by glyph index."""

    try:
        from natsort import natsorted
    except ImportError:
        natsorted = sorted  # type: ignore[assignment]

    corpus = load_corpus_transliterations()
    prefix = address_prefix_for_tablet_line(letter, side, line)
    matches = [a for a in corpus if isinstance(a, str) and a.startswith(prefix)]
    return list(natsorted(matches))


@dataclass(frozen=True)
class GlyphFile:
    """
    Lightweight representation of a glyph image on disk (address->filepath).
    """

    address: str
    tablet: str
    filepath: Path


def parse_address_from_filename(filename: str) -> str:
    """
    Converts a static image filename like "Ba1-001.png" -> "Ba1-001".
    """

    return Path(filename).stem


def guess_tablet_from_address(address: str) -> str:
    # Your original script uses address[0]
    return address[0] if address else ""


def glyph_filepath_for_address(address: str, data_root: Optional[Path] = None) -> Optional[Path]:
    """
    Builds the filepath for the glyph under the corpus data root.
    Mirrors your original path logic:
      root/subfolder_prefix/{address}.png
    where subfolder_prefix is derived from the address up to the first [arbv] occurrence.
    """

    data_root = data_root or _get_corpus_data_root()
    if not data_root.exists():
        return None

    # Your original KohauCode.py uses: re.search(r'[arbv]', address)
    # It’s case-sensitive; addresses in your dataset appear to contain lowercase a/r/b/v later.
    match = re.search(r"[arbv]", address)
    prefix = address[: match.start()] if match else address
    return data_root / prefix / f"{address}.png"


def get_glyph_file(address: str) -> Optional[GlyphFile]:
    """
    Returns glyph file info if the corpus data root exists and the constructed file exists.
    """

    fp = glyph_filepath_for_address(address)
    if not fp or not fp.exists():
        return None
    return GlyphFile(
        address=address,
        tablet=guess_tablet_from_address(address),
        filepath=fp,
    )


def get_transliteration_meta(address: str) -> Dict[str, Any]:
    """
    Returns transliteration metadata for an address, or {} if unknown.
    """

    translits = load_corpus_transliterations()
    raw = translits.get(address, {}) or {}
    if not isinstance(raw, dict):
        return {}

    # Return a copy so we never mutate the cache in-place.
    out = dict(raw)
    conf = out.get("confidence", None)
    if conf is not None:
        try:
            out["confidence"] = max(0, min(4, int(conf)))
        except (TypeError, ValueError):
            out.pop("confidence", None)
    return out

