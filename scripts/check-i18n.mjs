/** Check that all literal t('...') keys have RU translations. Run: node scripts/check-i18n.mjs */
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
const dir = new URL('../src/', import.meta.url)
const dictionary = readFileSync(new URL('../src/i18n.ts', import.meta.url), 'utf8')
const ru = dictionary.split('const RU: Record<string, string> = {')[1]?.split('\n}\n\n')[0]
if (!ru) throw new Error('RU dictionary not found in src/i18n.ts')
const keys = new Set([...ru.matchAll(/(?:^|,|\{|\n)\s*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|([A-Za-z_]\w*))\s*:/g)].map(m => m[1] || m[2] || m[3]))
const failed = []
for (const name of readdirSync(dir)) {
  if (!/\.tsx?$/.test(name) || name === 'i18n.ts') continue
  const source = readFileSync(join(dir.pathname, name), 'utf8')
  for (const match of source.matchAll(/\bt\(\s*(['"])(.*?)\1/g)) {
    if (!keys.has(match[2])) failed.push(name + ': untranslated t(' + JSON.stringify(match[2]) + ')')
  }
}
if (failed.length) {
  console.error('Missing Russian translations:\n' + failed.join('\n'))
  process.exitCode = 1
} else {
  console.log('i18n static check passed: all literal t() keys have RU entries (' + keys.size + ' dictionary keys).')
}
