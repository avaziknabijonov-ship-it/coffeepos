// Syntax-check the platform admin's inline JavaScript during CI.
// This is intentionally a parse-only check; it never connects to a live API.
import { readFileSync } from 'node:fs'
import { Script } from 'node:vm'

const html = readFileSync('backend/app/platform_admin.html', 'utf8')
const source = html.match(/<script>([\s\S]*?)<\/script>/i)?.[1]
if (!source) throw new Error('Platform admin inline JavaScript not found')

new Script(source, { filename: 'backend/app/platform_admin.html' })
console.log('Platform administrator JavaScript syntax: OK')
