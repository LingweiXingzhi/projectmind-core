"""ProjectMind architecture-loop workbench (A role).

CONTRACT_V1 shared seam for the architecture cognition loop:
A workbench (this package, app.py, web) consumes B (drafts/versions/review),
C (candidates and natural-language corrections) and D (handoff / fix tasks)
through one adapter. Until a real backend is registered, the adapter answers
BACKEND_UNAVAILABLE in production mode; dev samples are only served when the
caller explicitly passes mode="dev_sample" and every response stays labeled.
"""
