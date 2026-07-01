# WS5 — Custom RAG

> **Workflow E. Phase 3 — LAST. Most research; built on the corpus (WS2) + brain (WS3).**

## Context
A basic dense-retrieval RAG already works (`corpus_retrieve`, cosine top-k, citation-enforced) and carries every other workstream in the meantime. WS5 upgrades it to a **custom retrieval stack tuned for regulatory compliance**, where generic RAG fails: exact terms-of-art (codes, thresholds, citations) defeat pure vectors; law is *versioned*; citations are liability; and there are several distinct query shapes. **It is deliberately last** — custom retrieval is designed from *measurement*, not guesswork, so it opens with an embedding-analysis spike (which also fits the owner's intent to study how embeddings behave).

## Goals
1. **Embedding-analysis spike** → evidence-based design decisions.
2. **Hybrid retrieval**: dense + lexical/BM25 + metadata filters, fused (reciprocal-rank fusion).
3. **Structure-aware legal chunking** (by CFR section/subsection, citation hierarchy intact).
4. **Temporal**: current-law default + point-in-time ("as of my filing date").
5. **Re-rank + relevance threshold** (return empty rather than a weak citation).
6. **Query understanding/routing** (flash) → structured intent + filters.
7. **Eval harness** → the moat becomes *measurable*.
8. **5 retrieval modes** over one engine: compliance, tax, grants, company-brain matching, evidence.

## Non-goals
- Replacing pgvector/AlloyDB (use its dense index; add lexical alongside).
- Fine-tuning embeddings (RAG, not fine-tuning — per strategy).

## Current state (grounded)
- Chunking: `ingestion/chunking.py` (fixed ~1200-char, page-aware).
- Retrieval: `ingestion/corpus_retrieval.py` (`corpus_retrieve`, dense cosine, `is_current` filter), `ingestion/retrieval.py` (org-scoped).
- Embeddings: `providers/embeddings.py` (Gemini, 768-dim).
- Index: `models/corpus.py` partial HNSW; AlloyDB adds ScaNN in prod.
- Anti-fabrication: `services/copilot.py` discards model citations, uses only retrieved snippets.

## Design

### 0. Embedding-analysis spike (first task; `docs/prd/ws5-rag-findings.md`)
- Embed real FAR/CFR/IRS samples; measure similarity-score distributions, cluster structure, where dense retrieval succeeds vs fails on exact-term queries (codes, thresholds, citations). Output: chosen fusion weights, relevance threshold, chunking decision — *evidence, not guesses*.

### 1. Hybrid retrieval (`ingestion/hybrid_retrieval.py`)
- Dense (Gemini embeddings) + lexical (Postgres FTS/BM25 or `pg_trgm`) + metadata filters (authority/doc_type/jurisdiction/`is_current`), combined via **RRF**. Configurable per retrieval mode.

### 2. Structure-aware chunking
- New chunker for regulations: split by CFR section/subsection so each chunk is one coherent provision with its citation hierarchy. Re-embed corpus under the new chunker (two-phase embed already supports clean re-embed). Keep the generic chunker for org docs.

### 3. Temporal
- Default `is_current`; add a point-in-time mode using `effective_date`/`supersedes_id` to retrieve law as-of a date.

### 4. Re-rank + threshold
- Cheap flash cross-encoder re-rank over top-N; a **relevance threshold** returns empty (→ "no relevant source") rather than forcing a weak citation — feeds the existing anti-fabrication gate.

### 5. Query understanding/routing
- Flash step extracts structured intent (entities, codes, program type) → selects retrieval mode + filters before retrieval.

### 6. Retrieval modes (one engine, per-mode config)
compliance (regs→CFR/FAR) · tax (IRS pubs/forms) · grants (profile→SBIR/grants) · company-brain (profile-as-query→corpus) · evidence (requirement→org docs, isolated). *Extensible — more modes later.*

### 7. Eval harness (`tests/rag_eval/`)
- Gold question→citation set; metrics: recall@k, citation accuracy, hallucination rate. CI-runnable; gates RAG changes. This is what makes the moat provable under inspection.

## Dependencies
- WS2 (corpus content + structure-aware re-embed), WS3 (company-brain as query source), WS0 (flash for re-rank/routing). AlloyDB ScaNN at deploy.

## Acceptance criteria
- Spike findings doc with measured distributions + chosen parameters.
- Hybrid beats dense-only on the eval set (recall@k + citation accuracy ↑); exact-term queries (a specific CFR cite / NAICS / threshold) retrieve the governing provision.
- Point-in-time query returns the version in effect on a given date.
- Below-threshold query returns empty + "no relevant source" (no fabricated citation).
- Eval harness runs in CI with reported metrics.

## QA / Security checklist
- `make gate` + `/qa`; **adversarial verification** that re-rank/threshold never emits an unsupported citation (the core liability).
- Org isolation preserved across all modes (evidence mode is org-scoped; corpus modes carry no tenant data) — `test_org_scoping.py`, `test_corpus.py`.
- Eval metrics are a merge gate for RAG changes (no silent regressions).
