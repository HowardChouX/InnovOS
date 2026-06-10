import { EditorContent } from '@tiptap/react'
import React, { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'

import './tiptap.css'

import {
  getAllCommands,
  getToolbarCommands,
  registerCommand,
  registerToolbarCommand,
  setCommandAvailability,
  unregisterCommand,
  unregisterToolbarCommand
} from './command'
import LinkEditor from './components/LinkEditor'
import { EditorContent as StyledEditorContent, RichEditorWrapper } from './styles'
import { Toolbar } from './toolbar'
import type { FormattingCommand, RichEditorProps, RichEditorRef } from './types'
import { useRichEditor } from './useRichEditor'

const RichEditor = ({
  ref,
  initialContent = '',
  placeholder = '',
  onContentChange,
  onHtmlChange,
  onMarkdownChange,
  onBlur,
  editable = true,
  className = '',
  wrapperStyle,
  showToolbar = true,
  minHeight,
  maxHeight,
  initialCommands,
  onCommandsReady,
  isFullWidth = false,
  fontFamily = 'default',
  fontSize = 16,
  enableSpellCheck = false
}: RichEditorProps & { ref?: React.RefObject<RichEditorRef | null> }) => {
  const {
    editor,
    markdown,
    html,
    formattingState,
    setMarkdown,
    setHtml,
    clear,
  } = useRichEditor({
    initialContent,
    onChange: onMarkdownChange,
    onHtmlChange,
    onContentChange,
    onBlur,
    placeholder,
    editable,
    enableSpellCheck,
  })

  const scrollContainerRef = useRef<HTMLDivElement | null>(null)

  const handleCommand = useCallback(
    (command: FormattingCommand) => {
      if (!editor) return
      switch (command) {
        case 'bold': editor.chain().focus().toggleBold().run(); break
        case 'italic': editor.chain().focus().toggleItalic().run(); break
        case 'underline': editor.chain().focus().toggleUnderline().run(); break
        case 'strike': editor.chain().focus().toggleStrike().run(); break
        case 'code': editor.chain().focus().toggleCode().run(); break
        case 'clearMarks': editor.chain().focus().unsetAllMarks().run(); break
        case 'paragraph': editor.chain().focus().setParagraph().run(); break
        case 'heading1': editor.chain().focus().toggleHeading({ level: 1 }).run(); break
        case 'heading2': editor.chain().focus().toggleHeading({ level: 2 }).run(); break
        case 'heading3': editor.chain().focus().toggleHeading({ level: 3 }).run(); break
        case 'heading4': editor.chain().focus().toggleHeading({ level: 4 }).run(); break
        case 'heading5': editor.chain().focus().toggleHeading({ level: 5 }).run(); break
        case 'heading6': editor.chain().focus().toggleHeading({ level: 6 }).run(); break
        case 'bulletList': editor.chain().focus().toggleBulletList().run(); break
        case 'orderedList': editor.chain().focus().toggleOrderedList().run(); break
        case 'codeBlock': editor.chain().focus().toggleCodeBlock().run(); break
        case 'blockquote': editor.chain().focus().toggleBlockquote().run(); break
        case 'link': {
          const sel = editor.state.selection
          if (editor.isActive('enhancedLink')) {
            editor.chain().focus().unsetEnhancedLink().run()
          } else if (sel.from !== sel.to) {
            const text = editor.state.doc.textBetween(sel.from, sel.to)
            if (text.trim()) {
              const url = text.trim().startsWith('http') ? text.trim() : `https://${text.trim()}`
              editor.chain().focus().setEnhancedLink({ href: url }).run()
            }
          } else {
            editor.chain().focus().setEnhancedLink({ href: '' }).run()
          }
          break
        }
        case 'undo': editor.chain().focus().undo().run(); break
        case 'redo': editor.chain().focus().redo().run(); break
        case 'table': editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); break
        case 'taskList': editor.chain().focus().toggleTaskList().run(); break
        default: break
      }
    },
    [editor]
  )

  // Register initial commands on mount
  useEffect(() => {
    if (initialCommands) {
      initialCommands.forEach((cmd) => {
        if (cmd.showInToolbar) {
          registerToolbarCommand(cmd)
        } else {
          registerCommand(cmd)
        }
      })
    }
  }, [initialCommands])

  // Call onCommandsReady when editor is ready
  useEffect(() => {
    if (editor && onCommandsReady) {
      const commandAPI = {
        registerCommand, registerToolbarCommand,
        unregisterCommand, unregisterToolbarCommand, setCommandAvailability
      }
      onCommandsReady(commandAPI)
    }
  }, [editor, onCommandsReady])

  // Expose editor methods via ref
  useImperativeHandle(
    ref,
    () => ({
      getContent: () => editor?.getText() || '',
      getHtml: () => html,
      getMarkdown: () => markdown,
      setContent: (content: string) => editor?.commands.setContent(content),
      setHtml: (htmlContent: string) => setHtml(htmlContent),
      setMarkdown: (markdownContent: string) => setMarkdown(markdownContent),
      focus: () => editor?.commands.focus(),
      clear: () => { clear(); editor?.commands.clearContent() },
      insertText: (text: string) => editor?.commands.insertContent(text),
      executeCommand: (command: string, value?: any) => {
        if (editor?.commands && command in editor.commands) {
          (editor.commands as any)[command](value)
        }
      },
      getPreviewText: () => editor?.getText().slice(0, 100) || '',
      getScrollTop: () => scrollContainerRef.current?.scrollTop ?? 0,
      setScrollTop: (value: number) => { if (scrollContainerRef.current) scrollContainerRef.current.scrollTop = value },
      registerCommand, registerToolbarCommand, unregisterCommand, unregisterToolbarCommand,
      setCommandAvailability, getAllCommands, getToolbarCommands
    }),
    [editor, html, markdown, setHtml, setMarkdown, clear]
  )

  return (
    <RichEditorWrapper
      className={`rich-editor-wrapper ${className}`}
      $minHeight={minHeight}
      $maxHeight={maxHeight}
      $isFullWidth={isFullWidth}
      $fontFamily={fontFamily}
      $fontSize={fontSize}
      style={wrapperStyle}
    >
      {showToolbar && (
        <Toolbar
          editor={editor}
          formattingState={formattingState}
          onCommand={handleCommand}
          scrollContainer={scrollContainerRef}
        />
      )}
      <div
        ref={scrollContainerRef}
        className="rich-editor-content"
        style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'auto' }}
      >
        <StyledEditorContent>
          <EditorContent style={{ minHeight: '100%' }} editor={editor} />
        </StyledEditorContent>
      </div>
      <LinkEditor
        visible={false}
        position={{ x: 0, y: 0 }}
        link={{ href: '', text: '' }}
        onSave={() => {}}
        onRemove={() => {}}
        onCancel={() => {}}
      />
    </RichEditorWrapper>
  )
}

RichEditor.displayName = 'RichEditor'

export default RichEditor
