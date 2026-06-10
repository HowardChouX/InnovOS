import React, { useState } from 'react'

interface ImageUploaderProps {
  /** Whether the uploader is visible */
  visible: boolean
  /** Callback when image is selected/uploaded */
  onImageSelect: (imageUrl: string) => void
  /** Callback when uploader should be closed */
  onClose: () => void
}

const MAX_IMAGE_SIZE = 10 * 1024 * 1024

// Convert file to base64 URL
const convertFileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
      } else {
        reject(new Error('Failed to convert file to base64'))
      }
    }
    reader.onerror = () => reject(new Error('Failed to read file'))
    reader.readAsDataURL(file)
  })
}

const ImageUploader: React.FC<ImageUploaderProps> = ({ visible, onImageSelect, onClose }) => {
  const [activeTab, setActiveTab] = useState<'upload' | 'link'>('upload')
  const [urlInput, setUrlInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const validateFile = (file: File): string | null => {
    if (!file.type.startsWith('image/')) {
      return '仅支持图片格式'
    }
    if (file.size >= MAX_IMAGE_SIZE) {
      return '图片大小不能超过 10MB'
    }
    return null
  }

  const handleFileSelect = async (file: File) => {
    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const base64Url = await convertFileToBase64(file)
      onImageSelect(base64Url)
      onClose()
    } catch {
      setError('图片上传失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    const files = e.dataTransfer.files
    if (files.length > 0) {
      const file = files[0]
      if (file) {
        void handleFileSelect(file)
      }
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleUrlSubmit = () => {
    const trimmed = urlInput.trim()
    if (!trimmed) {
      setError('请输入图片链接')
      return
    }

    try {
      new URL(trimmed)
      onImageSelect(trimmed)
      setUrlInput('')
      onClose()
    } catch {
      setError('链接格式不正确，请输入有效的 URL')
    }
  }

  const handleCancel = () => {
    setUrlInput('')
    setError(null)
    onClose()
  }

  if (!visible) return null

  const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    zIndex: 1000,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }

  const cardStyle: React.CSSProperties = {
    background: 'var(--bg-card, #fff)',
    border: '1px solid var(--border, #d9d9d9)',
    borderRadius: 8,
    boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
    padding: 24,
    width: 540,
    maxWidth: '90vw',
  }

  const tabBarStyle: React.CSSProperties = {
    display: 'flex',
    gap: 4,
    marginBottom: 16,
    borderBottom: '1px solid var(--border, #e5e7eb)',
    paddingBottom: 0,
  }

  const tabBtnStyle = (active: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '8px 16px',
    fontSize: 14,
    border: 'none',
    borderBottom: active ? '2px solid var(--color-primary, #7c3aed)' : '2px solid transparent',
    background: 'transparent',
    color: active ? 'var(--color-primary, #7c3aed)' : 'var(--color-foreground, #333)',
    cursor: 'pointer',
    fontWeight: active ? 600 : 400,
    marginBottom: -1,
  })

  const inputStyle: React.CSSProperties = {
    width: '100%',
    height: 36,
    padding: '0 12px',
    fontSize: 14,
    border: '1px solid var(--border, #d9d9d9)',
    borderRadius: 6,
    background: 'var(--bg-input, #fff)',
    color: 'var(--color-foreground, #333)',
    outline: 'none',
    boxSizing: 'border-box',
  }

  const btnStyle: React.CSSProperties = {
    padding: '8px 16px',
    fontSize: 14,
    border: '1px solid var(--border, #d9d9d9)',
    borderRadius: 6,
    cursor: 'pointer',
    background: 'transparent',
    color: 'var(--color-foreground, #333)',
  }

  const primaryBtnStyle: React.CSSProperties = {
    ...btnStyle,
    background: 'var(--color-primary, #7c3aed)',
    color: '#fff',
    border: 'none',
  }

  const disabledBtnStyle: React.CSSProperties = {
    ...primaryBtnStyle,
    opacity: 0.5,
    cursor: 'not-allowed',
  }

  const dropzoneStyle: React.CSSProperties = {
    minHeight: 180,
    border: '2px dashed var(--border, #d9d9d9)',
    borderRadius: 8,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    background: 'var(--bg-muted, #f9fafb)',
    cursor: loading ? 'not-allowed' : 'pointer',
    opacity: loading ? 0.6 : 1,
    padding: 24,
  }

  return (
    <div style={overlayStyle} onClick={handleCancel}>
      <div style={cardStyle} onClick={(e) => e.stopPropagation()}>
        {/* Title */}
        <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 16, color: 'var(--color-foreground, #333)' }}>
          插入图片
        </div>

        {/* Tabs */}
        <div style={tabBarStyle}>
          <button
            style={tabBtnStyle(activeTab === 'upload')}
            onClick={() => setActiveTab('upload')}
          >
            <i className="fa-solid fa-upload" style={{ fontSize: 13 }} />
            上传
          </button>
          <button
            style={tabBtnStyle(activeTab === 'link')}
            onClick={() => setActiveTab('link')}
          >
            <i className="fa-solid fa-link" style={{ fontSize: 13 }} />
            链接
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div style={{
            padding: '8px 12px',
            marginBottom: 12,
            background: 'var(--bg-danger-light, #fef2f2)',
            border: '1px solid var(--color-danger, #e53e3e)',
            borderRadius: 6,
            color: 'var(--color-danger, #e53e3e)',
            fontSize: 13,
          }}>
            {error}
          </div>
        )}

        {/* Upload tab */}
        {activeTab === 'upload' && (
          <div
            style={dropzoneStyle}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => !loading && document.getElementById('image-upload-input')?.click()}
          >
            <div style={{
              width: 40,
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 8,
              background: 'var(--bg-muted-foreground, #f3f4f6)',
            }}>
              {loading ? (
                <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: 18, color: 'var(--text-muted, #9ca3af)' }} />
              ) : (
                <i className="fa-solid fa-image" style={{ fontSize: 18, color: 'var(--text-muted, #9ca3af)' }} />
              )}
            </div>
            <div style={{ fontWeight: 500, fontSize: 14, color: 'var(--color-foreground, #333)' }}>
              {loading ? '正在上传...' : '点击或拖拽图片到此处'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted, #9ca3af)' }}>
              {loading ? '正在处理中...' : '支持 JPG、PNG、GIF 等格式，最大 10MB'}
            </div>
            <input
              id="image-upload-input"
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              disabled={loading}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) {
                  void handleFileSelect(file)
                }
                // Reset so the same file can be selected again
                e.target.value = ''
              }}
            />
          </div>
        )}

        {/* Link tab */}
        {activeTab === 'link' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <i
                className="fa-solid fa-link"
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: 12,
                  transform: 'translateY(-50%)',
                  fontSize: 14,
                  color: 'var(--text-muted, #9ca3af)',
                }}
              />
              <input
                style={{ ...inputStyle, paddingLeft: 36 }}
                placeholder="输入图片 URL 链接"
                value={urlInput}
                onChange={(e) => {
                  setUrlInput(e.target.value)
                  if (error) setError(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleUrlSubmit()
                  }
                }}
              />
            </div>
            <button
              style={btnStyle}
              onClick={() => {
                setUrlInput('')
                setError(null)
              }}
            >
              清空
            </button>
            <button
              style={urlInput.trim() ? primaryBtnStyle : disabledBtnStyle}
              onClick={handleUrlSubmit}
              disabled={!urlInput.trim()}
            >
              嵌入图片
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default ImageUploader
