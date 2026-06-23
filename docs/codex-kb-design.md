# CaptureOS Knowledge-Base Architecture Plan

Grounding notes from the current code:

- `apps/api/captureos/ingestion/retrieval.py` only retrieves `DocumentChunk` rows where `DocumentChunk.org_id == org_id`, so the current vector path is hard-tenant-scoped.
- `apps/api/captureos/ingestion/service.py` hardcodes `Document`, `DocumentChunk`, and an org-scoped `Source` row per ingest, so the existing ingest entrypoint cannot ingest global corpus rows as-is.
- `apps/api/captureos/ingestion/chunking.py` is generic paragraph/page chunking with `ordinal` + `locator`; it has no doc-type strategy yet.
- `apps/api/captureos/models/documents.py` fixes embeddings at `Vector(768)` with an HNSW cosine index and uses `OrgScopedMixin` on both `Document` and `DocumentChunk`.
- `apps/api/captureos/models/evidence.py` makes `Source` and `EvidenceItem` org-scoped; `EvidenceItem.document_chunk_id` can only point at `document_chunks.id`.
- `apps/api/captureos/db/base.py` makes `org_id` non-null and indexed on every `OrgScopedMixin` table. That invariant is the reason a shared corpus must be physically separate.
- `apps/api/captureos/providers/embeddings.py` already exposes the right seam: deterministic mock embeddings for CI and Gemini embeddings with configurable `output_dimensionality=self.dim`.
- `apps/api/captureos/ingestion/website.py`, `apps/api/captureos/sources/base.py`, `apps/api/captureos/sources/registry.py`, and `apps/api/captureos/config.py` already provide the SSRF guard, adapter seam, TTL cache settings, and rate-limit settings that a corpus ingest pipeline should reuse.

## D1-D7 Decision Table

| Decision | Verdict (AGREE/DISAGREE/AMEND) | Your Reasoning | Alternative if not AGREE |
| --- | --- | --- | --- |
| D1: Hybrid collection — direct APIs for clean sources; Firecrawl only for HTML-heavy/JS/scrape-only; do not Firecrawl what has an API | AGREE | This matches both the repo shape and the source economics. The codebase already has structured-source seams (`SourceAdapter`, TTL, rate-limit) and an SSRF-guarded fetch path. Use authoritative APIs, bulk feeds, and predictable static URLs first; use Firecrawl only where the source is truly scrape-only or JS-rendered. Do not pay crawl credits or add scrape fragility when the authority already exposes machine-readable content. | — |
| D2: Reuse existing parse->chunk->embed->content_hash pipeline + Gemini 768; add doc-type-aware chunking; regs section-aware, forms embedded as a unit, NOFOs sectioned | AMEND | Reuse the pipeline concepts and embedding contract, but not the existing `ingest_content()` function verbatim. That function writes `Document`, `DocumentChunk`, and org-scoped `Source`, so it is structurally tied to tenant-private ingestion. Also, "forms embedded as a unit" is too coarse. A whole form PDF or instruction packet as one vector hurts recall on field-specific questions like `SF-424 box 8c` or `OMB 4040-0004 expiration`. Regulations should be section-aware, NOFOs should be section-aware, and forms should be dual-represented: a document-level synopsis chunk plus section/field/instruction chunks. | Factor shared helpers for `parse -> normalize -> chunk -> embed`, introduce a chunking strategy interface by `doc_type`, and keep form-level metadata plus smaller field/instruction chunks instead of one monolithic form vector. |
| D3: Dedicated GLOBAL corpus tables separate from org-scoped `DocumentChunk`; Vector(768) + HNSW; metadata filters for current-only/doc_type/jurisdiction/CFR title | AGREE | This is the cleanest answer to the current `OrgScopedMixin` contract. Making `org_id` nullable on `documents`, `document_chunks`, or `sources` would weaken the strongest isolation invariant in the codebase and create accidental-footgun risk on every future query. Separate corpus tables preserve the current tenant model intact while allowing global-read-only rows. | — |
| D4: Corpus-aware retrieval unions global corpus + strict org-private evidence, one-directional | AMEND | The security invariant is right; the implementation shape is not. A literal SQL `UNION` over two vector tables is the wrong default because it muddies provenance and usually gives worse planner behavior than two bounded index-backed searches. The correct architecture is two searches: one against `DocumentChunk` filtered by `org_id`, one against `CorpusChunk` filtered by corpus metadata, then a Python-side merge/rerank into a single result envelope tagged with `scope=private|global`. The flow stays one-directional, but the indexes remain independent and the provenance remains explicit. | Implement `retrieve(query, scopes, filters)` as `private_search()` + `global_search()` + `merge_results()`, never as a single undifferentiated vector table or nullable-tenant union. |
| D5: Agents call `retrieve(query, scopes, filters)`; every corpus chunk produces a citable `Source` row; `Source` rows are read-only references, not duplicated data | AMEND | The retrieve API is correct. The `Source` materialization shape is not. In the current schema `Source` is org-scoped, and `EvidenceItem.source_id` requires an org-scoped row. Pre-creating one global `Source` row per corpus chunk either breaks the current org invariant or forces tenant-specific duplication of every chunk upfront. The better model is lazy org-scoped citation references: corpus rows stay global in `corpus_documents` / `corpus_chunks`; when an org actually cites a corpus hit, create a small org-scoped `Source` reference row that points to `corpus_doc_id` and `corpus_chunk_id` and stores no duplicated chunk text. | Keep corpus text only in the corpus tables. Extend `Source` with nullable `corpus_doc_id` and `corpus_chunk_id`, and create org-scoped read-only reference rows lazily on first citation or evidence materialization. |
| D6: Firecrawl monitor = future freshness/cron mechanism — defer entirely | AGREE | Nothing in the current repo requires Firecrawl to deliver Phase 1 value. The worker engine exists, but the corpus can launch with source-native polling from APIs/bulk feeds and manual/scheduled jobs later. Defer crawl monitoring, but do not defer freshness fields in the schema. Effective dates, supersession, and source timestamps belong in Phase 1. | — |
| D7: Firecrawl sizing — start Free tier; Standard is ample; self-host only if usage grows; usage stays modest because APIs carry the bulk | AMEND | Free tier is fine for prototyping and crawl-shape measurement, not as the production default assumption. Once you crawl GSA form libraries, SBA pages, NIH Guide pages, and retry failed pages, 1k pages/month disappears quickly. Because D6 defers monitoring, Free is enough for a Phase-1 pilot; for any recurring production corpus refresh that includes scrape-only sources, budget Standard from the start. Self-host only if you need data locality or materially exceed Standard. | Use Free for initial backfill experiments only; move to Standard before production recurring crawls; self-host only for residency or sustained high-volume scrape workloads. |

## Consensus Status

Not yet in consensus with the human:

1. D2 form chunking shape
   - My resolution: do not embed an entire form as one chunk. Store one form-level synopsis chunk plus section/field/instruction chunks.
   - Why: the current chunker already assumes retrieval-sized text units, and field-level compliance questions will be common.
   - Human confirmation needed: confirm that Phase 1 should support field/instruction-level retrieval for forms, not just form-level retrieval.

2. D4 retrieval implementation
   - My resolution: do not implement corpus-aware retrieval as a literal SQL `UNION`.
   - Why: separate HNSW indexes on `document_chunks` and `corpus_chunks` should be searched independently, then merged with explicit provenance.
   - Human confirmation needed: confirm that preserving separate physical retrieval paths is preferred over a single SQL abstraction.

3. D5 citation materialization
   - My resolution: do not pre-create `Source` rows for every corpus chunk.
   - Why: `Source` is currently org-scoped, and eager global-source fanout is the wrong cardinality and the wrong isolation boundary.
   - Human confirmation needed: confirm lazy org-scoped `Source` references to corpus rows rather than eager source row creation for the entire corpus.

4. D7 Firecrawl starting tier
   - My resolution: Free tier is acceptable for pilot measurement only; Standard should be the production starting point for recurring scrape-based refresh.
   - Why: scrape-only agency pages plus retries will exceed 1k pages/month quickly even if APIs cover most of the corpus.
   - Human confirmation needed: confirm whether Phase 1 is strictly pilot-scale or expected to run as a production recurring sync immediately.

## Corpus Chunk Metadata Schema

### Exact `CorpusChunk` field list

| Field | Python / SQLAlchemy Type | Null? | Comment |
| --- | --- | --- | --- |
| `chunk_id` | `Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)` | No | Stable row identifier for this chunk version. Distinct from private `document_chunks.id` to avoid FK confusion. |
| `corpus_doc_id` | `Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("corpus_documents.corpus_doc_id", ondelete="CASCADE"), index=True)` | No | Parent global document version. Cascades when a corpus document version is removed. |
| `content` | `Mapped[str] = mapped_column(Text)` | No | Normalized text used for retrieval and passed to the embedding provider. |
| `embedding` | `Mapped[list[float] | None] = mapped_column(Vector(768))` | Yes | 768-dim Gemini-compatible embedding; nullable during ingest retry windows only. |
| `content_hash` | `Mapped[str] = mapped_column(String(64), index=True)` | No | SHA-256 of normalized chunk text; used for chunk-level idempotency and refresh diffs. |
| `chunk_index` | `Mapped[int] = mapped_column(Integer)` | No | Zero-based order within the parent document version. |
| `doc_type` | `Mapped[str] = mapped_column(String(16))` | No | One of `REGULATION`, `FORM`, `NOFO`, `LISTING`; duplicated from the parent for filter pushdown. |
| `source_url` | `Mapped[str] = mapped_column(String(2048))` | No | Authoritative or canonical fetch URL for this chunk's parent content. |
| `citation_ref` | `Mapped[str] = mapped_column(String(255), index=True)` | No | Human citation anchor such as `48 CFR 52.219-8` or `SF-424 Section 8`. |
| `effective_date` | `Mapped[date | None] = mapped_column(Date)` | Yes | When this chunk's rule/form/listing text became effective. |
| `superseded_by` | `Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("corpus_chunks.chunk_id", ondelete="SET NULL"), index=True)` | Yes | Successor chunk version, if a like-for-like replacement exists. |
| `jurisdiction` | `Mapped[str] = mapped_column(String(64))` | No | Normalized scope such as `federal`, `dod`, `hhs`, `sba`. |
| `cfr_title` | `Mapped[int | None] = mapped_column(Integer)` | Yes | CFR title number for regulation chunks; null for non-CFR sources. |
| `metadata_` | `Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=sa.text("'{}'::jsonb"))` | No | Flexible source-specific metadata such as `part`, `section`, `agency`, `omb_control_number`, `form_number`, `edition`, `aln`, `html_selector_path`, `table_rows`, or `ingest_job_id`. |
| `locator` | `Mapped[str | None] = mapped_column(String(255))` | Yes | Page/section/subheading locator. Required because the current private chunk model already relies on `locator` for citations. |
| `is_current` | `Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.true(), index=True)` | No | Denormalized current-version flag for cheap default filtering. Needed because `superseded_by is null` is not sufficient when a chunk disappears, a document is retired wholesale, or lineage is document-level. |

### Missing fields I am explicitly adding

1. `locator`
   - Missing from the proposed list, but the private model already needs it (`DocumentChunk.locator`) and the evidence path assumes locator-resolved citations.

2. `is_current`
   - Missing from the proposed list, but operationally necessary. Relying only on `effective_date` and `superseded_by` makes "current only" queries fragile when a section is removed, split, or superseded at the document level rather than one-to-one at the chunk level.

### Recommended `CorpusDocument` companion fields

The chunk schema is not enough by itself. The parent document needs first-class version and provenance fields:

| Field | Python / SQLAlchemy Type | Null? | Comment |
| --- | --- | --- | --- |
| `corpus_doc_id` | `Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)` | No | Global document-version identifier. |
| `authority` | `Mapped[str] = mapped_column(String(64), index=True)` | No | Source family such as `ecfr`, `govinfo`, `federal_register`, `grants_gov`, `irs`, `gsa_forms`, `sam_assistance_listings`. |
| `authority_doc_id` | `Mapped[str] = mapped_column(String(255))` | No | Stable upstream identifier such as CFR section path, OMB control number + edition, Grants.gov opportunity number, or ALN code. |
| `title` | `Mapped[str] = mapped_column(String(512))` | No | Canonical title for display and citation context. |
| `doc_type` | `Mapped[str] = mapped_column(String(16), index=True)` | No | Same enum family as chunk. |
| `source_url` | `Mapped[str] = mapped_column(String(2048))` | No | Canonical source URL for the document version. |
| `snapshot_uri` | `Mapped[str | None] = mapped_column(String(2048))` | Yes | Optional object-store snapshot of the exact bytes/HTML/PDF used for ingest, mirroring the private `Source.snapshot_uri` auditability pattern. |
| `content_hash` | `Mapped[str] = mapped_column(String(64), index=True)` | No | SHA-256 of the normalized full document. |
| `mime_type` | `Mapped[str | None] = mapped_column(String(255))` | Yes | Original source MIME type. |
| `citation_ref` | `Mapped[str] = mapped_column(String(255), index=True)` | No | Root citation such as `48 CFR Part 19` or `SF-424`. |
| `effective_date` | `Mapped[date | None] = mapped_column(Date, index=True)` | Yes | Date the document version became effective. |
| `published_date` | `Mapped[date | None] = mapped_column(Date, index=True)` | Yes | Upstream publication date when distinct from effective date. |
| `retrieved_at` | `Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())` | No | When CaptureOS fetched the source bytes. |
| `superseded_by` | `Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("corpus_documents.corpus_doc_id", ondelete="SET NULL"), index=True)` | Yes | Successor document version. |
| `jurisdiction` | `Mapped[str] = mapped_column(String(64), index=True)` | No | Same normalized scope used on chunks. |
| `cfr_title` | `Mapped[int | None] = mapped_column(Integer, index=True)` | Yes | CFR title number if applicable. |
| `metadata_` | `Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=sa.text("'{}'::jsonb"))` | No | Source-specific metadata for the full document. |
| `is_current` | `Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.true(), index=True)` | No | Cheap current-version filter at document scope. |

## Table Design

### Exact SQLAlchemy definitions

```python
from __future__ import annotations

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, TimestampMixin

EMBEDDING_DIM = 768


class CorpusDocument(TimestampMixin, Base):
    __tablename__ = "corpus_documents"
    __table_args__ = (
        UniqueConstraint("authority", "authority_doc_id"),
        Index("ix_corpus_documents_current_doc_type", "is_current", "doc_type"),
        Index("ix_corpus_documents_effective_date", "effective_date"),
        Index("ix_corpus_documents_jurisdiction", "jurisdiction"),
        Index("ix_corpus_documents_cfr_title", "cfr_title"),
    )

    corpus_doc_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Global document-version primary key.",
    )
    authority: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Source family: ecfr, govinfo, federal_register, grants_gov, irs, gsa_forms, sam_assistance_listings.",
    )
    authority_doc_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Stable upstream identifier for this authoritative document.",
    )
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Canonical title for display and citation context.",
    )
    doc_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
        comment="REGULATION, FORM, NOFO, or LISTING.",
    )
    source_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Canonical authoritative source URL for this document version.",
    )
    snapshot_uri: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="Immutable storage URI for the exact bytes or HTML captured at ingest time.",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 of normalized full-document content.",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Original source MIME type.",
    )
    citation_ref: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Root citation reference such as 48 CFR Part 19 or SF-424.",
    )
    effective_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Date the document version became effective.",
    )
    published_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Date the source published this version, if distinct from effective_date.",
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When CaptureOS fetched the source used for this version.",
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("corpus_documents.corpus_doc_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Successor corpus document version, if one exists.",
    )
    jurisdiction: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Normalized authority scope such as federal, dod, hhs, or sba.",
    )
    cfr_title: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="CFR title number when applicable.",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        comment="Source-specific document metadata such as agency, edition, OMB control number, ALN, or section map.",
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa.true(),
        index=True,
        comment="Server-controlled flag indicating the default current document version.",
    )

    chunks: Mapped[list["CorpusChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CorpusChunk(TimestampMixin, Base):
    __tablename__ = "corpus_chunks"
    __table_args__ = (
        UniqueConstraint("corpus_doc_id", "chunk_index"),
        UniqueConstraint("corpus_doc_id", "content_hash"),
        Index("ix_corpus_chunks_current_filters", "is_current", "doc_type", "jurisdiction", "cfr_title"),
        Index(
            "ix_corpus_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Global chunk-version primary key.",
    )
    corpus_doc_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("corpus_documents.corpus_doc_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent corpus document version.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Normalized retrieval text for this chunk.",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=True,
        comment="Gemini-compatible 768-dim embedding; nullable only during transient ingest failures.",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 of normalized chunk text.",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Zero-based order within the parent document version.",
    )
    doc_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
        comment="REGULATION, FORM, NOFO, or LISTING; duplicated from the parent for filter pushdown.",
    )
    source_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Authoritative URL for the source content backing this chunk.",
    )
    citation_ref: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Chunk-level citation anchor such as 48 CFR 52.219-8 or SF-424 Section 8.",
    )
    effective_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="When this chunk's text became effective.",
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("corpus_chunks.chunk_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Successor chunk version, if a like-for-like replacement exists.",
    )
    jurisdiction: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Normalized authority scope such as federal, dod, hhs, or sba.",
    )
    cfr_title: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="CFR title number when applicable.",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        comment="Chunk-specific metadata such as part, subpart, section path, field name, table rows, or opportunity section.",
    )
    locator: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Page, section, heading path, or field locator used for precise citations.",
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa.true(),
        index=True,
        comment="Server-controlled current-version flag for default retrieval filtering.",
    )

    document: Mapped[CorpusDocument] = relationship(back_populates="chunks")
```

### HNSW index DDL

```sql
CREATE INDEX ix_corpus_chunks_embedding
ON corpus_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Recommended supporting filter index:

```sql
CREATE INDEX ix_corpus_chunks_current_filters
ON corpus_chunks (is_current, doc_type, jurisdiction, cfr_title);
```

### How the global corpus coexists with `OrgScopedMixin` without weakening tenant isolation

1. Do not change `OrgScopedMixin`.
   - Leave `org_id NOT NULL` exactly as it is on `documents`, `document_chunks`, `sources`, `evidence_items`, `workflow_runs`, and every other tenant table.
   - Do not introduce nullable `org_id` to any existing tenant table.

2. Keep corpus data in physically separate tables.
   - `corpus_documents` and `corpus_chunks` are not tenant tables and do not inherit `OrgScopedMixin`.
   - They are never queried by tenant CRUD endpoints directly.
   - They are only readable through a corpus-aware retrieval service that has an authenticated caller and explicit scope selection.

3. Keep private and global foreign-key graphs separate.
   - Private chain stays: `Organization -> Document -> DocumentChunk -> Source -> EvidenceItem`.
   - Global chain becomes: `CorpusDocument -> CorpusChunk`.
   - Do not make `DocumentChunk` or `Document` polymorphic for global rows.

4. Bridge the graphs only through explicit read-only references.
   - Phase 1 should add nullable `Source.corpus_doc_id` and `Source.corpus_chunk_id` FKs, plus nullable `EvidenceItem.corpus_chunk_id` for dedupe and traceability.
   - Those reference fields point from an org-scoped row into the global corpus; the reverse never exists.
   - No corpus row should ever point back to an org row.

5. Keep writes to corpus tables off tenant APIs.
   - Tenant upload/paste routes continue to write only `documents` and `document_chunks`.
   - Corpus writes happen only through worker/admin ingestion jobs, ideally under a dedicated corpus ingestion workflow type.

6. Use explicit retrieval scopes, not implicit widening.
   - Existing private-only callers should keep their current behavior by default.
   - Corpus-aware callers must pass `scopes={"private", "global"}` or `scopes={"global"}` explicitly.

### Migration strategy

1. Add new enums.
   - Add `CorpusDocType` to `models/enums.py` as string values to match the repo's current enum strategy.

2. Add new models, do not edit old tenant columns for this step.
   - Create `models/corpus.py`.
   - Import the models in `models/__init__.py`.

3. Add a dedicated Alembic migration.
   - Create `corpus_documents` and `corpus_chunks`.
   - Create the HNSW index and the filter indexes.
   - Do not touch `document_chunks.org_id`, `documents.org_id`, or `sources.org_id`.

4. Bridge citations in a second migration.
   - Add nullable `corpus_doc_id` and `corpus_chunk_id` to `sources`.
   - Add nullable `corpus_chunk_id` to `evidence_items`.
   - Add check constraints later if desired to enforce "exactly one of `document_chunk_id` or `corpus_chunk_id` for materialized evidence".

5. Roll retrieval code after schema is present.
   - Add the new retrieval envelope and corpus search path.
   - Keep the old `retrieve_relevant_chunks()` function for private-only callers during the transition, then fold callers over.

### Foreign-key implications

- `EvidenceItem.document_chunk_id -> document_chunks.id` cannot cite corpus rows today. That is a real schema limitation, not a theoretical one.
- Because `Source` is org-scoped, a corpus citation must be represented as an org-scoped reference row that points at `corpus_documents` / `corpus_chunks`; otherwise `EvidenceItem.source_id` breaks.
- The reverse direction must remain impossible:
  - no `corpus_*` table should reference `organizations`;
  - no `corpus_*` row should be mutated by tenant routes;
  - no query that starts from corpus tables should ever be able to discover org-private rows.

## Retrieval Invariants + Test Stubs

### Invariant 1

`org_id = X` can never retrieve a private `DocumentChunk` whose `org_id = Y`.

- Enforced in code:
  - Keep the existing private search predicate from `ingestion/retrieval.py`: `DocumentChunk.org_id == org_id`.
  - Put that logic in a dedicated `private_search()` helper and do not reuse corpus filters there.
- Tested with:

```python
async def test_private_scope_never_returns_other_org_chunks(client: AsyncClient) -> None:
    """A private-scope retrieval for org A must never surface org B chunks, even if B has a closer vector match."""
    # Arrange: org A and org B each ingest distinct documents; org B's text is the stronger semantic match.
    # Act: call the corpus-aware retrieval endpoint or service with scopes={"private"} as org A.
    # Assert:
    assert all(item["scope"] == "private" for item in results)
    assert all(item["orgId"] == org_a for item in results)
    assert not any(item["orgId"] == org_b for item in results)
```

### Invariant 2

Global corpus chunks have no `org_id` and are readable by any authenticated tenant, but only as `scope=global`.

- Enforced in code:
  - `CorpusChunk` has no `org_id` column.
  - Global search reads only `CorpusChunk` rows and tags every result `scope="global"`.
- Tested with:

```python
async def test_global_scope_returns_corpus_rows_for_any_authenticated_org(client: AsyncClient) -> None:
    """Any authenticated org may read global corpus chunks, and the result envelope must mark them as global."""
    # Arrange: seed one corpus document and two orgs.
    # Act: query from both orgs with scopes={"global"}.
    # Assert:
    assert results_a
    assert results_b
    assert {item["chunkId"] for item in results_a} == {item["chunkId"] for item in results_b}
    assert all(item["scope"] == "global" for item in results_a + results_b)
```

### Invariant 3

Global retrieval must never materialize org-private data into corpus tables.

- Enforced in code:
  - Corpus ingest code writes only `corpus_documents` and `corpus_chunks`.
  - Retrieval code never upserts into corpus tables.
  - Materialization writes only org-scoped `Source` / `EvidenceItem` references.
- Tested with:

```python
async def test_corpus_retrieval_materializes_only_org_scoped_references(client: AsyncClient) -> None:
    """Materializing a corpus hit creates org-scoped citation references and leaves corpus text stored only once."""
    # Arrange: seed one corpus chunk and run evidence acquisition for one org.
    # Act: materialize the corpus hit into evidence.
    # Assert:
    assert materialized_source["orgId"] == org_id
    assert materialized_source["corpusChunkId"] == corpus_chunk_id
    assert materialized_source["documentId"] is None
    assert materialized_evidence["sourceId"] == materialized_source["id"]
    assert materialized_evidence["corpusChunkId"] == corpus_chunk_id
```

### Invariant 4

The default corpus filter is current-only; superseded chunks must not appear unless historical retrieval is explicitly requested.

- Enforced in code:
  - Global search always adds `CorpusChunk.is_current.is_(True)` unless `filters.include_historical` is true.
  - Supersession updates flip `is_current` false on old rows.
- Tested with:

```python
async def test_global_retrieval_defaults_to_current_chunks_only(client: AsyncClient) -> None:
    """Superseded corpus chunks are excluded from default retrieval and appear only when history is explicitly requested."""
    # Arrange: seed one superseded chunk and one current successor for the same citation_ref.
    # Act: query once with default filters and once with include_historical=True.
    # Assert:
    assert current_chunk_id in default_chunk_ids
    assert superseded_chunk_id not in default_chunk_ids
    assert superseded_chunk_id in historical_chunk_ids
```

### Invariant 5

Private and global searches remain provenance-distinct even when merged into one answer set.

- Enforced in code:
  - Retrieval returns a typed envelope such as `RetrievedChunk(scope, chunk_id, source_row_id, citation_ref, distance, text, metadata_)`.
  - Merge happens after the per-scope searches complete.
- Tested with:

```python
async def test_retrieve_merges_private_and_global_results_without_losing_scope(client: AsyncClient) -> None:
    """A mixed-scope retrieval may return both private and global chunks, but each result must preserve its provenance."""
    # Arrange: seed one matching private chunk and one matching corpus chunk.
    # Act: query with scopes={"private", "global"}.
    # Assert:
    scopes = {item["scope"] for item in results}
    assert scopes == {"private", "global"}
    assert all(item["citationRef"] for item in results)
    assert all(item["sourceUrl"] for item in results)
```

### Invariant 6

Corpus-aware retrieval must not widen access control for tenant endpoints; cross-org requests still return `404`, not `403`.

- Enforced in code:
  - Membership checks stay at the API boundary exactly as they are today.
  - Retrieval only runs after org membership is resolved.
- Tested with:

```python
async def test_corpus_features_do_not_change_cross_org_api_isolation(client: AsyncClient) -> None:
    """Adding global corpus retrieval must not change the product's existing 404-not-403 cross-org behavior."""
    # Arrange: org A owns a filing or retrieval endpoint target; user B belongs to org B only.
    # Act: user B calls org A's retrieval-backed endpoint.
    # Assert:
    assert resp.status_code == 404
```

### Invariant 7

Corpus citation references are read-only and deduped per org.

- Enforced in code:
  - Add a uniqueness rule such as `UniqueConstraint("org_id", "corpus_chunk_id")` on `sources` once corpus reference columns are added.
  - Materialization path first looks up an existing org-scoped corpus `Source` reference before inserting.
- Tested with:

```python
async def test_corpus_source_reference_is_reused_within_an_org(client: AsyncClient) -> None:
    """Repeated citations of the same corpus chunk in one org should reuse one Source reference row, not fan out duplicates."""
    # Arrange: same org materializes the same corpus chunk twice.
    # Act: run the materialization path twice.
    # Assert:
    assert first_source_id == second_source_id
    assert source_count_for_org_and_chunk == 1
```

### Invariant 8

Chunking strategy is doc-type aware and preserves citation granularity.

- Enforced in code:
  - Introduce a dispatcher such as `chunk_corpus_document(parsed, doc_type, metadata)` that routes to `chunk_regulation`, `chunk_form`, `chunk_nofo`, or `chunk_listing`.
  - Each chunker must emit `citation_ref` and `locator`.
- Tested with:

```python
async def test_doc_type_chunkers_emit_citation_ref_and_locator() -> None:
    """Every corpus chunker must emit citation-ready metadata, not just free text."""
    # Arrange: one parsed regulation, one parsed form, one parsed NOFO.
    # Act: chunk each through the doc-type dispatcher.
    # Assert:
    assert all(chunk.citation_ref for chunk in regulation_chunks)
    assert all(chunk.locator for chunk in regulation_chunks)
    assert all(chunk.metadata_.get("form_number") for chunk in form_chunks)
    assert all(chunk.metadata_.get("section_heading") for chunk in nofo_chunks)
```

## Phase-1 Build Order

1. Introduce corpus enums and models.
   - What gets built: `CorpusDocType`, `CorpusDocument`, `CorpusChunk`.
   - Files change: `apps/api/captureos/models/enums.py`, `apps/api/captureos/models/corpus.py`, `apps/api/captureos/models/__init__.py`.
   - Done-done: metadata imports cleanly; `Base.metadata.create_all()` contains the new corpus tables without touching existing tenant columns.

2. Add the corpus schema migration.
   - What gets built: Alembic migration for `corpus_documents`, `corpus_chunks`, HNSW index, and filter indexes.
   - Files change: `apps/api/migrations/versions/<new_revision>_add_global_corpus_tables.py`.
   - Done-done: a fresh test database creates both corpus tables and indexes; existing tests still create `document_chunks` unchanged.

3. Bridge org-scoped citations to corpus rows.
   - What gets built: nullable corpus reference columns on `Source` and `EvidenceItem`, plus supporting uniqueness/indexes.
   - Files change: `apps/api/captureos/models/evidence.py`, `apps/api/migrations/versions/<new_revision>_add_corpus_reference_columns.py`.
   - Done-done: one org can cite a corpus chunk through a `Source` row without duplicating corpus text, and the schema can dedupe repeated citations of the same corpus chunk inside an org.

4. Refactor chunking into a strategy dispatcher.
   - What gets built: keep the existing generic splitter, add `chunk_corpus_document()` plus regulation/form/NOFO/listing chunker helpers.
   - Files change: `apps/api/captureos/ingestion/chunking.py`, likely new `apps/api/captureos/ingestion/corpus_chunking.py` if you want cleaner separation.
   - Done-done: unit tests show regulations emit section-aware chunks, forms emit synopsis + field/instruction chunks, and NOFOs emit sectioned chunks with citation metadata.

5. Extract shared ingest helpers and add corpus ingest service.
   - What gets built: shared parse/embed primitives plus a new corpus ingest path that writes `CorpusDocument` / `CorpusChunk` instead of `Document` / `DocumentChunk`.
   - Files change: `apps/api/captureos/ingestion/service.py`, new `apps/api/captureos/ingestion/corpus_service.py`, possibly `apps/api/captureos/ingestion/__init__.py`.
   - Done-done: tenant-private ingestion still behaves exactly as today, and a corpus ingest job can create global rows using the same Gemini/mock embeddings seam.

6. Add source adapters for the Phase-1 corpus.
   - What gets built: adapters or fetch clients for eCFR/GovInfo/Federal Register signals, IRS predictable PDFs, GSA/OPM forms, and SAM Assistance Listings. Firecrawl remains optional only for scrape-only sources.
   - Files change: new files under `apps/api/captureos/sources/` or a new `apps/api/captureos/corpus_sources/` package; `apps/api/captureos/config.py` for any new base URLs or API keys.
   - Done-done: each source can produce normalized document payloads ready for corpus ingest, and no API-backed source depends on Firecrawl.

7. Implement corpus-aware retrieval.
   - What gets built: `retrieve(query_text, org_id, scopes, filters, k_private, k_global)` returning a provenance-tagged result envelope.
   - Files change: `apps/api/captureos/ingestion/retrieval.py`, new types module if desired.
   - Done-done: private-only search still returns only org chunks; global-only search returns only corpus chunks; mixed search merges both without losing scope metadata.

8. Update evidence acquisition to materialize corpus citations safely.
   - What gets built: corpus-hit materialization into org-scoped `Source` and `EvidenceItem` rows, with dedupe on `corpus_chunk_id`.
   - Files change: `apps/api/captureos/services/evidence.py`, possibly `apps/api/captureos/services/compliance.py` and `apps/api/captureos/services/packaging.py` if they render citations.
   - Done-done: an answer can cite both private and global evidence without cross-org leakage and without duplicating corpus text into tenant-private tables.

9. Add tests for isolation, retrieval, chunking, and citation materialization.
   - What gets built: new `apps/api/tests/test_corpus_retrieval.py`, likely `test_corpus_ingestion.py`.
   - Files change: new test files; maybe `tests/conftest.py` if you add helper fixtures.
   - Done-done: invariants in the section above are covered, and existing org-isolation tests continue to pass unchanged.

10. Add a minimal corpus ingest workflow entrypoint.
   - What gets built: admin or internal worker entrypoint to run corpus backfills without exposing tenant APIs.
   - Files change: `apps/api/captureos/models/enums.py` for a new workflow type if desired, `apps/api/captureos/workflows/pipelines.py`, `apps/api/captureos/workflows/runner.py`, and an internal job trigger.
   - Done-done: engineers can backfill the corpus in the existing worker infrastructure, but no tenant-facing route can mutate the global corpus directly.

## Biggest Risk and Mitigation

The single biggest architectural risk is accidental weakening of tenant isolation while adding a shared retrieval domain.

Why this is the biggest risk:

- The current codebase has a very strong and simple invariant: every evidence-bearing table is org-scoped via `OrgScopedMixin`, and `retrieve_relevant_chunks()` only reads rows for one `org_id`.
- A sloppy shared-corpus implementation usually fails by overloading the private tables, making `org_id` nullable, or hiding provenance behind one generic vector table.
- That kind of shortcut would create exactly the class of leakage bug the current design has so far avoided.

Concrete mitigation plan:

1. Keep corpus data in separate physical tables with no `org_id`.
2. Never make `org_id` nullable on existing tenant tables.
3. Search private and global indexes separately, then merge results with explicit `scope`.
4. Bridge corpus citations into org-scoped `Source` / `EvidenceItem` rows lazily and one-directionally.
5. Preserve the API boundary membership checks that currently return `404` for cross-org access.
6. Add the retrieval invariants above as tests before enabling mixed-scope retrieval in any agent path.
7. Roll out mixed-scope retrieval behind a feature flag so private-only behavior remains the fallback until the invariants are proven in CI and staging.
