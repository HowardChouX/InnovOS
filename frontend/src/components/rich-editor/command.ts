import type { Editor } from '@tiptap/core'
import type { LucideIcon } from 'lucide-react'
import {
  Bold,
  Calculator,
  CheckCircle,
  Code,
  FileCode,
  Heading1,
  Heading2,
  Heading3,
  Image,
  Italic,
  Link,
  List,
  ListOrdered,
  Minus,
  Omega,
  Quote,
  Redo,
  Strikethrough,
  Table,
  Type,
  Underline,
  Undo,
  X
} from 'lucide-react'

const logger = {
  info: (...args: any[]) => console.log('[RichEditor.Command]', ...args),
  warn: (...args: any[]) => console.warn('[RichEditor.Command]', ...args),
  error: (...args: any[]) => console.error('[RichEditor.Command]', ...args),
}

export interface Command {
  id: string
  title: string
  description: string
  category: CommandCategory
  icon: LucideIcon
  keywords: string[]
  handler: (editor: Editor) => void
  isAvailable?: (editor: Editor) => boolean
  // Toolbar support
  showInToolbar?: boolean
  toolbarGroup?: 'text' | 'formatting' | 'blocks' | 'media' | 'structure' | 'history'
  formattingCommand?: string // Maps to FormattingCommand for state checking
}

export enum CommandCategory {
  TEXT = 'text',
  LISTS = 'lists',
  BLOCKS = 'blocks',
  MEDIA = 'media',
  STRUCTURE = 'structure',
  SPECIAL = 'special'
}

export interface CommandSuggestion {
  query: string
  range: any
  clientRect?: () => DOMRect | null
}

// Internal dynamic command registry
const commandRegistry = new Map<string, Command>()

export function registerCommand(cmd: Command): void {
  commandRegistry.set(cmd.id, cmd)
}

export function unregisterCommand(id: string): void {
  commandRegistry.delete(id)
}

export function getCommand(id: string): Command | undefined {
  return commandRegistry.get(id)
}

export function getAllCommands(): Command[] {
  return Array.from(commandRegistry.values())
}

export function getToolbarCommands(): Command[] {
  return getAllCommands().filter((cmd) => cmd.showInToolbar)
}

export function getCommandsByGroup(group: string): Command[] {
  return getAllCommands().filter((cmd) => cmd.toolbarGroup === group)
}

// Dynamic toolbar management
export function registerToolbarCommand(cmd: Command): void {
  if (!cmd.showInToolbar) {
    cmd.showInToolbar = true
  }
  registerCommand(cmd)
}

export function unregisterToolbarCommand(id: string): void {
  const cmd = getCommand(id)
  if (cmd) {
    cmd.showInToolbar = false
    // Keep command for slash menu, just hide from toolbar
  }
}

export function setCommandAvailability(id: string, isAvailable: (editor: Editor) => boolean): void {
  const cmd = getCommand(id)
  if (cmd) {
    cmd.isAvailable = isAvailable
  }
}

// Convenience functions for common scenarios
export function disableCommandsWhen(commandIds: string[], condition: (editor: Editor) => boolean): void {
  commandIds.forEach((id) => {
    setCommandAvailability(id, (editor) => !condition(editor))
  })
}

export function hideToolbarCommandsWhen(commandIds: string[], condition: () => boolean): void {
  if (condition()) {
    commandIds.forEach((id) => unregisterToolbarCommand(id))
  } else {
    commandIds.forEach((id) => {
      const cmd = getCommand(id)
      if (cmd) {
        cmd.showInToolbar = true
      }
    })
  }
}

// Default command definitions
const DEFAULT_COMMANDS: Command[] = [
  {
    id: 'bold',
    title: 'Bold',
    description: 'Make text bold',
    category: CommandCategory.TEXT,
    icon: Bold,
    keywords: ['bold', 'strong', 'b'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleBold().run()
    },
    showInToolbar: true,
    toolbarGroup: 'formatting',
    formattingCommand: 'bold'
  },
  {
    id: 'italic',
    title: 'Italic',
    description: 'Make text italic',
    category: CommandCategory.TEXT,
    icon: Italic,
    keywords: ['italic', 'emphasis', 'i'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleItalic().run()
    },
    showInToolbar: true,
    toolbarGroup: 'formatting',
    formattingCommand: 'italic'
  },
  {
    id: 'underline',
    title: 'Underline',
    description: 'Underline text',
    category: CommandCategory.TEXT,
    icon: Underline,
    keywords: ['underline', 'u'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleUnderline().run()
    },
    showInToolbar: true,
    toolbarGroup: 'formatting',
    formattingCommand: 'underline'
  },
  {
    id: 'strike',
    title: 'Strikethrough',
    description: 'Strike through text',
    category: CommandCategory.TEXT,
    icon: Strikethrough,
    keywords: ['strikethrough', 'strike', 's'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleStrike().run()
    },
    showInToolbar: true,
    toolbarGroup: 'formatting',
    formattingCommand: 'strike'
  },
  {
    id: 'inlineCode',
    title: 'Inline Code',
    description: 'Add inline code',
    category: CommandCategory.SPECIAL,
    icon: Code,
    keywords: ['code', 'inline', 'monospace'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleCode().run()
    },
    showInToolbar: true,
    toolbarGroup: 'formatting',
    formattingCommand: 'code'
  },
  {
    id: 'paragraph',
    title: 'Text',
    description: 'Start writing with plain text',
    category: CommandCategory.TEXT,
    icon: Type,
    keywords: ['text', 'paragraph', 'p'],
    handler: (editor: Editor) => {
      editor.chain().focus().setParagraph().run()
    },
    showInToolbar: true,
    toolbarGroup: 'text',
    formattingCommand: 'paragraph'
  },
  {
    id: 'heading1',
    title: 'Heading 1',
    description: 'Big section heading',
    category: CommandCategory.TEXT,
    icon: Heading1,
    keywords: ['heading', 'h1', 'title', 'big'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleHeading({ level: 1 }).run()
    },
    showInToolbar: true,
    toolbarGroup: 'text',
    formattingCommand: 'heading1'
  },
  {
    id: 'heading2',
    title: 'Heading 2',
    description: 'Medium section heading',
    category: CommandCategory.TEXT,
    icon: Heading2,
    keywords: ['heading', 'h2', 'subtitle', 'medium'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleHeading({ level: 2 }).run()
    },
    showInToolbar: true,
    toolbarGroup: 'text',
    formattingCommand: 'heading2'
  },
  {
    id: 'heading3',
    title: 'Heading 3',
    description: 'Small section heading',
    category: CommandCategory.TEXT,
    icon: Heading3,
    keywords: ['heading', 'h3', 'small'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleHeading({ level: 3 }).run()
    },
    showInToolbar: true,
    toolbarGroup: 'text',
    formattingCommand: 'heading3'
  },
  {
    id: 'bulletList',
    title: 'Bulleted list',
    description: 'Create a simple bulleted list',
    category: CommandCategory.LISTS,
    icon: List,
    keywords: ['bullet', 'list', 'ul', 'unordered'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleBulletList().run()
    },
    showInToolbar: true,
    toolbarGroup: 'blocks',
    formattingCommand: 'bulletList'
  },
  {
    id: 'orderedList',
    title: 'Numbered list',
    description: 'Create a list with numbering',
    category: CommandCategory.LISTS,
    icon: ListOrdered,
    keywords: ['number', 'list', 'ol', 'ordered'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleOrderedList().run()
    },
    showInToolbar: true,
    toolbarGroup: 'blocks',
    formattingCommand: 'orderedList'
  },
  {
    id: 'codeBlock',
    title: 'Code',
    description: 'Capture a code snippet',
    category: CommandCategory.BLOCKS,
    icon: FileCode,
    keywords: ['code', 'block', 'snippet', 'programming'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleCodeBlock().run()
    },
    showInToolbar: true,
    toolbarGroup: 'blocks',
    formattingCommand: 'codeBlock'
  },
  {
    id: 'blockquote',
    title: 'Quote',
    description: 'Capture a quote',
    category: CommandCategory.BLOCKS,
    icon: Quote,
    keywords: ['quote', 'blockquote', 'citation'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleBlockquote().run()
    },
    showInToolbar: true,
    toolbarGroup: 'blocks',
    formattingCommand: 'blockquote'
  },
  {
    id: 'divider',
    title: 'Divider',
    description: 'Add a horizontal line',
    category: CommandCategory.STRUCTURE,
    icon: Minus,
    keywords: ['divider', 'hr', 'line', 'separator'],
    handler: (editor: Editor) => {
      editor.chain().focus().setHorizontalRule().run()
    }
  },
  {
    id: 'image',
    title: 'Image',
    description: 'Insert an image',
    category: CommandCategory.MEDIA,
    icon: Image,
    keywords: ['image', 'img', 'picture', 'photo'],
    handler: (editor: Editor) => {
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = 'image/*'
      input.onchange = () => {
        const file = input.files?.[0]
        if (!file) return
        const reader = new FileReader()
        reader.onload = (e) => {
          const dataUrl = e.target?.result as string
          if (dataUrl) {
            editor.chain().focus().setImage({ src: dataUrl }).run()
          }
        }
        reader.readAsDataURL(file)
      }
      input.click()
    },
    showInToolbar: true,
    toolbarGroup: 'media',
    formattingCommand: 'image'
  },
  {
    id: 'link',
    title: 'Link',
    description: 'Add a link',
    category: CommandCategory.SPECIAL,
    icon: Link,
    keywords: ['link', 'url', 'href'],
    handler: (editor: Editor) => {
      editor.chain().focus().setEnhancedLink({ href: '' }).run()
    },
    showInToolbar: true,
    toolbarGroup: 'media',
    formattingCommand: 'link'
  },
  {
    id: 'table',
    title: 'Table',
    description: 'Insert a table',
    category: CommandCategory.STRUCTURE,
    icon: Table,
    keywords: ['table', 'grid', 'rows', 'columns'],
    handler: (editor: Editor) => {
      editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
    },
    showInToolbar: true,
    toolbarGroup: 'structure',
    formattingCommand: 'table'
  },
  // Additional commands for slash menu only
  {
    id: 'taskList',
    title: 'Task List',
    description: 'Create a checklist',
    category: CommandCategory.LISTS,
    icon: CheckCircle,
    keywords: ['task', 'todo', 'checklist', 'checkbox'],
    handler: (editor: Editor) => {
      editor.chain().focus().toggleTaskList().run()
    },
    showInToolbar: true,
    toolbarGroup: 'blocks',
    formattingCommand: 'taskList'
  },
  {
    id: 'hardBreak',
    title: 'Line Break',
    description: 'Insert a line break',
    category: CommandCategory.STRUCTURE,
    icon: X,
    keywords: ['break', 'br', 'newline'],
    handler: (editor: Editor) => {
      editor.chain().focus().setHardBreak().run()
    }
  },
  {
    id: 'inlineMath',
    title: 'Inline Equation',
    description: 'Insert inline equation',
    category: CommandCategory.BLOCKS,
    icon: Omega,
    keywords: ['inline', 'math', 'formula', 'equation', 'latex'],
    handler: (editor: Editor) => {
      const latex = prompt('输入 LaTeX 行内公式:', 'E = mc^2')
      if (latex != null) {
        editor.chain().focus().insertContent(`\\(${latex}\\)`).run()
      }
    },
    showInToolbar: true,
    toolbarGroup: 'blocks',
    formattingCommand: 'inlineMath'
  },
  {
    id: 'blockMath',
    title: 'Math Formula',
    description: 'Insert mathematical formula',
    category: CommandCategory.BLOCKS,
    icon: Calculator,
    keywords: ['math', 'formula', 'equation', 'latex'],
    handler: (editor: Editor) => {
      const latex = prompt('输入 LaTeX 块级公式:', 'E = mc^2')
      if (latex != null) {
        editor.chain().focus().insertContent(`\`\`\`math\n${latex}\n\`\`\``).run()
      }
    },
    showInToolbar: true,
    toolbarGroup: 'blocks',
    formattingCommand: 'blockMath'
  },
  // History commands
  {
    id: 'undo',
    title: 'Undo',
    description: 'Undo last action',
    category: CommandCategory.SPECIAL,
    icon: Undo,
    keywords: ['undo', 'revert'],
    handler: (editor: Editor) => {
      editor.chain().focus().undo().run()
    },
    showInToolbar: true,
    toolbarGroup: 'history',
    formattingCommand: 'undo'
  },
  {
    id: 'redo',
    title: 'Redo',
    description: 'Redo last action',
    category: CommandCategory.SPECIAL,
    icon: Redo,
    keywords: ['redo', 'repeat'],
    handler: (editor: Editor) => {
      editor.chain().focus().redo().run()
    },
    showInToolbar: true,
    toolbarGroup: 'history',
    formattingCommand: 'redo'
  }
]

export interface CommandFilterOptions {
  query?: string
  category?: CommandCategory
  maxResults?: number
}

// Filter commands based on search query and category
export function filterCommands(options: CommandFilterOptions = {}): Command[] {
  const { query = '', category } = options

  let filtered = getAllCommands()

  // Filter by category if specified
  if (category) {
    filtered = filtered.filter((cmd) => cmd.category === category)
  }

  // Filter by search query
  if (query) {
    const searchTerm = query.toLowerCase().trim()
    filtered = filtered.filter((cmd) => {
      const searchableText = [cmd.title, cmd.description, ...cmd.keywords].join(' ').toLowerCase()

      return searchableText.includes(searchTerm)
    })

    // Sort by relevance (exact matches first, then title matches, then keyword matches)
    filtered.sort((a, b) => {
      const aTitle = a.title.toLowerCase()
      const bTitle = b.title.toLowerCase()
      const aExactMatch = aTitle === searchTerm
      const bExactMatch = bTitle === searchTerm
      const aTitleMatch = aTitle.includes(searchTerm)
      const bTitleMatch = bTitle.includes(searchTerm)

      if (aExactMatch && !bExactMatch) return -1
      if (bExactMatch && !aExactMatch) return 1
      if (aTitleMatch && !bTitleMatch) return -1
      if (bTitleMatch && !aTitleMatch) return 1

      return a.title.localeCompare(b.title)
    })
  }

  return filtered
}

// Register default commands into the dynamic registry
DEFAULT_COMMANDS.forEach(registerCommand)
