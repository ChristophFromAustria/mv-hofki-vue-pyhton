"""KI-Import: turn scanned inventory documents into reviewable JSON.

Pipeline (each step independently testable):

1. :mod:`pages`      - PDF/image file -> list of page PNGs at a bounded width
2. :mod:`llm_client` - OpenAI-compatible chat call with images + JSON schema
3. :mod:`extraction` - prompt + schema + pydantic models for one page's raw data

Resolving the raw data against the database (instrument types, musicians,
inventory numbers) is deliberately *not* part of this package's first step.
"""
