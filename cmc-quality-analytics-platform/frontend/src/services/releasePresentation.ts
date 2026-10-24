import legacy from '@/config/legacyPresentation.json'
import type { AttributeMeta } from '@/types'

export const indicatorGroups = legacy.groups
const aliases: Record<string, string> = legacy.aliases

export function attributeLabel(name: string, options: AttributeMeta[] = []): string {
  return aliases[name]?.trim() || options.find((item) => item.attribute_name === name)?.attribute_raws[0] || name
}

export function selectPreset(fields: string[], available: AttributeMeta[]) {
  const exactNames = new Set(available.map((item) => item.attribute_name))
  return { selected: fields.filter((field) => exactNames.has(field)), missing: fields.filter((field) => !exactNames.has(field)) }
}
