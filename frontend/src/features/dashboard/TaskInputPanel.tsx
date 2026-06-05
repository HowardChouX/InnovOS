import { useState } from 'react';
import { useTaskStore } from '../../store/useTaskStore';

const DEFAULT_TAGS = ['电池安全', '能量密度', '循环寿命', '热管理'];

export function TaskInputPanel() {
  const [description, setDescription] = useState('如何在保证电池能量密度的同时，提高其安全性并延长循环寿命？');
  const [tags, setTags] = useState<string[]>(DEFAULT_TAGS);
  const [newTag, setNewTag] = useState('');
  const createTask = useTaskStore((s) => s.createTask);

  const handleSubmit = async () => {
    if (!description.trim()) return;
    const task = await createTask({ title: description.slice(0, 50), description, tags });
    if (task) setDescription('');
  };

  const addTag = () => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      setTags([...tags, newTag.trim()]);
      setNewTag('');
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="card-title">
          <i className="fa-solid fa-pen-to-square" style={{ fontSize: 12, color: 'var(--accent-blue)' }} />
          创新任务输入
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{
            fontSize: 11, padding: '5px 12px', background: 'transparent',
            color: 'var(--text-secondary)', border: '1px solid var(--border)',
            borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
          }}>
            任务模板 <i className="fa-solid fa-chevron-down" style={{ fontSize: 8, marginLeft: 4 }} />
          </button>
          <button style={{
            fontSize: 11, padding: '5px 12px', background: 'transparent',
            color: 'var(--text-secondary)', border: '1px solid var(--border)',
            borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
          }}>
            <i className="fa-solid fa-file-import" style={{ marginRight: 4 }} />
            导入文档
          </button>
        </div>
      </div>

      <textarea value={description} onChange={(e) => setDescription(e.target.value)}
        placeholder="输入您的创新问题..."
        style={{
          width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 12, marginBottom: 12, minHeight: 60,
          fontSize: 14, color: 'var(--text-primary)',
          resize: 'vertical', outline: 'none', fontFamily: 'inherit',
        }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <button
          onClick={() => {
            const tag = prompt('输入关键词:');
            if (tag?.trim()) addTag();
          }}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '4px 10px', borderRadius: 20, fontSize: 12,
            background: 'transparent', border: '1px dashed var(--border)',
            color: 'var(--text-tertiary)', cursor: 'pointer', fontFamily: 'inherit',
          }}
        >
          + 添加关键词
        </button>
        {tags.map((tag) => (
          <span key={tag} style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '4px 10px', borderRadius: 20, fontSize: 12,
            background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
            color: 'var(--accent-blue)',
          }}>
            {tag}
            <button onClick={() => removeTag(tag)} style={{
              background: 'none', border: 'none', color: 'inherit',
              cursor: 'pointer', fontSize: 10, padding: 0, fontFamily: 'inherit',
            }}>
              <i className="fa-solid fa-xmark" />
            </button>
          </span>
        ))}
      </div>

      <button onClick={handleSubmit} style={{
        marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
        background: 'var(--accent)', border: 'none',
        color: '#fff', padding: '8px 20px', borderRadius: 6,
        cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
      }}>
        开始分析 <i className="fa-solid fa-arrow-right" style={{ fontSize: 11 }} />
      </button>
    </div>
  );
}
