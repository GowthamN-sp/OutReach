import io
import zipfile

from fastapi import APIRouter, HTTPException, Query, UploadFile
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError

from ..db import lock_user, owned
from ..models import Contact, Delivery
from ..schemas import ContactIn, ImportIn
from ..security import DB, Current
from ..services.importer import normalize_import, parse_import

router = APIRouter()


@router.get("/contacts")
def contacts(
    auth: Current,
    db: DB,
    search: str = "",
    status: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    stmt = select(Contact).where(Contact.user_id == auth.user_id)
    if search:
        from sqlalchemy import or_

        stmt = stmt.where(
            or_(
                *(
                    col.icontains(search, autoescape=True)
                    for col in (Contact.name, Contact.email, Contact.company)
                )
            )
        )
    if status:
        stmt = stmt.where(Contact.status == status)
    return db.scalars(
        stmt.order_by(Contact.id.desc()).offset(offset).limit(limit)
    ).all()


def save(db, contact):
    db.add(contact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already exists in your contacts")
    return {"id": contact.id}


@router.post("/contacts", status_code=201)
def add(data: ContactIn, auth: Current, db: DB):
    return save(db, Contact(user_id=auth.user_id, **data.model_dump()))


@router.put("/contacts/{contact_id}")
def edit(contact_id: int, data: ContactIn, auth: Current, db: DB):
    contact = owned(db, Contact, auth.user_id, contact_id)
    for key, value in data.model_dump().items():
        setattr(contact, key, value)
    return save(db, contact)


@router.delete("/contacts/{contact_id}")
def remove(contact_id: int, auth: Current, db: DB):
    contact = owned(db, Contact, auth.user_id, contact_id)
    if db.scalar(
        select(
            exists().where(
                Delivery.user_id == auth.user_id, Delivery.contact_id == contact_id
            )
        )
    ):
        raise HTTPException(409, "Contacts with send history must be retained")
    db.delete(contact)
    db.commit()
    return {"ok": True}


@router.post("/import/preview")
async def preview(file: UploadFile, auth: Current):
    content = await file.read(7 * 1024 * 1024 + 1)
    if len(content) > 7 * 1024 * 1024:
        raise HTTPException(413, "Import files must be under 7 MB")
    try:
        if (file.filename or "").lower().endswith(".xlsx"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(f.file_size for f in archive.infolist()) > 48 * 1024 * 1024:
                    raise HTTPException(413, "Workbook is too large when expanded")
        raw = parse_import(file.filename or "", content)
        if len(raw) > 2000:
            raise HTTPException(400, "Split files into batches of up to 1,000 contacts")
        records = normalize_import(raw)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - third-party document parsers raise varied errors
        raise HTTPException(400, "Could not read this document")
    if len(records) > 1000:
        raise HTTPException(400, "Split imports into files of up to 1,000 contacts")
    return {"contacts": records, "total": len(records)}


@router.post("/import/commit")
def commit(data: ImportIn, auth: Current, db: DB):
    lock_user(db, auth.user_id)
    added = 0
    for row in data.contacts:
        try:
            with db.begin_nested():
                db.add(
                    Contact(
                        user_id=auth.user_id,
                        **(row.model_dump() | {"source": "Import"}),
                    )
                )
                db.flush()
            added += 1
        except IntegrityError:
            continue
    db.commit()
    return {"added": added, "skipped": len(data.contacts) - added}
