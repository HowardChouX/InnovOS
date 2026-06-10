import React, { useEffect, useState } from 'react'
import { getCommandsByGroup } from './command'
import { ToolbarButton, ToolbarDivider, ToolbarWrapper } from './styles'
import type { FormattingCommand, FormattingState, ToolbarProps } from './types'
import ImageUploader from './components/ImageUploader'
import MathInputDialog from './components/MathInputDialog'

export function Toolbar({ editor, formattingState, onCommand, scrollContainer }: ToolbarProps) {
  const [showImageUploader, setShowImageUploader] = useState(false)
  const [showMathInput, setShowMathInput] = useState(false)
  const [placeholderCbs, setPlaceholderCbs] = useState<{
    onMathSubmit?: (latex: string) => void
    onMathCancel?: () => void
    onMathFormulaChange?: (formula: string) => void
    mathDefaultValue?: string
    mathPosition?: { x: number; y: number; top: number }
    onImageSelect?: (imageUrl: string) => void
    onImageCancel?: () => void
  }>({})

  // Listen for custom events from placeholder nodes
  useEffect(() => {
    const handleMathDialog = (event: CustomEvent) => {
      const { defaultValue, onSubmit, onFormulaChange, position } = event.detail
      setPlaceholderCbs((prev) => ({
        ...prev,
        onMathSubmit: onSubmit,
        onMathCancel: () => {},
        onMathFormulaChange: onFormulaChange,
        mathDefaultValue: defaultValue,
        mathPosition: position,
      }))
      setShowMathInput(true)
    }
    const handleImageUploader = (event: CustomEvent) => {
      const { onImageSelect, onCancel } = event.detail
      setPlaceholderCbs((prev) => ({ ...prev, onImageSelect, onImageCancel: onCancel }))
      setShowImageUploader(true)
    }
    window.addEventListener('openMathDialog', handleMathDialog as EventListener)
    window.addEventListener('openImageUploader', handleImageUploader as EventListener)
    return () => {
      window.removeEventListener('openMathDialog', handleMathDialog as EventListener)
      window.removeEventListener('openImageUploader', handleImageUploader as EventListener)
    }
  }, [])

  if (!editor) return null

  const TOOLBAR_GROUP_ORDER = ['formatting', 'text', 'blocks', 'structure', 'media', 'history']

  function getFormattingState(state: FormattingState, command: FormattingCommand): boolean {
    switch (command) {
      case 'bold': return state.isBold
      case 'italic': return state.isItalic
      case 'underline': return state.isUnderline
      case 'strike': return state.isStrike
      case 'code': return state.isCode
      case 'paragraph': return state.isParagraph
      case 'heading1': return state.isHeading1
      case 'heading2': return state.isHeading2
      case 'heading3': return state.isHeading3
      case 'heading4': return state.isHeading4
      case 'heading5': return state.isHeading5
      case 'heading6': return state.isHeading6
      case 'bulletList': return state.isBulletList
      case 'orderedList': return state.isOrderedList
      case 'codeBlock': return state.isCodeBlock
      case 'blockquote': return state.isBlockquote
      case 'link': return state.isLink
      case 'table': return state.isTable
      case 'taskList': return state.isTaskList
      default: return false
    }
  }

  function getDisabledState(state: FormattingState, command: FormattingCommand): boolean {
    switch (command) {
      case 'undo': return !state.canUndo
      case 'redo': return !state.canRedo
      case 'link': return !state.canLink
      case 'bold': return !state.canBold
      case 'italic': return !state.canItalic
      case 'underline': return !state.canUnderline
      case 'strike': return !state.canStrike
      case 'code': return !state.canCode
      case 'table': return !state.canTable
      default: return false
    }
  }

  const handleCommand = (command: FormattingCommand) => {
    if (command === 'image') {
      editor.chain().focus().insertImagePlaceholder().run()
    } else if (command === 'blockMath') {
      editor.chain().focus().insertMathPlaceholder({ mathType: 'block' }).run()
    } else if (command === 'inlineMath') {
      editor.chain().focus().insertMathPlaceholder({ mathType: 'inline' }).run()
    } else {
      onCommand(command)
    }
  }

  const handleImageSelect = (imageUrl: string) => {
    if (editor) {
      editor.chain().focus().setImage({ src: imageUrl }).run()
    }
    setShowImageUploader(false)
  }

  const groups = TOOLBAR_GROUP_ORDER.map((groupName, groupIndex) => {
    const commands = getCommandsByGroup(groupName)
    if (commands.length === 0) return null
    const items = commands.map((cmd, cmdIndex) => {
      const fc = cmd.formattingCommand as FormattingCommand
      const isActive = getFormattingState(formattingState, fc)
      const isDisabled = getDisabledState(formattingState, fc)
      return (
        <ToolbarButton
          key={`${cmd.id}-${cmdIndex}`}
          title={cmd.title}
          $active={isActive}
          disabled={isDisabled}
          onClick={() => handleCommand(fc)}
        >
          <cmd.icon size={16} />
        </ToolbarButton>
      )
    })
    return (
      <React.Fragment key={groupName}>
        {groupIndex > 0 && <ToolbarDivider />}
        {items}
      </React.Fragment>
    )
  })

  return (
    <>
      <ToolbarWrapper>{groups}</ToolbarWrapper>
      <ImageUploader
        visible={showImageUploader}
        onImageSelect={(imageUrl) => {
          if (placeholderCbs.onImageSelect) {
            placeholderCbs.onImageSelect(imageUrl)
            setPlaceholderCbs((prev) => ({ ...prev, onImageSelect: undefined, onImageCancel: undefined }))
          } else {
            handleImageSelect(imageUrl)
          }
          setShowImageUploader(false)
        }}
        onClose={() => {
          if (placeholderCbs.onImageCancel) {
            placeholderCbs.onImageCancel()
            setPlaceholderCbs((prev) => ({ ...prev, onImageSelect: undefined, onImageCancel: undefined }))
          }
          setShowImageUploader(false)
        }}
      />
      <MathInputDialog
        visible={showMathInput}
        defaultValue={placeholderCbs.mathDefaultValue || ''}
        position={placeholderCbs.mathPosition}
        scrollContainer={scrollContainer}
        onSubmit={(formula) => {
          if (placeholderCbs.onMathSubmit) {
            placeholderCbs.onMathSubmit(formula)
          } else if (editor && formula.trim()) {
            editor.chain().focus().insertBlockMath({ latex: formula }).run()
          }
          setPlaceholderCbs((prev) => ({
            ...prev,
            onMathSubmit: undefined,
            onMathCancel: undefined,
            onMathFormulaChange: undefined,
            mathDefaultValue: undefined,
            mathPosition: undefined,
          }))
          setShowMathInput(false)
        }}
        onCancel={() => {
          if (placeholderCbs.onMathCancel) {
            placeholderCbs.onMathCancel()
          }
          setPlaceholderCbs((prev) => ({
            ...prev,
            onMathSubmit: undefined,
            onMathCancel: undefined,
            onMathFormulaChange: undefined,
            mathDefaultValue: undefined,
            mathPosition: undefined,
          }))
          setShowMathInput(false)
        }}
        onFormulaChange={(formula) => {
          if (placeholderCbs.onMathFormulaChange) {
            placeholderCbs.onMathFormulaChange(formula)
          } else if (editor) {
            const inlineMath = editor.schema.nodes.inlineMath
            const blockMath = editor.schema.nodes.blockMath
            if (inlineMath) {
              editor.chain().updateInlineMath({ latex: formula }).run()
            } else if (blockMath) {
              editor.chain().updateBlockMath({ latex: formula }).run()
            }
          }
        }}
      />
    </>
  )
}
