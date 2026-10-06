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

test('a board lays out its ~-separated entries side by side in one widget', () => {
  const markup = renderWidget({
    k: 'board',
    d: 'bars:Firmware=42;Model A=28;Web=18~kpi:Builds=128=+12;Fails=3=-1~steps:Read the archive',
    t: 'Build board'
  })

  assert.ok(markup.startsWith('<div class="hv hv-widget" data-kind="board">'))
  assert.ok(markup.includes('hv-board'), 'the pane-sizing grid class is present')
  // all three entries draw themselves, one cell each
  assert.ok(markup.includes('hv-bar'))
  assert.ok(markup.includes('hv-kpi-value'))
  assert.ok(markup.includes('hv-step'))
  // one board, not three paragraphs
  assert.equal(markup.split('hv-board').length - 1, 1)
  assert.ok(!markup.includes('hv-prose'))
})

test('the board takes its entries raw, so ~ is the only thing that splits it', () => {
  const markup = renderKind('board', ['bars:A=1;B=2', 'table:h=X|Y;1|2'], {})
  assert.ok(markup.includes('hv-bar') && markup.includes('hv-table'))
  assert.ok(markup.startsWith('<div class="hv hv-grid hv-board">'))
})

test('a bad board cell falls back to prose for that cell only, never an empty frame', () => {
  const markup = renderWidget({ k: 'board', d: 'bars:A=1~bogus:x=1~kpi:C=3' })

  assert.ok(markup.includes('data-kind="board"'), 'the board itself still stands')
  assert.ok(markup.includes('data-reason="unknown-kind"'), 'the bad cell reads as prose')
  assert.ok(markup.includes('hv-bar') && markup.includes('hv-kpi-value'), 'the good cells survive')
  assert.ok(markup.includes('hv-board'))
})

test('a partially written board spec never throws anywhere in the render path', () => {
  const partials = [
    { k: 'board' },
    { k: 'board', d: '' },
    { k: 'board', d: '~' },
    { k: 'board', d: '~tail' },
    { k: 'board', d: 'bars' },
    { k: 'board', d: 'bars:A=1~kpi:' },
    { k: 'board', d: 'bars:A=1~' },
    { k: 'board', d: 'bars:A=1~:payload' },
    { k: 'board', d: 'bars' + 'x'.repeat(4000) }
  ]

  for (const attrs of partials) {
    const markup = renderWidget(attrs)
    assert.equal(typeof markup, 'string')
    assert.ok(markup.trim().length > 0, 'never an empty frame')
    assert.ok(markup.startsWith('<div class="hv hv-widget"'))
  }
  // an entry with no rows and one with no colon both read as prose, not a blank
  assert.ok(renderWidget({ k: 'board', d: 'bars:A=1~kpi:' }).includes('hv-prose'))
  assert.ok(renderWidget({ k: 'board', d: 'bars:A=1~:payload' }).includes('hv-prose'))
})

test('~ is stripped from model values like the other separators', () => {
  const spec = parseSpec({ k: 'bars', d: 'A=1~2' })
  assert.equal(spec.rows[0].cells[0].label, 'A')
  assert.equal(spec.rows[0].cells[0].value, '12', 'the tilde never survives into the value')
  const markup = renderWidget({ k: 'bars', d: 'A=1', t: 'x~y' })
  assert.ok(!markup.includes('~'))
})

test('the board grid asks for a wider column than the plain grid', () => {
  const board = CSS.match(/\.hv-board\s*{[^}]*}/)
  assert.ok(board, 'a .hv-board rule exists')
  assert.ok(board[0].includes('repeat(auto-fit, minmax('))
  assert.ok(!/max-width|max-height/.test(board[0]))
})

test('every theme token the CSS uses is one the app actually defines', () => {
  // Read off the live renderer. The app's own tree defines exactly these five; the shorter set a
  // `::preview` iframe injects (`--accent`, `--border`, `--card`, `--muted-foreground`) does not
  // exist here. A `var()` naming anything else resolves to nothing and drops its declaration
  // silently — which is how a fully styled widget rendered as plain text, no bars, no colour.
  const APP_TOKENS = new Set([
    '--foreground',
    '--color-muted-foreground',
    '--dt-primary',
    '--dt-border',
    '--dt-muted'
  ])
  const used = [...CSS.matchAll(/var\((--[a-z0-9-]+)/g)].map(m => m[1])
  assert.ok(used.length > 0, 'the CSS uses theme tokens at all')
  const unknown = [...new Set(used)].filter(token => !APP_TOKENS.has(token))
  assert.deepEqual(unknown, [], 'tokens the app does not define: ' + unknown.join(', '))
})

test('a series is a series: bare numbers plot a varying line, not a flat one', () => {
  const line = renderWidget({ k: 'line', d: '3;7;4;9;11;8;14', t: 'Latency' })
  const points = line.match(/hv-line-path" points="([^"]+)"/)[1].split(' ')
  const ys = [...new Set(points.map(point => point.split(',')[1]))]
  assert.ok(ys.length > 2, `line y-values: ${ys.join(', ')}`)
  assert.ok(line.includes('hv-line-meta'), 'the line labels its low and high')
  assert.ok(line.includes('>14<'), 'the high value reaches the reader')
  assert.ok(line.includes('hv-line-area'), 'the series carries an area, not a bare stroke')

  const spark = renderWidget({ k: 'sparkline', d: '1;1;2;3;5;8;13;21', t: 'Trend' })
  const sparkYs = [
    ...new Set(spark.match(/hv-spark-path" points="([^"]+)"/)[1].split(' ').map(point => point.split(',')[1]))
  ]
  assert.ok(sparkYs.length > 2, `sparkline y-values: ${sparkYs.join(', ')}`)
})

test('bars state their scale: a labelled cap, and no second percent that contradicts it', () => {
  const markup = renderWidget({ k: 'bars', d: 'Firmware=42;Model A=28;Web=18', t: 'Share', u: '%' })
  assert.ok(markup.includes('hv-axis'), 'a baseline axis is drawn')
  assert.ok(markup.includes('>0<'), 'the baseline reads 0')
  assert.ok(markup.includes('hv-axis-hi">100'), 'a percent unit caps the domain at 100')
  // The bar length and the axis already say "42 of 100"; a share-of-total would
  // print a second, different percent on the same row.
  assert.ok(!markup.includes('hv-row-share'), 'no share when the values already are percentages')

  // Any other unit scales to the row maximum, says so, and carries the share.
  const raw = renderWidget({ k: 'bars', d: 'Flash=812;Verify=430;Idle=96', t: 'Stage', u: 'ms' })
  assert.ok(raw.includes('hv-axis-hi">812'), 'the cap is the row max when the unit is not %')
  assert.ok(raw.includes('hv-row-share">61%<'), 'each bar carries its whole-number share of the total')
})

test('the donut ramp is four distinct tones, starting on the primary and ending on the neutral', () => {
  // Mixing the primary into --color-muted-foreground looked plausible and produced
  // two steps that resolved to the same colour (that token is a translucent white).
  const strokes = [...CSS.matchAll(/\.hv-seg-\d \{ stroke: ([^;]+);/g)].map(m => m[1].trim())
  assert.equal(strokes.length, 4, 'four segment steps')
  assert.equal(new Set(strokes).size, 4, 'no two steps share a declaration')
  assert.ok(strokes[0] === 'var(--dt-primary)', 'the ramp starts on the full primary')
  assert.ok(strokes[3].includes('--color-muted-foreground'), 'the ramp ends on the app neutral')
})

test('motion is removed wholesale under prefers-reduced-motion', () => {
  const reduce = CSS.match(/@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\n\}/)
  assert.ok(reduce, 'a reduced-motion block exists')
  assert.ok(/animation: none !important/.test(reduce[0]), 'every animation is switched off')
  // ...and the ordinary path animates only compositor properties.
  const animated = [...CSS.matchAll(/animation: hv-(rise|grow)/g)]
  assert.ok(animated.length > 0, 'the default path animates')
  for (const [decl] of CSS.matchAll(/animation: hv-\w+ [^;]+;/g)) {
    assert.ok(!/width|height|top|left|margin|padding/.test(decl), `non-composited animation: ${decl}`)
  }
})
