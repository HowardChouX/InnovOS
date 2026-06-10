import type { NodeType, Schema } from '@tiptap/pm/model'

export function getTableNodeTypes(schema: Schema): { [key: string]: NodeType } {
  if ((schema.cached as Record<string, unknown>).tableNodeTypes) {
    return (schema.cached as Record<string, unknown>).tableNodeTypes as { [key: string]: NodeType }
  }

  const roles: { [key: string]: NodeType } = {}
  Object.keys(schema.nodes).forEach((type) => {
    const nodeType = schema.nodes[type]
    if (nodeType.spec.tableRole) {
      roles[nodeType.spec.tableRole] = nodeType
    }
  })

  ;(schema.cached as Record<string, unknown>).tableNodeTypes = roles
  return roles
}
