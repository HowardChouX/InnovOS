import { Link } from 'react-router-dom'

interface Props {
  title: string
  description?: string
  icon?: string
}

export function PlaceholderPage({ title, description = '该功能正在开发中', icon = 'fa-solid fa-hammer' }: Props) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
      <div style={{ textAlign: 'center', maxWidth: 400 }}>
        <i className={icon} style={{ fontSize: 48, color: 'var(--text-tertiary)', opacity: 0.3, marginBottom: 16, display: 'block' }} />
        <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 8px' }}>{title}</h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 16px', lineHeight: 1.5 }}>{description}</p>
        <Link to="/" style={{
          padding: '8px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500,
          background: 'var(--accent)', color: '#fff', textDecoration: 'none',
          display: 'inline-block',
        }}>返回首页</Link>
      </div>
    </div>
  )
}
