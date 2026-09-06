"""Archive everything the KI-Import receives and produces.

Every upload is kept, whether or not the import succeeds: the original file,
the rendered pages the model actually saw, the model's raw answers (or the
error), and the prompt version. This is the corpus for regression tests and
for improving prompt and post-processing later.

Layout::

    data/uploads/imports/archive/<YYYYMMDD-HHMMSS>_<slug>/
        meta.json          source, model, page sizes, timings, token usage
        prompt.txt         system + user prompt used for page 1
        original/<file>    the uploaded file, byte for byte
        pages/p01.png      rendered page images
        raw/p01.json       model output as returned (before validation)
        raw/p01.error.txt  error message if a page failed
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from mv_hofki.core.config import settings

from .pages import PageImage

ARCHIVE_ROOT = Path(settings.PROJECT_ROOT) / "data" / "uploads" / "imports" / "archive"


def _slug(name: str, max_len: int = 40) -> str:
    stem = Path(name).stem
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-").lower()
    return (slug or "upload")[:max_len]


@dataclass
class ImportArchive:
    """One archived document. Create via :func:`create_archive`."""

    root: Path
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.root.name

    def _write_meta(self) -> None:
        (self.root / "meta.json").write_text(
            json.dumps(self.meta, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def add_original(self, filename: str, data: bytes) -> Path:
        target = self.root / "original" / Path(filename).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.meta.setdefault("originals", []).append(
            {
                "filename": target.name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        self._write_meta()
        return target

    def add_pages(self, pages: list[PageImage]) -> None:
        (self.root / "pages").mkdir(parents=True, exist_ok=True)
        entries = self.meta.setdefault("pages", [])
        for page in pages:
            filename = f"p{page.index + 1:02d}.png"
            (self.root / "pages" / filename).write_bytes(page.png)
            entries.append(
                {
                    "index": page.index,
                    "file": filename,
                    "width": page.width,
                    "height": page.height,
                    "source_name": page.source_name,
                }
            )
        self._write_meta()

    def add_prompt(self, system_prompt: str, user_prompt: str) -> None:
        text = f"### system\n{system_prompt}\n\n### user\n{user_prompt}\n"
        (self.root / "prompt.txt").write_text(text, encoding="utf-8")
        self.meta["prompt_sha256"] = hashlib.sha256(text.encode()).hexdigest()[:16]
        self._write_meta()

    def add_result(
        self,
        page_index: int,
        raw: dict[str, Any],
        usage: dict[str, Any] | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        (self.root / "raw").mkdir(parents=True, exist_ok=True)
        (self.root / "raw" / f"p{page_index + 1:02d}.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.meta.setdefault("results", []).append(
            {
                "index": page_index,
                "ok": True,
                "usage": usage or {},
                "duration_seconds": duration_seconds,
            }
        )
        self._write_meta()

    def add_error(self, page_index: int, message: str) -> None:
        (self.root / "raw").mkdir(parents=True, exist_ok=True)
        (self.root / "raw" / f"p{page_index + 1:02d}.error.txt").write_text(
            message, encoding="utf-8"
        )
        self.meta.setdefault("results", []).append(
            {"index": page_index, "ok": False, "error": message}
        )
        self._write_meta()

    def set(self, **fields: Any) -> None:
        """Record arbitrary metadata (model, base_url, session id, ...)."""
        self.meta.update(fields)
        self._write_meta()


def create_archive(
    source_name: str,
    root: Path | None = None,
    now: datetime | None = None,
) -> ImportArchive:
    base = root or ARCHIVE_ROOT
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    candidate = base / f"{stamp}_{_slug(source_name)}"
    n = 1
    while candidate.exists():
        n += 1
        candidate = base / f"{stamp}_{_slug(source_name)}-{n}"
    candidate.mkdir(parents=True)
    archive = ImportArchive(
        root=candidate,
        meta={"created_at": (now or datetime.now()).isoformat(timespec="seconds")},
    )
    archive.set(source_name=source_name)
    return archive
