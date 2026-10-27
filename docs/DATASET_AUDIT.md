# Study-only image audit — October 21, 2026

The website contains exactly **200 original product photos**, all from Assignment 2's frozen `data/study.csv`, plus **200 Grad-CAM overlays of those same study photos**. The overlays are AI-assistance visualizations, not 200 additional trials.

The audit verified:

- The packaged manifest has exactly the same 200 `(brand, reference label, source filename)` identities as the study split.
- Every original photo and Grad-CAM overlay matches its Assignment 2 study source byte-for-byte (400 SHA-256 comparisons).
- Frozen AI predictions, confidence, calibrated fake probability, and raw fake probability match the submitted study output CSV.
- The packaged stimuli directory contains exactly those 400 image files and no additional images.
- None of the packaged trial identities occur in the train, validation, or development-test split CSVs.

Dataset fingerprint: `592d94f412af6c9782fe6ae7f1dabc0939ce75a45094c0e2247b8596f117bc47`.

Reproduce from the app folder: `python scripts/audit_study.py`. The adjacent Assignment 2 source folder is needed for this audit, but not for running the packaged website.

Both conditions draw only from this same 200-image pool. As confirmed by the user, each participant receives different random images across the two conditions where unassigned images remain. The same participant ID/nickname links their two conditions. Starting another run also prefers previously unassigned items; after exhaustion, repeated items are permitted and their prior assignments are logged.
