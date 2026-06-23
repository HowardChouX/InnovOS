import { useState } from 'react';

const SECTIONS = [
  { id: 'quickstart', title: '快速开始' },
  { id: 'demand', title: '需求洞察' },
  { id: 'modeling', title: '问题建模' },
  { id: 'patent', title: '专利检索' },
  { id: 'solution', title: '方案生成' },
  { id: 'evaluation', title: '方案评估' },
  { id: 'history', title: '历史方案库' },
  { id: 'knowledge', title: '知识库' },
  { id: 'faq', title: '常见问题' },
];

const STEPS = [
  ['描述问题', '在首页输入框中描述您的技术问题或创新需求'],
  ['关联知识库', '（可选）关联知识库以获取更精准的分析'],
  ['启动分析', '点击"开始分析"按钮，AI 将自动执行多步骤分析'],
  ['逐步反馈', '在每一步查看 AI 的分析结果并给出评分反馈'],
  ['查看方案', '工作流完成后查看生成的创新方案'],
];

const FAQS = [
  { q: '分析需要多长时间？', a: '一般 1-3 分钟，具体时间取决于问题复杂度和专利检索范围。' },
  { q: '如何查看历史分析结果？', a: '点击左侧导航栏的"历史方案库"，即可查看所有过往分析任务。' },
  { q: '可以删除历史记录吗？', a: '可以。在历史方案库中，悬停在任务卡片上会出现删除按钮。' },
  {
    q: '如何提高分析质量？',
    a: '在描述问题时尽量详细具体，并关联相关的知识库资料，可以提高分析质量。',
  },
  {
    q: '分析结果可以保存吗？',
    a: '所有分析结果自动保存在历史方案库中，可随时查看。导出功能正在开发中。',
  },
];

export function GuidePage() {
  const [activeSection, setActiveSection] = useState<string>('quickstart');

  const renderSection = () => {
    switch (activeSection) {
      case 'quickstart':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              快速开始
            </h2>
            <p
              style={{
                fontSize: 13,
                color: 'var(--text-secondary)',
                lineHeight: 1.8,
                margin: '0 0 20px',
              }}
            >
              InnovOS 是一个创新智能分析平台，帮助您从技术问题出发，通过 AI 驱动的多 Agent
              协作，生成创新方案。
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {STEPS.map(([step, desc], i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 12,
                    padding: '12px 14px',
                    borderRadius: 8,
                    background: 'rgba(0,0,0,0.18)',
                    border: '1px solid var(--border-light)',
                  }}
                >
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      flexShrink: 0,
                      marginTop: 1,
                      background: 'rgba(59,130,246,0.15)',
                      color: 'var(--accent-blue)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {i + 1}
                  </span>
                  <div>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        marginBottom: 2,
                      }}
                    >
                      {step}
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      {desc}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        );
      case 'demand':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              需求洞察
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, margin: 0 }}>
              AI 会自动分析您的输入，识别出关键技术需求。您可以为每个需求打分（1-5星），确认 AI
              的判断。 如有遗漏，可以手动补充额外需求。确认后进入下一步。
            </p>
          </section>
        );
      case 'modeling':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              问题建模
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, margin: 0 }}>
              AI 基于需求构建冲突分析图，展示技术矛盾和创新方向。您可以看到 AI
              识别的创新原理和预期效果， 为每个创新方向评分确认。
            </p>
          </section>
        );
      case 'patent':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              专利检索
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, margin: 0 }}>
              AI
              自动检索与分析问题相关的最新专利，展示专利摘要和相关度评分，帮助您了解现有技术布局，
              避免重复研发。
            </p>
          </section>
        );
      case 'solution':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              方案生成
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, margin: 0 }}>
              AI 综合需求分析、问题建模和专利检索结果，生成创新方案。每个方案包含技术原理说明、
              实现路径描述和相关专利参考。
            </p>
          </section>
        );
      case 'evaluation':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              方案评估
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, margin: 0 }}>
              AI 从四个维度评估方案：创新性、可行性、完整性和转化价值。每个维度有独立评分，
              并提供改进建议和优势分析。
            </p>
          </section>
        );
      case 'history':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              历史方案库
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, margin: 0 }}>
              所有完成的分析任务自动保存在历史方案库中，支持搜索、按状态筛选和删除。
              点击任意任务可查看完整分析过程的每一步结果。
            </p>
          </section>
        );
      case 'knowledge':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 4px',
              }}
            >
              知识库
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, margin: 0 }}>
              在知识库页面管理您的技术资料，支持上传 PDF、Word、TXT 等格式文档。创建知识库后，
              在首页分析时可关联使用，让 AI 结合您的专属知识进行分析。
            </p>
          </section>
        );
      case 'faq':
        return (
          <section>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: '0 0 16px',
              }}
            >
              常见问题
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {FAQS.map((faq, i) => (
                <div
                  key={i}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 8,
                    background: 'rgba(0,0,0,0.18)',
                    border: '1px solid var(--border-light)',
                  }}
                >
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      marginBottom: 4,
                    }}
                  >
                    Q: {faq.q}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                    A: {faq.a}
                  </div>
                </div>
              ))}
            </div>
          </section>
        );
      default:
        return null;
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        gap: 28,
        padding: '28px 24px',
        minHeight: 0,
        maxWidth: 960,
        margin: '0 auto',
      }}
    >
      {/* Content Area */}
      <div style={{ flex: 1, minWidth: 0 }}>{renderSection()}</div>

      {/* TOC Sidebar */}
      <div
        style={{
          width: 170,
          flexShrink: 0,
          position: 'sticky',
          top: 24,
          alignSelf: 'flex-start',
          padding: '10px 0',
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--text-tertiary)',
            marginBottom: 8,
            textTransform: 'uppercase',
            letterSpacing: 1.5,
            padding: '0 8px',
          }}
        >
          目录
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {SECTIONS.map((sec) => (
            <button
              key={sec.id}
              onClick={() => setActiveSection(sec.id)}
              style={{
                display: 'block',
                width: '100',
                padding: '7px 10px',
                borderRadius: 5,
                textAlign: 'left',
                background: activeSection === sec.id ? 'var(--accent)' : 'transparent',
                border: 'none',
                color: activeSection === sec.id ? '#fff' : 'var(--text-secondary)',
                fontSize: 12,
                cursor: 'pointer',
                fontFamily: 'inherit',
                transition: 'all 0.1s',
              }}
            >
              {sec.title}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
