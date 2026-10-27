/** Prepare the pinned @sparticuz/chromium package for a local CI runner.
 * node scripts/prepare_browser.mjs PACKAGE_DIRECTORY OUTPUT_DIRECTORY
 * Extract without preserving archive ownership (some managed filesystems forbid chown).
 */
import { readFile, writeFile, mkdir, chmod } from 'node:fs/promises'
import { brotliDecompressSync } from 'node:zlib'
import { execFileSync } from 'node:child_process'
import { resolve, join } from 'node:path'
import assert from 'node:assert/strict'

const [packageDirectory, outputDirectory] = process.argv.slice(2)
assert.ok(packageDirectory && outputDirectory, 'Specify package and output directories')
const input = resolve(packageDirectory, 'bin')
const output = resolve(outputDirectory)
await mkdir(output, { recursive: true })
const binary = join(output, 'chromium')
await writeFile(binary, brotliDecompressSync(await readFile(join(input, 'chromium.br'))))
await chmod(binary, 0o755)
for (const archive of ['fonts', 'swiftshader']) {
  execFileSync('tar', ['-x', '--no-same-owner', '-C', output], {
    input: brotliDecompressSync(await readFile(join(input, archive + '.tar.br'))),
  })
}
console.log('Prepared Chromium:', binary)
