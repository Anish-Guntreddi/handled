"""Streamlit dashboard for the dev-only ``rag_eval`` store (dev-tool quality).

Run with::

    cd apps/api && uv run --group rag-eval streamlit run captureos/rag_eval/dashboard/app.py

Reads the isolated ``rag_eval`` schema over a synchronous engine and never touches product
tables. Importing this package is side-effect-free.
"""

from __future__ import annotations
