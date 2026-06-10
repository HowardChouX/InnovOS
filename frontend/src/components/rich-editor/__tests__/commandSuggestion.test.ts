import { describe, expect, it, beforeEach, afterEach } from 'vitest'
import {
  registerCommand,
  unregisterCommand,
  getCommand,
  getAllCommands,
  filterCommands,
  getToolbarCommands,
  CommandCategory,
  type Command,
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

const testCommand: Command = {
  id: 'test-command',
  title: 'Test Command',
  description: 'A test command for unit testing',
  category: CommandCategory.SPECIAL,
  icon: TestIcon,
  keywords: ['test', 'unit', 'example'],
  handler: () => {},
}

const anotherCommand: Command = {
  id: 'another-command',
  title: 'Another Command',
  description: 'Another test command',
  category: CommandCategory.TEXT,
  icon: TestIcon,
  keywords: ['another', 'second'],
  handler: () => {},
}

describe('command module', () => {
  // Clean up custom commands after each test
  afterEach(() => {
    unregisterCommand('test-command')
    unregisterCommand('another-command')
  })

  it('registers and retrieves a command', () => {
    registerCommand(testCommand)
    const retrieved = getCommand('test-command')
    expect(retrieved).toBeDefined()
    expect(retrieved?.id).toBe('test-command')
    expect(retrieved?.title).toBe('Test Command')
    expect(retrieved?.category).toBe(CommandCategory.SPECIAL)
  })

  it('returns undefined for unregistered command', () => {
    expect(getCommand('does-not-exist')).toBeUndefined()
  })

  it('unregisters a command', () => {
    registerCommand(testCommand)
    unregisterCommand('test-command')
    expect(getCommand('test-command')).toBeUndefined()
  })

  it('getAllCommands includes default commands', () => {
    const all = getAllCommands()
    expect(all.length).toBeGreaterThan(0)
    expect(all.some((cmd) => cmd.id === 'bold')).toBe(true)
    expect(all.some((cmd) => cmd.id === 'italic')).toBe(true)
    expect(all.some((cmd) => cmd.id === 'paragraph')).toBe(true)
  })

  it('getAllCommands includes custom registered commands', () => {
    registerCommand(testCommand)
    const all = getAllCommands()
    expect(all.some((cmd) => cmd.id === 'test-command')).toBe(true)
  })

  it('getToolbarCommands returns only commands with showInToolbar', () => {
    registerCommand(testCommand)
    const toolbarCmds = getToolbarCommands()
    expect(toolbarCmds.every((cmd) => cmd.showInToolbar)).toBe(true)
    // testCommand doesn't have showInToolbar set, so it shouldn't appear
    expect(toolbarCmds.some((cmd) => cmd.id === 'test-command')).toBe(false)
  })
})

describe('filterCommands', () => {
  beforeEach(() => {
    registerCommand(testCommand)
    registerCommand(anotherCommand)
  })

  afterEach(() => {
    unregisterCommand('test-command')
    unregisterCommand('another-command')
  })

  it('returns all commands when no filter is applied', () => {
    const results = filterCommands()
    expect(results.length).toBeGreaterThan(0)
  })

  it('filters commands by query matching title', () => {
    const results = filterCommands({ query: 'Bold' })
    expect(results.length).toBeGreaterThan(0)
    expect(results.every((cmd) => /bold/i.test(cmd.title))).toBe(true)
  })

  it('filters commands by query matching keywords', () => {
    const results = filterCommands({ query: 'unit' })
    expect(results.some((cmd) => cmd.id === 'test-command')).toBe(true)
  })

  it('filters commands by category', () => {
    const results = filterCommands({ category: CommandCategory.SPECIAL })
    expect(results.every((cmd) => cmd.category === CommandCategory.SPECIAL)).toBe(true)
  })

  it('returns empty array for non-matching query', () => {
    const results = filterCommands({ query: 'zxvqwyzznonexistent' })
    expect(results.length).toBe(0)
  })

  it('sorts by exact match first, then title match', () => {
    registerCommand({
      id: 'bold-custom',
      title: 'Bold Custom',
      description: 'Another bold option',
      category: CommandCategory.TEXT,
      icon: TestIcon,
      keywords: [],
      handler: () => {},
    })

    const results = filterCommands({ query: 'bold' })
    const exactMatchTitle = results[0].title.toLowerCase()
    // The exact match for 'bold' should be the default 'bold' command (title === 'Bold')
    expect(exactMatchTitle).toBe('bold')

    unregisterCommand('bold-custom')
  })

  it('combines category and query filters', () => {
    const results = filterCommands({
      query: 'bold',
      category: CommandCategory.TEXT,
    })
    expect(results.length).toBeGreaterThan(0)
    expect(results.every((cmd) => cmd.category === CommandCategory.TEXT)).toBe(true)
  })
})
