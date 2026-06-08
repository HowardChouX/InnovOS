"""
知识库数据模型 — 参考 CherryStudio 类型系统设计

使用 Pydantic 定义类型，确保类型安全和数据验证。
"""
from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# 常量定义
# ============================================================================

class KnowledgeItemType(str, Enum):
    """知识项类型"""
    FILE = "file"
    URL = "url"
    NOTE = "note"
    DIRECTORY = "directory"


class KnowledgeItemStatus(str, Enum):
    """
    知识项生命周期状态
    
    状态机：
    file/url/note:
      idle -> processing -> reading -> embedding -> completed
         \\                    \\             \\          \\
          +--------------------+-------------+-----------> failed
         \\---------------------------------------------> deleting
    
    directory:
      idle -> preparing -> processing -> completed
         \\        \\             \\          \\
          +--------+-------------+-----------> failed
         \\---------------------------------> deleting
    """
    IDLE = "idle"
    PREPARING = "preparing"
    PROCESSING = "processing"
    READING = "reading"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETING = "deleting"


class KnowledgeBaseStatus(str, Enum):
    """知识库状态"""
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeBaseErrorCode(str, Enum):
    """知识库错误码"""
    MISSING_EMBEDDING_MODEL = "missing_embedding_model"


class KnowledgeSearchMode(str, Enum):
    """搜索模式"""
    DEFAULT = "default"
    BM25 = "bm25"
    HYBRID = "hybrid"


# ============================================================================
# 知识库实体
# ============================================================================

class KnowledgeBase(BaseModel):
    """知识库元数据 — 存储在 SQLite"""
    id: str = Field(..., description="知识库 UUID")
    name: str = Field(..., min_length=1, description="知识库名称")
    group_id: Optional[str] = Field(None, description="分组 ID")
    dimensions: Optional[int] = Field(None, gt=0, description="向量维度")
    embedding_model_id: Optional[str] = Field(None, description="嵌入模型 ID")
    status: KnowledgeBaseStatus = Field(KnowledgeBaseStatus.COMPLETED, description="状态")
    error: Optional[KnowledgeBaseErrorCode] = Field(None, description="错误码")
    rerank_model_id: Optional[str] = Field(None, description="重排模型 ID")
    file_processor_id: Optional[str] = Field(None, description="文件处理器 ID")
    chunk_size: int = Field(1024, gt=0, description="分块大小")
    chunk_overlap: int = Field(200, ge=0, description="分块重叠")
    threshold: Optional[float] = Field(None, ge=0, le=1, description="阈值")
    document_count: Optional[int] = Field(None, gt=0, description="文档数量")
    search_mode: KnowledgeSearchMode = Field(KnowledgeSearchMode.HYBRID, description="搜索模式")
    hybrid_alpha: Optional[float] = Field(None, ge=0, le=1, description="混合搜索权重")
    created_at: str = Field(..., description="创建时间 ISO 格式")
    updated_at: str = Field(..., description="更新时间 ISO 格式")

    @field_validator("chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, v, info):
        chunk_size = info.data.get("chunk_size")
        if chunk_size and v >= chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        return v

    @field_validator("error")
    @classmethod
    def validate_error(cls, v, info):
        status = info.data.get("status")
        if status == KnowledgeBaseStatus.COMPLETED and v is not None:
            raise ValueError("completed 状态不能有 error")
        if status == KnowledgeBaseStatus.FAILED and v is None:
            raise ValueError("failed 状态必须有 error")
        return v

    @field_validator("hybrid_alpha")
    @classmethod
    def validate_hybrid_alpha(cls, v, info):
        search_mode = info.data.get("search_mode")
        if v is not None and search_mode != KnowledgeSearchMode.HYBRID:
            raise ValueError("hybrid_alpha 需要 hybrid 搜索模式")
        return v


# ============================================================================
# 知识项数据
# ============================================================================

class KnowledgeItemData(BaseModel):
    """知识项数据基类"""
    source: str = Field(..., min_length=1, description="原始来源标识")


class FileItemData(KnowledgeItemData):
    """文件类型数据"""
    file_entry_id: str = Field(..., description="文件条目 ID")


class UrlItemData(KnowledgeItemData):
    """URL 类型数据"""
    url: str = Field(..., min_length=1, description="URL 地址")


class NoteItemData(KnowledgeItemData):
    """笔记类型数据"""
    content: str = Field(..., max_length=1_000_000, description="笔记内容")
    source_url: Optional[str] = Field(None, description="关联的外部 URL")


class DirectoryItemData(KnowledgeItemData):
    """目录类型数据"""
    path: str = Field(..., min_length=1, description="目录路径")


KnowledgeItemDataUnion = Union[FileItemData, UrlItemData, NoteItemData, DirectoryItemData]


# ============================================================================
# 知识项实体
# ============================================================================

class KnowledgeItemBase(BaseModel):
    """知识项基础字段"""
    id: str = Field(..., description="知识项 ID")
    base_id: str = Field(..., description="所属知识库 ID")
    group_id: Optional[str] = Field(None, description="父容器项 ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")


class IdleKnowledgeItem(KnowledgeItemBase):
    """空闲状态知识项"""
    status: Literal["idle"] = "idle"
    error: None = None


class PreparingKnowledgeItem(KnowledgeItemBase):
    """准备中状态（仅目录类型）"""
    status: Literal["preparing"] = "preparing"
    error: None = None


class ProcessingKnowledgeItem(KnowledgeItemBase):
    """处理中状态"""
    status: Literal["processing"] = "processing"
    error: None = None


class ReadingKnowledgeItem(KnowledgeItemBase):
    """读取中状态（仅 file/url/note）"""
    status: Literal["reading"] = "reading"
    error: None = None


class EmbeddingKnowledgeItem(KnowledgeItemBase):
    """嵌入中状态（仅 file/url/note）"""
    status: Literal["embedding"] = "embedding"
    error: None = None


class CompletedKnowledgeItem(KnowledgeItemBase):
    """完成状态"""
    status: Literal["completed"] = "completed"
    error: None = None


class FailedKnowledgeItem(KnowledgeItemBase):
    """失败状态"""
    status: Literal["failed"] = "failed"
    error: str = Field(..., min_length=1, description="错误信息")


class DeletingKnowledgeItem(KnowledgeItemBase):
    """删除中状态"""
    status: Literal["deleting"] = "deleting"
    error: None = None


# 文件类型知识项
class FileKnowledgeItem(IdleKnowledgeItem):
    type: Literal["file"] = "file"
    data: FileItemData


class UrlKnowledgeItem(IdleKnowledgeItem):
    type: Literal["url"] = "url"
    data: UrlItemData


class NoteKnowledgeItem(IdleKnowledgeItem):
    type: Literal["note"] = "note"
    data: NoteItemData


class DirectoryKnowledgeItem(IdleKnowledgeItem):
    type: Literal["directory"] = "directory"
    data: DirectoryItemData


# 知识项联合类型
KnowledgeItem = Union[
    FileKnowledgeItem,
    UrlKnowledgeItem,
    NoteKnowledgeItem,
    DirectoryKnowledgeItem,
    # 可以添加其他状态的类型...
]


# ============================================================================
# 搜索结果
# ============================================================================

class KnowledgeSearchScoreKind(str, Enum):
    """搜索评分类型"""
    RELEVANCE = "relevance"
    RANKING = "ranking"


class KnowledgeChunkMetadata(BaseModel):
    """分块元数据"""
    item_id: str = Field(..., description="知识项 ID")
    item_type: KnowledgeItemType = Field(..., description="知识项类型")
    source: str = Field(..., min_length=1, description="来源")
    chunk_index: int = Field(..., ge=0, description="分块索引")
    token_count: int = Field(..., ge=0, description="token 数量")


class KnowledgeSearchResult(BaseModel):
    """搜索结果"""
    page_content: str = Field(..., description="分块内容")
    score: float = Field(..., description="相似度分数")
    score_kind: KnowledgeSearchScoreKind = Field(..., description="评分类型")
    rank: int = Field(..., gt=0, description="排名")
    metadata: KnowledgeChunkMetadata = Field(..., description="分块元数据")
    item_id: Optional[str] = Field(None, description="知识项 ID")
    chunk_id: str = Field(..., description="分块 ID")


# ============================================================================
# 运行时操作 DTO
# ============================================================================

class CreateKnowledgeBaseDto(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, description="知识库名称")
    group_id: Optional[str] = Field(None, description="分组 ID")
    dimensions: int = Field(..., gt=0, description="向量维度")
    embedding_model_id: str = Field(..., min_length=1, description="嵌入模型 ID")
    rerank_model_id: Optional[str] = Field(None, description="重排模型 ID")
    file_processor_id: Optional[str] = Field(None, description="文件处理器 ID")
    chunk_size: Optional[int] = Field(None, gt=0, description="分块大小")
    chunk_overlap: Optional[int] = Field(None, ge=0, description="分块重叠")
    threshold: Optional[float] = Field(None, ge=0, le=1, description="阈值")
    document_count: Optional[int] = Field(None, gt=0, description="文档数量")
    search_mode: Optional[KnowledgeSearchMode] = Field(None, description="搜索模式")
    hybrid_alpha: Optional[float] = Field(None, ge=0, le=1, description="混合搜索权重")


class UpdateKnowledgeBaseDto(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, min_length=1, description="知识库名称")
    group_id: Optional[str] = Field(None, description="分组 ID")
    rerank_model_id: Optional[str] = Field(None, description="重排模型 ID")
    file_processor_id: Optional[str] = Field(None, description="文件处理器 ID")
    chunk_size: Optional[int] = Field(None, gt=0, description="分块大小")
    chunk_overlap: Optional[int] = Field(None, ge=0, description="分块重叠")
    threshold: Optional[float] = Field(None, ge=0, le=1, description="阈值")
    document_count: Optional[int] = Field(None, gt=0, description="文档数量")
    search_mode: Optional[KnowledgeSearchMode] = Field(None, description="搜索模式")
    hybrid_alpha: Optional[float] = Field(None, ge=0, le=1, description="混合搜索权重")
    status: Optional[KnowledgeBaseStatus] = Field(None, description="状态")
    error: Optional[KnowledgeBaseErrorCode] = Field(None, description="错误码")
    dimensions: Optional[int] = Field(None, gt=0, description="向量维度")
    embedding_model_id: Optional[str] = Field(None, description="嵌入模型 ID")


class CreateKnowledgeItemDto(BaseModel):
    """创建知识项请求"""
    type: KnowledgeItemType = Field(..., description="知识项类型")
    group_id: Optional[str] = Field(None, description="父容器项 ID")
    data: KnowledgeItemDataUnion = Field(..., description="知识项数据")


class UpdateKnowledgeItemDto(BaseModel):
    """更新知识项请求"""
    status: Optional[KnowledgeItemStatus] = Field(None, description="状态")
    error: Optional[str] = Field(None, description="错误信息")
    data: Optional[KnowledgeItemDataUnion] = Field(None, description="知识项数据")
