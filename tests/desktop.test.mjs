/**
 * hermes-viz — the drawing core's tests.
 *
 * Node only, no dependency: `node tests/desktop.test.mjs`. The core is pure,
 * so these run without a DOM, without React and without the app.
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

import { CSS, KINDS, parseSpec, renderKind, renderWidget } from '../desktop/render/core.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, '..')

const PLUGIN_SRC = readFileSync(join(ROOT, 'desktop/plugin.js'), 'utf8')
const CORE_SRC = readFileSync(join(ROOT, 'desktop/render/core.mjs'), 'utf8')

/** The single-line paragraph the model writes, one per kind. */
const SAMPLES = {
  kpi: { k: 'kpi', d: 'Builds=128=+12;Fails=3=-1', t: 'CI', u: '' },
  bars: { k: 'bars', d: 'Firmware=42;Model A=28;Web=18', t: 'Share', u: '%' },
  line: { k: 'line', d: '3;7;4;9;11', t: 'Latency', u: 'ms' },
  donut: { k: 'donut', d: 'Used=62;Free=38', t: 'Disk', u: '%' },
  steps: { k: 'steps', d: 'Read the archive;Patch the entry;Flash over EC3', t: 'Runbook', u: '' },
  table: { k: 'table', d: 'h=Board|Runs;291e|42;296|17', t: 'Boards', u: '' },
  progress: { k: 'progress', d: 'Flash=75', t: 'Bring-up', u: '' },
  sparkline: { k: 'sparkline', d: '1;1;2;3;5;8;13', t: 'Trend', u: '' }
}

test('the core knows exactly the eight kinds we advertise', () => {
  assert.equal(KINDS.length, 8)
  assert.deepEqual([...KINDS].sort(), Object.keys(SAMPLES).sort())
})

test('every kind renders a widget, not a fallback', () => {
  for (const kind of KINDS) {
    const markup = renderWidget(SAMPLES[kind])

    assert.ok(markup.startsWith('<div class="hv hv-widget"'), `${kind}: widget wrapper`)
    assert.ok(markup.includes(`data-kind="${kind}"`), `${kind}: kind is labelled`)
    assert.ok(!markup.includes('hv-prose'), `${kind}: no fallback prose`)
    assert.ok(markup.includes('hv-grid'), `${kind}: mounts inside the one grid`)
    assert.ok(markup.replace(/<[^>]*>/g, '').trim().length > 0, `${kind}: has visible text`)
  }
})

test('a malformed spec yields prose, never an empty frame', () => {
  const cases = [
    renderWidget(null),
    renderWidget({}),
    renderWidget({ k: 'bogus', d: 'a=1' }),
    renderWidget({ k: 'kpi', d: '' }),
    renderWidget({ k: 'progress', d: ';;;' })
  ]

  for (const markup of cases) {
    assert.ok(markup.includes('hv-prose'), `expected prose fallback in: ${markup}`)
    assert.ok(markup.replace(/<[^>]*>/g, '').trim().length > 0, 'fallback carries text')
  }

  // The original directive text is what the reader sees, escaped.
  const escaped = renderWidget({ k: 'bogus', d: '', source: '::viz{k="bogus"}' })
  assert.ok(escaped.includes('::viz{k=&quot;bogus&quot;}'))
})

test('separators inside model values are stripped, not rendered', () => {
  const spec = parseSpec({ k: 'bars', d: 'A=1;B=2', t: 'x=y;z|w\nv', u: 'a=b' })

  assert.equal(spec.title, 'xyzwv', 'title stripped of ; | = and newline')
  assert.equal(spec.unit, 'ab', 'unit stripped of =')
  assert.equal(spec.rows.length, 2, 'row split on ;')
  assert.equal(spec.rows[0].cells[0].label, 'A')
  assert.equal(spec.rows[0].cells[0].value, '1')

  const markup = renderWidget({ k: 'bars', d: 'A=1;B=2', t: 'x=y;z|w\nv', u: 'a=b' })
  assert.ok(!markup.includes(';'), 'no ; survives into markup')
  assert.ok(!markup.includes('|'), 'no | survives into markup')

  // A value holding its own `=` is split, so the `=` never reaches the reader.
  const withEquals = renderWidget({ k: 'bars', d: 'Load=1=2' })
  assert.ok(withEquals.includes('>1<') || withEquals.includes('>1</span>'))
  assert.equal(parseSpec({ k: 'bars', d: 'Load=1=2' }).rows[0].cells[0].extra, '2')
})

test('no max-width or max-height anywhere in the markup or our CSS', () => {
  const forbidden = /max-width|max-height/

  assert.ok(!forbidden.test(CSS), 'core CSS')
  assert.ok(!forbidden.test(CORE_SRC), 'core source')
  assert.ok(!forbidden.test(PLUGIN_SRC), 'plugin source')

  for (const kind of KINDS) {
    assert.ok(!forbidden.test(renderWidget(SAMPLES[kind])), `${kind} markup`)
    assert.ok(!forbidden.test(renderKind(kind, parseSpec(SAMPLES[kind]).rows, {})), `${kind} body`)
  }
})

test('the widget surface paints nothing — only tokens, no literal colour', () => {
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(CSS), 'no literal hex in the CSS')
  assert.ok(!/\.hv-widget[^{]*\{[^}]*background/.test(CSS), 'the widget itself stays transparent')
  assert.ok(!/rgb\(|hsl\(|oklch\(/.test(CSS), 'no literal colour functions')
})

test('plugin.js carries the core verbatim, so the two copies cannot drift', () => {
  const region = source => {
    const begin = '// >>> vendored-core\n'
    const end = '// <<< vendored-core\n'
    const from = source.indexOf(begin)
    const to = source.indexOf(end)
    assert.ok(from >= 0 && to > from, 'both markers present')
    return source.slice(from + begin.length, to)
  }

  assert.equal(region(PLUGIN_SRC), region(CORE_SRC))
  assert.ok(region(CORE_SRC).includes('function renderKind'))
})

test('plugin.js imports only what the runtime loader resolves', () => {
  const specifiers = [...PLUGIN_SRC.matchAll(/\bfrom\s*['"]([^'"]+)['"]/g)].map(m => m[1])
  const allowed = new Set(['@hermes/plugin-sdk', 'react', 'react/jsx-runtime'])

  for (const specifier of specifiers) {
    assert.ok(allowed.has(specifier), `unsupported import: ${specifier}`)
  }

  assert.ok(PLUGIN_SRC.includes('TRANSCRIPT_DIRECTIVE_AREA'))
  assert.ok(PLUGIN_SRC.includes("name: 'viz'"))
})
