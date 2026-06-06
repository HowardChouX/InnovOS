import { useState, useEffect } from 'react';
import { knowledgeApi } from '../../api/knowledge';
import type { KnowledgeDoc } from '../../types/knowledge';
import { InlineConfirmModal } from '../../components/ui/InlineConfirmModal';

function DocModal({
  doc,
  onClose,
  onSave,
}: {
  doc: KnowledgeDoc | null;
  onClose: () => void;
  onSave: (data: { title: string; content: string; category: string; tags: string[]; source: string }) => void;
}) {
  const [title, setTitle] = useState(doc?.title || '');
  const [content, setContent] = useState(doc?.content || '');
  const [category, setCategory] = useState(doc?.category || '未分类');
  const [tags, setTags] = useState(doc?.tags?.join(', ') || '');
  const [source, setSource] = useState(doc?.source || '');

  const handleSubmit = () => {
    if (!title.trim()) return;
    onSave({
      title,
      content,
      category,
      tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      source,
    });
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        width: 600, maxHeight: '80vh', overflow: 'auto', padding: 24,
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            {doc ? '编辑文档' : '新建文档'}
          </h3>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', fontSize: 16,
          }}>
            <i className="fa-solid fa-xmark" />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>标题</div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="文档标题"
              style={{
                width: '100%', padding: '8px 10px', borderRadius: 6,
                background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>分类</div>
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="分类"
                style={{
                  width: '100%', padding: '8px 10px', borderRadius: 6,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
                }}
              />
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>标签（逗号分隔）</div>
              <input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="tag1, tag2"
                style={{
                  width: '100%', padding: '8px 10px', borderRadius: 6,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
                }}
              />
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>来源</div>
            <input
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="文档来源"
              style={{
                width: '100%', padding: '8px 10px', borderRadius: 6,
                background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
              }}
            />
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>内容</div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="文档内容..."
              rows={8}
              style={{
                width: '100%', padding: '8px 10px', borderRadius: 6,
                background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
            <button onClick={onClose} style={{
              padding: '8px 16px', borderRadius: 6,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
            }}>
              取消
            </button>
            <button onClick={handleSubmit} style={{
              padding: '8px 16px', borderRadius: 6,
              background: 'var(--accent)', border: 'none',
              color: '#fff', cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
            }}>
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function KnowledgeBasePage() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [categories, setCategories] = useState<{ name: string; count: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingDoc, setEditingDoc] = useState<KnowledgeDoc | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
  const [confirmModal, setConfirmModal] = useState<{ open: boolean; title: string; message: string; onConfirm: () => void }>({ open: false, title: '', message: '', onConfirm: () => {} });
  const pageSize = 20;

  const fetchDocs = async (pageNum = 1) => {
    setLoading(true);
    try {
      const res = await knowledgeApi.listDocs({
        q: search,
        category: selectedCategory,
        page: pageNum,
        page_size: pageSize,
      });
      setDocs(res.data);
      setTotal(res.total);
      setPage(pageNum);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await knowledgeApi.listCategories();
      setCategories(res.data);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchDocs(1);
    fetchCategories();
  }, [selectedCategory]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);



  const handleSearch = () => {
    fetchDocs(1);
  };

  const handleSave = async (data: {
    title: string;
    content: string;
    category: string;
    tags: string[];
    source: string;
  }) => {
    try {
      if (editingDoc) {
        await knowledgeApi.updateDoc(editingDoc.id, data);
      } else {
        await knowledgeApi.createDoc(data);
      }
      setShowModal(false);
      setEditingDoc(null);
      fetchDocs(1);
      fetchCategories();
    } catch {
      // ignore
    }
  };

  const handleDelete = (id: string) => {
    setConfirmModal({
      open: true,
      title: '确认删除',
      message: '确认删除该文档？',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, open: false }));
        try {
          await knowledgeApi.deleteDoc(id);
          fetchDocs(1);
          fetchCategories();
          setToast({ msg: '文档已删除', type: 'success' });
        } catch {
          setToast({ msg: '删除失败', type: 'error' });
        }
      },
    });
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <i className="fa-solid fa-database" style={{ marginRight: 8, color: 'var(--accent-purple)' }} />
          知识库管理
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          共 {total} 篇文档
        </span>
      </div>

      {/* 工具栏 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <i className="fa-solid fa-magnifying-glass" style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            fontSize: 12, color: 'var(--text-tertiary)',
          }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索文档..."
            style={{
              width: '100%', padding: '8px 10px 8px 32px', borderRadius: 6,
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
            }}
          />
        </div>
        <button onClick={handleSearch} style={{
          padding: '8px 16px', borderRadius: 6,
          background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
          color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
        }}>
          搜索
        </button>
        <button onClick={() => { setEditingDoc(null); setShowModal(true); }} style={{
          padding: '8px 16px', borderRadius: 6,
          background: 'var(--accent)', border: 'none',
          color: '#fff', cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <i className="fa-solid fa-plus" style={{ fontSize: 11 }} />
          新建文档
        </button>
      </div>

      {/* 分类过滤 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        <button
          onClick={() => setSelectedCategory('')}
          style={{
            padding: '4px 12px', borderRadius: 4, fontSize: 11,
            background: selectedCategory === '' ? 'rgba(59,130,246,0.15)' : 'transparent',
            border: selectedCategory === '' ? '1px solid rgba(59,130,246,0.3)' : '1px solid var(--border)',
            color: selectedCategory === '' ? 'var(--accent-blue)' : 'var(--text-tertiary)',
            cursor: 'pointer', fontFamily: 'inherit',
          }}
        >
          全部
        </button>
        {categories.map((cat) => (
          <button
            key={cat.name}
            onClick={() => setSelectedCategory(cat.name)}
            style={{
              padding: '4px 12px', borderRadius: 4, fontSize: 11,
              background: selectedCategory === cat.name ? 'rgba(59,130,246,0.15)' : 'transparent',
              border: selectedCategory === cat.name ? '1px solid rgba(59,130,246,0.3)' : '1px solid var(--border)',
              color: selectedCategory === cat.name ? 'var(--accent-blue)' : 'var(--text-tertiary)',
              cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            {cat.name} ({cat.count})
          </button>
        ))}
      </div>

      {/* 文档列表 */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center' }}>
            <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 24, color: 'var(--accent-blue)' }} />
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 8 }}>加载中...</div>
          </div>
        ) : docs.length === 0 ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
            <i className="fa-solid fa-inbox" style={{ fontSize: 32, marginBottom: 12, display: 'block', opacity: 0.3 }} />
            暂无文档，点击「新建文档」添加
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {docs.map((doc) => (
              <div
                key={doc.id}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 12,
                  padding: '12px 14px', borderRadius: 8,
                  background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                    marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {doc.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6, lineHeight: 1.5 }}>
                    {doc.content?.slice(0, 150) || '暂无内容'}
                    {doc.content?.length > 150 ? '...' : ''}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'var(--text-tertiary)' }}>
                    <span style={{
                      padding: '2px 6px', borderRadius: 3,
                      background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)',
                      border: '1px solid rgba(59,130,246,0.2)',
                    }}>
                      {doc.category}
                    </span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {(doc.tags || []).map((tag) => (
                        <span key={tag} style={{
                          padding: '1px 5px', borderRadius: 3,
                          background: 'rgba(100,116,139,0.1)', color: 'var(--text-tertiary)',
                        }}>
                          {tag}
                        </span>
                      ))}
                    </div>
                    {doc.source && <span>来源: {doc.source}</span>}
                    <span>更新: {doc.updatedAt?.slice(0, 10)}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => { setEditingDoc(doc); setShowModal(true); }}
                    style={{
                      padding: '4px 8px', borderRadius: 4,
                      background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                      color: 'var(--accent-blue)', cursor: 'pointer', fontSize: 11, fontFamily: 'inherit',
                    }}
                  >
                    <i className="fa-solid fa-pen" />
                  </button>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    style={{
                      padding: '4px 8px', borderRadius: 4,
                      background: 'rgba(248,113,113,0.1)',
                      border: '1px solid rgba(248,113,113,0.2)',
                      color: 'var(--accent-red)',
                      cursor: 'pointer', fontSize: 11, fontFamily: 'inherit',
                      transition: 'all 0.15s',
                    }}
                  >
                    <i className="fa-solid fa-trash" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8,
          marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border-light)',
        }}>
          <button onClick={() => fetchDocs(page - 1)} disabled={page <= 1} style={{
            padding: '4px 10px', borderRadius: 4,
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
            color: page <= 1 ? 'var(--text-tertiary)' : 'var(--text-secondary)',
            cursor: page <= 1 ? 'not-allowed' : 'pointer', fontSize: 11, fontFamily: 'inherit',
          }}>
            <i className="fa-solid fa-chevron-left" />
          </button>

          <div style={{ display: 'flex', gap: 4 }}>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => i + 1).map((pageNum) => (
              <button
                key={pageNum}
                onClick={() => fetchDocs(pageNum)}
                style={{
                  width: 28, height: 28, borderRadius: 4,
                  background: pageNum === page ? 'var(--accent)' : 'rgba(0,0,0,0.2)',
                  border: '1px solid var(--border-light)',
                  color: pageNum === page ? '#fff' : 'var(--text-secondary)',
                  cursor: 'pointer', fontSize: 11, fontFamily: 'inherit',
                }}
              >
                {pageNum}
              </button>
            ))}
          </div>

          <button onClick={() => fetchDocs(page + 1)} disabled={page >= totalPages} style={{
            padding: '4px 10px', borderRadius: 4,
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
            color: page >= totalPages ? 'var(--text-tertiary)' : 'var(--text-secondary)',
            cursor: page >= totalPages ? 'not-allowed' : 'pointer', fontSize: 11, fontFamily: 'inherit',
          }}>
            <i className="fa-solid fa-chevron-right" />
          </button>

          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            {page} / {totalPages}
          </span>
        </div>
      )}

      {/* 弹窗 */}
      {showModal && (
        <DocModal
          doc={editingDoc}
          onClose={() => { setShowModal(false); setEditingDoc(null); }}
          onSave={handleSave}
        />
      )}
      <InlineConfirmModal
        open={confirmModal.open}
        title={confirmModal.title}
        message={confirmModal.message}
        onConfirm={confirmModal.onConfirm}
        onCancel={() => setConfirmModal(prev => ({ ...prev, open: false }))}
      />
    </div>
  );
}
