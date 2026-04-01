import json
import re
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

from django.http import (
    FileResponse,
    Http404,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from viewer.corpus.kohau_code import (
    get_glyph_file,
    get_tablet_layout_from_corpus,
    get_transliteration_meta,
    glyph_filepath_for_address,
    list_addresses_for_tablet_line,
    run_transliteration_search,
    replace_transliteration_sign,
    tablet_line_selection_sort_key,
    transliteration_sign_occurrences,
    compound_glyph_addresses_containing_sign,
    single_sign_glyph_addresses,
    step_adjacent_glyph_address,
    update_transliteration_meta,
)
from viewer.glyph_sort import KNOWN_CRITERIA, corpus_address_order_index, sort_glyph_addresses
from viewer.placer import (
    Rect,
    DEFAULT_HORIZONTAL_GAP,
    DEFAULT_MAX_RENDER_DIM,
    DEFAULT_VERTICAL_GAP,
    top_left_left_of,
    top_left_right_of,
    layout_horizontal_wrap,
    layout_rows_sequential,
    layout_vertical_stack,
    scaled_render_size,
)

# Corpus / static glyph addresses (no path separators or odd characters).
GLYPH_ADDRESS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DEBUG_LOG_PATH = Path(__file__).resolve().parents[1] / "debug-2cf695.log"


def _debug_log_step(hypothesis_id: str, location: str, message: str, data: Optional[dict] = None, run_id: str = "pre-fix") -> None:
    try:
        payload = {
            "sessionId": "2cf695",
            "id": f"log_{uuid4().hex}",
            "timestamp": int(__import__("time").time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "runId": run_id,
            "hypothesisId": hypothesis_id,
        }
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _glyph_address_ok(address: str) -> bool:
    return bool(address and GLYPH_ADDRESS_RE.fullmatch(address))


def _image_url_for_address(address: str, static_image_dir: Path) -> tuple[str, bool]:
    static_png = static_image_dir / f"{address}.png"
    if static_png.is_file():
        return f"/static/viewer/images/{address}.png", True
    if get_glyph_file(address):
        return f"/api/corpus-glyph/{address}", True
    return "", False


def _natural_image_size(address: str, static_image_dir: Path) -> Optional[Tuple[int, int]]:
    try:
        from PIL import Image
    except ImportError:
        return None
    candidates: List[Path] = []
    static_png = static_image_dir / f"{address}.png"
    if static_png.is_file():
        candidates.append(static_png)
    gf = get_glyph_file(address)
    if gf and gf.filepath.is_file():
        candidates.append(gf.filepath)
    for path in candidates:
        try:
            with Image.open(path) as im:
                return im.size
        except OSError:
            continue
    return None


def _glyph_payload_for_address(address: str, static_image_dir: Path) -> dict:
    meta = get_transliteration_meta(address)
    url, has_image = _image_url_for_address(address, static_image_dir)
    return {
        "address": address,
        "name": f"{address}.png",
        "transliteration": meta.get("transliteration"),
        "confidence": meta.get("confidence"),
        "labels_str": meta.get("labels_str"),
        "comments_str": meta.get("comments_str"),
        "alternates_str": meta.get("alternates_str"),
        "image_url": url,
        "has_image": has_image,
    }


def board_view(request):
    return render(
        request,
        'viewer/board.html',
        {
            'glyphs': [],
            'tablet_layout': get_tablet_layout_from_corpus(),
        },
    )


def sign_catalog_view(request):
    return render(request, 'viewer/sign_catalog.html', {})


@csrf_exempt
@require_POST
def glyph_meta_update(request):
    """
    Persists transliteration/confidence/labels/comments edits for one address.

    Expected JSON:
      {
        "address": "Ba3-012",
        "transliteration": "16",
        "labels_str": "x,y",
        "comments_str": "note",
        "confidence": 0..4
      }
    """

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    address = payload.get("address")
    transliteration = payload.get("transliteration", "")
    labels_str = payload.get("labels_str", "")
    comments_str = payload.get("comments_str", "")
    confidence = payload.get("confidence", None)

    if not address or not isinstance(address, str):
        return HttpResponseBadRequest("Missing/invalid 'address'")

    if confidence is None:
        conf_int = None
    else:
        try:
            conf_int = int(confidence)
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Invalid 'confidence'")
        conf_int = max(0, min(4, conf_int))

    updated_entry = update_transliteration_meta(
        address=address,
        transliteration=transliteration,
        labels_str=labels_str,
        comments_str=comments_str,
        confidence=conf_int,
    )

    return JsonResponse(
        {
            "ok": True,
            "address": address,
            "glyphMeta": {
                "transliteration": updated_entry.get("transliteration"),
                "confidence": updated_entry.get("confidence"),
                "labels_str": updated_entry.get("labels_str"),
                "comments_str": updated_entry.get("comments_str"),
                "alternates_str": updated_entry.get("alternates_str"),
            },
        }
    )


@csrf_exempt
@require_POST
def glyph_search_api(request):
    """
    Transliteration / label search using KohauCode.transliteration_search.

    JSON body:
      { "query": "1.2", "exact_match": false, "include_letters": true, "search_labels": true }
    """

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    query = payload.get("query", "")
    if not isinstance(query, str):
        return HttpResponseBadRequest("Invalid query")

    exact_match = bool(payload.get("exact_match", False))
    include_letters = bool(payload.get("include_letters", True))
    search_labels = bool(payload.get("search_labels", True))

    raw = run_transliteration_search(
        query,
        exact_match=exact_match,
        include_letters=include_letters,
        search_labels=search_labels,
    )

    static_image_dir = Path(__file__).resolve().parent / "static" / "viewer" / "images"

    rows_out = []
    for row in raw["rows"]:
        glyphs = []
        for address in row["addresses"]:
            if not _glyph_address_ok(address):
                continue
            glyphs.append(_glyph_payload_for_address(address, static_image_dir))
        rows_out.append(
            {
                "transliteration": row["transliteration"],
                "glyphs": glyphs,
            }
        )

    flat_out = []
    for address in raw["flat_addresses"]:
        if not _glyph_address_ok(address):
            continue
        flat_out.append(_glyph_payload_for_address(address, static_image_dir))

    return JsonResponse(
        {
            "ok": True,
            "total_groups": raw["total_groups"],
            "rows": rows_out,
            "flat_glyphs": flat_out,
        }
    )


@csrf_exempt
@require_POST
def transliteration_sign_stats_api(request):
    """
    Returns transliteration signs sorted by occurrence count (desc), then lexicographically.

    JSON body:
      { "query": "38", "limit": 200 }
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    query = payload.get("query", "")
    if query is None:
        query = ""
    if not isinstance(query, str):
        return HttpResponseBadRequest("Invalid 'query'")
    query = query.strip()

    limit = payload.get("limit", 200)
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Invalid 'limit'")
    limit_int = max(1, min(500, limit_int))

    counts = transliteration_sign_occurrences()
    rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if query:
        q = query.lower()
        rows = [row for row in rows if row[0].lower().startswith(q)]
    rows = rows[:limit_int]

    return JsonResponse(
        {
            "ok": True,
            "total_unique_signs": len(counts),
            "signs": [{"sign": sign, "count": count} for sign, count in rows],
        }
    )


@csrf_exempt
@require_POST
def transliteration_sign_replace_api(request):
    """
    Replaces one transliteration sign with another, where signs are split by '.'

    JSON body:
      { "old_sign": "381.1", "new_sign": "381" }
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    old_sign = payload.get("old_sign", "")
    new_sign = payload.get("new_sign", "")
    if not isinstance(old_sign, str) or not isinstance(new_sign, str):
        return HttpResponseBadRequest("Invalid 'old_sign'/'new_sign'")

    try:
        result = replace_transliteration_sign(old_sign, new_sign)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return JsonResponse({"ok": True, **result})


@csrf_exempt
@require_POST
def transliteration_sign_examples_api(request):
    """
    Example glyphs for a sign: single-sign transliterations first, then compound
    glyphs that contain the sign, until ``limit`` total.

    JSON body:
      { "sign": "381", "limit": 100 }
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    sign = payload.get("sign", "")
    if not isinstance(sign, str):
        return HttpResponseBadRequest("Invalid 'sign'")
    sign = sign.strip()
    if not sign:
        return HttpResponseBadRequest("'sign' is required")

    limit = payload.get("limit", 100)
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Invalid 'limit'")
    limit_int = max(1, min(100, limit_int))

    static_image_dir = Path(__file__).resolve().parent / "static" / "viewer" / "images"

    single_addrs = single_sign_glyph_addresses(sign, limit=limit_int)
    glyphs_single = []
    for addr in single_addrs:
        if not _glyph_address_ok(addr):
            continue
        row = _glyph_payload_for_address(addr, static_image_dir)
        row["example_kind"] = "single"
        glyphs_single.append(row)

    remaining = limit_int - len(glyphs_single)
    glyphs_compound = []
    if remaining > 0:
        compound_addrs = compound_glyph_addresses_containing_sign(
            sign,
            limit=remaining,
            exclude=set(single_addrs),
        )
        for addr in compound_addrs:
            if not _glyph_address_ok(addr):
                continue
            row = _glyph_payload_for_address(addr, static_image_dir)
            row["example_kind"] = "compound"
            glyphs_compound.append(row)

    all_glyphs = glyphs_single + glyphs_compound

    return JsonResponse(
        {
            "ok": True,
            "sign": sign,
            "glyphs_single": glyphs_single,
            "glyphs_compound": glyphs_compound,
            "glyphs": all_glyphs,
            "returned_single_count": len(glyphs_single),
            "returned_compound_count": len(glyphs_compound),
            "returned_count": len(all_glyphs),
        }
    )


@csrf_exempt
@require_POST
def glyphs_by_address_api(request):
    """
    Resolve metadata/image URLs for explicit glyph addresses.

    JSON body:
      { "addresses": ["Hr6-002", "Qr5-055", ...] }
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    raw = payload.get("addresses")
    if not isinstance(raw, list):
        return HttpResponseBadRequest("'addresses' must be a list")

    static_image_dir = Path(__file__).resolve().parent / "static" / "viewer" / "images"
    out = []
    seen = set()
    for item in raw:
        addr = str(item).strip()
        if not _glyph_address_ok(addr):
            continue
        if addr in seen:
            continue
        seen.add(addr)
        row = _glyph_payload_for_address(addr, static_image_dir)
        if not row.get("has_image"):
            continue
        out.append(row)

    return JsonResponse({"ok": True, "glyphs": out})


def corpus_glyph_png(request, address: str):
    if not _glyph_address_ok(address):
        return HttpResponseBadRequest("Invalid address")
    path = glyph_filepath_for_address(address)
    if not path or not path.is_file():
        raise Http404("Glyph image not found")
    return FileResponse(path.open("rb"), content_type="image/png")


@csrf_exempt
@require_POST
def tablet_load_api(request):
    """
    Resolve selected tablet lines to glyphs and compute (x, y) using viewer.placer.

    JSON body:
      { "selections": [ { "letter": "E", "side": "r", "line": 1 }, ... ] }

    Each selected line becomes one horizontal row (10px gap); rows are stacked with 40px gap.
    """

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    raw = payload.get("selections")
    if raw is None:
        return HttpResponseBadRequest("Missing 'selections'")
    if not isinstance(raw, list):
        return HttpResponseBadRequest("'selections' must be a list")

    static_image_dir = Path(__file__).resolve().parent / "static" / "viewer" / "images"

    seen = set()
    triples = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        letter = str(item.get("letter", "")).strip().upper()
        side = str(item.get("side", "")).strip().lower()
        try:
            line = int(item.get("line"))
        except (TypeError, ValueError):
            continue
        if len(letter) != 1 or letter < "A" or letter > "Z":
            continue
        if len(side) != 1:
            continue
        if line < 1:
            continue
        key = (letter, side, line)
        if key in seen:
            continue
        seen.add(key)
        triples.append(key)

    triples.sort(key=lambda t: tablet_line_selection_sort_key(t[0], t[1], t[2]))

    rows_dims = []
    rows_addrs: List[List[str]] = []
    for letter, side, line in triples:
        addrs = list_addresses_for_tablet_line(letter, side, line)
        row_dims = []
        row_addrs: List[str] = []
        for addr in addrs:
            if not _glyph_address_ok(addr):
                continue
            _url, has_image = _image_url_for_address(addr, static_image_dir)
            if not has_image:
                continue
            nat = _natural_image_size(addr, static_image_dir)
            if nat:
                rw, rh = scaled_render_size(nat[0], nat[1], DEFAULT_MAX_RENDER_DIM)
            else:
                rw = rh = float(DEFAULT_MAX_RENDER_DIM)
            row_dims.append((rw, rh))
            row_addrs.append(addr)
        if row_dims:
            rows_dims.append(row_dims)
            rows_addrs.append(row_addrs)

    positions = layout_rows_sequential(
        rows_dims,
        (0.0, 0.0),
        horizontal_gap=DEFAULT_HORIZONTAL_GAP,
        vertical_gap=DEFAULT_VERTICAL_GAP,
    )

    flat_addresses = [addr for row in rows_addrs for addr in row]

    glyphs_out = []
    for addr, (gx, gy) in zip(flat_addresses, positions):
        meta = get_transliteration_meta(addr)
        gf = get_glyph_file(addr)
        url, _hi = _image_url_for_address(addr, static_image_dir)
        glyphs_out.append(
            {
                "address": addr,
                "name": f"{addr}.png",
                "x": gx,
                "y": gy,
                "image_url": url,
                "transliteration": meta.get("transliteration"),
                "confidence": meta.get("confidence"),
                "labels_str": meta.get("labels_str"),
                "comments_str": meta.get("comments_str"),
                "alternates_str": meta.get("alternates_str"),
                "corpus_filepath": str(gf.filepath) if gf else None,
            }
        )

    return JsonResponse({"ok": True, "glyphs": glyphs_out})


def _parse_links_map(raw: object) -> Optional[dict]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("links must be a JSON object")
    out: dict = {}
    for k, v in raw.items():
        key = str(k)
        if isinstance(v, (list, tuple)):
            out[key] = [str(x) for x in v]
        else:
            out[key] = []
    return out


@csrf_exempt
@require_POST
def sort_layout_api(request):
    """
    Sort a list of glyph addresses and compute (x, y) layout (origin-relative).

    JSON body:
      {
        "addresses": ["Ba1-001", ...],
        "criterion": "Order" | "Transliteration" | ...,
        "orientation": "horizontal" | "vertical",
        "max_row_width": number,   // required when orientation is horizontal
        "links": { "Ba1-001": ["Ba1-002"], ... }  // optional; for Connections
      }
    """

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    raw_addrs = payload.get("addresses")
    if raw_addrs is None or not isinstance(raw_addrs, list):
        return HttpResponseBadRequest("Missing or invalid 'addresses'")

    criterion = payload.get("criterion", "")
    if not isinstance(criterion, str) or criterion not in KNOWN_CRITERIA:
        return HttpResponseBadRequest("Missing or invalid 'criterion'")

    orientation = payload.get("orientation", "")
    if orientation not in ("horizontal", "vertical"):
        return HttpResponseBadRequest("Invalid 'orientation'")

    try:
        links = _parse_links_map(payload.get("links"))
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    max_row_width: Optional[float] = None
    if orientation == "horizontal":
        try:
            max_row_width = float(payload.get("max_row_width"))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Missing or invalid 'max_row_width' for horizontal layout")
        if max_row_width <= 0:
            return HttpResponseBadRequest("'max_row_width' must be positive")

    addresses_in: List[str] = []
    for a in raw_addrs:
        if not isinstance(a, str):
            return HttpResponseBadRequest("Each address must be a string")
        if not _glyph_address_ok(a):
            return HttpResponseBadRequest(f"Invalid glyph address: {a!r}")
        addresses_in.append(a)

    if not addresses_in:
        return JsonResponse({"ok": True, "glyphs": []})

    corpus_index = corpus_address_order_index()
    ordered = sort_glyph_addresses(
        addresses_in,
        criterion,
        links=links,
        corpus_index=corpus_index,
    )

    static_image_dir = Path(__file__).resolve().parent / "static" / "viewer" / "images"

    sizes: List[Tuple[float, float]] = []
    for addr in ordered:
        nat = _natural_image_size(addr, static_image_dir)
        if nat:
            rw, rh = scaled_render_size(nat[0], nat[1], DEFAULT_MAX_RENDER_DIM)
        else:
            rw = rh = float(DEFAULT_MAX_RENDER_DIM)
        sizes.append((rw, rh))

    if orientation == "horizontal":
        positions = layout_horizontal_wrap(
            sizes,
            (0.0, 0.0),
            max_row_width=float(max_row_width),
            horizontal_gap=DEFAULT_HORIZONTAL_GAP,
            vertical_gap=DEFAULT_VERTICAL_GAP,
        )
    else:
        positions = layout_vertical_stack(
            sizes,
            (0.0, 0.0),
            horizontal_gap=DEFAULT_HORIZONTAL_GAP,
            vertical_gap=DEFAULT_VERTICAL_GAP,
        )

    glyphs_out = []
    for addr, (gx, gy), (rw, rh) in zip(ordered, positions, sizes):
        meta = get_transliteration_meta(addr)
        gf = get_glyph_file(addr)
        url, _hi = _image_url_for_address(addr, static_image_dir)
        glyphs_out.append(
            {
                "address": addr,
                "name": f"{addr}.png",
                "x": gx,
                "y": gy,
                "render_width": rw,
                "render_height": rh,
                "image_url": url,
                "transliteration": meta.get("transliteration"),
                "confidence": meta.get("confidence"),
                "labels_str": meta.get("labels_str"),
                "comments_str": meta.get("comments_str"),
                "alternates_str": meta.get("alternates_str"),
                "corpus_filepath": str(gf.filepath) if gf else None,
            }
        )

    return JsonResponse({"ok": True, "glyphs": glyphs_out})


@csrf_exempt
@require_POST
def step_glyph_api(request):
    """
    Step next/previous glyphs on the same tablet.

    Request JSON:
      {
        "direction": 1 | -1,
        "selections": [
          { "address": "Ba1-001", "x": 10, "y": 20, "w": 80, "h": 120 },
          ...
        ]
      }
    """

    # #region agent log
    _debug_log_step("H6", "views.py:step_glyph_api:entry", "Step glyph API entered", {
        "method": request.method,
        "body_len": len(request.body or b""),
    })
    # #endregion
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        # #region agent log
        _debug_log_step("H7", "views.py:step_glyph_api:bad-json", "Invalid JSON body")
        # #endregion
        return HttpResponseBadRequest("Invalid JSON")

    direction = payload.get("direction", None)
    if direction not in (1, -1):
        # also accept string form
        try:
            direction = int(direction)
        except (TypeError, ValueError):
            # #region agent log
            _debug_log_step("H7", "views.py:step_glyph_api:bad-direction-cast", "Direction cast failed", {"direction": direction})
            # #endregion
            return HttpResponseBadRequest("Invalid 'direction'")
    if direction not in (1, -1):
        # #region agent log
        _debug_log_step("H7", "views.py:step_glyph_api:bad-direction", "Direction invalid after cast", {"direction": direction})
        # #endregion
        return HttpResponseBadRequest("Invalid 'direction'")

    raw = payload.get("selections")
    if raw is None or not isinstance(raw, list):
        # #region agent log
        _debug_log_step("H7", "views.py:step_glyph_api:bad-selections", "Selections missing/invalid", {"type": str(type(raw))})
        # #endregion
        return HttpResponseBadRequest("Missing/invalid 'selections'")
    # #region agent log
    _debug_log_step("H6", "views.py:step_glyph_api:payload-ok", "Payload parsed", {
        "direction": direction,
        "selection_count": len(raw),
    })
    # #endregion

    static_image_dir = Path(__file__).resolve().parent / "static" / "viewer" / "images"

    seen_addresses = set()
    glyphs_out = []

    for item in raw:
        if not isinstance(item, dict):
            continue
        addr = item.get("address")
        if not isinstance(addr, str) or not _glyph_address_ok(addr):
            continue

        # Anchor (current glyph) in Konva world coords.
        try:
            ax = float(item.get("x"))
            ay = float(item.get("y"))
            aw = float(item.get("w", DEFAULT_MAX_RENDER_DIM))
            ah = float(item.get("h", DEFAULT_MAX_RENDER_DIM))
        except (TypeError, ValueError):
            continue

        next_addr = step_adjacent_glyph_address(addr, direction=direction)
        if not next_addr:
            continue
        if not _glyph_address_ok(next_addr):
            continue
        if next_addr in seen_addresses:
            continue

        url, has_image = _image_url_for_address(next_addr, static_image_dir)
        if not has_image:
            continue

        nat = _natural_image_size(next_addr, static_image_dir)
        if nat:
            rw, rh = scaled_render_size(nat[0], nat[1], DEFAULT_MAX_RENDER_DIM)
        else:
            rw = rh = float(DEFAULT_MAX_RENDER_DIM)

        anchor_rect = Rect(x=ax, y=ay, width=aw, height=ah)
        if direction == 1:
            nx, ny = top_left_right_of(anchor_rect, rw, rh, gap=DEFAULT_HORIZONTAL_GAP)
        else:
            nx, ny = top_left_left_of(anchor_rect, rw, rh, gap=DEFAULT_HORIZONTAL_GAP)

        meta = get_transliteration_meta(next_addr)
        gf = get_glyph_file(next_addr)

        glyphs_out.append(
            {
                "address": next_addr,
                "name": f"{next_addr}.png",
                "x": nx,
                "y": ny,
                "render_width": rw,
                "render_height": rh,
                "image_url": url,
                "transliteration": meta.get("transliteration"),
                "confidence": meta.get("confidence"),
                "labels_str": meta.get("labels_str"),
                "comments_str": meta.get("comments_str"),
                "alternates_str": meta.get("alternates_str"),
                "corpus_filepath": str(gf.filepath) if gf else None,
            }
        )
        seen_addresses.add(next_addr)

    # #region agent log
    _debug_log_step("H8", "views.py:step_glyph_api:return", "Returning step results", {
        "result_count": len(glyphs_out),
        "seen_count": len(seen_addresses),
    })
    # #endregion
    return JsonResponse({"ok": True, "glyphs": glyphs_out})
