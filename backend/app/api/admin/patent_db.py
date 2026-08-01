import json
import logging
import os
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.algorithm.patent_search_engine import PatentSearchEngine, get_patent_search_engine
from app.auth import require_admin
from app.database import get_db
from app.services.file_storage_service import file_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patents", tags=["admin-patent-db"])

# PDF 存储目录
PATENT_PDF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "storage", "patents"
)
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
    try:
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
    finally:
        db.close()


@router.post("")
async def create_patent(body: PatentCreate, user: dict = Depends(require_admin)):
    db = get_db()
    try:
        if not db:
            raise HTTPException(503, "数据库未连接")

        # 检查专利号是否已存在
        if body.patent_number:
            existing = db.execute(
                "SELECT id FROM patents WHERE patent_number=?",
                (body.patent_number,),
            ).fetchone()
            if existing:
                raise HTTPException(409, detail=f"专利号 {body.patent_number} 已存在")

        cur = db.execute(
            """INSERT INTO patents (title, abstract, applicants, inventors, filing_date,
               publication_date, patent_number, publication_number,
               ipc_codes, claims, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               RETURNING id""",
            [
                body.title,
                body.abstract,
                json.dumps(body.applicants, ensure_ascii=False),
                json.dumps(body.inventors, ensure_ascii=False),
                body.filing_date,
                body.publication_date,
                body.patent_number,
                body.publication_number,
                json.dumps(body.ipc_codes, ensure_ascii=False),
                body.claims,
                body.description,
            ],
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(500, "创建失败")
        row_id = row["id"]
        db.commit()
        patent = db.execute("SELECT * FROM patents WHERE id = ?", [row_id]).fetchone()
    finally:
        db.close()

    # 异步嵌入（使用单例引擎）
    try:
        engine = get_patent_search_engine()
        import asyncio

        asyncio.create_task(
            engine.index_patent(
                row_id, body.title or "", body.abstract or "", body.claims or "", body.description or ""
            )
        )
    except Exception as e:
        logger.warning(f"专利嵌入任务创建失败: {e}")
    return row_to_patent(patent)


@router.put("/{patent_id}")
async def update_patent(patent_id: int, body: PatentUpdate, user: dict = Depends(require_admin)):
    db = get_db()
    try:
        existing = db.execute("SELECT id FROM patents WHERE id = ?", [patent_id]).fetchone()
        if not existing:
            raise HTTPException(404, "专利不存在")

        db.execute(
            """UPDATE patents SET title=?, abstract=?, applicants=?, inventors=?,
               filing_date=?, publication_date=?, patent_number=?, publication_number=?,
               ipc_codes=?, claims=?, description=?
               WHERE id=?""",
            [
                body.title,
                body.abstract,
                json.dumps(body.applicants, ensure_ascii=False),
                json.dumps(body.inventors, ensure_ascii=False),
                body.filing_date,
                body.publication_date,
                body.patent_number,
                body.publication_number,
                json.dumps(body.ipc_codes, ensure_ascii=False),
                body.claims,
                body.description,
                patent_id,
            ],
        )
        db.commit()
        patent = db.execute("SELECT * FROM patents WHERE id = ?", [patent_id]).fetchone()
    finally:
        db.close()

    import asyncio

    try:
        engine = get_patent_search_engine()
        asyncio.create_task(
            engine.index_patent(
                patent_id, body.title or "", body.abstract or "", body.claims or "", body.description or ""
            )
        )
    except Exception as e:
        logger.warning(f"专利嵌入任务创建失败: {e}")
    return row_to_patent(patent)


@router.delete("/{patent_id}")
def delete_patent(patent_id: int, user: dict = Depends(require_admin)):
    db = get_db()
    try:
        existing = db.execute("SELECT id FROM patents WHERE id = ?", [patent_id]).fetchone()
        if not existing:
            raise HTTPException(404, "专利不存在")
        db.execute("DELETE FROM patents WHERE id = ?", [patent_id])
        db.commit()
    finally:
        db.close()
    return {"message": "删除成功"}


@router.post("/import")
async def import_patents(patents: list[PatentCreate], user: dict = Depends(require_admin)):
    """批量导入专利"""
    db = get_db()
    try:
        imported = 0
        for p in patents:
            db.execute(
                """INSERT INTO patents (title, abstract, applicants, inventors, filing_date,
                   publication_date, patent_number, publication_number,
                   ipc_codes, claims, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    p.title,
                    p.abstract,
                    json.dumps(p.applicants, ensure_ascii=False),
                    json.dumps(p.inventors, ensure_ascii=False),
                    p.filing_date,
                    p.publication_date,
                    p.patent_number,
                    p.publication_number,
                    json.dumps(p.ipc_codes, ensure_ascii=False),
                    p.claims,
                    p.description,
                ],
            )
            imported += 1
        db.commit()
    finally:
        db.close()

    # 后台回填向量
    import asyncio

    try:
        engine = get_patent_search_engine()
        asyncio.create_task(engine.backfill())
    except Exception as e:
        logger.warning(f"专利回填任务创建失败: {e}")
    return {"message": f"成功导入 {imported} 条专利", "count": imported}


@router.post("/upload")
async def upload_patent_pdf(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
    user: dict = Depends(require_admin),
):
    """上传专利 PDF → 解析 → 正则提取结构化字段

    mode: auto | pdfminer | docling（auto=优先docling，失败降级pdfminer）
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    # ── File upload hardening ──
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件 {file.filename} 超过大小限制 (50MB)")

    # 路径穿越防护：去除目录组件
    raw_name = os.path.basename(file.filename or "patent.pdf")
    safe_name = f"{user['id']}_{int(time.time())}_{raw_name}"
    safe_name = safe_name.replace("..", "_")

    # 上传到 MinIO/S3（如果已配置）
    if file_storage.enabled:
        await file_storage.upload(user["id"], safe_name, content)

    # 写入临时文件供解析（parse_file 需要本地路径）
    pdf_path = os.path.join(PATENT_PDF_DIR, safe_name)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with open(pdf_path, "wb") as f:
        f.write(content)

    from app.algorithm.file_parser import parse_file

    parsed = parse_file(pdf_path, mode=mode)
    full_text = parsed.get("content", "") or ""

    from app.algorithm.patent_extractor import extract_patent_fields

    fields = extract_patent_fields(full_text)
    fields.pop("_missing", None)

    # 清理 NUL 字符（部分 PDF 文本含 0x00，psycopg2 会报错）
    import re as _re

    _nul = _re.compile(r"\x00+")
    for _k in fields:
        if isinstance(fields[_k], str):
            fields[_k] = _nul.sub("", fields[_k])
        elif isinstance(fields[_k], list):
            fields[_k] = [_nul.sub("", str(i)) for i in fields[_k]]

    # AI 增强：生成干净的标题用于展示（用 extract_model，单次）
    ai_title = fields.get("title", "") or ""
    abstract = fields.get("abstract", "") or ""
    if len(full_text) > 200:
        try:
            from app.algorithm.ai_client import chat_completion
            from app.algorithm.base import parse_ai_json
            from app.algorithm.model_resolver import model_resolver

            s = model_resolver.get_assigned_settings()
            extract_id = s.get("extract_model") or ""
            if extract_id and ":" in extract_id:
                result = await chat_completion(
                    user_id=user["id"],
                    purpose="extract",
                    messages=[
                        {
                            "role": "system",
                            "content": '你是一个专利分析助手。分析以下专利文本，输出JSON：{"title": "简洁的专利名称", "abstract": "完整的专利摘要（100-300字，描述技术方案和效果）"}',
                        },
                        {"role": "user", "content": full_text[:3000]},
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    model_override=extract_id,
                )
                parsed = parse_ai_json((result.get("content") or "").strip())
                if isinstance(parsed, dict):
                    if parsed.get("title") and len(parsed["title"]) > 5:
                        ai_title = parsed["title"].strip()
                    # 只在正则摘要太短时用 AI 摘要兜底
                    if parsed.get("abstract") and len(abstract) < 50:
                        abstract = parsed["abstract"].strip()
        except Exception as e:
            logger.warning(f"专利DB操作异常: {e}")

    db = get_db()
    try:
        if not db:
            raise HTTPException(503, "数据库未连接")

        # 检查专利号是否已存在
        patent_num = fields.get("patent_number", "") or ""
        if patent_num:
            existing = db.execute(
                "SELECT id FROM patents WHERE patent_number=?",
                (patent_num,),
            ).fetchone()
            if existing:
                raise HTTPException(409, detail=f"专利号 {patent_num} 已存在")

        cur = db.execute(
            """INSERT INTO patents (title, abstract, applicants, inventors, filing_date,
               publication_date, patent_number, publication_number,
               ipc_codes, claims, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            [
            ai_title,
            abstract,
                json.dumps(fields.get("applicants", []), ensure_ascii=False),
                json.dumps(fields.get("inventors", []), ensure_ascii=False),
                fields.get("filing_date", "") or "",
                fields.get("publication_date", "") or "",
                fields.get("patent_number", "") or "",
                fields.get("publication_number", "") or "",
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
    finally:
        db.close()

    # 原始 PDF 已提取完毕，删除临时文件
    try:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
    except Exception as e:
        logger.warning(f"专利DB操作异常: {e}")

    import asyncio

    # 向量化：所有结构化字段拼接（与 index_patent 一致），无字段则用 pdfminer 原文
    parts = [
        ai_title or "",
        abstract or "",
        fields.get("claims", "") or "",
        fields.get("description", "") or "",
    ]
    text_content = "\n".join(p for p in parts if p.strip()) or full_text
    if len(text_content) > 100:
        asyncio.create_task(_index_patent_vectors(row_id, text_content))

    return {**row_to_patent(patent), "mode": mode, "extractSource": parsed["type"]}


async def _index_patent_vectors(patent_id: int, content: str):
    """后台异步索引专利向量（使用 PatentSearchEngine）"""
    try:
        from app.algorithm.patent_search_engine import get_patent_search_engine

        engine = get_patent_search_engine()
        await engine.index_patent_with_content(patent_id, content)
        logger.info(f"专利 {patent_id} 向量索引完成")
    except Exception as e:
        logger.warning(f"专利 {patent_id} 向量索引失败: {e}")
