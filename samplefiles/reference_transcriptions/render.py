#!/usr/bin/env python3
"""Render a LilyPond .ly file to PDF using the lilypond PyPI package.

Usage:
    python render.py                    # render once
    python render.py path/to/file.ly    # render specific file once
    python render.py --watch            # watch default file for changes
    python render.py --watch file.ly    # watch specific file for changes
"""

import os
import subprocess
import sys
import time
from pathlib import Path


def find_lilypond() -> str:
    try:
        from lilypond import executable  # type: ignore[import-not-found]

        return str(executable())
    except (ImportError, Exception):
        pass
    import shutil

    path = shutil.which("lilypond")
    if path:
        return path
    print("LilyPond not found. Install with: pip install lilypond", file=sys.stderr)
    sys.exit(1)


def render(ly_file: Path, lilypond_bin: str) -> bool:
    output_stem = ly_file.with_suffix("")

    print(f"\n--- Rendering {ly_file.name} ---")
    result = subprocess.run(
        [lilypond_bin, f"--output={output_stem}", str(ly_file)],
        capture_output=True,
        timeout=60,
    )

    if result.returncode != 0:
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        return False

    pdf_path = output_stem.with_suffix(".pdf")
    if pdf_path.exists():
        print(f"PDF: {pdf_path}")
        rotated_path = output_stem.with_name(output_stem.stem + "_rotated.pdf")
        rot = subprocess.run(
            ["qpdf", str(pdf_path), "--rotate=+90", "--", str(rotated_path)],
            capture_output=True,
        )
        if rot.returncode == 0:
            print(f"PDF (rotated): {rotated_path}")
    else:
        print("Warning: no PDF generated", file=sys.stderr)
        return False

    midi_path = output_stem.with_suffix(".midi")
    if midi_path.exists():
        print(f"MIDI: {midi_path}")

    return True


def watch(ly_file: Path, lilypond_bin: str):
    print(f"Watching {ly_file.name} for changes (Ctrl+C to stop) ...")
    last_mtime = 0.0

    while True:
        try:
            mtime = os.path.getmtime(ly_file)
            if mtime != last_mtime:
                last_mtime = mtime
                render(ly_file, lilypond_bin)
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


def main():
    args = [a for a in sys.argv[1:] if a != "--watch"]
    watching = "--watch" in sys.argv

    ly_file = Path(__file__).parent / "frisch_auf_tuba1.ly"
    if args:
        ly_file = Path(args[0])

    if not ly_file.exists():
        print(f"File not found: {ly_file}", file=sys.stderr)
        sys.exit(1)

    lilypond_bin = find_lilypond()

    if watching:
        render(ly_file, lilypond_bin)
        watch(ly_file, lilypond_bin)
    else:
        if not render(ly_file, lilypond_bin):
            sys.exit(1)


if __name__ == "__main__":
    main()
