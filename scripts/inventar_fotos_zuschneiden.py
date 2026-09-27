"""Cut individual photos out of scanned A4 pages with glued-on prints.

Fully automatic splitting is unreliable (prints touch each other, some photo
backgrounds are as pale as the paper), so the boxes come from a reviewer who
looked at the page: approximate rectangles in source pixels. Each edge is then
snapped to the strongest straight edge nearby, edge lines that are plain paper
are trimmed off, and the photo is cropped.

Box file (JSON), one entry per page image:
    {"tu_1.jpg": [{"box": [x0, y0, x1, y1], "inventar_nr": "TU 1"}, ...]}

Optional per box: ``"snap": false`` keeps the given edges exactly (for touching
prints where a stronger edge inside the photo would win), ``"trim": false``
keeps pale photo background that looks like paper.

Usage (inside the devcontainer):
    python scripts/inventar_fotos_zuschneiden.py \
        samplefiles/inventar_scans/Tuba/bilder \
        --boxes samplefiles/inventar_scans/_extraktion/Tuba/fotos/boxen.json \
        --out samplefiles/inventar_scans/_extraktion/Tuba/fotos

Writes ``<out>/<seite>_<n>.jpg``, ``<out>/fotos.json`` (snapped boxes plus the
reviewer's fields) and ``<out>/kontrolle/<seite>.jpg`` overlays for review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

SEARCH_FRAC = 0.04  # search window per edge, share of the page size
MIN_STEP = 40  # colour jump (sum over BGR) that counts as an edge pixel
MIN_COVERAGE = 0.45  # share of the side that must show an edge to snap
PAPER_TOLERANCE = 30  # colour distance (sum over BGR) to the paper colour
PAPER_LINE_SHARE = 0.97  # a row/column this paper-like is trimmed off


def _edge_coverage(img: np.ndarray, axis: int, pos: int, lo: int, hi: int) -> float:
    """Share of pixels along a line (x=pos if axis 0, y=pos if axis 1) that
    separate two different colours."""
    if axis == 0:
        a = img[lo:hi, pos - 3 : pos - 1].mean(axis=1)
        b = img[lo:hi, pos + 1 : pos + 3].mean(axis=1)
    else:
        a = img[pos - 3 : pos - 1, lo:hi].mean(axis=0)
        b = img[pos + 1 : pos + 3, lo:hi].mean(axis=0)
    step = np.abs(np.subtract(a, b)).sum(axis=-1)
    return float((step >= MIN_STEP).mean())


def snap_box(img: np.ndarray, box: list[int]) -> tuple[list[int], list[float]]:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    out, scores = [x0, y0, x1, y1], []
    for i, (axis, pos, lo, hi, size) in enumerate(
        [
            (0, x0, y0, y1, w),
            (1, y0, x0, x1, h),
            (0, x1, y0, y1, w),
            (1, y1, x0, x1, h),
        ]
    ):
        # use the middle 80 % of the side so neighbouring corners don't interfere
        span = hi - lo
        lo2, hi2 = lo + span // 10, hi - span // 10
        r = int(size * SEARCH_FRAC)
        best, best_s = pos, 0.0
        for p in range(max(4, pos - r), min(size - 4, pos + r)):
            s = _edge_coverage(img, axis, p, lo2, hi2)
            if s > best_s:
                best, best_s = p, s
        if best_s >= MIN_COVERAGE:
            out[i] = best
        scores.append(round(best_s, 2))
    return out, scores


def paper_colour(img: np.ndarray) -> np.ndarray:
    """Median colour of the outer page margin."""
    h, w = img.shape[:2]
    m = max(8, min(h, w) // 50)
    border = np.concatenate(
        [
            img[:m].reshape(-1, 3),
            img[-m:].reshape(-1, 3),
            img[:, :m].reshape(-1, 3),
            img[:, -m:].reshape(-1, 3),
        ]
    )
    return np.median(border, axis=0)


def trim_paper(img: np.ndarray, box: list[int], paper: np.ndarray) -> list[int]:
    """Drop edge rows/columns that are (almost) entirely paper."""
    x0, y0, x1, y1 = box
    is_paper = np.abs(img[y0:y1, x0:x1] - paper).sum(axis=-1) < PAPER_TOLERANCE
    rows, cols = is_paper.mean(axis=1), is_paper.mean(axis=0)
    top, bottom, left, right = 0, len(rows), 0, len(cols)
    while top < bottom - 1 and rows[top] >= PAPER_LINE_SHARE:
        top += 1
    while bottom > top + 1 and rows[bottom - 1] >= PAPER_LINE_SHARE:
        bottom -= 1
    while left < right - 1 and cols[left] >= PAPER_LINE_SHARE:
        left += 1
    while right > left + 1 and cols[right - 1] >= PAPER_LINE_SHARE:
        right -= 1
    return [x0 + left, y0 + top, x0 + right, y0 + bottom]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bilder", type=Path, help="Ordner mit den Seiten-JPGs")
    ap.add_argument("--boxes", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    boxes = json.loads(args.boxes.read_text())
    (args.out / "kontrolle").mkdir(parents=True, exist_ok=True)
    index: dict[str, list[dict]] = {}
    for page_name, entries in boxes.items():
        img = cv2.imread(str(args.bilder / page_name))
        if img is None:
            raise SystemExit(f"Seite nicht gefunden: {page_name}")
        imgf = cv2.GaussianBlur(img, (5, 5), 0).astype(np.int16)
        paper = paper_colour(imgf)
        overlay = img.copy()
        stem = Path(page_name).stem
        index[page_name] = []
        for n, entry in enumerate(entries, 1):
            if entry.get("snap", True):
                snapped, scores = snap_box(imgf, entry["box"])
            else:
                snapped, scores = list(entry["box"]), None
            if entry.get("trim", True):
                snapped = trim_paper(imgf, snapped, paper)
            x0, y0, x1, y1 = snapped
            name = f"{stem}_{n}.jpg"
            cv2.imwrite(
                str(args.out / name), img[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 92]
            )
            cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 0, 255), 10)
            cv2.putText(
                overlay,
                str(n),
                (x0 + 30, y0 + 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                5,
                (0, 0, 255),
                12,
            )
            index[page_name].append(
                {
                    **entry,
                    "datei": name,
                    "box_geschaetzt": entry["box"],
                    "box": snapped,
                    "kanten_score": scores,
                }
            )
        h, w = img.shape[:2]
        cv2.imwrite(
            str(args.out / "kontrolle" / f"{stem}.jpg"),
            cv2.resize(overlay, (w // 4, h // 4)),
            [cv2.IMWRITE_JPEG_QUALITY, 80],
        )
        print(
            f"{page_name}: {len(entries)} Fotos, "
            f"Kanten {[e['kanten_score'] for e in index[page_name]]}"
        )
    (args.out / "fotos.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
