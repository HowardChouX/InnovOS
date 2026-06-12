import json, os, shutil
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/patents", tags=["admin-patent-db"])

# PDF 存储目录
PATENT_PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "storage", "patents")
os.makedirs(PATENT_PDF_DIR, exist_ok=True)


class PatentCreate(BaseModel):
    title: str
    abstract: str = ""
    applicants: list[str] = []
    inventors: list[str] = []
    filing_date: str = ""
    publication_date: str = ""
    patent_number: str = ""
    publication_number: str = ""
    priority_number: str = ""
    ipc_codes: list[str] = []
    claims: str = ""
    description: str = ""


class PatentUpdate(PatentCreate):
    pass


def row_to_patent(r):
    return {
        "id": str(r["id"]),
        "title": r["title"],
        "abstract": r["abstract"],
        "applicants": json.loads(r["applicants"]) if isinstance(r["applicants"], str) else r["applicants"],
        "inventors": json.loads(r["inventors"]) if isinstance(r["inventors"], str) else r["inventors"],
        "filingDate": r["filing_date"],
        "publicationDate": r["publication_date"],
        "patentNumber": r["patent_number"],
        "publicationNumber": r["publication_number"],
        "priorityNumber": r["priority_number"],
        "ipcCodes": json.loads(r["ipc_codes"]) if isinstance(r["ipc_codes"], str) else r["ipc_codes"],
        "claims": r["claims"],
        "description": r["description"],
        "createdAt": r["created_at"],
    }


@router.get("")
def list_patents(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = "created_at",
    order: str = "desc",
    user: dict = Depends(require_admin),
):
    db = get_db()

    conditions = []
    params = []
    if q:
        conditions.append("(title LIKE ? OR patent_number LIKE ? OR applicants LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    row = db.execute(f"SELECT COUNT(*) FROM patents {where}", params).fetchone()
    count = row[0] if row else 0

    order_col = "created_at"
    if sort_by in ("title", "filing_date", "patent_number"):
        order_col = sort_by
    order_dir = "DESC" if order == "desc" else "ASC"
    offset = (page - 1) * page_size

    rows = db.execute(
        f"SELECT * FROM patents {where} ORDER BY {order_col} {order_dir} LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()

    return {
        "data": [row_to_patent(r) for r in rows],
        "total": count,
        "page": page,
        "pageSize": page_size,
    }


@router.post("")
def create_patent(body: PatentCreate, user: dict = Depends(require_admin)):
    db = get_db()
    if not db:
        raise HTTPException(503, "数据库未连接")
    cur = db.execute(
        """INSERT INTO patents (title, abstract, applicants, inventors, filing_date,
           publication_date, patent_number, publication_number, priority_number,
           ipc_codes, claims, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           RETURNING id""",
        [
            body.title, body.abstract,
            json.dumps(body.applicants, ensure_ascii=False),
            json.dumps(body.inventors, ensure_ascii=False),
            body.filing_date, body.publication_date,
            body.patent_number, body.publication_number, body.priority_number,
            json.dumps(body.ipc_codes, ensure_ascii=False),
            body.claims, body.description,
        ],
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(500, "创建失败")
    row_id = row["id"]
    db.commit()
    patent = db.execute("SELECT * FROM patents WHERE id = ?", [row_id]).fetchone()
    return row_to_patent(patent)


@router.put("/{patent_id}")
def update_patent(patent_id: int, body: PatentUpdate, user: dict = Depends(require_admin)):
    db = get_db()
    existing = db.execute("SELECT id FROM patents WHERE id = ?", [patent_id]).fetchone()
    if not existing:
        raise HTTPException(404, "专利不存在")

    db.execute(
        """UPDATE patents SET title=?, abstract=?, applicants=?, inventors=?,
           filing_date=?, publication_date=?, patent_number=?, publication_number=?,
           priority_number=?, ipc_codes=?, claims=?, description=?
           WHERE id=?""",
        [
            body.title, body.abstract,
            json.dumps(body.applicants, ensure_ascii=False),
            json.dumps(body.inventors, ensure_ascii=False),
            body.filing_date, body.publication_date,
            body.patent_number, body.publication_number, body.priority_number,
            json.dumps(body.ipc_codes, ensure_ascii=False),
            body.claims, body.description,
            patent_id,
        ],
    )
    db.commit()
    patent = db.execute("SELECT * FROM patents WHERE id = ?", [patent_id]).fetchone()
    return row_to_patent(patent)


@router.delete("/{patent_id}")
def delete_patent(patent_id: int, user: dict = Depends(require_admin)):
    db = get_db()
    existing = db.execute("SELECT id FROM patents WHERE id = ?", [patent_id]).fetchone()
    if not existing:
        raise HTTPException(404, "专利不存在")
    db.execute("DELETE FROM patents WHERE id = ?", [patent_id])
    db.commit()
    return {"message": "删除成功"}


@router.post("/import")
def import_patents(patents: list[PatentCreate], user: dict = Depends(require_admin)):
    """批量导入专利"""
    db = get_db()
    imported = 0
    for p in patents:
        db.execute(
            """INSERT INTO patents (title, abstract, applicants, inventors, filing_date,
               publication_date, patent_number, publication_number, priority_number,
               ipc_codes, claims, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                p.title, p.abstract,
                json.dumps(p.applicants, ensure_ascii=False),
                json.dumps(p.inventors, ensure_ascii=False),
                p.filing_date, p.publication_date,
                p.patent_number, p.publication_number, p.priority_number,
                json.dumps(p.ipc_codes, ensure_ascii=False),
                p.claims, p.description,
            ],
        )
        imported += 1
    db.commit()
    return {"message": f"成功导入 {imported} 条专利", "count": imported}


@router.post("/upload")
async def upload_patent_pdf(
    file: UploadFile = File(...),
    mode: str = Form("pdfminer"),
    user: dict = Depends(require_admin),
):
    """上传专利 PDF → 提取文字 → 结构化字段 → 存入数据库

    mode: pdfminer | paddleocr | deepseek
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    # 保存 PDF
    safe_name = f"{user['id']}_{int(__import__('time').time())}_{file.filename}"
    pdf_path = os.path.join(PATENT_PDF_DIR, safe_name)
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 提取文字
    from app.algorithm.file_parser import parse_file
    parsed = parse_file(pdf_path, mode=mode)

    # 提取结构化字段
    from app.algorithm.patent_extractor import extract_patent_fields
    fields = extract_patent_fields(parsed["content"])
    fields.pop("_missing", None)

    # 写入数据库
    db = get_db()
    if not db:
        raise HTTPException(503, "数据库未连接")
    cur = db.execute(
        """INSERT INTO patents (title, abstract, applicants, inventors, filing_date,
           publication_date, patent_number, publication_number, priority_number,
           ipc_codes, claims, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           RETURNING id""",
        [
            fields.get("title", file.filename) or file.filename,
            fields.get("abstract", "") or "",
            json.dumps(fields.get("applicants", []), ensure_ascii=False),
            json.dumps(fields.get("inventors", []), ensure_ascii=False),
            fields.get("filing_date", "") or "",
            fields.get("publication_date", "") or "",
            fields.get("patent_number", "") or "",
            fields.get("publication_number", "") or "",
            fields.get("priority_number", "") or "",
            json.dumps(fields.get("ipc_codes", []), ensure_ascii=False),
            fields.get("claims", "") or "",
            fields.get("description", "") or "",
        ],
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(500, "创建失败")
    row_id = row["id"]
    db.commit()
    patent = db.execute("SELECT * FROM patents WHERE id = ?", [row_id]).fetchone()

    # 异步触发 RAG 索引
    import asyncio
    content_for_index = f"{fields.get('title', '')}\n{fields.get('abstract', '')}\n{fields.get('claims', '')}\n{fields.get('description', '')}"
    if len(content_for_index) > 100:
        asyncio.create_task(_index_patent_vectors(row_id, content_for_index))

    return {
        **row_to_patent(patent),
        "mode": mode,
        "extractSource": parsed["type"],
    }


async def _index_patent_vectors(patent_id: int, content: str):
    """后台异步索引专利向量"""
    try:
        from app.services.patent_rag_service import PatentRagService
        svc = PatentRagService()
        chunks = await svc.index_patent(patent_id, content)
        logger = __import__("logging").getLogger(__name__)
        logger.info(f"专利 {patent_id} RAG 索引完成: {chunks} 分块")
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"专利 {patent_id} RAG 索引失败: {e}")
