export function WelcomeGuide() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: 400, textAlign: 'center', padding: '40px 20px',
    }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent)', marginBottom: 8 }}>
        InnovOS
      </div>
      <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 32, maxWidth: 480 }}>
        智能创新问题求解系统 — 输入技术问题，AI 驱动创新路径推理与方案生成
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, maxWidth: 600 }}>
        {[
          { step: '1', title: '描述问题', desc: '用自然语言描述您的技术问题或创新目标', icon: 'fa-pen' },
          { step: '2', title: 'AI 分析', desc: '自动识别核心矛盾，检索专利路径，推荐创新原理', icon: 'fa-brain' },
          { step: '3', title: '生成方案', desc: '多 Agent 协同生成创新方案，四维评估引擎评分', icon: 'fa-lightbulb' },
        ].map((item) => (
          <div key={item.step} style={{
            background: 'var(--bg-card)', borderRadius: 10, padding: 20,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%', background: 'var(--accent)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 10px', fontSize: 14, fontWeight: 700, color: '#fff',
            }}>{item.step}</div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: 'var(--text-primary)' }}>{item.title}</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>{item.desc}</div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 28, padding: '12px 16px', background: 'var(--bg-card)',
        border: '1px solid var(--border-light)', borderRadius: 8, maxWidth: 480,
        fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'left', lineHeight: 1.6,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 4, color: 'var(--text-secondary)' }}>使用示例</div>
        <div>"如何提高锂电池能量密度的同时保证安全性？"</div>
        <div>"优化风力发电叶片效率，降低噪音"</div>
        <div>"设计轻量化汽车车身，保持碰撞强度"</div>
        <div style={{ marginTop: 8, color: 'var(--accent-yellow)' }}>
          ⚡ 需要设置 DEEPSEEK_API_KEY 环境变量才能启用 AI 分析
        </div>
      </div>
    </div>
  );
}
