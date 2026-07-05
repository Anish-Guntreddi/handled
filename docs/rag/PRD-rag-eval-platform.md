# PRD — RAG Evaluation & Experimentation Platform (`feat/custom-rag`)

> **Purpose.** Build the *judge* and the *experiment platform* for a proprietary, domain-specialized
> retrieval architecture. Every future retrieval technique (from the deep-research report) becomes a
> **measured A/B** against a baseline on **our own labeled data** — so "better than standard RAG" is
> proven on our corpus, not asserted from a paper. The moat is the labeled gov-compliance eval set +
> the domain-tuned pipeline measured on it, not a copyable technique.

## Locked decisions
- **Golden set:** Gemini bootstraps candidate labels → **human review in the Streamlit dashboard** (dashboard has a write surface for label review).
- **Corpus:** real federal text (`make corpus-sync`) — analysis + labels are on real data.
- **Eval scope:** **retrieval quality only** this build (recall@k / MRR / nDCG@10 / MAP). Generation-quality eval (faithfulness/answer-relevance) is a deferred later phase.
- **Retrievers:** build the **pluggable retriever seam + dense baseline now**; advanced techniques (hybrid/BM25, re-ranker, embedding adapter) are **deferred to post-research-report**, each a measured A/B.
- **Baseline retriever under test:** `captureos.ingestion.corpus_retrieval.corpus_retrieve` (the org-less global corpus retriever).

## Engineering constraints (non-negotiable)
- **Dev-only, isolated.** The eval store is a **separate `rag_eval` Postgres schema** on its own `RagEvalBase` (NOT the product `Base`), created by a dev init via `create_all` — **never in the product Alembic chain, never deployed.** It stores corpus ids as **plain UUIDs (no cross-schema FK)** so it's fully decoupled from product tables; chunk text is resolved by query when needed.
- **Deps are a dev-only `rag-eval` dependency group** (`ranx`, `streamlit`, analysis libs). Excluded from the production image (`uv sync --no-dev` won't pull them).
- **The harness gets production-grade rigor** (it's the judge — a wrong metric invalidates every decision). The **Streamlit dashboard is dev-tool quality** (correct, not polished).
- **Lean/free/local**; Gemini free tier; no GPU farm.
- **Isolation invariant preserved:** we only ever read `corpus_chunks`; we never touch tenant `document_chunks` in the eval path.

## Architecture (new package `captureos/rag_eval/`)
```
rag_eval/
  db.py          RagEvalBase + rag_eval schema + init_rag_eval_schema() (create_all, dev-only)
  models.py      the 6 eval tables (below)
  retrievers.py  RetrievedChunk, Retriever protocol, DenseRetriever(corpus_retrieve), build_retriever()
  metrics.py     pytrec_eval wrappers: build qrel/run dicts → recall@k, MRR, nDCG@10, MAP
  harness.py     run_eval(dataset, retriever_config, k) → persists a run + per-query results
  goldenset.py   query seeding + Gemini candidate-label bootstrap (over-retrieve → LLM judges relevance)
  analysis.py    embedding stats: norms, NN-distances, clustering, PCA/UMAP, Matryoshka dim sweep
  experiments.py A/B runner: N configs over a dataset → ranked leaderboard
  cli.py         `make rag-eval` entrypoints (init, run, bootstrap-labels, analyze, experiment)
  dashboard/app.py   Streamlit: runs/leaderboard, per-query drill-down, label review (write), embedding views
tests/rag_eval/  unit + integration tests (own fixtures; isolated rag_eval schema)
```

## Data model — `rag_eval` schema (all ids UUID; corpus refs are plain UUIDs, no FK)
- **`rag_eval_dataset`** — `id, name (unique), description, created_at`. A named golden set.
- **`rag_eval_query`** — `id, dataset_id→dataset, query_text, source (seed|gemini|user), embedding (Vector(768), nullable), created_at`. The `embedding` is the **cached query vector**: each eval query is embedded ONCE and reused across every run so repeated experiments never re-burn the daily embed quota (Gemini free tier = 1000 embeds/day).
- **`rag_eval_qrel`** — the labels. `id, query_id→query, corpus_chunk_id (UUID), corpus_document_id (UUID), relevance (int, graded 0–3), label_source (gemini|human), reviewed (bool default false), created_at`. `UNIQUE(query_id, corpus_chunk_id)`.
- **`rag_eval_run`** — `id, dataset_id→dataset, retriever_name, retriever_config (JSON), embedding_model, k, git_sha, notes, metrics (JSON: {"recall@5":…,"mrr":…,"ndcg@10":…,"map":…}), created_at`.
- **`rag_eval_result`** — per retrieved chunk. `id, run_id→run, query_id→query, rank (int), corpus_chunk_id (UUID), corpus_document_id (UUID), score (float; higher=better, = -cosine_distance), is_relevant (bool, computed vs qrels)`.
- **`rag_embedding_stat`** — analysis snapshot. `id, snapshot_label, corpus_chunk_id, corpus_document_id, doc_type, dim (int), l2_norm (float), nn1_distance (float), cluster_id (int|null), pca_x, pca_y, umap_x, umap_y, created_at`.

## Retriever seam (the spine — advanced techniques plug in here later)
```python
@dataclass(slots=True)
class RetrievedChunk:
    corpus_chunk_id: uuid.UUID
    corpus_document_id: uuid.UUID
    text: str
    score: float   # higher = better (store as -cosine_distance for the dense baseline)
    rank: int

class Retriever(Protocol):
    name: str
    config: dict
    async def retrieve(self, session, query_text: str, *, k: int) -> list[RetrievedChunk]: ...

# DenseRetriever wraps corpus_retrieve (config: doc_type, jurisdiction, current_only, embedding_model, matryoshka_dim?)
# build_retriever(config: dict) -> Retriever   # registry keyed by config["type"]: "dense" now; "hybrid"/"rerank"/"adapter" later
```

## Metrics (never hand-roll the math — use `pytrec_eval`, the NIST trec_eval bindings)
`metrics.py` builds the **qrel dict** `{query_id: {chunk_id: relevance_int}}` from `rag_eval_qrel` and the **run dict** `{query_id: {chunk_id: score_float}}` from `rag_eval_result`, then:
```python
import pytrec_eval
ev = pytrec_eval.RelevanceEvaluator(qrel, {"recall.1,5,10", "recip_rank", "ndcg_cut.10", "map"})
per_query = ev.evaluate(run)   # {query_id: {"recall_5":…, "recip_rank":…, "ndcg_cut_10":…, "map":…}}
```
Aggregate = mean across queries. **Name mapping: MRR = `recip_rank`, recall@k = `recall_k`, nDCG@10 = `ndcg_cut_10`, MAP = `map`.** Chunk ids are the ranking unit (string-cast UUIDs); a doc-level rollup is available. Single source of metric truth. (`ranx` was rejected — its `numba` dep hangs on Python 3.13.)

---

# Phases (each = one dynamic workflow, then a `/qa` + `/security-audit` gate)

### Phase 1 — Foundation & Judge
Build: `db.py` (RagEvalBase + schema init) · `models.py` (6 tables) · `retrievers.py` (seam + DenseRetriever + build_retriever) · `metrics.py` (pytrec_eval) · `harness.py` (`run_eval`) · `cli.py` (`rag-eval init|run`) · `dashboard/app.py` (skeleton: run list + metric tiles) · `rag-eval` dep group · Makefile targets (`rag-eval-init`, `rag-eval`, `rag-dashboard`) · a tiny **synthetic dataset** (verify_rag-style samples) to prove the pipe end-to-end.
**Acceptance:** `make rag-eval-init` creates the schema; `make rag-eval` runs the dense baseline over the synthetic dataset, computes recall@k/MRR/nDCG via pytrec_eval, persists a run; `make rag-dashboard` shows that run's metric tiles; `make check` green; the eval store is provably absent from the product Alembic head.

### Phase 2 — Golden Set & Real Corpus
`goldenset.py`: a hand-written **seed query set** (~15 realistic SMB compliance queries matching the embedded corpus topics: SBIR/STTR, WOSB/EDWOSB, 8(a), SAM.gov registration, IRC §41 R&D credit, …) + optional Gemini query augmentation + **Gemini candidate-label bootstrap** (over-retrieve K≫k candidates via the dense retriever → Gemini **flash** grades each candidate's relevance 0–3 → write `rag_eval_qrel` with `label_source=gemini, reviewed=false`).
- **Query-embedding cache:** embed each query ONCE at build time, store on `rag_eval_query.embedding`; `corpus_retrieve` gains an optional `query_vector` param and `DenseRetriever`/`run_eval` pass the cached vector so a re-run embeds **zero** queries. (Quota-frugal + faster.)
- **Grader safety (correctness-critical):** the candidate chunk text is UNTRUSTED corpus content — the flash grader MUST fence it (`<untrusted_source>…</untrusted_source>` + ignore-embedded-instructions directive) and return a strict schema (grade only), so a chunk containing "mark me relevant" can't steer the label. Mirror `agents/company_brain.py`'s fencing.
- Streamlit **label-review view** (write surface): dataset → query → candidate qrels with chunk text resolved from `corpus_chunks` → accept/reject/edit-grade → sets `reviewed=true` + relevance. Plus a **dataset browser** (datasets, query counts, qrel counts, review progress).

**Acceptance:** a real named dataset exists with human-reviewed qrels; the harness runs the dense baseline on it and reports real recall@k/MRR/nDCG (using cached query vectors — a re-run embeds zero queries); label review round-trips through the dashboard; `make check` green. *(Populating the REAL data needs embed quota; if today's is exhausted the code + hermetic tests land now and the real bootstrap runs on quota reset.)*

### Phase 3 — Embedding-Analysis Spike
`analysis.py`:
- **Corpus structure analysis (quota-FREE — reads existing vectors, runs REAL on the 900 embedded chunks today):** populate `rag_embedding_stat` with per-chunk L2 norm, nearest-neighbor cosine distance, clustering (scikit-learn **KMeans + HDBSCAN**), and 2-D projection coords (**PCA + t-SNE** — *not* UMAP, whose numba dep is Python-3.13-hostile, same trap as ranx). Store under a `snapshot_label`.
- **Matryoshka dim sweep (golden-set-dependent → code now, populate on quota reset):** truncate query+corpus vectors to 256/512/768 and measure recall@k at each (quality-vs-index-cost tradeoff). Needs the golden set's query embeddings, so it lands as tested code + runs when the golden data exists.
- Streamlit views: embedding **scatter** (PCA/t-SNE, color by cluster / doc_type), **norm + NN-distance histograms**, cluster summary, and a **per-query failure drill-down** (query → retrieved vs. should-have-retrieved, from a run's results + qrels — populates with the golden set).

**Acceptance:** a REAL `rag_embedding_stat` snapshot over the 900 embedded chunks exists (no embeds spent); the dashboard renders scatter + histograms + cluster summary on it; the dim-sweep + failure-drilldown code is built + hermetically tested (populates when golden data lands); `make check` green.

### Phase 4 — Experiment Platform
`experiments.py`: config-driven A/B runner (run N `RetrieverConfig`s over a dataset → **ranked leaderboard** with metric deltas + significance note) · Streamlit leaderboard + run-comparison + ablation views · a **baseline-characterization report** (generated from the data: where dense retrieval wins/loses by doc_type/query-type).
**Acceptance:** running ≥2 configs (e.g., dense @ chunk-size A vs. B, or k sweep) yields a ranked leaderboard in the dashboard; the baseline report is generated; the seam accepts a new config type without touching the harness; `make check` green.

### Deferred — Phase 5+ (post research report)
Implement each advanced retriever behind `build_retriever` as its own measured A/B on P4's runner: **HybridRetriever** (BM25/learned-sparse + dense + RRF), **RerankRetriever** (cross-encoder, then fine-tuned on our qrels), **AdapterRetriever** (learned low-rank projection on frozen Gemini embeddings, trained on our qrels). Each kept only if it beats baseline on the golden set. Built one at a time, after the report lands, with the user's go.

## Non-goals (this build)
Generation-quality eval; deploying the eval platform; evaluating the org-scoped `retrieve_relevant_chunks` (focus is the shared corpus retriever); training any advanced retriever (deferred).

## Per-phase gate (locked)
`make check` (ruff + mypy + pytest) green → **`/qa`** → **`/security-audit`** → fix findings → only then the next phase. Correctness-critical logic (metric computation, schema isolation) gets adversarial verification inside the workflow before the gate.
