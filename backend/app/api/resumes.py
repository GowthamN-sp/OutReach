import io
from pathlib import PureWindowsPath
from urllib.parse import quote

import pdfplumber
from fastapi import APIRouter, Form, HTTPException, Response, UploadFile
from sqlalchemy import select, update

from ..db import lock_user, owned
from ..models import Campaign, Resume
from ..security import DB, Current

router = APIRouter()


def metadata(row: Resume):
    return {
        key: getattr(row, key)
        for key in ("id", "name", "filename", "is_default", "size", "created_at")
    }


@router.get("/resumes")
def listing(auth: Current, db: DB):
    return [
        metadata(row)
        for row in db.scalars(
            select(Resume)
            .where(Resume.user_id == auth.user_id)
            .order_by(Resume.id.desc())
        )
    ]


@router.post("/resumes", status_code=201)
async def upload(
    file: UploadFile, auth: Current, db: DB, name: str = Form("", max_length=140)
):
    content = await file.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(413, "PDF maximum is 8 MB")
    try:
        if not content.startswith(b"%PDF-"):
            raise ValueError()
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not pdf.pages:
                raise ValueError()
    except Exception:  # noqa: BLE001 - third-party document parsers raise varied errors
        raise HTTPException(400, "Choose a valid, unencrypted PDF")
    filename = PureWindowsPath(file.filename or "resume.pdf").name[:140]
    lock_user(db, auth.user_id)
    first = (
        db.scalar(select(Resume.id).where(Resume.user_id == auth.user_id).limit(1))
        is None
    )
    row = Resume(
        user_id=auth.user_id,
        name=name.strip() or filename,
        filename=filename,
        content=content,
        size=len(content),
        is_default=first,
    )
    db.add(row)
    db.commit()
    return metadata(row)


@router.get("/resumes/{rid}/file")
def content(rid: int, auth: Current, db: DB, download: bool = False):
    row = owned(db, Resume, auth.user_id, rid)
    disposition = "attachment" if download else "inline"
    return Response(
        row.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(row.filename, safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/resumes/{rid}/default")
def default(rid: int, auth: Current, db: DB):
    lock_user(db, auth.user_id)
    row = owned(db, Resume, auth.user_id, rid)
    db.execute(
        update(Resume).where(Resume.user_id == auth.user_id).values(is_default=False)
    )
    row.is_default = True
    db.commit()
    return metadata(row)


@router.delete("/resumes/{rid}")
def remove(rid: int, auth: Current, db: DB):
    lock_user(db, auth.user_id)
    row = owned(db, Resume, auth.user_id, rid)
    if db.scalar(
        select(Campaign.id)
        .where(Campaign.user_id == auth.user_id, Campaign.resume_id == rid)
        .limit(1)
    ):
        raise HTTPException(409, "This resume is attached to a saved campaign")
    was_default = row.is_default
    db.delete(row)
    db.flush()
    if was_default:
        replacement = db.scalar(
            select(Resume)
            .where(Resume.user_id == auth.user_id)
            .order_by(Resume.id.desc())
            .limit(1)
        )
        if replacement:
            replacement.is_default = True
    db.commit()
    return {"ok": True}
