import { MARKDOWN_SOURCE_LINE_ATTR } from './constants'
import type { FormattingState } from './types'
import type { Editor } from '@tiptap/core'
import { Extension } from '@tiptap/core'
import { TaskItem, TaskList } from '@tiptap/extension-list'
import Typography from '@tiptap/extension-typography'
import { useEditor, useEditorState } from '@tiptap/react'
import { StarterKit } from '@tiptap/starter-kit'
import { useCallback, useEffect, useMemo, useState } from 'react'

import Placeholder from '@tiptap/extension-placeholder'
import { EnhancedLink } from './extensions/enhancedLink'
import { EnhancedImage } from './extensions/enhancedImage'
import { EnhancedMath } from './extensions/enhancedMath'

import { TableKit } from '../../lib/extension-table-plus'

// Create extension to preserve data-source-line attribute
const SourceLineAttribute = Extension.create({
  name: 'sourceLineAttribute',
  addGlobalAttributes() {
    return [
      {
        types: ['paragraph', 'heading', 'blockquote', 'bulletList', 'orderedList', 'listItem', 'horizontalRule'],
        attributes: {
          dataSourceLine: {
            default: null,
            parseHTML: (element) => {
              const value = element.getAttribute(MARKDOWN_SOURCE_LINE_ATTR)
              return value
            },
            renderHTML: (attributes) => {
              if (!attributes.dataSourceLine) return {}
              return { [MARKDOWN_SOURCE_LINE_ATTR]: attributes.dataSourceLine }
            }
          }
        }
      }
    ]
  }
})

export interface UseRichEditorOptions {
  initialContent?: string
  onChange?: (markdown: string) => void
  onHtmlChange?: (html: string) => void
  onContentChange?: (content: string) => void
  onBlur?: () => void
  placeholder?: string
  editable?: boolean
  enableSpellCheck?: boolean
  scrollParent?: () => HTMLElement | null
}

export interface UseRichEditorReturn {
  editor: Editor
  markdown: string
  html: string
  formattingState: FormattingState
  setMarkdown: (content: string) => void
  setHtml: (html: string) => void
  clear: () => void
}

/**
 * Custom hook for managing rich text content
 */
export const useRichEditor = (options: UseRichEditorOptions = {}): UseRichEditorReturn => {
  const {
    initialContent = '',
    onChange,
    onHtmlChange,
    onContentChange,
    onBlur,
    placeholder = '',
    editable = true,
    enableSpellCheck = false,
    scrollParent,
  } = options

  const [markdown, setMarkdownState] = useState<string>(initialContent)

  const html = useMemo(() => {
    if (!markdown) return ''
    return markdown
  }, [markdown])

  // Link editor state
  const [linkEditorState, setLinkEditorState] = useState<{
    show: boolean
    position: { x: number; y: number }
    link: { href: string; text: string; title?: string }
    linkRange?: { from: number; to: number }
  }>({
    show: false,
    position: { x: 0, y: 0 },
    link: { href: '', text: '' }
  })

  const handleLinkHover = useCallback(
    (
      attrs: { href: string; text: string; title?: string },
      position: DOMRect,
      _element: HTMLElement,
      linkRange?: { from: number; to: number }
    ) => {
      if (!editable) return
      const linkPosition = { x: position.left, y: position.top }
      const effectiveHref = attrs.href || attrs.text || ''
      setLinkEditorState({
        show: true,
        position: linkPosition,
        link: { ...attrs, href: effectiveHref },
        linkRange
      })
    },
    [editable]
  )

  const handleLinkHoverEnd = useCallback(() => {}, [])

  // TipTap editor extensions
  const extensions = useMemo(
    () => [
      SourceLineAttribute,
      Placeholder.configure({
        placeholder: placeholder || '输入内容...',
      }),
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3, 4, 5, 6]
        },
        codeBlock: false,
        link: false
      }),
      EnhancedLink.configure({
        onLinkHover: handleLinkHover,
        onLinkHoverEnd: handleLinkHoverEnd,
        editable: editable
      }),
      Typography,
      TaskList,
      TaskItem.configure({
        nested: true
      }),
      TableKit.configure({
        table: { resizable: true, allowTableNodeSelection: true },
        tableRow: {},
        tableHeader: {},
        tableCell: { allowNestedNodes: false }
      }),
      EnhancedImage,
      EnhancedMath.configure({ katexOptions: {} })
    ],
    [handleLinkHover, handleLinkHoverEnd]
  )

  const editor = useEditor({
    shouldRerenderOnTransaction: true,
    extensions,
    content: html || '',
    editable: editable,
    editorProps: {
      attributes: {
        style: editable
          ? 'padding: 16px 20px; min-height: 160px;'
          : 'padding: 16px 20px; min-height: 160px; user-select: text; -webkit-user-select: text;',
        spellcheck: enableSpellCheck ? 'true' : 'false'
      }
    },
    onUpdate: ({ editor: currentEditor, transaction }) => {
      if (!editable || !transaction.docChanged) return
      const htmlContent = currentEditor.getHTML()
      setMarkdownState(htmlContent)
      onChange?.(htmlContent)
      onHtmlChange?.(htmlContent)
      onContentChange?.(currentEditor.getText())
    },
    onBlur: () => {
      onBlur?.()
    },
    onCreate: ({ editor: currentEditor }) => {
      try {
        currentEditor.commands.focus('end')
      } catch (e) {
        // ignore
      }
    }
  })

  useEffect(() => {
    if (editor && !editor.isDestroyed) {
      editor.setEditable(editable)
    }
  }, [editor, editable])

  // Link editor callbacks
  const handleLinkSave = useCallback(
    (href: string, text: string) => {
      if (!editor || editor.isDestroyed) return
      const { linkRange } = linkEditorState
      if (linkRange) {
        editor
          .chain()
          .focus()
          .setTextSelection({ from: linkRange.from, to: linkRange.to })
          .insertContent(text)
          .setTextSelection({ from: linkRange.from, to: linkRange.from + text.length })
          .setEnhancedLink({ href })
          .run()
      }
      setLinkEditorState({ show: false, position: { x: 0, y: 0 }, link: { href: '', text: '' } })
    },
    [editor, linkEditorState]
  )

  const handleLinkRemove = useCallback(() => {
    if (!editor || editor.isDestroyed) return
    const { linkRange } = linkEditorState
    if (linkRange) {
      const tr = editor.state.tr
      tr.removeMark(linkRange.from, linkRange.to, editor.schema.marks.enhancedLink || editor.schema.marks.link)
      editor.view.dispatch(tr)
    } else {
      editor.chain().focus().extendMarkRange('enhancedLink').unsetEnhancedLink().run()
    }
    setLinkEditorState({ show: false, position: { x: 0, y: 0 }, link: { href: '', text: '' } })
  }, [editor, linkEditorState])

  const handleLinkCancel = useCallback(() => {
    setLinkEditorState({ show: false, position: { x: 0, y: 0 }, link: { href: '', text: '' } })
  }, [])

  useEffect(() => {
    return () => {
      if (editor && !editor.isDestroyed) {
        editor.destroy()
      }
    }
  }, [editor])

  const formattingState = useEditorState({
    editor,
    selector: ({ editor: ed }) => {
      if (!ed || ed.isDestroyed) {
        return {
          isBold: false, canBold: false,
          isItalic: false, canItalic: false,
          isUnderline: false, canUnderline: false,
          isStrike: false, canStrike: false,
          isCode: false, canCode: false,
          canClearMarks: false,
          isParagraph: false,
          isHeading1: false, isHeading2: false, isHeading3: false,
          isHeading4: false, isHeading5: false, isHeading6: false,
          isBulletList: false, isOrderedList: false,
          isCodeBlock: false, isBlockquote: false,
          isLink: false, canLink: false, canUnlink: false,
          canUndo: false, canRedo: false,
          isTable: false, canTable: false,
          canImage: false,
          isMath: false, isInlineMath: false, canMath: false,
          isTaskList: false,
        }
      }
      return {
        isBold: ed.isActive('bold') ?? false,
        canBold: ed.can().chain().toggleBold().run() ?? false,
        isItalic: ed.isActive('italic') ?? false,
        canItalic: ed.can().chain().toggleItalic().run() ?? false,
        isUnderline: ed.isActive('underline') ?? false,
        canUnderline: ed.can().chain().toggleUnderline().run() ?? false,
        isStrike: ed.isActive('strike') ?? false,
        canStrike: ed.can().chain().toggleStrike().run() ?? false,
        isCode: ed.isActive('code') ?? false,
        canCode: ed.can().chain().toggleCode().run() ?? false,
        canClearMarks: ed.can().chain().unsetAllMarks().run() ?? false,
        isParagraph: ed.isActive('paragraph') ?? false,
        isHeading1: ed.isActive('heading', { level: 1 }) ?? false,
        isHeading2: ed.isActive('heading', { level: 2 }) ?? false,
        isHeading3: ed.isActive('heading', { level: 3 }) ?? false,
        isHeading4: ed.isActive('heading', { level: 4 }) ?? false,
        isHeading5: ed.isActive('heading', { level: 5 }) ?? false,
        isHeading6: ed.isActive('heading', { level: 6 }) ?? false,
        isBulletList: ed.isActive('bulletList') ?? false,
        isOrderedList: ed.isActive('orderedList') ?? false,
        isCodeBlock: ed.isActive('codeBlock') ?? false,
        isBlockquote: ed.isActive('blockquote') ?? false,
        isLink: (ed.isActive('enhancedLink') || ed.isActive('link')) ?? false,
        canLink: ed.can().chain().setEnhancedLink({ href: '' }).run() ?? false,
        canUnlink: ed.can().chain().unsetEnhancedLink().run() ?? false,
        canUndo: ed.can().chain().undo().run() ?? false,
        canRedo: ed.can().chain().redo().run() ?? false,
        isTable: ed.isActive('table') ?? false,
        canTable: ed.can().chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run() ?? false,
        canImage: ed.can().chain().setImage({ src: '' }).run() ?? false,
        isMath: false, isInlineMath: false, canMath: true,
        isTaskList: ed.isActive('taskList') ?? false,
      }
    }
  })

  const setMarkdown = useCallback(
    (content: string) => {
      try {
        setMarkdownState(content)
        onChange?.(content)
        editor.commands.setContent(content)
        onHtmlChange?.(content)
      } catch (e) {
        console.error('Error setting markdown content:', e)
      }
    },
    [editor.commands, onChange, onHtmlChange]
  )

  const setHtml = useCallback(
    (htmlContent: string) => {
      try {
        setMarkdownState(htmlContent)
        onChange?.(htmlContent)
        editor.commands.setContent(htmlContent)
        onHtmlChange?.(htmlContent)
      } catch (e) {
        console.error('Error setting HTML content:', e)
      }
    },
    [editor.commands, onChange, onHtmlChange]
  )

  const clear = useCallback(() => {
    setMarkdownState('')
    onChange?.('')
    onHtmlChange?.('')
  }, [onChange, onHtmlChange])

  return {
    editor,
    markdown,
    html,
    formattingState,
    setMarkdown,
    setHtml,
    clear,
  }
}
