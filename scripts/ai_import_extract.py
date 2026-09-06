#!/usr/bin/env python
"""Run the KI-Import extraction on a PDF or image and print the raw JSON.

Usage (inside the devcontainer, from the project root):

    PYTHONPATH=src/backend python scripts/ai_import_extract.py dokument.pdf
    PYTHONPATH=src/backend python scripts/ai_import_extract.py seite.jpg --out /tmp/out
    PYTHONPATH=src/backend python scripts/ai_import_extract.py dokument.pdf --pages 1-3

Every run archives the original file, the rendered pages, the prompt and the
raw model answers under data/uploads/imports/archive/ (disable with
--no-archive). With --out, page images with the reported bounding boxes
drawn in and the photo crops are additionally written to that directory, so
the model's output can be checked against the document by eye.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mv_hofki.services.ai_import.archive import ARCHIVE_ROOT, create_archive
from mv_hofki.services.ai_import.extraction import (
    SYSTEM_PROMPT,
    build_prompt,
    extract_page,
)
from mv_hofki.services.ai_import.llm_client import LlmClient, LlmError
from mv_hofki.services.ai_import.pages import (
    DEFAULT_MAX_WIDTH,
    PageImage,
    crop,
    render_file,
)


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def parse_pages(spec: str | None) -> list[int] | None:
    """'1-3,5' (1-based, as printed on the document) -> [0, 1, 2, 4]."""
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a) - 1, int(b)))
        elif part:
            out.add(int(part) - 1)
    return sorted(out)


def write_debug_output(
    out_dir: Path, page: PageImage, extraction: dict[str, Any]
) -> None:
    import cv2
    import numpy as np

    stem = f"{Path(page.source_name).stem}_p{page.index + 1:02d}"
    (out_dir / f"{stem}.png").write_bytes(page.png)
    (out_dir / f"{stem}.json").write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    img = cv2.imdecode(np.frombuffer(page.png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return
    font = cv2.FONT_HERSHEY_SIMPLEX
    for i, inst in enumerate(extraction.get("instruments", [])):
        if inst.get("bbox_2d"):
            x1, y1, x2, y2 = inst["bbox_2d"]
            cv2.rectangle(img, (x1, y1), (x2, y2), (40, 90, 200), 2)
            cv2.putText(
                img, f"#{i + 1}", (x1 + 4, y1 + 22), font, 0.7, (40, 90, 200), 2
            )
    for i, photo in enumerate(extraction.get("photos", [])):
        x1, y1, x2, y2 = photo["bbox_2d"]
        cv2.rectangle(img, (x1, y1), (x2, y2), (60, 160, 60), 3)
        cv2.putText(
            img, f"Foto {i + 1}", (x1 + 4, max(20, y1 - 8)), font, 0.7, (60, 160, 60), 2
        )
        try:
            (out_dir / f"{stem}_foto{i + 1:02d}.png").write_bytes(
                crop(page, photo["bbox_2d"])
            )
        except ValueError as e:
            log(f"  Foto {i + 1}: {e}")
    cv2.imwrite(str(out_dir / f"{stem}_boxes.png"), img)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("file", type=Path, help="PDF oder Bild (png/jpg/tif)")
    ap.add_argument("--pages", help="Seiten, 1-basiert, z.B. '1-3,5' (nur PDF)")
    ap.add_argument(
        "--max-width", type=int, default=DEFAULT_MAX_WIDTH, help="Renderbreite px"
    )
    ap.add_argument(
        "--out", type=Path, help="Verzeichnis für Box-Overlays und Foto-Crops"
    )
    ap.add_argument("--base-url", help="überschreibt LLM_BASE_URL")
    ap.add_argument("--model", help="überschreibt LLM_MODEL")
    ap.add_argument(
        "--render-only", action="store_true", help="nur rendern, kein LLM-Aufruf"
    )
    ap.add_argument(
        "--no-archive", action="store_true", help=f"nicht unter {ARCHIVE_ROOT} ablegen"
    )
    return ap


async def main() -> int:
    args = build_parser().parse_args()

    if not args.file.exists():
        log(f"Datei nicht gefunden: {args.file}")
        return 2

    pages = render_file(
        args.file, max_width=args.max_width, pages=parse_pages(args.pages)
    )
    log(f"{len(pages)} Seite(n) gerendert aus {args.file.name}")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    archive = None
    if not args.no_archive:
        archive = create_archive(args.file.name)
        archive.add_original(args.file.name, args.file.read_bytes())
        archive.add_pages(pages)
        archive.set(max_width=args.max_width, pages_requested=args.pages)
        log(f"Archiv: {archive.root}")

    if args.render_only:
        for p in pages:
            log(f"  Seite {p.index + 1}: {p.width}x{p.height} px")
            if args.out:
                (args.out / f"{args.file.stem}_p{p.index + 1:02d}.png").write_bytes(
                    p.png
                )
        return 0

    client = LlmClient(base_url=args.base_url, model=args.model)
    try:
        models = await client.list_models()
    except LlmError as e:
        log(str(e))
        return 1
    log(f"Endpunkt {client.base_url}, Modell {client.model}")
    log(f"Verfügbare Modelle: {', '.join(models)}")
    if archive:
        archive.set(base_url=client.base_url, model=client.model)
        if pages:
            archive.add_prompt(
                SYSTEM_PROMPT, build_prompt(pages[0].width, pages[0].height)
            )

    results: list[dict[str, Any]] = []
    for page in pages:
        try:
            result = await extract_page(client, page)
        except LlmError as e:
            log(f"  Seite {page.index + 1}: FEHLER {e}")
            if archive:
                archive.add_error(page.index, str(e))
            results.append(
                {
                    "source_name": page.source_name,
                    "page_index": page.index,
                    "error": str(e),
                }
            )
            continue
        ex = result.extraction
        log(
            f"  Seite {page.index + 1}: {ex.page_kind}, "
            f"{len(ex.instruments)} Instrument(e), {len(ex.photos)} Foto(s), "
            f"{result.duration_seconds}s, "
            f"{result.usage.get('total_tokens', '?')} Tokens"
        )
        if archive:
            archive.add_result(
                page.index, result.raw, result.usage, result.duration_seconds
            )
        data = result.model_dump(exclude={"raw"})
        results.append(data)
        if args.out:
            write_debug_output(args.out, page, data["extraction"])

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
