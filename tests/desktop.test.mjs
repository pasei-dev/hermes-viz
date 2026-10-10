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

import { CSS, GLYPHS, KINDS, SHAPES, SHAPE_OF, SHAPELESS, parseRows, parseSpec, renderKind, renderWidget, resolveCells, applyTemplate, sendText, templateFor } from '../desktop/render/core.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, '..')

const PLUGIN_SRC = readFileSync(join(ROOT, 'desktop/plugin.js'), 'utf8')
const CORE_SRC = readFileSync(join(ROOT, 'desktop/render/core.mjs'), 'utf8')

/** A step off the sheet's own token block, in rem. The scale is the contract:
 *  a test asserts the ORDER a rule names, not a number a rule happens to carry. */
const tokenRem = name => {
  const m = CSS.match(new RegExp(`--hv-${name}:\\s*([\\d.]+)rem`))
  assert.ok(m, `the sheet declares --hv-${name}`)
  return Number(m[1])
}

/** The single-line paragraph the model writes, one per kind. */
const SAMPLES = {
  kpi: { k: 'kpi', d: 'Builds=128=+12;Fails=3=-1', t: 'CI', u: '' },
  bars: { k: 'bars', d: 'Firmware=42;Model A=28;Web=18', t: 'Share', u: '%' },
  line: { k: 'line', d: '3;7;4;9;11', t: 'Latency', u: 'ms' },
  donut: { k: 'donut', d: 'Used=62;Free=38', t: 'Disk', u: '%' },
  steps: { k: 'steps', d: 'Read the archive;Patch the entry;Flash the board', t: 'Runbook', u: '' },
  table: { k: 'table', d: 'h=Board|Runs;Alpha|42;Beta|17', t: 'Boards', u: '' },
  progress: { k: 'progress', d: 'Flash=75', t: 'Bring-up', u: '' },
  sparkline: { k: 'sparkline', d: '1;1;2;3;5;8;13', t: 'Trend', u: '' },
  section: { k: 'section', d: 'Rolling out Alpha', t: 'Deployment', u: '' },
  checklist: { k: 'checklist', d: 'Build=done;Flash=doing;Verify=todo', t: 'Run', u: '' },
  outline: { k: 'outline', d: '1=Intro;1.1=Scope;2=Method', t: 'Contents', u: '' },
  facts: { k: 'facts', d: 'Port=Probe;Chip=MCU-1', t: 'Board', u: '' },
  files: { k: 'files', d: 'src/core.mjs=180 lines;tests/x.mjs=90 lines', t: 'Files', u: '' },
  parts: { k: 'parts', d: 'h=Ref|Part|Qty;U1|MCU-1|1;U2|Radio|2', t: 'BOM', u: '' },
  settings: { k: 'settings', d: 'Motion=on;Sound=off', t: 'Prefs', u: '' },
  timeline: { k: 'timeline', d: 'Mon=Kickoff=crew brief;Wed=Build', t: 'Schedule', u: '' },
  ranges: { k: 'ranges', d: 'Build=2..9;Flash=5..14', t: 'Windows', u: 'h' },
  metrics: { k: 'metrics', d: 'Coverage=88=-2;Latency=14=+3', t: 'Health', u: '' },
  array: { k: 'array', d: 'a|b|c;d|e|f', t: 'Matrix', u: '' },
  heatmap: { k: 'heatmap', d: 'Mon=40;Tue=90;Wed=12', t: 'Load', u: '' },
  wireframe: { k: 'wireframe', d: 'Toolbar=btn:3,field:1;List=item:4,text:2', t: 'Frame', u: '' },
  candlestick: { k: 'candlestick', d: 'Mon=12:18:9:16;Tue=16:21:14:20', t: 'Price', u: '' },
  words: { k: 'words', d: 'Nouns;der Hund=[deːɐ hʊnt]=the dog=Der Hund bellt.', t: 'Words', u: '' },
  recipe: { k: 'recipe', d: 'h=Ingredient|Amount|Note;Butter|2 tbsp|brown;Caster sugar|150 g|whisk;!Do not boil|—|it will scorch', t: 'Recipe', u: '' },
  route: { k: 'route', d: '09:40=Depot 1=Check in;11:10=Gate B=Board', t: 'Route', u: '' },
  nutrition: { k: 'nutrition', d: 'Calories=1850 of 2200;Protein=132 g of 150', t: 'Macros', u: '' },
  matches: { k: 'matches', d: '18:00=Arsenal 2-1 Chelsea=League Cup;20:45=Brentford vs Leeds=League Cup', t: 'Matches', u: '' },
  bracket: { k: 'bracket', d: 'R16=Arsenal>Chelsea,Brentford>Leeds;QF=Arsenal>Brentford', t: 'Cup', u: '' },
  gloss: { k: 'gloss', d: 'der Hund bellt=the dog barks=PRS.3SG', t: 'Gloss', u: '' },
  forms: { k: 'forms', d: 'h=person|singular|plural;1st|habe|haben;2nd|hast|habt', t: 'Paradigm', u: '' },
  funnel: { k: 'funnel', d: 'Visited=1200;Signed up=340;Activated=180;Paid=64', t: 'Funnel', u: '' },
  scatter: { k: 'scatter', d: '1=2.4;2=3.1;3=2.9;4=4.2', t: 'Latency', u: 'ms' },
  waterfall: { k: 'waterfall', d: 'Start=+120;Refunds=-30;Costs=-45;Net=+45', t: 'Cash', u: '' },
  // The shapes: no subject kind claims them, they are how data is arranged.
  records: { k: 'records', d: 'Owner=Platform=on call;SLA=99.9%;Escalation=@pager', t: 'Service', u: '' },
  pairs: { k: 'pairs', d: '2=14;4=28;6=41;8=57', t: 'Throughput', u: 'ms' },
  series: { k: 'series', d: '12;19;17;24;31', t: 'Uptime', u: '' },
  stages: { k: 'stages', d: 'Seen=4800;Signed up=1240;Activated=610;Retained=240', t: 'Stages', u: '' },
  changes: { k: 'changes', d: 'core.mjs=+120=-8;plugin.js=+40=-12', t: 'Diff', u: '' },
  grid: { k: 'grid', d: 'h=Region|Q1|Q2|Q3;North|12|15|19;South|9|11|14', t: 'By region', u: '' },
  groups: { k: 'groups', d: 'Mon=Argon=Physics;Tue=Boron=Physics;Wed=Cobalt=Chemistry', t: 'Labs', u: '' },
  events: { k: 'events', d: '2026-03-01=Kickoff=crew brief;2026-04-15=Beta;2026-06-01=Launch', t: 'Milestones', u: '' },
  // Round 13: the five shapes this plugin did not draw.
  tags: { k: 'tags', d: 'Firmware;DSP=28;Web', t: 'Tags', u: '' },
  calendar: { k: 'calendar', d: '2026-10-04=release;2026-10-09=review', t: 'Release', u: '' },
  area: { k: 'area', d: '3;7;4;9;11', t: 'Latency', u: 'ms' },
  tabs: { k: 'tabs', d: 'Firmware:bars=x=1;y=2~Cost:table=h=Item|k', t: 'Panels', u: '' },
  followup: { k: 'followup', d: 'Round both halves=Make the tie round the same way;Trim the log=', t: 'Next', u: '' }
}

test('the core knows exactly the kinds we advertise', () => {
  // 8 original + section + the 12 answer-shaped round-2 kinds + the 2 round-3 kinds
  // + the 5 round-5 subject kinds + the 3 round-6 kinds + the 3 round-7 kinds
  // + the 7 shapes that are not already a kind (`steps` is both)
  // + the 5 remaining shapes of round 13 (`tags`, `calendar`, `area`, `tabs`, `followup`).
  assert.equal(KINDS.length, 46)
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
  // The stagger property itself carries `;` inside a style attribute; the model's
  // separators must not survive anywhere else in the markup.
  const withoutStyles = markup.replace(/style="[^"]*"/g, '')
  assert.ok(!withoutStyles.includes(';'), 'no model ; survives into markup')
  assert.ok(!withoutStyles.includes('|'), 'no | survives into markup')

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
  // The ROOT is where the contract lives: it paints nothing, so the app's surface shows
  // through. A descendant may carry an ink wash for a state (a picked row, a hover) —
  // that is the reader's own text colour at 6-12%, never a surface of its own.
  assert.ok(!/\.hv-widget\s*\{[^}]*background/.test(CSS), 'the widget itself stays transparent')
  const sheet = CSS.replace(/\/\*[\s\S]*?\*\//g, '') // a comment is prose, not a paint
  for (const [rule] of sheet.matchAll(/[^};]*\{[^}]*background:[^}]*\}/g)) {
    const where = rule.trim().slice(0, 64)
    assert.ok(!/#[0-9a-f]/i.test(rule) && !/\b(rgb|hsl|oklch|oklab)\(/.test(rule), `no literal paint: ${where}`)
    assert.ok(/var\(--/.test(rule) || /background:\s*(none|transparent)\b/.test(rule), `every paint is resolved from a token, or nothing at all: ${where}`)
  }
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

test('plugin.js registers hermes-viz’s own Settings page', () => {
  // The manifest declares no `config_schema`, so the app folds no auto-generated
  // "Agent settings" form under this page; it is the plugin's own controls, fed by
  // its backend. Feature-detected for older hosts.
  assert.match(PLUGIN_SRC, /ctx\.registerSettingsPage\?\.\(\{/)
  assert.ok(PLUGIN_SRC.includes("id: 'settings'"), 'the page has its own id')
  assert.ok(PLUGIN_SRC.includes("title: 'Visuals'"), 'the rail entry is named')
  // The page is a shell over the plugin's own backend: GET for the fields,
  // sections and rendered samples; PUT to write the config subtree back.
  assert.ok(PLUGIN_SRC.includes("rest('/settings')"), 'reads GET /settings')
  assert.ok(PLUGIN_SRC.includes("rest('/settings', { method: 'PUT'"), 'writes PUT /settings')
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
  assert.ok(markup.startsWith('<div class="hv hv-grid hv-board"'))
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

  // `--d`/`--k` are the stagger index the core writes per element; they carry a
  // fallback (`var(--d, 0)`), so an element without one resolves to 0, not empty.
  const FROM_MARKUP = new Set(['--d', '--k'])
  const unknown = [...new Set(used)].filter(token => !APP_TOKENS.has(token) && !declared.has(token) && !FROM_MARKUP.has(token))
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

test('the core derives NO hover label: the only one is the answer’s own', () => {
  const readouts = markup => [...markup.matchAll(/data-hv-readout="([^"]*)"/g)].map(m => m[1])

  // Not one kind labels a row of its own accord. Every one of these draws a comparison somebody
  // once thought worth explaining; the reader can see all of it, so none of it is a label.
  for (const kind of ['bars', 'progress', 'files', 'ranges', 'metrics', 'nutrition', 'heatmap']) {
    const markup = renderWidget(SAMPLES[kind])
    assert.deepEqual(readouts(markup), [], `${kind} derives no label`)
    assert.ok(!markup.includes('data-hv-note-slot'), `${kind} carries no slot nobody asked for`)
  }

  // The one label there is, is the one the answer asked for with n=.
  const noted = renderWidget({ k: 'bars', d: 'A=42;B=28', t: 'Runs', n: '100 runs across both' })
  assert.ok(noted.includes('data-hv-note="100 runs across both"'), 'the note rides on the widget')
  assert.ok(/<span class="hv-note" data-hv-note-slot><\/span>/.test(noted), 'and the caption carries one slot')
  assert.equal(noted.split('data-hv-note-slot').length - 1, 1, 'exactly one slot per widget')

  // Without it: no attribute, no slot, nothing to reveal.
  const plain = renderWidget({ k: 'bars', d: 'A=42;B=28', t: 'Runs' })
  assert.ok(!plain.includes('data-hv-note'), 'no note means no attribute')
  assert.ok(!plain.includes('data-hv-note-slot'), 'and no empty caption span')

  // A note is escaped like any other model fragment.
  const quoted = renderWidget({ k: 'bars', d: 'A=1;B=2', n: 'x"y' })
  assert.ok(quoted.includes('data-hv-note="x&quot;y"'), 'the note is escaped')

  // The mount reveals the widget's own note; it derives nothing from a row.
  assert.ok(PLUGIN_SRC.includes("querySelector('[data-hv-note-slot]')"), 'the mount finds the slot')
  assert.ok(PLUGIN_SRC.includes("node.getAttribute('data-hv-note')"), 'and reads the widget’s own note')
  assert.ok(!PLUGIN_SRC.includes('data-hv-readout'), 'the mount never reads a per-row readout')
  assert.ok(!CORE_SRC.includes('data-hv-readout'), 'and the core never declares one')
})

test('a changed file reads as the host’s own changed-files card', () => {
  // The host solved this card already (thread/changed-files-card.tsx): the file's own name under a type
  // glyph, the green +a / red -b at the row's end, the full path one hover away, and the row the thing
  // you click. A column of absolute paths is the noise that card exists to avoid.
  const markup = renderWidget({ k: 'changes', d: '/srv/app/x/core.mjs=+120=-8;/tmp/notes.md=+4' })

  assert.ok(/<span class="hv-change-name">core\.mjs<\/span>/.test(markup), 'the row shows the basename')
  assert.ok(!/hv-change-name">\/Users/.test(markup), 'and not the whole path')
  assert.ok(markup.includes('title="/srv/app/x/core.mjs"'), 'the full path is one hover away')
  assert.ok(/<span class="hv-change-glyph" aria-hidden="true">/.test(markup), 'the type glyph leads the row')
  assert.ok(/<span class="hv-add">\+120<\/span>/.test(markup), 'the additions are green by token')
  assert.ok(/<span class="hv-del">-8<\/span>/.test(markup), 'the removals are red by token')
  assert.ok(!markup.includes('hv-del">-0<'), 'a zero side is left out, as the host’s DiffCount does')

  // The row IS the button, as in the host, and it carries the reveal.
  assert.ok(markup.includes('class="hv-change"'), 'the row is the control')
  assert.ok(!/<span class="hv-change">/.test(markup), 'and not a span wrapping a second control')
  assert.ok(markup.includes('data-hv-link="file"') && markup.includes('data-hv-value="/tmp/notes.md"'), 'a click reveals it')

  // No proportional bar, and no per-row label — the host's card has neither, and the core derives
  // no label for any kind.
  assert.ok(!markup.includes('hv-change-bar'), 'no churn bar: the counts are the data')
  assert.ok(!markup.includes('data-hv-readout='), 'and no row withholds a number')

  // The footer carries what the rows do not: how many files, and the totals.
  assert.ok(markup.includes('2 files changed'), 'the host’s own wording for the count')
  assert.ok(/hv-change-total-label">2 files changed<\/span><span class="hv-change-counts">/.test(markup), 'with the totals beside it')
  assert.ok(renderWidget({ k: 'changes', d: 'a=+1' }).includes('1 file changed'), 'the singular reads right')
})

test('a measured block is centred, so the leftover is split evenly', () => {
  // A capped block left flush is exactly the asymmetry the reader sees on a wide pane: prose (or a
  // widget) stops well short of the right edge with nothing on the other side to balance it.
  const ruleFor = selector => {
    const at = CSS.indexOf(selector + ' {')
    return at === -1 ? '' : CSS.slice(at, CSS.indexOf('}', at))
  }
  for (const selector of ['.hv-grid', '.hv-caption', '.hv-section']) {
    const rule = ruleFor(selector)
    assert.ok(rule.includes('max-width: var(--hv-measure)'), `${selector} carries the measure`)
    assert.ok(/margin(-inline)?: (0 )?auto/.test(rule), `${selector} is centred, not left flush`)
  }
  const title = ruleFor('.hv-title')
  assert.ok(title.includes('max-width: var(--hv-measure)'), 'the caption carries the measure')
  assert.ok(/margin: 0 auto/.test(title), 'the caption is centred too')

  // and the body's own measure, in the other half of the plugin
  // The body measure sits on the block, not on each element: `ch` resolves against the element's own
  // font size, so a heading capped per-element measured wider than the paragraph beside it — which is
  // exactly what was reported. One cap on `.aui-md` holds the prose, the headings and the widgets.
  assert.ok(/\.aui-md \{[^}]*max-width: var\(--hv-body-measure\);[^}]*margin-inline: auto;/.test(PLUGIN_SRC),
    'the answer block carries the measure and is centred, not left flush')
  assert.ok(!/\.aui-md :where\([^)]*\bp\b[^)]*\)[^{]*\{/.test(PLUGIN_SRC),
    'no per-element measure survives: the block owns it')
})

test('a section draws a header band and a lead line, with no caption above it', () => {
  const markup = renderWidget({ k: 'section', t: 'Deployment', d: 'Rolling out Alpha' })
  assert.ok(markup.includes('hv-section-band'), 'the band exists')
  assert.ok(markup.includes('hv-section-title">Deployment'), 'the heading is in the band')
  assert.ok(markup.includes('hv-section-lead">Rolling out Alpha'), 'the lead line follows')
  assert.ok(!markup.includes('hv-title'), 'no duplicate caption above the band')

  assert.ok(renderWidget({ k: 'section' }).includes('hv-prose'), 'an empty section is prose, not a bare rule')
})

test('a legend appears when a chart has more than one series, and never for one', () => {
  assert.ok(renderWidget({ k: 'donut', d: 'A=1;B=2' }).includes('hv-legend'), 'two slices -> a legend')
  assert.ok(!renderWidget({ k: 'sparkline', d: '1;2;3' }).includes('hv-legend'), 'one series -> no legend')
})

test('motion is opt-in: every animation sits inside prefers-reduced-motion: no-preference', () => {
  // The still rendering is the default and the guard cannot be forgotten: all
  // motion lives inside ONE media query, and nothing animates outside it.
  const open = CSS.indexOf('@media (prefers-reduced-motion: no-preference) {')
  assert.ok(open >= 0, 'a no-preference motion block exists')
  const close = CSS.indexOf('\n}', open)
  assert.ok(close > open, 'the block is closed')
  for (const match of CSS.matchAll(/animation:/g)) {
    assert.ok(match.index > open && match.index < close, `animation outside the guard at ${match.index}`)
  }
  assert.ok(!CSS.includes('prefers-reduced-motion: reduce'), 'no reduce block is needed — the guard is the default')

  // ...and the default path animates only compositor properties.
  const animated = [...CSS.matchAll(/animation: hv-(rise|grow)/g)]
  assert.ok(animated.length > 0, 'the default path animates')
  for (const [decl] of CSS.matchAll(/animation: hv-\w+ [^;]+;/g)) {
    assert.ok(!/width|height|top|left|margin|padding/.test(decl), `non-composited animation: ${decl}`)
  }
})

// ---------------------------------------------------------------- round 3 -----

test('the type scale ranks reading order by size and weight alone', () => {
  // A rule names a step; the token block IS the scale, and it is strictly
  // increasing, so the rank still reads from type alone with colour off.
  const STEPS = ['fs-micro', 'fs-label', 'fs-body', 'fs-lead', 'fs-head', 'fs-display']
  const steps = STEPS.map(name => tokenRem(name))
  for (let i = 1; i < steps.length; i++) {
    assert.ok(steps[i] > steps[i - 1], `${STEPS[i]} is a step above ${STEPS[i - 1]} (${steps[i]} > ${steps[i - 1]})`)
  }

  const tier = selector => {
    const at = CSS.indexOf(selector)
    assert.ok(at >= 0, `a rule for ${selector}`)
    const body = CSS.slice(CSS.indexOf('{', at), CSS.indexOf('}', at))
    const size = body.match(/font-size:\s*var\(--hv-(fs-[a-z]+)\)/)
    assert.ok(size, `${selector} names a type step`)
    const weight = body.match(/font-weight:\s*(\d+)/)
    return { rem: tokenRem(size[1]), weight: weight ? Number(weight[1]) : 400 }
  }

  const l1 = tier('.hv-section-title')
  const l2 = tier('.hv-section--l2 .hv-section-title')
  const title = tier('.hv-title')
  const label = tier('.hv-row-label')
  const caption = tier('.hv-kpi-label')

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
  const l1 = renderWidget({ k: 'section', t: 'Deployment', d: 'Rolling out Alpha' })
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
      vars.every(v => v === '--foreground' || v === '--color-muted-foreground' || v.startsWith('--hv-fs-')),
      `${selector} uses surface tokens only: ${vars.join(', ')}`
    )
  }
})

test('a board carries one vertical rhythm between its entries', () => {
  const board = CSS.match(/\.hv-board\s*\{[^}]*\}/)[0]
  const rowGap = board.match(/row-gap:\s*var\(--hv-(s\d)\)/)
  assert.ok(rowGap, 'the board declares a row rhythm off the scale')
  assert.ok(tokenRem(rowGap[1]) > tokenRem('s3'), 'and it is wider than the plain grid\u2019s gap')
  assert.ok(/align-items:\s*start/.test(board), 'entries keep their own height, so the gap is the spacing')
  // The measure is untouched; the count reflows through auto-fit, never a width.
  assert.ok(board.includes('repeat(auto-fit, minmax('), 'the columns still reflow')
  assert.ok(board.includes('var(--hv-cols)'), 'and are capped by the chosen count')
  assert.ok(!/max-width:\s*[0-9]/.test(board), 'and the board is still uncapped')
})

test('the board column count follows the entry count — never a lone orphan', () => {
  const boardOf = n =>
    renderWidget({ k: 'board', d: Array.from({ length: n }, (_, i) => `kpi:C${i + 1}=${i + 1}`).join('~') })
  const colsOf = n => Number(boardOf(n).match(/--hv-cols:(\d+)/)[1])

  assert.deepEqual([1, 2, 3, 4, 5, 6].map(colsOf), [1, 2, 3, 2, 3, 3], 'the count is chosen from the entry count')
  for (const n of [1, 2, 3, 4, 5, 6]) {
    const cols = colsOf(n)
    assert.ok(cols >= 1 && cols <= 3, `${n} entries -> ${cols} columns, always 1..3`)
    assert.notEqual(n % cols, 1, `${n} entries at ${cols} columns leaves no last-row orphan`)
  }
})

test('the board reflows to the pane with no clamp and no overflow at 1400/900/500px', () => {
  const board = CSS.match(/\.hv-board\s*\{[^}]*\}/)[0]
  assert.ok(!/max-width:\s*[0-9]/.test(board), 'the board is never clamped to a pixel width')
  assert.ok(!/max-height/.test(board), 'and never capped in height')

  const colsOf = n => Number(
    renderWidget({ k: 'board', d: Array.from({ length: n }, (_, i) => `kpi:C${i + 1}=${i + 1}`).join('~') })
      .match(/--hv-cols:(\d+)/)[1]
  )
  // The auto-fit track floor is max(24rem=384px, (pane - gaps) / chosen count);
  // the grid then places as many tracks (and their gaps) as fit, so the tracks can
  // never overflow the pane.
  const GAP = 12 // the board's 0.75rem gap, in px
  const fit = (pane, cols) => {
    const floor = Math.max(384, (pane - (cols - 1) * GAP) / cols)
    const placed = Math.min(cols, Math.floor((pane + GAP) / (floor + GAP)))
    return { placed, floor }
  }

  for (const pane of [1400, 900, 500]) {
    for (const n of [1, 2, 3, 4, 5, 6]) {
      const { placed, floor } = fit(pane, colsOf(n))
      assert.ok(placed >= 1, `${n} entries at ${pane}px place at least one column`)
      const used = placed * floor + (placed - 1) * GAP
      assert.ok(used <= pane, `${n} entries at ${pane}px do not overflow: ${used} <= ${pane}`)
    }
  }
  // The measured reflow the SPEC names, for a three-entry board: 3 / 2 / 1 columns.
  assert.deepEqual([1400, 900, 500].map(pane => fit(pane, colsOf(3)).placed), [3, 2, 1])
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
  const gap = tokenRem(grid[0].match(/gap:\s*var\(--hv-(s\d)\)/)[1])
  assert.ok(3 * floor + 2 * gap <= 42, `three columns fit the 42rem measure: ${3 * floor + 2 * gap}rem`)
  assert.ok(4 * floor + 3 * gap > 42, 'but four still wrap')
})

test('a wireframe draws proportional, labelled rows and never hides a row label', () => {
  const markup = renderWidget({ k: 'wireframe', d: 'Toolbar=btn:3,field:1;Sidebar=card:2,circle:1', t: 'Frame' })

  assert.ok(markup.includes('hv-wf-label">Toolbar'), 'the row label is drawn')
  assert.ok(/style="flex-grow:3[^"]*"/.test(markup), 'a block is proportional to its count')
  assert.ok(markup.includes('hv-wf-block--btn') && markup.includes('hv-wf-block--circle'), 'block kinds draw')
  assert.ok(markup.includes('btn ×3') && markup.includes('field'), 'blocks carry their type and count, so the mock reads without colour')

  // The row label sits outside the block track — a narrow pane can never hide it.
  const row = markup.match(/hv-wf-row[^>]*>([\s\S]*?)<\/div>/)[1]
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

// ---------------------------------------------------------------- round 5 -----

test('words draws a vocabulary row: word, pronunciation, meaning, example', () => {
  const markup = renderWidget({ k: 'words', d: 'der Hund=[deːɐ hʊnt]=the dog=Der Hund bellt.;laufen=[ˈlaʊfn̩]=to run', t: 'Vocab' })

  assert.ok(markup.includes('hv-word-w">der Hund'), 'the word')
  assert.ok(markup.includes('hv-word-say">[deːɐ hʊnt]'), 'the pronunciation')
  assert.ok(markup.includes('hv-word-meaning">the dog'), 'the meaning')
  assert.ok(markup.includes('hv-word-example">Der Hund bellt.'), 'the example')

  // A row with no `=` is a heading.
  const headed = renderWidget({ k: 'words', d: 'Nouns;der Hund=[deːɐ hʊnt]=the dog' })
  assert.ok(headed.includes('hv-words-head">Nouns'), 'a heading row draws as a heading')
  assert.ok(headed.includes('hv-word-w">der Hund'), 'and the data row still draws')
  assert.ok(headed.includes('hv-word-say">[deːɐ hʊnt]'), 'with its parts split on =, not left raw')
  assert.ok(!headed.includes('der Hund=[deːɐ hʊnt]'), 'no raw `=` separator reaches the reader')
})

test('recipe draws like parts and flags a warning without relying on colour', () => {
  const markup = renderWidget({ k: 'recipe', d: 'h=Ingredient|Amount|Note;Butter|2 tbsp|brown it;!Do not boil|—|it will scorch;Flour|120 g|sifted', t: 'Recipe' })

  assert.ok(markup.includes('hv-recipe'), 'a recipe table')
  assert.ok(markup.includes('>Butter<') && markup.includes('>120 g<'), 'the ordinary rows draw')
  assert.ok(markup.includes('hv-recipe-warn'), 'the warning row is marked')
  assert.ok(markup.includes('hv-recipe-warn-glyph'), 'and carries a glyph, so colour is not the only signal')
  assert.ok(!markup.includes('!Do not boil'), 'the flag is consumed, never printed raw')

  // The warning is told apart with colour off: a glyph and a type change.
  const warn = CSS.match(/\.hv-recipe-warn td\s*\{[^}]*\}/)
  assert.ok(warn, 'a .hv-recipe-warn td rule exists')
  assert.ok(/font-weight|font-style/.test(warn[0]), 'the type itself changes, not only the colour')
})

test('route draws a rail of stops, each with its time', () => {
  const markup = renderWidget({ k: 'route', d: '09:40=Depot 1=Check in;11:10=Gate B=Board;12:55=Depot 3=Ship', t: 'Itinerary' })

  assert.ok(markup.includes('hv-route-stop'), 'a stop on the rail')
  assert.ok(markup.includes('hv-route-time">09:40'), 'its time')
  assert.ok(markup.includes('hv-route-place">Depot 1'), 'its place')
  assert.ok(markup.includes('hv-route-detail">Check in'), 'its detail')

  const rail = CSS.match(/\.hv-route-stop::before\s*\{[^}]*\}/)
  assert.ok(rail, 'the rail itself is drawn')
  assert.ok(rail[0].includes('var(--dt-border)'), 'with a surface token, not a data hue')
})

test('nutrition reuses the `of` form: each macro is measured against its target', () => {
  const markup = renderWidget({ k: 'nutrition', d: 'Calories=1850 of 2200;Protein=132 g of 150;Fat=60 of 70', t: 'Macros' })

  assert.ok(markup.includes('hv-nutrition'), 'the nutrition widget draws')
  const widths = [...markup.matchAll(/hv-bar-fill[^"]*" style="width:([\d.]+)%/g)].map(m => Number(m[1]))
  assert.equal(widths.length, 3, 'one bar per macro')
  assert.ok(Math.abs(widths[0] - 84.09) < 0.01, `1850 of 2200 fills 84.09%: ${widths[0]}`)
  assert.ok(markup.includes('hv-row-target">of 2200'), 'the target is named')
  assert.ok(markup.includes('hv-row-share">84%'), 'the share is named')
})

test('matches shows a result and a fixture differently, grouped by tournament', () => {
  const markup = renderWidget({
    k: 'matches',
    d: '18:00=Arsenal 2-1 Chelsea=League Cup;20:45=Brentford vs Leeds=League Cup;15:00=Ajax 0-0 PSV=Eredivisie',
    t: 'Fixtures'
  })

  assert.ok(markup.includes('hv-match--result'), 'a row with a score is a result')
  assert.ok(markup.includes('hv-match-score'), 'and the score is drawn as a score')
  assert.ok(markup.includes('hv-match--fixture'), 'a row without a score reads as a fixture')
  const groups = [...markup.matchAll(/hv-match-group">([^<]+)</g)].map(m => m[1])
  assert.deepEqual(groups, ['League Cup', 'Eredivisie'], 'each tournament groups its rows, named once')
})

// ---------------------------------------------------------------- round 6 -----

test('bracket draws rounds as columns and carries the winners forward', () => {
  const markup = renderWidget({
    k: 'bracket',
    d: 'R16=Arsenal>Chelsea,Brentford>Leeds,Ajax>PSV,Lyon>Nice;QF=Arsenal>Brentford,Ajax>Lyon;SF=Arsenal>Ajax',
    t: 'Cup'
  })

  assert.equal(markup.match(/class="hv-bracket-round"/g).length, 3, 'one column per round')
  const names = [...markup.matchAll(/hv-bracket-name">([^<]+)</g)].map(m => m[1])
  assert.deepEqual(names, ['R16', 'QF', 'SF'], 'rounds read left to right, in payload order')
  assert.equal(markup.match(/hv-bracket-win">([^<]+)</g).length, 7, 'one winner per pairing')
  assert.ok(markup.includes('hv-bracket-win">Arsenal'), 'the winner is the emphasised side')
  assert.ok(markup.includes('hv-bracket-lose">Chelsea'), 'the loser is drawn, muted')
  assert.ok(!markup.includes('hv-bracket-inconsistent'), 'a consistent bracket flags nothing')
})

test('a bracket that contradicts itself is shown, not silently redrawn', () => {
  // Chelsea lost R16 but is named again in the QF: the payload is a contradiction.
  const markup = renderWidget({
    k: 'bracket',
    d: 'R16=Arsenal>Chelsea,Brentford>Leeds;QF=Chelsea>Brentford',
    t: 'Cup'
  })

  assert.ok(markup.includes('hv-bracket-bad'), 'the impossible participant is marked in place')
  assert.ok(markup.includes('hv-bracket-inconsistent'), 'and the contradiction is written out')
  assert.ok(/hv-bracket-inconsistent[\s\S]*Chelsea[^<]*did not win R16/.test(markup), 'the note names who and which round')
  // It is drawn as the payload says — Chelsea still appears as the QF winner.
  assert.ok(markup.includes('hv-bracket-win hv-bracket-bad'), 'the payload is not edited')

  // The flag does not lean on colour alone: the glyph and the note carry it.
  const bad = CSS.match(/\.hv-bracket-bad\s*\{[^}]*\}/)
  assert.ok(bad, 'a .hv-bracket-bad rule exists')
  assert.ok(/text-decoration/.test(bad[0]), 'a non-colour signal marks the bad side')
})

test('gloss aligns word by word only where the counts allow', () => {
  const aligned = renderWidget({ k: 'gloss', d: 'der Hund bellt=the dog barks=PRS.3SG', t: 'Gloss' })

  assert.equal(aligned.match(/hv-gloss-col/g).length, 3, 'three source words, three gloss words -> three columns')
  assert.ok(aligned.includes('hv-gloss-src">der') && aligned.includes('hv-gloss-word">the'), 'source over gloss')
  assert.ok(aligned.includes('hv-gloss-note">PRS.3SG'), 'the note rides beside the row')
  assert.ok(!aligned.includes('hv-gloss-row--unaligned'), 'equal counts align')

  // A gloss with a different word count is shown unaligned, never squeezed.
  const off = renderWidget({ k: 'gloss', d: 'der Hund bellt=the dog barks loudly', t: 'Gloss' })
  assert.ok(off.includes('hv-gloss-row--unaligned'), 'a count mismatch falls to the unaligned form')
  assert.ok(!off.includes('hv-gloss-col'), 'no false columns are forced')
  assert.ok(/hv-gloss-mismatch">3 vs 4 words/.test(off), 'and the mismatch is named, not hidden')
})

test('forms draws a paradigm grid: header plus one row per form, not a table', () => {
  const markup = renderWidget({
    k: 'forms',
    d: 'h=person|singular|plural;1st|habe|haben;2nd|hast|habt;3rd|hat|haben',
    t: 'haben — present'
  })

  assert.ok(markup.includes('hv-forms'), 'the paradigm grid draws')
  assert.ok(!markup.includes('<table'), 'a grid, not a table')
  assert.ok(/grid-template-columns:repeat\(3,/.test(markup), 'three columns from the header')
  assert.ok(markup.includes('hv-form-axis">person'), 'the header names the axis')
  assert.ok(markup.includes('hv-form-head">singular'), 'and each column')
  assert.ok(markup.includes('hv-form-label">1st'), 'a row label')
  assert.ok(markup.includes('>habe<') && markup.includes('>hat<'), 'the forms themselves')

  assert.ok(renderWidget({ k: 'forms' }).includes('hv-prose'), 'an empty paradigm is prose, not a bare grid')
})

// ---------------------------------------------------------------- round 7 -----

test('funnel keeps stage order and names the share lost between each pair', () => {
  const markup = renderWidget({ k: 'funnel', d: 'Visited=1200;Signed up=340;Activated=180;Paid=64', t: 'Funnel' })

  const names = [...markup.matchAll(/hv-funnel-label">([^<]+)</g)].map(m => m[1])
  assert.deepEqual(names, ['Visited', 'Signed up', 'Activated', 'Paid'], 'stages keep their payload order')

  const widths = [...markup.matchAll(/hv-funnel-fill[^"]*" style="width:([\d.]+)%/g)].map(m => Number(m[1]))
  assert.equal(widths.length, 4, 'one bar per stage')
  assert.deepEqual(widths, [100, 28.33, 15, 5.33], 'the length is the share of the first stage')
  for (let i = 1; i < widths.length; i++) assert.ok(widths[i] < widths[i - 1], `stage ${i} is narrower than the one before`)

  // The point of the kind: the DROP is named, in count and share, between stages.
  const drops = [...markup.matchAll(/hv-funnel-drop-text">([^<]+)</g)].map(m => m[1])
  assert.equal(drops.length, 3, 'one loss named between each pair of stages')
  assert.ok(drops[0].includes('lost 860'), `the count lost is named: ${drops[0]}`)
  assert.ok(drops[0].includes('72%'), 'and the share lost')
  assert.ok(drops[0].includes('of Visited'), 'and the stage it fell from')
  assert.ok(drops[2].includes('of Activated'), 'the last drop names its own stage')
  assert.ok(markup.includes('hv-funnel-drop-glyph'), 'the fall carries a glyph, so colour is not the only signal')

  assert.ok(markup.includes('hv-funnel-share">28%'), 'the share of the first stage is named on each row')
})

test('scatter: both axes carry a range and ticks, and a point reads without hovering', () => {
  const markup = renderWidget({ k: 'scatter', d: '1=2.4;2=3.1;3=2.9;4=4.2', t: 'Latency', u: 'ms' })

  assert.ok(markup.includes('hv-line-y'), 'the y axis exists')
  assert.ok(/hv-line-y">[\s\S]*?>4\.2/.test(markup), 'the y range top is named, with its unit')
  assert.ok(/hv-line-y">[\s\S]*?>2\.4/.test(markup), 'and the y range floor')
  assert.ok(markup.includes('hv-line-x'), 'the x axis exists')
  const xTicks = markup.match(/hv-line-x">([\s\S]*?)<\/div>/)[1].match(/>([^<]+)</g).map(s => s.slice(1, -1))
  assert.deepEqual(xTicks, ['1', '2', '3', '4'], 'one x tick per point')

  assert.equal([...markup.matchAll(/hv-scatter-dot/g)].length, 4, 'one dot per point')
  assert.ok(markup.includes('left:33.33%'), 'a dot is placed by its x value')

  // The coordinate is printed beside the dot — visible text, not a hover only.
  const tags = [...markup.matchAll(/hv-scatter-tag"[^>]*>([^<]+)</g)].map(m => m[1])
  assert.equal(tags.length, 4, 'one printed coordinate per point')
  assert.ok(/^1 [^0-9]*2\.4$/.test(tags[0]), `the x and y both read: ${tags[0]}`)
  assert.ok(/^4 [^0-9]*4\.2$/.test(tags[3]), `the far point reads too: ${tags[3]}`)
})

test('waterfall steps from the running total, and the sign reads without colour', () => {
  const markup = renderWidget({ k: 'waterfall', d: 'Start=+120;Refunds=-30;Costs=-45;Net=+45', t: 'Cash' })

  // A rise and a fall are drawn in opposite directions.
  const rects = [...markup.matchAll(/hv-wf-bar hv-wf-bar--(up|down)"[^>]*y="([\d.]+)"[^>]*height="([\d.]+)"/g)]
    .map(m => ({ dir: m[1], y: Number(m[2]), h: Number(m[3]) }))
  assert.equal(rects.length, 4, 'one bar per step')
  assert.deepEqual(rects.map(r => r.dir), ['up', 'down', 'down', 'up'], 'each step takes its sign from its value')

  // Each bar steps from the running total (from -> to), so the step is readable.
  assert.ok(/<title>Start: \+120 \(0 [^)]*120\)<\/title>/.test(markup), 'the first bar steps up from zero')
  assert.ok(/<title>Refunds: -30 \(120 [^)]*90\)<\/title>/.test(markup), 'the next steps DOWN from the running 120 to 90')
  assert.ok(/<title>Costs: -45 \(90 [^)]*45\)<\/title>/.test(markup), 'and the run continues from 90')
  assert.ok(markup.includes('hv-wf-link'), 'each step is joined to the running total')

  // Colour is not the only signal: a glyph and the printed sign carry it too.
  assert.ok(markup.includes('hv-wf-glyph--up') && markup.includes('hv-wf-glyph--down'), 'a glyph marks each direction')
  const deltas = [...markup.matchAll(/hv-wf-delta">([^<]+)</g)].map(m => m[1])
  assert.deepEqual(deltas, ['+120', '-30', '-45', '+45'], 'the signed value prints for every bar')

  // Direction is geometry, not only hue: a rise and a fall of the same size
  // still sit at different heights because they step the other way.
  assert.notEqual(`${rects[0].y}:${rects[0].h}`, `${rects[1].y}:${rects[1].h}`, 'up and down bars are drawn differently')

  assert.ok(renderWidget({ k: 'waterfall' }).includes('hv-prose'), 'an empty walk is prose, not a bare frame')
})

test('the waterfall sign never leans on colour: class, glyph and printed sign carry it', () => {
  assert.ok(CSS.includes('.hv-wf-bar--up') && CSS.includes('.hv-wf-bar--down'), 'both directions have a rule')
  const markup = renderWidget({ k: 'waterfall', d: 'A=+10;B=-4', t: 'Walk' })
  assert.ok(markup.includes('hv-wf-bar--down') && markup.includes('hv-wf-glyph--down'), 'direction is in the markup')
  assert.ok(markup.includes('hv-wf-delta">-4'), 'and the sign prints')
  assert.ok(/A: \+10 \(0 [^)]*10\)/.test(markup) && /B: -4 \(10 [^)]*6\)/.test(markup), 'the step is named for each bar')
})

test('every drawn kind declares one of the eight shapes', () => {
  assert.deepEqual(
    [...SHAPES].sort(),
    ['events', 'grid', 'groups', 'pairs', 'records', 'series', 'stages', 'steps'],
    'the eight shapes are the contract'
  )

  for (const kind of KINDS) {
    if (SHAPELESS.includes(kind)) continue
    assert.ok(SHAPES.includes(SHAPE_OF[kind]), `${kind}: declares a shape (got ${SHAPE_OF[kind]})`)
  }

  // A structural kind draws no data, so it must NOT pretend to a shape.
  for (const kind of SHAPELESS) {
    assert.ok(!(kind in SHAPE_OF), `${kind}: draws structure, not data`)
  }
})

test('every shape renders on its own, with no subject rule', () => {
  // The bare shapes carry data no subject kind claims: the shape's own renderer
  // must draw it deliberately, never fall to prose and never an empty frame.
  const BARE = {
    records: 'Alpha=1=first;Beta=2=second;Gamma=3',
    pairs: '8=13;16=27;24=44',
    series: '4;9;6;14;11',
    stages: 'Seen=900;Tried=410;Kept=180',
    steps: 'Cut the stencil;Etch the board;Populate it',
    grid: 'h=Node|State|Load;A|up|0.4;B|down|0.9',
    groups: 'Ada=Maths=Set A;Bo=Maths=Set B;Cyd=Labs=Set A',
    events: 'Mar=Kickoff=crew brief;Jun=Launch'
  }

  for (const shape of SHAPES) {
    const markup = renderWidget({ k: shape, d: BARE[shape], t: 'Shape', u: '' })
    assert.ok(markup.includes(`data-kind="${shape}"`), `${shape}: labelled`)
    assert.ok(!markup.includes('hv-prose'), `${shape}: not a fallback`)
    assert.ok(markup.replace(/<[^>]*>/g, '').trim().length > 0, `${shape}: has visible text`)
  }

  // `steps` reads done-ness when it is there and stays a numbered run when it is
  // not; a `records` rule with no subject name at all still draws as a list.
  assert.ok(renderWidget({ k: 'steps', d: 'Build=done;Flash=doing' }).includes('hv-check--done'))
  assert.ok(renderWidget({ k: 'steps', d: 'Build;Flash' }).includes('hv-step-n'))
  assert.ok(renderWidget({ k: 'records', d: 'Fee=12;Tax=3' }).includes('hv-rec'))
})

test('a subject kind is a skin over its shape, not a second engine', () => {
  const spec = { k: 'grid', d: 'h=person|singular|plural;1st|habe|haben', t: 'P', u: '' }
  const parsed = parseSpec(spec)
  const generic = renderKind('grid', parsed.rows, parsed).replace(
    /hv-grid-cell|hv-grid-head|hv-grid-axis|hv-grid-label|hv-matrix/g,
    'X'
  )
  const skin = renderKind('forms', parsed.rows, parsed).replace(
    /hv-form-cell|hv-form-head|hv-form-axis|hv-form-label|hv-forms/g,
    'X'
  )
  assert.equal(generic, skin, 'forms is the grid shape wearing its own class names')

  // words is the records engine with four cells; route is the events engine.
  assert.ok(renderKind('words', parseSpec({ k: 'words', d: 'der Hund=[hʊnt]=the dog' }).rows, {}).includes('hv-word-lead'))
  assert.equal(
    renderKind('route', parseSpec({ k: 'route', d: '09:40=Depot 1=Check in' }).rows, {}).replace(/hv-route(-[a-z]+)?/g, 'X'),
    renderKind('events', parseSpec({ k: 'events', d: '09:40=Depot 1=Check in' }).rows, {}).replace(
      /hv-timeline|hv-tl(-[a-z]+)?/g,
      'X'
    )
  )
})


// ---------------------------------------------------------------- round 9 -----

test('one glyph vocabulary: every glyph is in the SPEC table, and the emoji-capable marks are gone', () => {
  const TABLE = new Set(['\u2713', '\u25cf', '\u25cb', '\u2715', '\u25b2', '\u25bc', '\u25b8', '\u25a4', '\u25c8', '\u25a1'])
  // The core's own glyph constants are the vocabulary — every one is in the table.
  for (const [name, glyph] of Object.entries(GLYPHS)) {
    assert.equal([...glyph].length, 1, `${name}: a single code point`)
    assert.ok(TABLE.has(glyph), `${name} (U+${glyph.codePointAt(0).toString(16)}) is outside the SPEC table`)
  }
  assert.deepEqual([...Object.values(GLYPHS)].sort(), [...TABLE].sort(), 'the table is exactly the six meanings')
  assert.ok(Object.values(GLYPHS).every(g => TABLE.has(g)), 'no glyph escapes the table')

  // U+26A0 (the recipe warning) appears nowhere, and no emoji-capable block is used.
  assert.ok(!CORE_SRC.includes('\u26a0'), 'U+26A0 must not appear in the core')
  for (const match of CORE_SRC.matchAll(/[\u{2B00}-\u{2BFF}\u{1F000}-\u{1FAFF}]/gu)) {
    assert.fail(`banned code point U+${match[0].codePointAt(0).toString(16)} in the core`)
  }

  // The doing glyph is this deployment's own mark; the recipe warning is the table's.
  const doing = renderWidget({ k: 'checklist', d: 'Build=doing' })
  assert.ok(doing.includes('\u25cf') && !doing.includes('\u25d0'), 'doing is U+25CF, not the old U+25D0')
  const recipe = renderWidget({ k: 'recipe', d: 'h=A|B;!do not|x' })
  assert.ok(recipe.includes('\u25b2') && !recipe.includes('\u26a0'), 'the recipe warning is U+25B2, never U+26A0')
})

test('the stagger index rides in the markup: --d per row, --k per bar', () => {
  const check = renderWidget({ k: 'checklist', d: 'A=done;B=doing;C=todo;D=blocked' })
  assert.deepEqual([...check.matchAll(/--d:(\d+)/g)].map(m => Number(m[1])), [0, 1, 2, 3], 'one --d per row, zero-based in order')

  const bars = renderWidget({ k: 'bars', d: 'A=1;B=2;C=3' })
  assert.deepEqual([...bars.matchAll(/--k:(\d+)/g)].map(m => Number(m[1])), [0, 1, 2], 'one --k per growing bar')

  // No silent cliff: the six :nth-child delay rules are gone, replaced by the property.
  assert.ok(!/nth-child\(\d+\)/.test(CSS), 'no numeric nth-child rule survives')
  assert.ok(!CSS.includes('animation-delay'), 'no fixed animation-delay remains')
  assert.ok(CSS.includes('calc(var(--d, 0) * 34ms)'), 'row delay = --d * 34ms')
  assert.ok(CSS.includes('calc(var(--k, 0) * 45ms)'), 'bar delay = --k * 45ms')
})

test('the core declares affordances as attributes and never touches the DOM', () => {
  const bars = renderWidget(SAMPLES.bars)
  assert.ok(bars.includes('data-hv-row'), 'a row declares that a pointer may land on it')
  assert.ok(bars.includes('tabindex="0"'), 'a row is focusable')
  assert.ok(!bars.includes('data-hv-note'), 'and it declares no label of its own')

  // The core is pure: no handler, no DOM read anywhere.
  assert.ok(!CORE_SRC.includes('addEventListener'), 'the core has no addEventListener')
  assert.ok(!/\bdocument\./.test(CORE_SRC), 'the core never reads document')
  assert.ok(!/\bwindow\./.test(CORE_SRC), 'the core never reads window')
})

test('the note slot lives in the caption, and the still widget is complete without it', () => {
  const noted = renderWidget({ k: 'bars', d: 'A=1;B=2', t: 'Share', n: 'both runs are warm' })
  assert.ok(/<div class="hv-title"><span class="hv-title-text">Share<\/span><span class="hv-note" data-hv-note-slot><\/span><\/div>/.test(noted), 'the slot sits in the caption beside the title')
  assert.ok(noted.includes('hv-row-value">1'), 'every value is printed in the widget already')
  assert.ok(CSS.includes('.hv-note:empty { display: none; }'), 'an unfilled note takes no space')

  // A widget with no note is complete as it stands: nothing to reveal, nothing to reveal it with.
  const plain = renderWidget({ k: 'bars', d: 'A=1;B=2', t: 'Share' })
  assert.ok(!plain.includes('hv-note'), 'no note, no slot')
})

test('hover and focus focus a row, and the keyboard is not a second-class reader', () => {
  // The dim rides on `data-hv-row`, the affordance every row carries — independent of any note.
  assert.ok(/\.hv-widget:hover \[data-hv-row\] \{ opacity: 0\.55; \}/.test(CSS), 'siblings dim on hover')
  assert.ok(/\.hv-widget \[data-hv-row\]:focus-visible \{ opacity: 1; \}/.test(CSS), ':focus-visible gets the same treatment as :hover')
  assert.ok(/\.hv-widget \[data-hv-row\]:hover,/.test(CSS), 'the hovered element stays full')
})

test('body_style adds a measure and a heading colour, and copies nothing the app already sets', () => {
  assert.match(PLUGIN_SRC, /\.aui-md\s*\{/, 'the scoped rule targets the app transcript root')
  assert.ok(PLUGIN_SRC.includes('body_style'), 'the value is read through the plugin settings API')
  assert.ok(!/--conversation-text-font-size\s*:/.test(PLUGIN_SRC), 'it never overrides the reader’s own font size')
  // Its own tag, so the base sheet stays byte-identical when the setting is off.
  assert.ok(PLUGIN_SRC.includes('style.textContent = CSS'), 'the base stylesheet is injected byte-for-byte')
  assert.ok(PLUGIN_SRC.includes("BODY_STYLE_ID = 'hermes-viz-body-style'"), 'body styling rides in a second tag')

  const body = PLUGIN_SRC.slice(PLUGIN_SRC.indexOf('const BODY_STYLE = `'), PLUGIN_SRC.indexOf('function installBodyStyle'))
  const heads = body
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.includes('{') && !line.startsWith('/*'))

  for (const head of heads) {
    const selector = head.slice(0, head.indexOf('{')).trim()
    assert.ok(selector === '.aui-md' || selector.startsWith('.aui-md :where('), `every rule is scoped under .aui-md: ${selector}`)
    assert.ok(selector === '.aui-md' || selector.includes(':where('), `every rule weighs one class: ${selector}`)
  }

  // The two things the app does NOT do, and nothing else.
  assert.ok(body.includes('--hv-body-measure: 68ch'), 'a line-length measure, which the app leaves at max-w-none')
  assert.ok(body.includes('margin-inline: auto'), 'and the measured blocks are centred, not left flush')
  assert.ok(/\.aui-md :where\(h1, h2, h3\) \{ color: var\(--dt-primary\); \}/.test(body), 'headings take the accent')

  // And it copies none of the app's own typography: the line-height token, the heading scale, the
  // paragraph rhythm. Restating those is how a plugin fights the app it draws inside.
  assert.ok(!body.includes('--dt-line-height'), 'the app owns line-height (leading-(--dt-line-height))')
  assert.ok(!/font-size\s*:/.test(body), 'and the heading scale (HEADING_SIZES)')
  assert.ok(!/margin-block\s*:/.test(body), 'and the paragraph gap (--paragraph-gap)')
  assert.ok(!/letter-spacing|text-wrap|line-height\s*:/.test(body), 'and the headings’ own metrics')
  assert.ok(!/#[0-9a-f]{3,8}\b/i.test(body) && !/rgba?\(/.test(body), 'no literal colour: the app’s token carries it')
})

test('a URL or a rooted path in a cell is drawn as a reference the host acts on', () => {
  const table = renderWidget({ k: 'table', d: 'Name|Where;Docs|https://example.com/guide;Repo|/srv/app' })

  assert.ok(table.includes('class="ref hv-ref"'), 'the host’s own reference class')
  assert.ok(table.includes('data-ref="url"'), 'a URL takes the url kind')
  assert.ok(table.includes('data-ref="file"'), 'a rooted path takes the file kind')
  assert.ok(table.includes('data-hv-link="url"') && table.includes('data-hv-link="file"'), 'the core declares the click')
  assert.ok(!table.includes('addEventListener'), 'and never performs it — the core stays DOM-free')
  assert.ok(table.includes('data-hv-value="https://example.com/guide"'), 'the value travels in an attribute')
  assert.ok(table.includes('data-hv-value="/srv/app"'), 'a path travels whole')
  assert.ok(table.includes('<svg viewBox="0 0 24 24"'), 'the glyph leads it, as it does in the host’s own text')
  assert.ok(table.includes('style="color:var(--ref-color,currentColor)"'), 'the colour is the host’s own property, not a literal')

  // A header names a column; only a value is a reference.
  const head = renderWidget({ k: 'table', d: 'h=https://example.com|B;x|1' })
  assert.ok(!/<th><button/.test(head), 'a header stays text')

  // The files kind already leads with a glyph, so its path is the reference without a second one.
  const files = renderWidget({ k: 'files', d: '/srv/app/x.md=42 lines' })
  assert.ok(files.includes('data-ref="file"') && files.includes('hv-file-path'), 'the path is the reference')
  assert.ok(!files.includes('<svg'), 'and carries no second glyph')
})

test('only an unambiguous URL or rooted path becomes a reference', () => {
  const cases = ['10/09/2026', '1.2', '/usr', 'src/main.py', 'and/or', 'v1/v2', '-']
  const table = renderWidget({ k: 'table', d: 'h=What|Value;' + cases.map((c, i) => `r${i}|${c}`).join(';') })
  assert.ok(!table.includes('hv-ref'), `prose and numbers stay text: ${cases.join(', ')}`)

  // Model output is untrusted: a quote in a value must not close the attribute.
  const quoted = renderWidget({ k: 'table', d: 'x|https://example.com/a"bonmouseover' })
  assert.ok(quoted.includes('data-hv-value="https://example.com/a&quot;bonmouseover"'), 'the value is escaped')
  assert.ok(!quoted.includes('a"bonmouseover'), 'and cannot open a second attribute')
})

test('the mount performs a reference’s click through the host bridge, and only from the core', () => {
  assert.ok(PLUGIN_SRC.includes("closest('[data-hv-link]')"), 'the delegated listener finds the reference')
  assert.ok(PLUGIN_SRC.includes('bridge.openExternal(value)'), 'a URL opens externally')
  assert.ok(PLUGIN_SRC.includes('bridge.revealPath(value)'), 'a path is revealed to the OS file manager')
  assert.ok(PLUGIN_SRC.includes("typeof bridge.revealPath === 'function'"), 'and both are feature-detected')
  // The core declares; the mount acts. One listener, on the element React owns.
  assert.ok(!CORE_SRC.includes('openExternal') && !CORE_SRC.includes('revealPath'), 'the core names no host API')
})

// ---------------------------------------------------------------------------------------------
// Computed cells — SPEC.md, round 12.  The one table in `tests/cells.json` is read by both halves:
// this suite proves the drawing core computes what the agent half's suite says it computes, so a
// rule that drifts fails here instead of in an answer nobody can see was wrong.

test('a computed cell is computed from the payload the widget draws', () => {
  const vectors = JSON.parse(readFileSync(join(HERE, 'cells.json'), 'utf8')).vectors
  assert.ok(vectors.length >= 10, 'the shared vector table is the contract')
  for (const vector of vectors) {
    assert.equal(resolveCells(vector.payload), vector.resolved, vector.why)
  }
})

test('a payload with no call in it is returned byte-identical', () => {
  for (const payload of ['A=1;B=2', '', 'h=Board|Runs;Alpha|42', '  spaced = 1 ; b = 2 ', '12;18;9']) {
    assert.equal(resolveCells(payload), payload)
  }
  assert.equal(resolveCells(undefined), '')
})

test('the call is the whole value: a formula in prose stays prose', () => {
  // `[^()]*` keeps the grammar flat, so a call inside a call is not a call either
  assert.equal(resolveCells('A=1;T=about sum(A, A)'), 'A=1;T=about sum(A, A)')
  assert.equal(resolveCells('A=1;B=2;T=sum(share(A, B), A)'), 'A=1;B=2;T=sum(share(A, B), A)')
  assert.equal(resolveCells('A=1;T=sum(A)(A)'), 'A=1;T=sum(A)(A)')
})

test('the drawing prints the number, and never a formula it could not compute', () => {
  const computed = renderWidget({ k: 'metrics', d: 'A=1;B=2;T=sum(A, B)', t: 'Totals' })
  assert.ok(computed.includes('>3<'), 'the total is drawn as the number it is')
  assert.ok(!computed.includes('sum('), 'and the formula is gone')

  const stuck = renderWidget({ k: 'metrics', d: 'A=1;B=2;T=sum(A, Nope)', t: 'Totals' })
  assert.ok(stuck.includes('sum(A, Nope)'), 'an unresolvable call is visible, not invented')
  assert.ok(!/\bnan\b/i.test(stuck), 'and nothing in the drawing invents a number for it')

  // The core never rewrites the answer's own encoding: a payload without a call is untouched.
  assert.equal(
    renderWidget({ k: 'bars', d: 'A=1;B=2' }),
    renderWidget({ k: 'bars', d: 'A=1;B=2' })
  )
  const rows = parseRows('Firmware=42;DSP=28;Web=18;Total=sum(Firmware, DSP, Web)')
  assert.equal(rows[3].cells[0].value, '88', 'parseRows hands every renderer numbers')
})

test('the core declares no evaluator the answer can reach: a call is data, never code', () => {
  for (const name of ['eval(', 'new Function', 'import(', 'require(']) {
    assert.ok(!CORE_SRC.includes(name), `the core must not carry ${name}`)
  }
  // and the only names a call may use are the three SPEC.md lists
  assert.ok(/const CALL_ARITY = \{ sum: null, share: 2, diff: 2 \}/.test(CORE_SRC), 'the three functions, and no more')
})

// ---------------------------------------------------------------------------------------------
// The interaction templates — SPEC.md rounds 11 and 13. A template is DATA: the model writes an
// `x=` value and pays nothing, the core only DECLARES (attributes, never a handler), and the mount
// performs. So the template itself is a pure function, and it is proved here without a DOM — a
// widget the mount never touches is exactly the string these tests read.

test('a template belongs to a shape, and a kind that cannot carry it draws as a static widget', () => {
  assert.equal(templateFor('toggle', 'checklist'), 'toggle')
  assert.equal(templateFor('pick', 'records'), 'pick')
  assert.equal(templateFor('step', 'facts'), 'step')
  assert.equal(templateFor('step', 'settings'), '', 'step is not a settings template — nothing to move')
  assert.equal(templateFor('toggle', 'bars'), '', 'a template the shape cannot carry names nothing')
  assert.equal(templateFor('nonsense', 'kpi'), '')
  // Total, and never a throw: a prototype key is not a template either.
  for (const name of ['constructor', '__proto__', 'toString', '', null, undefined, 42, {}]) {
    assert.equal(templateFor(name, 'kpi'), '', `templateFor(${String(name)})`)
    assert.doesNotThrow(() => applyTemplate(name, 'kpi', parseRows('A=1'), { picked: 0 }))
  }
  assert.equal(applyTemplate('zzz', 'kpi', parseRows('A=1'), {}).length, 1)
})

test('a widget that carries a template declares it, and every row the template acts on', () => {
  const pick = renderWidget({ k: 'settings', d: 'Motion=on;Sound=off', x: 'pick' })
  assert.ok(pick.includes('data-hv-x="pick"'), 'the root says the widget is operable')
  assert.ok(pick.includes('data-hv-i="0"') && pick.includes('data-hv-i="1"'), 'each row it acts on is named')
  assert.ok(!pick.includes('data-hv-picked'), 'nothing is marked before a pick')

  const step = renderWidget({ k: 'facts', d: 'Ports=2', x: 'step' })
  assert.ok(step.includes('data-hv-x="step"'))
  assert.ok(step.includes('data-hv-d="-1"') && step.includes('data-hv-d="1"'), 'a minus and a plus control')
  assert.ok(step.includes('data-hv-send'), 'one send control at the widget’s foot')
  assert.ok(step.includes('disabled'), 'and it is disabled while nothing has moved')
  assert.ok(!step.includes('addEventListener'), 'the core never installs a handler')

  // A step widget with a moved row can send; the same widget with nothing moved cannot.
  const moved = renderWidget({ k: 'facts', d: 'Ports=2', x: 'step' }, null, { stepped: { 0: 1 } })
  assert.ok(!moved.includes('data-hv-send disabled'), 'a moved row enables the send')
  assert.ok(renderWidget({ k: 'facts', d: 'Ports=2', x: 'step' }, null, { stepped: { 0: 1 }, sending: true }).includes('data-hv-send disabled'),
    'and an in-flight send disables it again')
})

test('the markup of a widget with no x= is byte-identical, whatever the new arguments are', () => {
  for (const kind of KINDS) {
    const attrs = SAMPLES[kind]
    const before = renderWidget(attrs)
    // The optional rows argument and an empty state change nothing at all.
    assert.equal(renderWidget(attrs, parseRows(attrs.d), {}), before, `${kind}: the second argument changes nothing`)
    // And neither does a template the kind cannot carry.
    if (!templateFor('pick', kind)) {
      assert.equal(renderWidget({ ...attrs, x: 'pick' }), before, `${kind}: a template its shape cannot carry is not an attribute`)
    }
    assert.equal(renderWidget({ ...attrs, x: 'nonsense' }), before, `${kind}: an unknown template draws as a static widget`)
  }
  assert.equal(renderWidget({ k: 'bars', d: 'A=1;B=2', x: 'pick' }), renderWidget({ k: 'bars', d: 'A=1;B=2' }))
})

test('per-row state: a toggle ticks the row it was clicked on and no other', () => {
  const rows = parseRows('Read the archive;Patch the entry;Flash the board')
  const once = applyTemplate('toggle', 'steps', rows, { ticked: { 1: true } })
  assert.equal(once[1].ticked, true, 'the clicked row is ticked')
  assert.equal(once[0].ticked, undefined, 'and its siblings are untouched')
  assert.equal(once[2].ticked, undefined)

  const twice = applyTemplate('toggle', 'steps', once, { ticked: { 1: false } })
  assert.equal(twice[1].ticked, false, 'a second click unticks it')

  // The tick is drawn from the state, never inferred from the data: one row's state, one row's glyph.
  const tickedRows = applyTemplate('toggle', 'steps', rows, { ticked: { 0: true } })
  const markup = renderWidget({ k: 'steps', d: 'Read the archive;Patch the entry', x: 'toggle' }, tickedRows, {})
  assert.ok(markup.includes('hv-check--done'), 'the ticked row draws as done')
  assert.ok(markup.includes('hv-check--todo'), 'its neighbour stays todo')
  assert.ok(markup.includes('data-hv-i="0"') && markup.includes('data-hv-i="1"'))

  // An outline row's value is its own title, so the tick rides beside the text, never over it.
  const outline = renderWidget({ k: 'outline', d: '1=Intro;1.1=Scope', x: 'toggle' },
    applyTemplate('toggle', 'outline', parseRows('1=Intro;1.1=Scope'), { ticked: { 1: true } }), {})
  assert.ok(outline.includes('hv-outline-glyph" aria-hidden="true">\u2713<'), 'a tick glyph, in the one vocabulary')
  assert.ok(outline.includes('hv-outline-t">Scope<'), 'and the row keeps its own title')
})

test('a step change recomputes the total the payload computes', () => {
  const rows = parseRows('Firmware=42;DSP=28;Web=18;Total=sum(Firmware, DSP, Web)')
  assert.equal(rows[3].cells[0].value, '88', 'the call resolves before any state is applied')

  const up = applyTemplate('step', 'metrics', rows, { stepped: { 0: 2 } })
  assert.equal(up[0].cells[0].value, '44', 'the stepped row moved by its delta')
  assert.equal(up[1].cells[0].value, '28', 'and no other row moved')
  assert.equal(up[3].cells[0].value, '90', 'the model’s own sum followed the reader’s hand')

  const down = applyTemplate('step', 'metrics', up, { stepped: { 2: -50 } })
  assert.equal(down[2].cells[0].value, '0', 'a row never goes below 0')
  assert.equal(down[3].cells[0].value, '72', 'and the total is recomputed over the clamped rows')

  // The same state applied to rows that moved nothing changes nothing at all.
  const still = applyTemplate('step', 'metrics', rows, { stepped: { 0: 0 } })
  assert.equal(still, rows, 'no delta, the input is returned untouched')
})

test('the turn is derived from the payload, never authored by the model', () => {
  const rows = parseRows('Firmware=42;DSP=28;Web=18')
  assert.equal(sendText('pick', 'facts', rows, { picked: 1 }, ''), 'Picked DSP')
  assert.equal(sendText('pick', 'facts', rows, { picked: 1 }, 'Mix'), 'Mix: Picked DSP')
  // A step carries the DELTA only — never the whole state, and one entry per moved row.
  assert.equal(sendText('step', 'kpi', rows, { stepped: { 0: 2, 2: -1 } }, ''), 'Firmware +2, Web -1')
  assert.equal(sendText('step', 'kpi', rows, { stepped: { 0: 2 } }, 'Mix'), 'Mix: Firmware +2')
  assert.equal(sendText('step', 'kpi', rows, { stepped: { 0: 0 } }, ''), '', 'nothing moved, nothing to send')
  assert.equal(sendText('step', 'kpi', rows, {}, ''), '')
  assert.equal(sendText('pick', 'bars', rows, { picked: 0 }, ''), '', 'an impossible template sends nothing')
  assert.equal(sendText('nonsense', 'kpi', rows, { picked: 0 }, ''), '')
})

test('the mount owns the behaviour: one listener, one send, and no session means no send', () => {
  assert.ok(PLUGIN_SRC.includes('if (!node || !template) return undefined'), 'a static widget installs no listener')
  assert.ok(PLUGIN_SRC.includes("closest('[data-hv-i]')"), 'the listener maps a click to a row')
  assert.ok(PLUGIN_SRC.includes("closest('[data-hv-d]')"), 'and a step control to its delta')
  assert.ok(PLUGIN_SRC.includes("closest('[data-hv-send]')"), 'and the send control to the send')
  // The send is ONE isolated function, so the fallback path is a one-line change if the probe fails.
  assert.ok(/function submitTurn\(text\) \{[\s\S]*?prompt\.submit[\s\S]*?\n\}/.test(PLUGIN_SRC), 'one submitTurn')
  assert.ok(PLUGIN_SRC.includes("display_kind: 'hidden'"), 'and it is a hidden turn')
  assert.ok(PLUGIN_SRC.includes('if (inflight.current) return'), 'one send in flight per widget')
  assert.ok(PLUGIN_SRC.includes('if (!text || !focusedSession()) return'), 'no resolvable session, no send')
  assert.ok(
    PLUGIN_SRC.includes('state.focusedSessionId') &&
      PLUGIN_SRC.includes('state.focusedStoredSessionId') &&
      PLUGIN_SRC.includes('state.activeSessionId'),
    'the session resolves focus first, the primary last'
  )
  assert.ok(PLUGIN_SRC.includes('applyTemplate(template, spec.kind, spec.rows, state)'), 'the mount re-derives rows')
  assert.ok(PLUGIN_SRC.includes('renderWidget(input, rows,'), 'and re-renders through renderWidget with them')
  // The core DECLARES and never performs: it names no host API and installs no handler.
  assert.ok(!CORE_SRC.includes('prompt.submit') && !CORE_SRC.includes('focusedSessionId'), 'the core names no host API')
  assert.ok(!CORE_SRC.includes('addEventListener') && !CORE_SRC.includes('useState'), 'and owns no behaviour')
})

// ---------------------------------------------------------------- round 13 -----

test('the five remaining shapes draw, name themselves, and keep every value they cannot draw', () => {
  // tags: one chip a row, `label=value` prints the value inside the chip, and the label always stays
  // (the colour is a first-seen key, so it ranks and never encodes).
  const tags = renderWidget(SAMPLES.tags)
  assert.ok(tags.includes('class="hv hv-tags"'), 'the chips draw')
  assert.ok(tags.includes('hv-tag-label">Firmware'), 'a bare label keeps its text')
  assert.ok(tags.includes('hv-tag-label">DSP') && tags.includes('hv-tag-value">28'), 'label=value prints both inside the chip')
  assert.ok(tags.includes('hv-tag-key hv-c0'), 'a chip ranks with a first-seen palette key')

  // calendar: one month from the FIRST row's date, its marked days labelled; a date in another month,
  // or one that is not a date, is printed as text under the drawing, never dropped.
  const cal = renderWidget({ k: 'calendar', d: '2026-10-04=release;2026-10-09=review;2026-11-02=later;nope=bad', t: 'Release' })
  assert.ok(cal.includes('hv-cal-month">October 2026'), 'the month is the first row’s')
  assert.ok(cal.includes('hv-cal-day--marked'), 'the marked days are drawn')
  assert.ok(cal.includes('hv-cal-label">release') && cal.includes('hv-cal-label">review'), 'each marked day carries its label')
  assert.ok(cal.includes('hv-cal-stray') && cal.includes('2026-11-02') && cal.includes('nope'), 'a row out of the month is shown as text, not lost')
  assert.ok(!cal.includes('hv-prose'), 'a calendar with drawn days is never a fallback')

  // area: the SAME series as `line`, its region filled in the series' own hue under the stroke.
  const area = renderWidget(SAMPLES.area)
  const line = renderWidget({ k: 'line', d: SAMPLES.area.d, t: 'Latency', u: 'ms' })
  assert.ok(area.includes('hv-line hv-area'), 'the area is the line with its own root class')
  assert.ok(area.includes('hv-line-area') && area.includes('hv-line-path'), 'the region sits under the stroke')
  assert.ok(CSS.includes('.hv-area .hv-line-area'), 'and the area fills in the series hue')
  assert.equal(area.replace('hv-line hv-area', 'hv-line').replace('data-kind="area"', 'data-kind="line"'), line, 'same labels and measure as `line`')

  // tabs: one panel a tab; the first `:` delimits the label, and a panel draws what a single-widget
  // directive of that kind draws. An entry with no kind keeps its text under the drawing.
  const tabs = renderWidget({ k: 'tabs', d: 'Firmware:bars=x=1;y=2~Cost:table=h=Item|k~brokenentry', t: 'Panels' })
  assert.ok(tabs.includes('data-hv-tab="0"') && tabs.includes('data-hv-tab="1"'), 'one tab a panel')
  assert.ok(tabs.includes('>Firmware<') && tabs.includes('>Cost<'), 'the tab is its label')
  assert.ok(tabs.includes('hv-tabpanel') && tabs.includes('hv-bar'), 'the chosen panel draws its kind')
  assert.ok(tabs.includes('aria-selected="true"'), 'the chosen tab says so')
  assert.ok(tabs.includes('hv-tabs-stray') && tabs.includes('brokenentry'), 'an entry with no kind is shown, not dropped')
  // The chosen panel rides in `opts` (mount state): index 1 draws the table, not the bars.
  const second = renderWidget({ k: 'tabs', d: 'Firmware:bars=x=1;y=2~Cost:table=h=Item|k' }, null, { tab: 1 })
  assert.ok(second.includes('hv-table') && !second.includes('hv-bar'), 'the mount’s chosen panel is the one drawn')

  // followup: one button a row; the label is the button and the prompt is what it sends. An empty
  // prompt keeps its label as text.
  const follow = renderWidget(SAMPLES.followup)
  assert.ok(follow.includes('data-hv-followup="Make the tie round the same way"'), 'the prompt rides in the attribute')
  assert.ok(follow.includes('>Round both halves<'), 'the label is the button')
  assert.ok(follow.includes('hv-followup-stray') && follow.includes('Trim the log'), 'an empty prompt keeps its label')
})

test('the mount performs tabs and followup, and reuses the one send', () => {
  // tabs: the chosen panel persists for the turn, as a `pick` keeps its row.
  assert.ok(PLUGIN_SRC.includes("closest('[data-hv-tab]')"), 'the mount maps a tab click to its panel')
  assert.ok(PLUGIN_SRC.includes("spec.kind !== 'tabs'"), 'and only a tabs widget installs it')
  // followup: the click sends the prompt once, through the SAME `submitTurn`, and honours the session gate.
  assert.ok(PLUGIN_SRC.includes("closest('[data-hv-followup]')"), 'the mount maps a followup click to its prompt')
  assert.ok(PLUGIN_SRC.includes("spec.kind !== 'followup'"), 'and only a followup widget installs it')
  // The core still DECLARES and never performs: it writes the attribute but names no host API.
  assert.ok(CORE_SRC.includes('data-hv-followup'), 'the core declares the followup attribute')
  assert.ok(!CORE_SRC.includes('submitTurn') && !CORE_SRC.includes('focusedSession'), 'and names no host API')
  assert.ok(!CORE_SRC.includes('addEventListener'), 'the core installs no handler')
})
