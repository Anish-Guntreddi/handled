"""Document routes (PRD §9.2): initiate-upload, upload sink, ingest, paste, list/get.

Uploads are org-scoped: the storage key is always prefixed with the caller's org id, and
the blob routes only ever touch keys under that prefix (CON-5 + path-traversal defense)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Request, Response, status
from sqlalchemy import func, select

from captureos.audit import record_event
from captureos.config import StorageProviderName, get_settings
from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
from captureos.core.errors import AppError, NotFoundError
from captureos.models.documents import Document, DocumentChunk
from captureos.models.enums import ActorType, DocumentSourceKind, ParseStatus, WorkflowType
from captureos.models.workflow import WorkflowRun
from captureos.providers import get_storage
from captureos.schemas.document import (
    DocumentResponse,
    IngestRequest,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PasteRequest,
)
from captureos.schemas.workflow import WorkflowRunCreated
from captureos.workflows.dispatch import schedule_workflow

router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])
blobs_router = APIRouter(prefix="/orgs/{org_id}/blobs", tags=["documents"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB cap to prevent memory-exhaustion DoS


async def _chunk_count(session: SessionDep, document_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
    ).scalar_one()


def _doc_response(doc: Document, chunk_count: int) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        mime_type=doc.mime_type,
        source_kind=doc.source_kind,
        parse_status=doc.parse_status,
        chunk_count=chunk_count,
        page_count=doc.page_count,
    )


async def _get_doc_or_404(
    session: SessionDep, org_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    doc = (
        await session.execute(
            select(Document).where(Document.id == document_id, Document.org_id == org_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")
    return doc


@router.post(":initiate-upload", response_model=InitiateUploadResponse)
async def initiate_upload(
    body: InitiateUploadRequest, ctx: OrgEditor, session: SessionDep
) -> InitiateUploadResponse:
    doc_id = uuid.uuid4()
    rel_key = f"{doc_id}/{body.filename}"
    full_key = f"{ctx.org_id}/{rel_key}"
    presigned = get_storage().presign_upload(full_key, content_type=body.mime_type)

    doc = Document(
        id=doc_id,
        org_id=ctx.org_id,
        filename=body.filename,
        mime_type=body.mime_type,
        content_hash=f"pending:{doc_id}",  # real hash assigned at ingest
        source_kind=DocumentSourceKind.upload.value,
        parse_status=ParseStatus.pending.value,
        storage_uri=presigned.storage_uri,
    )
    session.add(doc)
    await session.flush()

    # Local storage uploads go through our org-scoped route; GCS uses the signed URL.
    if get_settings().storage_provider is StorageProviderName.local:
        upload_url = f"/api/v1/orgs/{ctx.org_id}/blobs/{rel_key}"
    else:
        upload_url = presigned.url

    await record_event(
        "document.upload_initiated",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"document_id": str(doc_id), "filename": body.filename},
    )
    return InitiateUploadResponse(
        document_id=doc_id,
        upload_url=upload_url,
        method=presigned.method,
        storage_uri=presigned.storage_uri,
    )


@blobs_router.put("/{rel_key:path}")
async def put_blob(request: Request, ctx: OrgEditor, rel_key: str) -> dict:
    # Stream with a hard cap so an unbounded body can't exhaust memory (NFR-2).
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > _MAX_UPLOAD_BYTES:
            raise AppError(
                "Upload exceeds the 25 MB limit",
                code="payload_too_large",
                status_code=413,
            )
    # Key is always re-prefixed with the caller's org id; LocalStorage rejects traversal.
    key = f"{ctx.org_id}/{rel_key}"
    blob = await get_storage().put(
        key, bytes(buffer), content_type=request.headers.get("content-type")
    )
    return {"ok": True, "size": blob.size, "storageUri": blob.uri}


@blobs_router.get("/{rel_key:path}")
async def get_blob(ctx: OrgViewer, rel_key: str) -> Response:
    storage = get_storage()
    uri = f"local://{ctx.org_id}/{rel_key}"
    if not await storage.exists(uri):
        raise NotFoundError("Blob not found")
    data = await storage.get(uri)
    return Response(content=data, media_type="application/octet-stream")


@router.post(
    "/{document_id}:ingest", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
)
async def ingest_document(
    body: IngestRequest,
    ctx: OrgEditor,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    document_id: uuid.UUID,
) -> WorkflowRunCreated:
    await _get_doc_or_404(session, ctx.org_id, document_id)
    params: dict = {"document_id": str(document_id)}
    if body.raw_text is not None:
        params["raw_text"] = body.raw_text
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.document_ingest.value,
        status="queued",
        input_params=params,
    )
    session.add(run)
    await session.commit()  # durably persist before dispatching to the worker
    schedule_workflow(background_tasks, run.id)
    return WorkflowRunCreated(workflow_run_id=run.id)


@router.post(":paste", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def paste_document(
    body: PasteRequest, ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks
) -> WorkflowRunCreated:
    """Ingest pasted solicitation text with no file upload (FR-DI-3)."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        org_id=ctx.org_id,
        filename=body.filename,
        mime_type="text/plain",
        content_hash=f"pending:{doc_id}",
        source_kind=DocumentSourceKind.paste.value,
        parse_status=ParseStatus.pending.value,
    )
    session.add(doc)
    await session.flush()
    run = WorkflowRun(
        org_id=ctx.org_id,
        type=WorkflowType.document_ingest.value,
        status="queued",
        input_params={"document_id": str(doc_id), "raw_text": body.raw_text},
    )
    session.add(run)
    await session.commit()  # commit doc + run before dispatching to the worker
    schedule_workflow(background_tasks, run.id)
    return WorkflowRunCreated(workflow_run_id=run.id)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(ctx: OrgViewer, session: SessionDep) -> list[DocumentResponse]:
    docs = (
        (
            await session.execute(
                select(Document)
                .where(Document.org_id == ctx.org_id)
                .order_by(Document.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out: list[DocumentResponse] = []
    for doc in docs:
        out.append(_doc_response(doc, await _chunk_count(session, doc.id)))
    return out


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    ctx: OrgViewer, session: SessionDep, document_id: uuid.UUID
) -> DocumentResponse:
    doc = await _get_doc_or_404(session, ctx.org_id, document_id)
    return _doc_response(doc, await _chunk_count(session, doc.id))
