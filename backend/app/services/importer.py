import csv
import io
import re
from pathlib import Path

import pdfplumber
from fastapi import HTTPException
from openpyxl import load_workbook


def valid_email(email):
    return bool(re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", email.strip()))


def cleanstr(x):
    return str(x or "").strip()[:300]


def parse_import(filename, content):
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        rd = csv.DictReader(io.StringIO(text))
        return [dict(x) for _, x in zip(range(2001), rd)]
    if ext == ".xlsx":
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            sheet = wb.active
            it = sheet.iter_rows(values_only=True)
            headers = [cleanstr(x) for x in next(it, [])]
            return [dict(zip(headers, values)) for _, values in zip(range(2001), it)]
        finally:
            wb.close()
    if ext == ".pdf":
        # A PDF cannot reliably encode a roster table. Extract addresses, review each before importing.
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if len(pdf.pages) > 25:
                raise HTTPException(400, "Split PDFs into files of up to 25 pages")
            tables = []
            for page in pdf.pages:
                for table in page.extract_tables():
                    if table and table[0]:
                        tables.extend(
                            dict(zip(table[0], values)) for values in table[1:]
                        )
            tabular = normalize_import(tables, keep_flagged=True)
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        unique = list(
            dict.fromkeys(
                re.findall(
                    r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])", text
                )
            )
        )
        return [
            {"email": x, "name": "", "company": "", "role": ""}
            for x in unique
            if x.lower() not in {row["email"] for row in tabular}
        ] + tabular
    raise HTTPException(400, "Use .csv, .xlsx, or .pdf")


def normalize_import(raw, keep_flagged=False):
    normalized = []
    for item in raw:
        x = {
            re.sub(r"[^a-z]", "", str(k).lower()): cleanstr(v) for k, v in item.items()
        }
        email = next(
            (
                x[k]
                for k in (
                    "email",
                    "emailaddress",
                    "mail",
                    "emailid",
                    "emailids",
                    "recruiteremail",
                    "hremail",
                )
                if x.get(k)
            ),
            "",
        )
        if not email:
            email = next((v for v in x.values() if valid_email(v)), "")
        if not valid_email(email) and not keep_flagged:
            continue
        name = next(
            (
                x[k]
                for k in ("name", "fullname", "recruitername", "contactname", "hrname")
                if x.get(k)
            ),
            "",
        )
        company = next(
            (
                x[k]
                for k in ("company", "companyname", "organization", "organisation")
                if x.get(k)
            ),
            "",
        )
        role = next((x[k] for k in ("role", "jobtitle", "position") if x.get(k)), "")
        normalized.append(
            {
                "email": email.lower(),
                "name": name,
                "company": company,
                "role": role,
                "source": "Import",
            }
        )
    return normalized if keep_flagged else list({x["email"]: x for x in normalized}.values())
