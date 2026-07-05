# Deep-Research Brief — Domain-Specialized Retrieval Architecture for a US Government Compliance & Funding RAG

> Paste the section below into a deep-research tool (GPT-5.5 deep research, etc.).
> The output feeds our eval harness: every recommendation becomes a measured experiment
> against a baseline on our own labeled set. Grounded foundations in, ranked implementable
> menu out. Tune the constraints before running if the stack changes.

---

## Role
You are an information-retrieval + RAG research specialist. Produce a rigorously-cited, **implementable** design study, not a general survey. Prioritize verifiable, measurable, parameterizable recommendations over breadth.

## System you are designing retrieval for
- **Product:** an AI platform automating US **federal compliance + funding discovery** for small businesses.
- **Corpus:** slow-moving US federal reference text — eCFR / CFR regulations, the Federal Register, IRS publications, SBA program rules, SAM.gov / grants.gov solicitations. It is **highly structured, hierarchical, cross-referential, citation-heavy, and temporally versioned** (rules amend/supersede over time).
- **Queries:** from small-business owners and from our own agents — e.g. *"am I eligible for an 8(a) sole-source award"*, *"WOSB self-certification requirements"*, *"qualified research expenses under IRC §41"*. A mix of natural-language eligibility questions and entity/citation lookups.
- **Current baseline (what you must beat):** naive dense retrieval — Google `gemini-embedding-001` (768-dim, Matryoshka-capable) → **pgvector** cosine top-k → chunks. Stack is FastAPI + async SQLAlchemy + Postgres/pgvector.
- **Constraints:** lean and cost-sensitive. **RAG-first — we are NOT training a new foundation embedding model.** Small trained components ARE in scope: linear / low-rank **embedding adapters** and **cross-encoder re-rankers fine-tuned on our own labeled pairs**. No GPU farm. Must run on pgvector, or explicitly justify any added index/store.

## Goal
Produce a **ranked, implementable menu of retrieval-architecture techniques** that measurably beat naive dense top-k on THIS domain (structured, hierarchical, citation-heavy, temporally-versioned federal regulatory text with eligibility-style queries). We will implement each and A/B it against baseline on our own labeled eval set. **Target metrics: recall@k, MRR, nDCG@10, context precision/recall.**

## For EACH technique, provide
1. **Name + specific paper(s)/source** with verifiable citations (title, authors, year, venue / arXiv id). **Do NOT fabricate citations** — if you are unsure a reference exists, say so explicitly.
2. **Core mechanism** in 3–5 sentences.
3. **Domain fit** — why it helps (or hurts) on hierarchical, citation-heavy, temporally-versioned regulatory text + eligibility queries.
4. **Parameters/knobs to tune for our domain** with sensible starting values (chunk size/overlap, fusion weights, k, re-ranker model, adapter rank/dim, etc.).
5. **Implementation cost + fit on our stack** (pgvector / Gemini / FastAPI): easy / moderate / hard, and what infra it adds.
6. **Expected gain + failure modes** — when it helps, when it hurts.
7. **How to measure** its effect on our metrics.

## Techniques to evaluate (at minimum)
- **Structure/hierarchy-aware chunking** for legal/regulatory text (section/subsection/clause boundaries, parent-context injection, small-to-big, sentence-window).
- **Hybrid dense + lexical retrieval:** BM25 and learned-sparse (SPLADE); fusion methods (Reciprocal Rank Fusion, weighted, learned) with practical parameters.
- **Late-interaction / multi-vector** (ColBERT / ColBERTv2 / PLAID) — feasibility + cost on Postgres/pgvector vs. a dedicated store. Is it worth it for us?
- **Query transformation:** HyDE, query decomposition, query expansion — value for eligibility/citation queries specifically.
- **Re-ranking:** cross-encoder re-rankers (which models); **fine-tuning a re-ranker on our own labeled query→chunk pairs** — data volume needed, expected lift.
- **Lightweight domain adaptation of embeddings WITHOUT full model training:** a linear / low-rank learned **projection ("embedding adapter" / linear probe)** trained on our labeled pairs; contrastive fine-tuning of a small open sentence-embedding model as a fallback. Expected lift vs. cost.
- **Matryoshka embedding dimensions:** truncation tradeoffs (retrieval quality vs. index cost) at 256 / 512 / 768.
- **Metadata / temporal / authority filtering + citation-precise retrieval:** retrieving the exact controlling section; handling superseded/amended rules; jurisdiction/agency filters; resolving cross-references between regulations.
- **Eval methodology for a domain like ours:** how to build a trustworthy labeled set (qrels) semi-automatically, its pitfalls, and which metrics correlate best with real answer quality.

## Also address
- A recommended **default composed pipeline** — a specific ordered stack with concrete parameters — as a strong starting point, plus 2–3 ablation variants worth testing.
- What is **genuinely proven vs. promising-but-speculative** — state your confidence explicitly.
- Where **domain specialization** (our parameters + our labeled data) is likely to matter more than the choice of technique itself.

## Output format
A structured report: a **ranked technique table** → the **recommended default pipeline** → an **ordered experiment backlog** we can execute one technique at a time. Favor verifiable, implementable, measurable recommendations over breadth.
