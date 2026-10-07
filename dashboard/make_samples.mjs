/**
 * hermes-viz dashboard — render one live sample per rule group.
 *
 * The settings page should show what a group *draws*, not just name it. The drawing core is pure
 * (`desktop/render/core.mjs`), so we can render the sample here, at build time, and ship the markup
 * as data — the page never re-implements a renderer. `--check` re-renders and exits non-zero if the
 * committed `samples.json` has drifted from the core, which is how selfcheck.py keeps the two honest.
 *
 *   node dashboard/make_samples.mjs           # write dashboard/samples.json
 *   node dashboard/make_samples.mjs --check   # exit 1 if it differs (selfcheck runs this)
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { CSS, renderWidget } from '../desktop/render/core.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const GROUPS_PATH = join(HERE, 'groups.json')
const OUT_PATH = join(HERE, 'samples.json')

/**
 * The dashboard surface injects no `--hv-*` tokens (the desktop plugin does that at runtime), and
 * the web host defines only `--foreground` / `--color-muted-foreground` of the five the core reads.
 * So we front-load the core CSS with the three it is missing, with fallbacks that resolve wherever
 * the page is mounted. A `var()` that resolves to nothing drops its whole declaration silently —
 * these make sure the sample can never render as uncoloured plain text.
 */
const SAMPLE_TOKENS = [
  '.hv-sample {',
  '  --dt-primary: var(--primary, var(--accent, #5b8def));',
  '  --dt-border: var(--border, color-mix(in srgb, currentColor 22%, transparent));',
  '  --dt-muted: var(--muted-foreground, color-mix(in srgb, currentColor 55%, transparent));',
  '}'
].join('\n')

function build() {
  const groups = JSON.parse(readFileSync(GROUPS_PATH, 'utf8'))
  const markup = {}
  for (const [id, note] of Object.entries(groups.groups || {})) {
    if (note && note.sample) {
      markup[id] = renderWidget(note.sample)
    }
  }
  return {
    _about: 'Rendered from desktop/render/core.mjs by dashboard/make_samples.mjs — do not edit by hand.',
    css: SAMPLE_TOKENS + '\n' + CSS,
    markup
  }
}

const rendered = JSON.stringify(build(), null, 2) + '\n'

if (process.argv.includes('--check')) {
  let onDisk = ''
  try { onDisk = readFileSync(OUT_PATH, 'utf8') } catch { onDisk = '' }
  if (onDisk !== rendered) {
    console.error('samples.json is stale — run: node dashboard/make_samples.mjs')
    process.exit(1)
  }
  console.log('samples.json matches the drawing core')
} else {
  writeFileSync(OUT_PATH, rendered)
  console.log('wrote ' + OUT_PATH + ' (' + Object.keys(build().markup).length + ' samples)')
}
