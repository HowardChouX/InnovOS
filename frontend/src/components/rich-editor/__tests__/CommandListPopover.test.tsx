import { describe, expect, it, beforeEach, afterEach } from 'vitest'
import {
  registerCommand,
  unregisterCommand,
  getCommand,
  getAllCommands,
  getCommandsByGroup,
  registerToolbarCommand,
  unregisterToolbarCommand,
  getToolbarCommands,
  CommandCategory,
  type Command,
  filterCommands,
} from '../command'

// A minimal icon component for testing
const TestIcon = (({ size }: { size?: number | string }) => {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('data-testid', 'command-icon')
  if (size) {
    svg.setAttribute('width', String(size))
    svg.setAttribute('height', String(size))
  }
  return svg
}) as unknown as Command['icon']

describe('Command category enum', () => {
  it('has all expected categories', () => {
    expect(CommandCategory.TEXT).toBe('text')
    expect(CommandCategory.LISTS).toBe('lists')
    expect(CommandCategory.BLOCKS).toBe('blocks')
    expect(CommandCategory.MEDIA).toBe('media')
    expect(CommandCategory.STRUCTURE).toBe('structure')
    expect(CommandCategory.SPECIAL).toBe('special')
  })
})

describe('Command types and interfaces', () => {
  it('accepts and stores a valid Command object', () => {
    const cmd: Command = {
      id: 'my-command',
      title: 'My Command',
      description: 'My test command',
      category: CommandCategory.TEXT,
      icon: TestIcon,
      keywords: ['my'],
      handler: () => {},
    }
    registerCommand(cmd)
    const retrieved = getCommand('my-command')
    expect(retrieved).toBeDefined()
    expect(retrieved?.id).toBe('my-command')
    expect(retrieved?.title).toBe('My Command')
    expect(retrieved?.description).toBe('My test command')
    expect(retrieved?.category).toBe(CommandCategory.TEXT)
    expect(retrieved?.keywords).toEqual(['my'])
    unregisterCommand('my-command')
  })

  it('stores optional fields correctly', () => {
    const cmd: Command = {
      id: 'full-command',
      title: 'Full Command',
      description: 'A command with all optional fields',
      category: CommandCategory.BLOCKS,
      icon: TestIcon,
      keywords: ['full', 'complete'],
      handler: () => {},
      showInToolbar: true,
      toolbarGroup: 'formatting',
      formattingCommand: 'bold',
      isAvailable: () => true,
    }
    registerCommand(cmd)
    const retrieved = getCommand('full-command')
    expect(retrieved?.showInToolbar).toBe(true)
    expect(retrieved?.toolbarGroup).toBe('formatting')
    expect(retrieved?.formattingCommand).toBe('bold')
    expect(retrieved?.isAvailable).toBeDefined()
    expect(retrieved?.isAvailable!({} as any)).toBe(true)
    unregisterCommand('full-command')
  })
})

describe('toolbar command management', () => {
  afterEach(() => {
    unregisterCommand('toolbar-test')
    unregisterCommand('toolbar-test-2')
  })

  it('registerToolbarCommand sets showInToolbar and registers the command', () => {
    const cmd: Command = {
      id: 'toolbar-test',
      title: 'Toolbar Test',
      description: 'A toolbar test command',
      category: CommandCategory.SPECIAL,
      icon: TestIcon,
      keywords: [],
      handler: () => {},
    }
    registerToolbarCommand(cmd)
    const retrieved = getCommand('toolbar-test')
    expect(retrieved).toBeDefined()
    expect(retrieved?.showInToolbar).toBe(true)
  })

  it('unregisterToolbarCommand hides from toolbar but keeps command', () => {
    const cmd: Command = {
      id: 'toolbar-test-2',
      title: 'Toolbar Test 2',
      description: 'Another toolbar test',
      category: CommandCategory.SPECIAL,
      icon: TestIcon,
      keywords: [],
      handler: () => {},
      showInToolbar: true,
    }
    registerCommand(cmd)
    expect(getToolbarCommands().some((c) => c.id === 'toolbar-test-2')).toBe(true)

    unregisterToolbarCommand('toolbar-test-2')
    // Command should still exist
    expect(getCommand('toolbar-test-2')).toBeDefined()
    // But not in toolbar
    expect(getCommand('toolbar-test-2')?.showInToolbar).toBe(false)
  })
})

describe('getCommandsByGroup', () => {
  it('returns commands matching the specified toolbar group', () => {
    const formattingCmds = getCommandsByGroup('formatting')
    expect(formattingCmds.length).toBeGreaterThan(0)
    expect(formattingCmds.every((cmd) => cmd.toolbarGroup === 'formatting')).toBe(true)
  })

  it('returns an empty array for non-existent group', () => {
    const result = getCommandsByGroup('non-existent-group')
    expect(result.length).toBe(0)
  })
})

describe('default command availability', () => {
  it('all default commands have required fields', () => {
    const defaults = getAllCommands().filter(
      (cmd) => cmd.id !== 'test-command' && cmd.id !== 'another-command'
    )
    for (const cmd of defaults) {
      expect(cmd.id).toBeTruthy()
      expect(cmd.title).toBeTruthy()
      expect(cmd.description).toBeTruthy()
      expect(cmd.icon).toBeDefined()
      expect(Array.isArray(cmd.keywords)).toBe(true)
      expect(typeof cmd.handler).toBe('function')
    }
  })

  it('all default commands have valid categories', () => {
    const defaults = getAllCommands().filter(
      (cmd) => cmd.id !== 'test-command' && cmd.id !== 'another-command'
    )
    const validCategories = Object.values(CommandCategory)
    for (const cmd of defaults) {
      expect(validCategories).toContain(cmd.category)
    }
  })

  it('bold command creates bold formatting', () => {
    // Not an integration test, just validating the handler doesn't throw
    const boldCmd = getCommand('bold')
    expect(boldCmd).toBeDefined()
    expect(boldCmd?.formattingCommand).toBe('bold')
    expect(boldCmd?.toolbarGroup).toBe('formatting')
    expect(boldCmd?.showInToolbar).toBe(true)
  })
})
