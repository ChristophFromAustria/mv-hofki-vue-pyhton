# Lilypond-Generierung aus Taktstruktur

## Problem

Die Taktstruktur (Measures) ist erkannt und in der DB gespeichert, aber es gibt keinen Weg, daraus ein Notenblatt zu generieren. Als erster Schritt soll ein Lilypond-Gerüst erzeugt werden, das die korrekte System-Anzahl und Taktaufteilung des Originals widerspiegelt — mit Platzhalter-Noten (ganze Noten) statt echten Tonhöhen.

## Lösung

### 1. Lilypond-Generator Service

Neue Datei: `src/backend/mv_hofki/services/lilypond_generator.py`

Funktion `generate_lilypond(measures, scan_title) -> str`:
- Reine Logik, kein DB-Zugriff
- Gruppiert Measures nach `staff_index`, sortiert nach `measure_number_in_staff`
- Generiert Lilypond-Code mit:
  - Paper-Block: A5 landscape, Margins aus Referenzdatei (`top-margin=1, bottom-margin=4, left-margin=16, right-margin=16`), System-Spacing, `indent=0`
  - Header: `title` = Scan-Titel (z.B. original_filename)
  - Score: `\clef bass`, `\time 2/2` (Alla breve), pro Takt `c1` (ganze Note als Platzhalter), `\break` zwischen Systemen
  - Layout: `staff-size 17`, `\omit BarNumber`

Beispiel-Output für 2 Systeme mit je 3 Takten:
```lilypond
\version "2.24.0"
#(set-default-paper-size "a5" 'landscape)
\paper {
  top-margin = 1
  bottom-margin = 4
  left-margin = 16
  right-margin = 16
  system-system-spacing.basic-distance = #6
  indent = 0\mm
}
\header {
  title = "47er Regimentsmarsch"
  tagline = ##f
}
\score {
  \new Staff {
    \clef bass
    \time 2/2
    c1 | c1 | c1 |
    \break
    c1 | c1 | c1 |
  }
  \layout {
    #(layout-set-staff-size 17)
    \context {
      \Score
      \omit BarNumber
    }
  }
}
```

### 2. Lilypond-Renderer

Funktion `render_lilypond(ly_content, output_dir) -> Path`:
- Schreibt `generated.ly` in `output_dir`
- Findet lilypond binary (gleiche Logik wie `render.py`: erst `lilypond` PyPI package, dann `shutil.which`)
- Ruft `lilypond --output=... generated.ly` auf
- Gibt Pfad zur generierten PDF zurück
- Wirft Exception bei Fehler (lilypond nicht gefunden, Compile-Fehler)

Beide Funktionen leben in derselben Datei `lilypond_generator.py`.

### 3. API-Endpoint

`POST /api/v1/scanner/scans/{scan_id}/generate-lilypond`

- Lädt Measures für den Scan aus der DB
- Lädt Scan-Metadaten für den Titel (original_filename)
- Ruft `generate_lilypond()` auf
- Ruft `render_lilypond()` auf, Output-Dir = Scan-Verzeichnis (`data/scans/{project}/{part}/{scan}/`)
- Gibt zurück:
  ```json
  {
    "lilypond_code": "\\version \"2.24.0\"\n...",
    "pdf_path": "data/scans/5/5/5/generated.pdf",
    "ly_path": "data/scans/5/5/5/generated.ly"
  }
  ```

### 4. Frontend

**ScanEditorPage.vue:**
- Button "Lilypond" in der Toolbar
- Nach Klick: API-Call, Loading-State
- Bei Erfolg: Modal öffnen

**LilypondModal.vue** (neue Komponente):
- Lilypond-Code in `<pre>` Block (scrollbar, monospace, dunkler Hintergrund)
- Download-Link für PDF (öffnet in neuem Tab)
- "Schließen" Button

### 5. Dateispeicherung

Generierte Dateien im Scan-Verzeichnis:
- `data/scans/{project}/{part}/{scan}/generated.ly`
- `data/scans/{project}/{part}/{scan}/generated.pdf`

Werden bei erneutem Generieren überschrieben.

## Nicht im Scope

- Konfigurierbare Paper-Settings
- Tonhöhen aus Y-Position
- Wiederholungszeichen, Dynamik, Verzierungen
- MIDI-Generierung
- PDF-Rotation (wie in render.py)
