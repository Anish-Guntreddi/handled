"""Dev-only RAG evaluation & experimentation platform (``feat/custom-rag``).

An isolated judge + experiment harness for the retrieval stack. It lives in its own
``rag_eval`` Postgres schema on a SEPARATE :class:`~captureos.rag_eval.db.RagEvalBase`
(never the product ``Base``, never the Alembic chain, never deployed) and reads ONLY the
shared ``corpus_chunks`` — so the tenant-isolation invariant holds in the eval path.

Importing this package is side-effect-free (no engine/DB access at import time).
"""

from __future__ import annotations
