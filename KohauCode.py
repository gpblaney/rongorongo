import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Transliteration search (pure; shared by web app and optional Tk UI)
# ---------------------------------------------------------------------------


def token_match(query_token: str, token: str, include_letters: bool = False) -> bool:
    """
    Returns True if query_token matches the transliteration token.

    If include_letters is True, allow matches like '600' -> '600a' (but not '6' -> '600').
    Still allows exact matches like '600' == '600'.
    """
    if token and token[0].isdigit():
        m = re.match(r"(\d+)", token)
        if m:
            num_part = m.group(1)
            if query_token.isdigit():
                if include_letters:
                    return token == query_token or (
                        token.startswith(query_token) and token[len(query_token) :].isalpha()
                    )
                return query_token == num_part
            return query_token == token
        return query_token == token
    return query_token == token


def match_transliteration(query: str, transliteration: str, include_letters: bool = False) -> bool:
    """
    Returns True if the query matches a contiguous subsequence of tokens
    in the transliteration.
    """
    query_tokens = query.split(".")
    translit_tokens = transliteration.split(".")

    for start in range(len(translit_tokens) - len(query_tokens) + 1):
        if all(
            token_match(query_tokens[i], translit_tokens[start + i], include_letters)
            for i in range(len(query_tokens))
        ):
            return True
    return False


def transliteration_search(
    corpus_transliterations: Dict[str, Dict[str, Any]],
    query: str,
    *,
    exact_match: bool = False,
    include_letters: bool = True,
    search_labels: bool = True,
) -> Dict[str, Any]:
    """
    Search corpus JSON (address -> metadata) by transliteration tokens and optionally labels.

    Returns:
      rows: list of { "transliteration": str, "addresses": [str, ...] }
      flat_addresses: all addresses in row order (for bulk add)
      total_groups: len(rows)
    """
    query = (query or "").strip()
    if not query:
        return {"rows": [], "flat_addresses": [], "total_groups": 0}

    distinct: Set[str] = set()
    translit_freq: Dict[str, int] = {}
    for data in corpus_transliterations.values():
        if not isinstance(data, dict):
            continue
        translit = (data.get("transliteration") or "").strip()
        if translit:
            distinct.add(translit)
            translit_freq[translit] = translit_freq.get(translit, 0) + 1
    distinct_transliterations = list(distinct)

    matches_dict: Dict[str, Tuple[int, int, int, int]] = {}

    for transliteration in distinct_transliterations:
        transliteration = transliteration.strip()
        if not transliteration:
            continue

        if exact_match:
            if query == transliteration:
                freq = translit_freq.get(transliteration, 0)
                sort_key = (-freq, len(transliteration), -1, 0)
            else:
                continue
        else:
            if not match_transliteration(query, transliteration, include_letters=include_letters):
                continue
            starts_with = transliteration.startswith(query)
            index_of_query = transliteration.find(query)
            freq = translit_freq.get(transliteration, 0)
            sort_key = (-freq, len(transliteration), -int(starts_with), index_of_query)

        if transliteration not in matches_dict or sort_key < matches_dict[transliteration]:
            matches_dict[transliteration] = sort_key

    label_matched_addresses: Set[str] = set()

    if search_labels:
        q_lower = query.lower()

        for address, data in corpus_transliterations.items():
            if not isinstance(data, dict):
                continue
            translit = (data.get("transliteration") or "").strip()
            if not translit:
                continue

            labels_str = (data.get("labels_str") or "").strip()
            if not labels_str:
                labels = data.get("labels", [])
                if isinstance(labels, list):
                    labels_str = ".".join(str(x) for x in labels).strip()

            if not labels_str:
                continue

            ls = labels_str.lower()

            if exact_match:
                if q_lower != ls:
                    continue
                starts_with = False
                index_of_query = -1
            else:
                if q_lower not in ls:
                    continue
                starts_with = ls.startswith(q_lower)
                index_of_query = ls.find(q_lower)

            label_matched_addresses.add(address)

            freq = translit_freq.get(translit, 0)
            sort_key = (-freq, len(translit), -int(starts_with), index_of_query)
            if translit not in matches_dict or sort_key < matches_dict[translit]:
                matches_dict[translit] = sort_key

    matches: List[Tuple[int, int, int, int, str]] = [
        sort_key + (translit,) for translit, sort_key in matches_dict.items()
    ]
    matches.sort()

    def addresses_for_transliteration(transliteration: str) -> List[str]:
        out: List[str] = []
        for address, data in corpus_transliterations.items():
            if not isinstance(data, dict):
                continue
            if (data.get("transliteration") or "").strip() == transliteration:
                out.append(address)
        return out

    rows: List[Dict[str, Any]] = []
    flat_addresses: List[str] = []

    for *_, transliteration in matches:
        addresses = addresses_for_transliteration(transliteration)

        if search_labels:
            addresses = [a for a in addresses if a in label_matched_addresses]

        if not addresses:
            continue

        rows.append({"transliteration": transliteration, "addresses": addresses})
        flat_addresses.extend(addresses)

    return {
        "rows": rows,
        "flat_addresses": flat_addresses,
        "total_groups": len(rows),
    }


# Tablet X (Tangata Manu): X + face a–h + line + glyph (face code is not limited to arbv).
_RE_ADDRESS_X = re.compile(r"^X([a-hA-H])(\d+)-(\d+)$")
# Standard: tablet letter + side (a,r,b,v) + line + glyph index.
_RE_ADDRESS_STANDARD = re.compile(r"^([A-Za-z])([arbv])(\d+)-(\d+)$")


def _sort_sides_for_tablet(letter: str, sides: Set[str]) -> List[str]:
    """Stable UI order: r, v, a, b for normal tablets; a–h for X."""
    letter_u = letter.upper()
    sset = {s.lower() for s in sides}
    if letter_u == "X":
        return [x for x in "abcdefgh" if x in sset]
    preferred = ["r", "v", "a", "b"]
    ordered = [p for p in preferred if p in sset]
    rest = sorted(sset - set(ordered))
    return ordered + rest


def infer_tablet_layout_from_addresses(addresses: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """
    Infer sides and max line numbers from glyph addresses (e.g. corpus JSON keys).

    - Most tablets: ``{Letter}{side}{line}-{glyph}`` with side in a, r, b, v.
    - Tablet X: ``X{face}{line}-{glyph}`` with face in a–h (inscription faces).

    Returns:
        ``{ "A": {"sides": ["r","v"], "linesBySide": {"r": 8, "v": 8}}, ... }``
    """
    std_lines: Dict[str, Dict[str, Set[int]]] = defaultdict(lambda: defaultdict(set))
    x_lines: Dict[str, Set[int]] = defaultdict(set)

    for raw in addresses:
        addr = str(raw).strip()
        if not addr:
            continue
        if addr[0].upper() == "X":
            mx = _RE_ADDRESS_X.match(addr)
            if mx:
                face, line_str, _g = mx.groups()
                x_lines[face.lower()].add(int(line_str))
            continue

        ms = _RE_ADDRESS_STANDARD.match(addr)
        if not ms:
            continue
        letter, side, line_str, _g = ms.groups()
        letter_u = letter.upper()
        side_l = side.lower()
        std_lines[letter_u][side_l].add(int(line_str))

    out: Dict[str, Dict[str, Any]] = {}
    for letter, side_map in std_lines.items():
        sides_list = _sort_sides_for_tablet(letter, set(side_map.keys()))
        lines_by_side = {s: max(side_map[s]) for s in sides_list}
        out[letter] = {"sides": sides_list, "linesBySide": lines_by_side}

    if x_lines:
        faces = _sort_sides_for_tablet("X", set(x_lines.keys()))
        out["X"] = {
            "sides": faces,
            "linesBySide": {f: max(x_lines[f]) for f in faces},
        }

    return out


def parse_address_components(address: str) -> Optional[Dict[str, Any]]:
    """
    Parse a glyph address key into components used for stepping.

    Standard tablets:
      {Letter}{side}{line}-{glyphIndex} where side in a,r,b,v

    Tangata Manu (X):
      X{face}{line}-{glyphIndex} where face in a-h
    """
    if not address:
        return None
    addr = str(address).strip()
    if not addr:
        return None

    mx = _RE_ADDRESS_X.match(addr)
    if mx:
        face, line_str, glyph_str = mx.groups()
        return {
            "letter": "X",
            "side": face.lower(),
            "line": int(line_str),
            "glyph_index": int(glyph_str),
        }

    ms = _RE_ADDRESS_STANDARD.match(addr)
    if not ms:
        return None
    letter, side, line_str, glyph_str = ms.groups()
    return {
        "letter": str(letter).upper(),
        "side": str(side).lower(),
        "line": int(line_str),
        "glyph_index": int(glyph_str),
    }


def adjacent_address_in_same_tablet_line(
    corpus_transliterations: Dict[str, Dict[str, Any]],
    address: str,
    direction: int,
) -> Optional[str]:
    """
    Return the adjacent glyph address on the *same* tablet+side+line.

    - direction = +1 => next (to the right)
    - direction = -1 => previous (to the left)
    """
    if direction not in (-1, 1):
        return None
    parts = parse_address_components(address)
    if not parts:
        return None

    letter = parts["letter"]
    side = parts["side"]
    line = parts["line"]

    if letter == "X":
        prefix = f"X{side}{line}-"
    else:
        prefix = f"{letter}{side}{line}-"

    try:
        from natsort import natsorted as _natsorted
    except Exception:
        _natsorted = sorted  # type: ignore[assignment]

    keys = [a for a in corpus_transliterations.keys() if isinstance(a, str) and a.startswith(prefix)]
    if not keys:
        return None
    keys = list(_natsorted(keys))

    try:
        idx = keys.index(address)
    except ValueError:
        return None

    nxt = idx + direction
    if nxt < 0 or nxt >= len(keys):
        return None
    return keys[nxt]


def adjacent_address_in_same_tablet(
    corpus_transliterations: Dict[str, Dict[str, Any]],
    address: str,
    direction: int,
) -> Optional[str]:
    """
    Return the adjacent glyph address within the same tablet letter.

    Unlike adjacent_address_in_same_tablet_line(), this can cross side/line
    boundaries. It halts only when stepping would leave the tablet.
    """
    if direction not in (-1, 1):
        return None
    parts = parse_address_components(address)
    if not parts:
        return None

    letter = parts["letter"]

    # Build an ordered sequence of all parseable addresses on this tablet.
    parsed_rows: List[Tuple[Dict[str, Any], str]] = []
    sides_seen: Set[str] = set()
    for raw in corpus_transliterations.keys():
        if not isinstance(raw, str):
            continue
        p = parse_address_components(raw)
        if not p or p["letter"] != letter:
            continue
        sides_seen.add(str(p["side"]))
        parsed_rows.append((p, raw))

    side_order = _sort_sides_for_tablet(letter, sides_seen)
    side_rank = {s: i for i, s in enumerate(side_order)}

    keys: List[Tuple[Tuple[int, int, int], str]] = []
    for p, raw in parsed_rows:
        # Unknown side values sort after known sides but still remain step-able.
        s_rank = side_rank.get(p["side"], 99)
        keys.append(((s_rank, int(p["line"]), int(p["glyph_index"])), raw))

    if not keys:
        return None
    keys.sort(key=lambda item: item[0])
    ordered = [k for _sort_key, k in keys]

    try:
        idx = ordered.index(address)
    except ValueError:
        return None

    nxt = idx + direction
    if nxt < 0 or nxt >= len(ordered):
        return None
    return ordered[nxt]


# ---------------------------------------------------------------------------
# Runtime paths and corpus (heavy init deferred — call init_kohau_runtime())
# ---------------------------------------------------------------------------

from PIL import Image
from natsort import natsorted

HERE = Path(__file__).resolve().parent
root = str(HERE / r"data\RRC-64%")

corpus_transliterations: Dict[str, Dict[str, Any]] = {}


def load_corpus_transliterations(filename=r"data\corpus_transliterations.json"):
    global corpus_transliterations

    if os.path.exists(filename):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = fr"data\transliterations_backup_{timestamp}.json"
        shutil.copy(filename, backup_filename)
        print(f"📝 Backup created: {backup_filename}")

        try:
            with open(filename, "r", encoding="utf-8") as f:
                corpus_transliterations = json.load(f)
            print(f"✅ Loaded {len(corpus_transliterations)} transliterations from {filename}")
        except Exception as e:
            print(f"❌ Error loading corpus_transliterations: {e}")
    else:
        corpus_transliterations = {}
        print("⚠️ transliterations.json not found. Starting with an empty dictionary.")


def save_transcriptions():
    try:
        with open(r"data\corpus_transliterations.json", "w", encoding="utf-8") as f:
            json.dump(corpus_transliterations, f, indent=2)
        print("Transcriptions saved instantly to transcriptions.json.")
    except Exception as e:
        print(f"Error saving transcriptions: {e}")


def init_kohau_runtime(load_transliterations: bool = True, load_corpus: bool = True) -> None:
    """
    Load transliterations JSON and/or scan the corpus filesystem.
    Call once from scripts; the Django app does not need this for search.
    """
    global corpus, allGlyphs
    if load_transliterations:
        load_corpus_transliterations()
    if load_corpus:
        c = Corpus()
        c.load()
        corpus = c
        allGlyphs.clear()
        for tablet in corpus.tablets:
            allGlyphs.extend(tablet.glyphs)


class Glyph:
    def __init__(self, address):
        """
        Parameters:
            address (str): The glyph address (e.g., "Gr1-002")
            tablet (str): The name of the tablet (i.e., folder name)
            filepath (str): Full path to the image file
        """
        self.address = address
        match = re.search(r"[arbv]", address)
        substring = address[: match.start()] if match else address
        self.filepath = os.path.join(root, substring, f"{address}.png")
        self._image = None
        self.text = ""
        self.tablet = address[0]
        self.subGlyphs = []

    def load_image(self):
        """Load and return the glyph image using PIL."""
        if self._image is None:
            try:
                self._image = Image.open(self.filepath)
            except Exception as e:
                print(f"Error loading image for {self.address} from {self.filepath}: {e}")
        return self._image

    def show(self):
        """Display the glyph image."""
        img = self.load_image()
        if img:
            img.show()

    def __repr__(self):
        return f"Glyph(address='{self.address}', tablet='{self.tablet}')"


class Tablet:
    def __init__(self, folder, root):
        """
        Parameters:
            folder (str): The folder name representing the tablet.
            root (str): The path to the root directory containing all tablet folders.
        """
        self.name = folder
        self.root = root
        self.glyphs = []

    def load(self):
        """Load all PNG glyph files from the tablet folder."""
        folder_path = os.path.join(self.root, self.name)
        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist.")
            return

        for filename in natsorted(os.listdir(folder_path)):
            if filename.lower().endswith(".png"):
                address = os.path.splitext(filename)[0]
                glyph = Glyph(address)
                self.glyphs.append(glyph)

    def __repr__(self):
        return f"Tablet(name='{self.name}', glyph_count={len(self.glyphs)})"


class Corpus:
    def __init__(self):
        self.root = root
        self.tablets = []
        self.glyph_index = {}

    def load(self):
        """Traverse the root directory, load each tablet folder, and index glyphs by address."""
        for folder in os.listdir(self.root):
            folder_path = os.path.join(self.root, folder)
            if os.path.isdir(folder_path):
                tablet = Tablet(folder, self.root)
                tablet.load()
                self.tablets.append(tablet)
                for glyph in tablet.glyphs:
                    self.glyph_index[glyph.address] = glyph

    def get_glyph(self, address):
        """Return the Glyph object with the given address, or None if not found."""
        return self.glyph_index.get(address)

    def get_tablet(self, tablet_name):
        """Return the Tablet object with the given name, or None if not found."""
        for tablet in self.tablets:
            if tablet.name == tablet_name:
                return tablet
        return None

    def __repr__(self):
        return f"Corpus(tablet_count={len(self.tablets)})"


corpus: Optional[Corpus] = None
allGlyphs: List[Any] = []


if __name__ == "__main__":
    print(root)
    init_kohau_runtime()
