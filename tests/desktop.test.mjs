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
  sparkline: { k: 'sparkline', d: '1;1;2;3;5;8;13', t: 'Trend', u: '' },
  section: { k: 'section', d: 'Rolling out 291e', t: 'Deployment', u: '' },
  checklist: { k: 'checklist', d: 'Build=done;Flash=doing;Verify=todo', t: 'Run', u: '' },
  changes: { k: 'changes', d: 'core.mjs=+120=-8;plugin.js=+40=-12', t: 'Diff', u: '' },
  outline: { k: 'outline', d: '1=Intro;1.1=Scope;2=Method', t: 'Contents', u: '' },
  facts: { k: 'facts', d: 'Port=EC3;Chip=C8051F121', t: 'Board', u: '' },
  files: { k: 'files', d: 'src/core.mjs=180 lines;tests/x.mjs=90 lines', t: 'Files', u: '' },
  parts: { k: 'parts', d: 'h=Ref|Part|Qty;U1|C8051F121|1;U2|ESP32|2', t: 'BOM', u: '' },
  settings: { k: 'settings', d: 'Motion=on;Sound=off', t: 'Prefs', u: '' },
  timeline: { k: 'timeline', d: 'Mon=Kickoff=crew brief;Wed=Build', t: 'Schedule', u: '' },
  ranges: { k: 'ranges', d: 'Build=2..9;Flash=5..14', t: 'Windows', u: 'h' },
  metrics: { k: 'metrics', d: 'Coverage=88=-2;Latency=14=+3', t: 'Health', u: '' },
  array: { k: 'array', d: 'a|b|c;d|e|f', t: 'Matrix', u: '' },
  heatmap: { k: 'heatmap', d: 'Mon=40;Tue=90;Wed=12', t: 'Load', u: '' },
  wireframe: { k: 'wireframe', d: 'Toolbar=btn:3,field:1;List=item:4,text:2', t: 'Frame', u: '' },
  candlestick: { k: 'candlestick', d: 'Mon=12:18:9:16;Tue=16:21:14:20', t: 'Price', u: '' }
}

test('the core knows exactly the kinds we advertise', () => {
  // 8 original + section + the 12 answer-shaped round-2 kinds + the 2 round-3 kinds.
  assert.equal(KINDS.length, 23)
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

test('no fixed pixel size and no max-height — the content is capped by a measure', () => {
  // The rule this test replaces ("no max-width anywhere") was overridden by the
  // user: on a wide pane the info was flung apart. The widget still never gets a
  // cap of its own — the grid reflows and the pane decides — but its CONTENT is
  // capped by a measure, and tables size by content instead of stretching.
  assert.ok(CSS.includes('--hv-measure: 42rem'), 'the measure is 42rem')
  assert.ok(/max-width:\s*var\(--hv-measure\)/.test(CSS), 'content is capped by the measure')
  assert.ok(!/max-width:\s*[0-9]/.test(CSS), 'no fixed pixel max-width')
  assert.ok(!/max-height/.test(CSS), 'still no max-height anywhere')

  const table = CSS.match(/\.hv-table\s*\{[^}]*\}/)
  assert.ok(table, 'a .hv-table rule exists')
  assert.ok(!/width:\s*100%/.test(table[0]), 'a table is not stretched to fill its cell')

  for (const kind of KINDS) {
    assert.ok(!/max-width:\s*[0-9]/.test(renderWidget(SAMPLES[kind])), `${kind} markup`)
  }
})

test('the widget surface paints nothing — only tokens, no literal colour', () => {
  assert.ok(!/\.hv-widget[^{]*\{[^}]*background/.test(CSS), 'the widget itself stays transparent')
})

test('the palette is six hues declared once, and literals live only there', () => {
  const declared = [...CSS.matchAll(/(--hv-[1-6])\s*:/g)].map(m => m[1])
  assert.deepEqual(declared, ['--hv-1', '--hv-2', '--hv-3', '--hv-4', '--hv-5', '--hv-6'], 'six slots, declared once, in order')
  assert.ok(CSS.includes('--hv-1: var(--dt-primary)'), '--hv-1 IS the theme accent')
  assert.ok(!/var\(--dt-primary\)[^;]*--dt-primary/.test(CSS), 'no accidental second accent')

  // Every literal colour in the sheet sits inside those six declarations. The
  // palette block is the ONE place a hex may appear; anywhere else it is a bug.
  const stripped = CSS.replace(/--hv-[1-6]:[^;]+;/g, '')
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(stripped), 'no hex outside the palette block')
  assert.ok(!/rgb\(|hsl\(|oklch\(|oklab\(/.test(stripped), 'no colour functions outside the palette block')
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(CORE_SRC.replace(/--hv-[1-6]:[^;]+;/g, '')), 'and none in the core source')
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(PLUGIN_SRC.replace(/--hv-[1-6]:[^;]+;/g, '')), 'and none in the plugin source')
})

test('categories take a hue in first-seen order, deterministically', () => {
  const payload = 'A=1;B=2;C=3'
  const first = renderWidget({ k: 'donut', d: payload })

  // Same payload -> same colours, every time.
  assert.equal(first, renderWidget({ k: 'donut', d: payload }))
  assert.ok(first.includes('hv-c0') && first.includes('hv-c1') && first.includes('hv-c2'), 'the first three slots are used')
  assert.ok(!first.includes('hv-c3'), 'a three-category payload stops at slot three')

  // The order of appearance is what assigns the hue, so a reorder repaints.
  assert.notEqual(first, renderWidget({ k: 'donut', d: 'B=2;A=1;C=3' }))

  // Past six categories the ramp wraps, still deterministically.
  const seven = renderWidget({ k: 'donut', d: 'A=1;B=1;C=1;D=1;E=1;F=1;G=1' })
  assert.ok(seven.includes('hv-c0') && seven.includes('hv-c5'), 'all six slots, then a wrap')
})

test('a tiny donut slice is separated from its neighbours, never erased', () => {
  const markup = renderWidget({ k: 'donut', d: 'Big=180;Small=9', t: 'Disk' })
  const arcs = [...markup.matchAll(/stroke-dasharray="([\d.]+) [\d.]+"/g)].map(m => Number(m[1]))
  assert.equal(arcs.length, 2, 'two slices are drawn')
  const [big, small] = [...arcs].sort((a, b) => b - a)
  assert.ok(small > 3, `the small slice keeps a visible arc: ${small}`)
  assert.ok(small < big, 'but it is still the smaller arc')
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
  assert.ok(!markup.includes('<div class="hv-grid"><div class="hv hv-grid hv-board"'), 'a board is not nested inside a second measured grid — otherwise the measure collapses it to one column')
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
  assert.ok(!/max-width:\s*[0-9]/.test(board[0]))
})

test('every theme token the CSS uses is one the app defines or the palette declares', () => {
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
  // `--hv-*` is ours: it must be declared in this sheet before it can be used.
  const declared = new Set([...CSS.matchAll(/(--hv-[a-z0-9-]+)\s*:/g)].map(m => m[1]))
  const used = [...CSS.matchAll(/var\((--[a-z0-9-]+)/g)].map(m => m[1])
  assert.ok(used.length > 0, 'the CSS uses theme tokens at all')
  assert.ok([...used].some(token => token.startsWith('--hv-')), 'and uses the palette')

  const unknown = [...new Set(used)].filter(token => !APP_TOKENS.has(token) && !declared.has(token))
  assert.deepEqual(unknown, [], 'tokens that resolve to nothing: ' + unknown.join(', '))
})

test('a series is a series: bare numbers plot a varying line, not a flat one', () => {
  const line = renderWidget({ k: 'line', d: '3;7;4;9;11;8;14', t: 'Latency' })
  const points = line.match(/hv-line-path" points="([^"]+)"/)[1].split(' ')
  const ys = [...new Set(points.map(point => point.split(',')[1]))]
  assert.ok(ys.length > 2, `line y-values: ${ys.join(', ')}`)
  assert.ok(line.includes('hv-line-y'), 'the line labels its scale on a real axis')
  assert.ok(line.includes('>14<'), 'the high value reaches the reader')
  assert.ok(line.includes('hv-line-area'), 'the series carries an area, not a bare stroke')

  const spark = renderWidget({ k: 'sparkline', d: '1;1;2;3;5;8;13;21', t: 'Trend' })
  const sparkYs = [
    ...new Set(spark.match(/hv-spark-path" points="([^"]+)"/)[1].split(' ').map(point => point.split(',')[1]))
  ]
  assert.ok(sparkYs.length > 2, `sparkline y-values: ${sparkYs.join(', ')}`)
})

test('bars and ranges carry a real axis with ticks and labels', () => {
  const markup = renderWidget({ k: 'bars', d: 'Firmware=42;Model A=28;Web=18', t: 'Share', u: '%' })
  const ticks = [...markup.matchAll(/class="hv-tick[^"]*">(\d+)/g)].map(m => m[1])
  assert.ok(ticks.length >= 5, `a labelled scale, at least 0..100 in steps: ${ticks.join(', ')}`)
  assert.deepEqual(ticks, ['0', '25', '50', '75', '100'], 'four even ticks, 0 at the lo end')

  const ranges = renderWidget({ k: 'ranges', d: 'A=2..9;B=5..14', t: 'Windows', u: 'h' })
  assert.ok(ranges.includes('hv-range-span'), 'the span is drawn')
  assert.ok(ranges.includes('hv-axis'), 'the range chart shares one scale')
  assert.ok(ranges.includes('hv-axis-hi">14'), 'the shared cap is the widest upper bound')
})

test('every plotted element carries its own hover detail, and reads without it', () => {
  const bars = renderWidget({ k: 'bars', d: 'A=42;B=28', t: 'S', u: '%' })
  assert.ok(bars.includes('title="A: 42%"'), 'a bar row names its value on hover')
  assert.ok(bars.includes('hv-row-value">42'), 'and prints it in the row')

  const line = renderWidget({ k: 'line', d: '3;7;9', t: 'L' })
  assert.ok(line.includes('hv-line-point'), 'each point gets a marker')
  assert.ok(/<title>#1: 3<\/title>/.test(line), 'and its marker carries the detail')

  const heat = renderWidget({ k: 'heatmap', d: 'Mon=40;Tue=90', t: 'Load' })
  assert.ok(heat.includes('title="Tue: 90"'), 'a heat cell names its value')
  assert.ok(/hv-heat-value">90</.test(heat), 'and prints it inside the cell')
})

test('a section draws a header band and a lead line, with no caption above it', () => {
  const markup = renderWidget({ k: 'section', t: 'Deployment', d: 'Rolling out 291e' })
  assert.ok(markup.includes('hv-section-band'), 'the band exists')
  assert.ok(markup.includes('hv-section-title">Deployment'), 'the heading is in the band')
  assert.ok(markup.includes('hv-section-lead">Rolling out 291e'), 'the lead line follows')
  assert.ok(!markup.includes('hv-title'), 'no duplicate caption above the band')

  assert.ok(renderWidget({ k: 'section' }).includes('hv-prose'), 'an empty section is prose, not a bare rule')
})

test('a legend appears when a chart has more than one series, and never for one', () => {
  assert.ok(renderWidget({ k: 'donut', d: 'A=1;B=2' }).includes('hv-legend'), 'two slices -> a legend')
  assert.ok(!renderWidget({ k: 'sparkline', d: '1;2;3' }).includes('hv-legend'), 'one series -> no legend')
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

// ---------------------------------------------------------------- round 3 -----

test('the type scale ranks reading order by size and weight alone', () => {
  const ruleFor = selector => {
    const at = CSS.indexOf(selector)
    assert.ok(at >= 0, `a rule for ${selector}`)
    const open = CSS.indexOf('{', at)
    const body = CSS.slice(open, CSS.indexOf('}', open))
    const size = body.match(/font-size:\s*([\d.]+)rem/)
    assert.ok(size, `${selector} declares a font-size`)
    const weight = body.match(/font-weight:\s*(\d+)/)
    return { rem: Number(size[1]), weight: weight ? Number(weight[1]) : 400 }
  }

  const l1 = ruleFor('.hv-section-title')
  const l2 = ruleFor('.hv-section--l2 .hv-section-title')
  const title = ruleFor('.hv-title')
  const label = ruleFor('.hv-row-label')
  const caption = ruleFor('.hv-kpi-label')

  // Strictly decreasing, so the rank reads from size alone with colour off.
  assert.ok(l1.rem > l2.rem, `section L1 > L2 (${l1.rem} > ${l2.rem})`)
  assert.ok(l2.rem > title.rem, `L2 > widget title (${l2.rem} > ${title.rem})`)
  assert.ok(title.rem > label.rem, `widget title > row label (${title.rem} > ${label.rem})`)
  assert.ok(label.rem > caption.rem, `row label > caption (${label.rem} > ${caption.rem})`)
  assert.ok(l1.weight > l2.weight, `the two levels differ in weight too (${l1.weight} > ${l2.weight})`)

  // Colour is switched off entirely: none of the five tiers paint their own colour
  // as the rank signal — the section levels are told apart by type, not by hue.
  assert.ok(CSS.includes('.hv-section--l2 .hv-section-title'), 'L2 is a distinct type step')
})

test('section L1 carries a palette key; L2 drops it, and neither draws a rule', () => {
  const l1 = renderWidget({ k: 'section', t: 'Deployment', d: 'Rolling out 291e' })
  const l2 = renderWidget({ k: 'section', t: 'Stage times', d: '', l: '2' })

  assert.ok(l1.includes('hv-section--l1') && l1.includes('hv-section-key'), 'level 1 keeps the key')
  assert.ok(l2.includes('hv-section--l2') && !l2.includes('hv-section-key'), 'level 2 drops the key')
  // No decorative separator: the band carries no rule of its own, at either level.
  const band = CSS.match(/\.hv-section-band\s*\{[^}]*\}/)
  assert.ok(band, 'a .hv-section-band rule exists')
  assert.ok(!/border/.test(band[0]), 'the band has no border')
  assert.ok(!CSS.includes('.hv-section--l2 .hv-section-band'), 'L2 adds no rule either')

  // The canonical board spelling: the level rides in the payload as an `l=` cell,
  // and the heading is the first non-`l=` cell. `section:Board runs;l=2` ships.
  const board = renderWidget({ k: 'board', d: 'section:Board runs;l=2~section:Timing~bars:A=1;B=2~kpi:C=3' })
  const bandOf = level => {
    const at = board.indexOf(`hv-section--l${level}`)
    assert.ok(at >= 0, `a level-${level} band in the board`)
    return board.slice(at, board.indexOf('</div></div>', at))
  }
  const band2 = bandOf(2)
  assert.ok(band2.includes('hv-section-title">Board runs'), ';l=2 levels the band')
  assert.ok(!band2.includes('hv-section-key'), 'and drops the palette key')
  const band1 = bandOf(1)
  assert.ok(band1.includes('hv-section-title">Timing'), 'an absent level is level 1')
  assert.ok(band1.includes('hv-section-key'), 'and keeps the key')

  // The fallback spelling still parses, so an older emitter does not regress.
  assert.ok(renderWidget({ k: 'board', d: 'section:2:Boards' }).includes('hv-section--l2'))
})

test('two stacked bands hold their hierarchy with no rule between them', () => {
  // The contract the guide names: separators are noise. A band is
  // told apart from the one above by type size and weight alone, never a line.
  const markup = renderWidget({ k: 'board', d: 'section:Deployment;l=1~section:Stage times;l=2' })

  assert.ok(markup.includes('hv-section--l1') && markup.includes('hv-section--l2'), 'both levels draw')
  const bands = markup.match(/hv-section-band/g)
  assert.equal(bands.length, 2, 'two bands, stacked')
  const bandRule = CSS.match(/\.hv-section-band\s*\{[^}]*\}/)[0]
  assert.ok(!/border/.test(bandRule), 'the band rule carries no border')
  assert.ok(!CSS.includes('border-bottom-style: dashed'), 'the L2 dashed rule is gone')
  assert.ok(!CSS.includes('.hv-section--l2 .hv-section-band'), 'and no per-level band rule exists')
})

test('a row value reads against a target: `<value> of <target>`, share named', () => {
  const markup = renderWidget({ k: 'bars', d: 'Intake=1850 of 2200;Burn=1200 of 2000', t: 'Energy', u: 'kcal' })

  // The target is the row's own track end.
  const widths = [...markup.matchAll(/hv-bar-fill[^"]*" style="width:([\d.]+)%/g)].map(m => Number(m[1]))
  assert.equal(widths.length, 2, 'one bar per row')
  assert.ok(Math.abs(widths[0] - 84.09) < 0.01, `1850 of 2200 fills 84.09%: ${widths[0]}`)
  assert.ok(Math.abs(widths[1] - 60) < 0.01, `1200 of 2000 fills 60%: ${widths[1]}`)
  // Both the value and its reference reach the reader; the share is named.
  assert.ok(markup.includes('hv-row-value">1850'), 'the value prints')
  assert.ok(markup.includes('hv-row-target">of 2200'), 'the target prints')
  assert.ok(markup.includes('hv-row-share">84%'), 'the share is named')
  // A shared axis would contradict a per-row target, so there is none.
  assert.ok(!markup.includes('hv-axis'), 'no shared axis against per-row targets')
})

test('with no target the row-max scale is the fallback', () => {
  const markup = renderWidget({ k: 'bars', d: 'Flash=812;Verify=430', t: 'Stage', u: 'ms' })
  assert.ok(!markup.includes('hv-row-target'), 'no target is invented')
  assert.ok(markup.includes('hv-axis'), 'the shared axis still describes the bars')
  const ticks = [...markup.matchAll(/class="hv-tick[^"]*">(\d+)/g)].map(m => m[1])
  assert.ok(ticks.includes('812'), 'the axis cap is the row maximum')
})

test('a metric reads against its target with the share named', () => {
  const markup = renderWidget({ k: 'metrics', d: 'Coverage=88 of 100;Latency=14 of 20', t: 'Health' })

  const widths = [...markup.matchAll(/hv-metric-scale-fill[^"]*" style="width:([\d.]+)%/g)].map(m => Number(m[1]))
  assert.deepEqual(widths, [88, 70], 'the fill is value over target')
  assert.ok(markup.includes('hv-metric-target">of 100'), 'the target prints')
  assert.ok(markup.includes('hv-metric-share">88%'), 'the share is named')
})

test('the `of` reference is drawn with surface tokens, never a data hue', () => {
  for (const selector of ['.hv-row-target', '.hv-metric-target', '.hv-metric-share']) {
    const at = CSS.indexOf(selector)
    assert.ok(at >= 0, `a rule for ${selector}`)
    const body = CSS.slice(CSS.indexOf('{', at), CSS.indexOf('}', at))
    assert.ok(!/--hv-[1-6]/.test(body), `${selector} uses no data hue`)
    const vars = [...body.matchAll(/var\((--[a-z0-9-]+)/g)].map(m => m[1])
    assert.ok(
      vars.every(v => v === '--foreground' || v === '--color-muted-foreground'),
      `${selector} uses surface tokens only: ${vars.join(', ')}`
    )
  }
})

test('a board carries one vertical rhythm between its entries', () => {
  const board = CSS.match(/\.hv-board\s*\{[^}]*\}/)[0]
  assert.ok(/row-gap:\s*[\d.]+rem/.test(board), 'the board declares a row rhythm')
  assert.ok(/align-items:\s*start/.test(board), 'entries keep their own height, so the gap is the spacing')
  // The columns and the measure are untouched.
  assert.ok(board.includes('repeat(auto-fit, minmax(24rem, 1fr))'), 'the columns are unchanged')
  assert.ok(!/max-width:\s*[0-9]/.test(board), 'and the board is still uncapped')
})

test('progress, sparkline, donut and metrics each carry a real reference', () => {
  // progress: a shared 0..100% scale, the share named, and a ramp slot per row.
  const progress = renderWidget({ k: 'progress', d: 'Flash=75;Verify=40', t: 'Bring-up' })
  assert.ok(progress.includes('hv-axis'), 'progress shares a scale')
  const ticks = [...progress.matchAll(/class="hv-tick[^"]*">(\d+)/g)].map(m => m[1])
  assert.deepEqual(ticks, ['0', '25', '50', '75', '100'], 'a 0..100% axis')
  assert.ok(progress.includes('>75%<') && progress.includes('>40%<'), 'the percentage is named')
  assert.ok(progress.includes('hv-c0') && progress.includes('hv-c1'), 'two rows take two palette slots')

  // sparkline: both ends named, and a baseline marking the floor.
  const spark = renderWidget({ k: 'sparkline', d: '1;3;2;8;5', t: 'Trend' })
  assert.ok(spark.includes('min 1') && spark.includes('max 8'), 'both ends of the range are named')
  assert.ok(spark.includes('hv-spark-base'), 'and a baseline marks the series floor')

  // donut: each slice names its share of the whole.
  const donut = renderWidget({ k: 'donut', d: 'Used=62;Free=38', t: 'Disk' })
  assert.ok(donut.includes('hv-legend-share'), 'each share is named')
  assert.ok(donut.includes('>62%<') && donut.includes('>38%<'), 'shares are percentages of the whole')

  // metrics: one delta domain, so a +12 draws longer than a +3.
  const metrics = renderWidget({ k: 'metrics', d: 'Coverage=1=-2;Latency=2=+3;Fails=3=-7', t: 'Health' })
  assert.ok(metrics.includes('hv-metric-scale-fill'), 'a delta scale exists')
  const widths = [...metrics.matchAll(/hv-metric-scale-fill[^"]*" style="width:([\d.]+)%/g)].map(m => Number(m[1]))
  assert.equal(widths.length, 3, 'one scale per metric')
  assert.ok(Math.max(...widths) === 100, `the largest delta spans the scale: ${widths.join(', ')}`)
  assert.ok(widths[2] > widths[1], 'a bigger delta draws longer than a smaller one')
  assert.ok(metrics.includes('>+3<') && metrics.includes('>-7<'), 'the delta still prints as a number')
})

test('three KPI tiles stay three columns inside the measure', () => {
  const grid = CSS.match(/\.hv-grid\s*\{[^}]*\}/)
  assert.ok(grid, 'a .hv-grid rule exists')
  const floor = Number(grid[0].match(/minmax\(([\d.]+)rem/)[1])
  const gap = Number(grid[0].match(/gap:\s*([\d.]+)rem/)[1])
  assert.ok(3 * floor + 2 * gap <= 42, `three columns fit the 42rem measure: ${3 * floor + 2 * gap}rem`)
  assert.ok(4 * floor + 3 * gap > 42, 'but four still wrap')
})

test('a wireframe draws proportional, labelled rows and never hides a row label', () => {
  const markup = renderWidget({ k: 'wireframe', d: 'Toolbar=btn:3,field:1;Sidebar=card:2,circle:1', t: 'Frame' })

  assert.ok(markup.includes('hv-wf-label">Toolbar'), 'the row label is drawn')
  assert.ok(markup.includes('style="flex-grow:3"'), 'a block is proportional to its count')
  assert.ok(markup.includes('hv-wf-block--btn') && markup.includes('hv-wf-block--circle'), 'block kinds draw')
  assert.ok(markup.includes('btn ×3') && markup.includes('field'), 'blocks carry their type and count, so the mock reads without colour')

  // The row label sits outside the block track — a narrow pane can never hide it.
  const row = markup.match(/hv-wf-row">([\s\S]*?)<\/div>/)[1]
  assert.ok(row.indexOf('hv-wf-label') >= 0 && row.indexOf('hv-wf-blocks') > row.indexOf('hv-wf-label'), 'label then track')

  // An unknown block kind still draws, and a bare row is prose, never an empty frame.
  assert.ok(renderWidget({ k: 'wireframe', d: 'Row=slider:2' }).includes('hv-wf-block--block'))
  assert.ok(renderWidget({ k: 'wireframe' }).includes('hv-prose'))
})

test('a candlestick shares one price scale and keeps a doji body visible', () => {
  const markup = renderWidget({ k: 'candlestick', d: 'Mon=12:18:9:16;Tue=16:21:14:20;Wed=20:26:18:14', t: 'Price' })

  assert.ok(markup.includes('hv-candle--up') && markup.includes('hv-candle--down'), 'direction is drawn')
  assert.ok(markup.includes('hv-candle-close'), 'the closes are joined by a line')
  assert.ok(markup.includes('hv-line-y'), 'one shared hi/lo scale')
  assert.ok(markup.includes('hv-line-x'), 'each candle is labelled by its when')
  assert.ok(markup.includes('>26<'), 'the shared cap is the highest high')

  // open == close is a doji: the body would vanish without a floor.
  const doji = renderWidget({ k: 'candlestick', d: 'Mon=15:15:15:15;Tue=16:21:14:20', t: 'Flat' })
  const bodies = [...doji.matchAll(/class="hv-candle hv-candle--\w+"[^>]*height="([\d.]+)"/g)].map(m => Number(m[1]))
  assert.equal(bodies.length, 2, 'one body per candle')
  assert.ok(Math.min(...bodies) >= 1.4, `a doji body stays visible: ${bodies.join(', ')}`)

  assert.ok(renderWidget({ k: 'candlestick' }).includes('hv-prose'), 'an empty candlestick is prose')
})
