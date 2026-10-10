/**
 * hermes-viz — the desktop half.
 *
 * Registers the `::viz` transcript directive and mounts the drawing core's
 * markup. The runtime loader resolves exactly three bare specifiers
 * (`@hermes/plugin-sdk`, `react`, `react/jsx-runtime`) and refuses every other
 * import — including relative ones, which cannot resolve against the blob: URL
 * a runtime plugin is evaluated from — so the pure core below is carried
 * verbatim from `render/core.mjs` and `tests/desktop.test.mjs` fails if the two
 * copies drift.
 *
 * A directive is one single-line paragraph `::viz{...}`; attrs arrive parsed
 * and untrusted. The widget mounts into the app's own React tree, so it is
 * transparent, follows the theme live and is sized by the pane: one grid,
 * `repeat(auto-fit, minmax(16rem, 1fr))`.
 */

import {
  Badge,
  Button,
  ListRow,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  ToggleRow,
  TRANSCRIPT_DIRECTIVE_AREA
} from '@hermes/plugin-sdk'
import { useCallback, useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const STYLE_ID = 'hermes-viz-widgets'

// >>> vendored-core
/** Every kind this plugin draws itself. `board` is the multi-widget form and is
 *  dispatched before this list is consulted. */
const KINDS = [
  'kpi', 'bars', 'line', 'donut', 'steps', 'table', 'progress', 'sparkline',
  'section',
  'checklist', 'changes', 'outline', 'facts', 'files', 'parts', 'settings',
  'timeline', 'ranges', 'metrics', 'array', 'heatmap',
  'wireframe', 'candlestick',
  'words', 'recipe', 'route', 'nutrition', 'matches',
  'bracket', 'gloss', 'forms',
  'funnel', 'scatter', 'waterfall',
  // The seven shapes that are not already a kind (`steps` is both). A rule may
  // emit a bare `k="records"` with no subject rule: the shape draws it well.
  'records', 'pairs', 'series', 'stages', 'grid', 'groups', 'events'
]

/** The eight data SHAPES — how data is arranged, not what it is about. Every
 *  drawn kind declares one, and each is itself a kind, so unfamiliar data
 *  renders deliberately instead of degrading to text. */
const SHAPES = ['records', 'pairs', 'series', 'stages', 'steps', 'grid', 'groups', 'events']

/** The kinds that draw structure, not data, so they carry no data shape. */
const SHAPELESS = ['section']

/** kind -> shape. A subject kind is a SKIN over a shape, never a new engine:
 *  `nutrition` is `records` measured against a target, `words` is `records` with
 *  four cells, `forms` is `grid`, `route` is `events`, `matches` is `groups`.
 *  The debatable ones (`waterfall` a signed run, `bracket` a columnar grid) sit
 *  with their nearest shape on purpose — the mapping only has to be honest. */
const SHAPE_OF = {
  records: 'records',
  pairs: 'pairs',
  series: 'series',
  stages: 'stages',
  steps: 'steps',
  grid: 'grid',
  groups: 'groups',
  events: 'events',

  kpi: 'records', facts: 'records', files: 'records', settings: 'records',
  metrics: 'records', heatmap: 'records', words: 'records', nutrition: 'records',
  bars: 'series', line: 'series', donut: 'series', progress: 'series',
  sparkline: 'series', candlestick: 'series', waterfall: 'series',
  checklist: 'steps', outline: 'steps',
  changes: 'pairs', ranges: 'pairs', gloss: 'pairs', scatter: 'pairs',
  table: 'grid', parts: 'grid', array: 'grid', recipe: 'grid', forms: 'grid',
  bracket: 'grid', wireframe: 'grid',
  timeline: 'events', route: 'events',
  funnel: 'stages', matches: 'groups'
}

/** Six palette slots, declared once in the CSS as `--hv-1` … `--hv-6`. */
const PALETTE = 6

/** The one glyph vocabulary. Every glyph the core draws comes from here, and
 *  every one of them keeps its text label — a glyph never carries meaning
 *  alone. Nothing outside near-ASCII: no U+2B00-U+2BFF, no U+1F000-U+1FAFF,
 *  and nothing an emoji font can claim — U+26A0 used to be the recipe's warning
 *  and a host substituting an emoji font drew it in colour. */
const GLYPHS = {
  done: '\u2713',
  doing: '\u25cf',
  todo: '\u25cb',
  blocked: '\u2715',
  up: '\u25b2',
  down: '\u25bc',
  next: '\u25b8',
  document: '\u25a4',
  code: '\u25c8',
  unknown: '\u25a1'
}

/** Strip the five characters the encoding reserves, plus newlines and edge space. */
function clean(value) {
  return String(value === undefined || value === null ? '' : value)
    .replace(/[;|=~\n\r]/g, '')
    .trim()
}

/** HTML-escape. Attr values are untrusted model output. */
function esc(value) {
  return String(value === undefined || value === null ? '' : value).replace(/[&<>"']/g, c => {
    if (c === '&') return '&amp;'
    if (c === '<') return '&lt;'
    if (c === '>') return '&gt;'
    if (c === '"') return '&quot;'
    return '&#39;'
  })
}

/** Two-decimal round, so emitted percentages never carry float tails. */
function round(n) {
  return Math.round(n * 100) / 100
}

/** First finite number in a string, else 0. */
function num(value) {
  const parsed = parseFloat(String(value === undefined || value === null ? '' : value).replace(/[^0-9.eE+-]/g, ''))
  return Number.isFinite(parsed) ? parsed : 0
}

function unitSuffix(opts) {
  return opts && opts.unit ? `<span class="hv-unit">${esc(opts.unit)}</span>` : ''
}

// ---------------------------------------------------------------------------
// References the host owns.
//
// A URL or a path in a cell is a thing the reader can act on, and the host
// already has one way of drawing those: `class="ref" data-ref="<kind>"` plus a
// 24x24 Tabler outline glyph, which its own stylesheet colours per kind and
// sizes in `em`. The host's glyph paths are copied from its
// `components/assistant-ui/reference-kinds.ts` (`REFERENCE_STYLES`) because a
// runtime plugin resolves three bare specifiers and cannot import them; the
// duplication is the price of a widget carrying the same glyph as the prose
// around it. If the host changes one, change it here in the same breath.
//
// The plugin declares no colour for them: the hue comes from `[data-ref]` in the
// host's stylesheet, so a theme restyles a widget's reference with the rest.
// `data-hv-link` is the core saying what a click MEANS, never doing it — the
// core stays DOM-free, and VizWidget owns the one listener that performs it.
const REF_ICONS = {
  url: [
    'M9 15l6 -6',
    'M11 6l.463 -.536a5 5 0 0 1 7.071 7.072l-.534 .464',
    'M13 18l-.397 .534a5.068 5.068 0 0 1 -7.127 0a4.972 4.972 0 0 1 0 -7.071l.524 -.463'
  ],
  file: [
    'M14 3v4a1 1 0 0 0 1 1h4',
    'M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2',
    'M9 9l1 0',
    'M9 13l6 0',
    'M9 17l6 0'
  ]
}

/** A URL cell: the scheme is the whole test, so nothing is guessed. */
const URL_CELL = /^https?:\/\/\S+$/i
/** A path cell: rooted at `/` with at least one more slash and no whitespace, so
 *  a column of dates, fractions or a bare `/usr` is never mistaken for one. A
 *  `~/` path cannot arrive — the payload grammar strips `~`, it separates board
 *  entries — so only the rooted form is tested for. */
const PATH_CELL = /^\/\S*\/\S*$/

/**
 * A reference the host draws, as a button: the host's own class and kind
 * attribute, its glyph, the visible text unchanged, and the value in
 * `data-hv-value` for the listener to act on. A button rather than an anchor
 * because a widget cannot rely on the host's navigation guards — the host
 * refuses a popup outright — so the click is handled, not navigated.
 *
 * The colour is the host's own `--ref-color`, taken inline: the host sets that
 * property from `[data-ref="<kind>"]` and paints `.ref` with it, but a widget
 * cell's own colour is a more specific selector than the host's `.ref`, so the
 * property is read here instead of fought over there. No literal colour is
 * involved and a host without the property falls back to the text colour.
 */
function refCell(kind, value, withIcon) {
  const glyph = withIcon
    ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      (REF_ICONS[kind] || []).map(d => `<path d="${d}"/>`).join('') +
      '</svg>'
    : ''

  return (
    `<button type="button" class="ref hv-ref" data-ref="${kind}"` +
    ` data-hv-link="${kind}" data-hv-value="${esc(value)}"` +
    ` title="${esc(value)}" style="color:var(--ref-color,currentColor)">` +
    `${glyph}${esc(value)}</button>`
  )
}

/** Cell text, drawn as a reference when it is unambiguously one — a full
 *  http(s) URL, or a rooted path. Anything else is plain text, escaped. */
function cellHtml(cell, withIcon) {
  const text = cellText(cell)
  if (URL_CELL.test(text)) return refCell('url', text, withIcon !== false)
  if (PATH_CELL.test(text)) return refCell('file', text, withIcon !== false)
  return esc(text)
}

/** The palette slot for a category, by first-seen order. Same payload -> same
 *  colours; past six categories the ramp wraps, deterministically. */
function slot(index) {
  const i = Number.isFinite(index) ? Math.trunc(index) : 0
  return `hv-c${((i % PALETTE) + PALETTE) % PALETTE}`
}

/** The dim affordance, declared as an attribute: a row a pointer or focus can land on. The
 *  core installs no handler — it only declares. */
const ROW = ' data-hv-row'

/** The agent's own hover note — the ONLY hover label there is.
 *
 *  The core derives none of its own. A label that explains what a row withholds
 *  when the answer never asked for one only says again what is already on
 *  screen, and it lands in the caption while the reader's eye is on the row. So
 *  the label is opt-in — the answer writes `n=` on the directive — and the core
 *  only DECLARES it, as `data-hv-note`, for the mount to reveal. */
function noteAttr(text) {
  return text ? ` data-hv-note="${esc(text)}"` : ''
}

/** The stagger index, written per row: delay is calc(var(--d) * 34ms), so the
 *  list can be any length. The six `:nth-child` delays this replaces stopped at
 *  the sixth row, which was a silent cliff. `extra` is any other inline style. */
function riseRow(index, extra) {
  return ` style="--d:${index}${extra ? ';' + extra : ''}"`
}

/** The grow index, written per bar: delay is calc(var(--k) * 45ms). */
function growBar(index, extra) {
  return ` style="${extra ? extra + ';' : ''}--k:${index}"`
}

/** One cell: `label`, `label=value` or `label=value=extra` (extra is the delta). */
function parseCell(text) {
  const raw = String(text === undefined || text === null ? '' : text)
  if (!raw.includes('=')) return { label: clean(raw), value: '', extra: '' }

  const parts = raw.split('=')
  const label = parts[0]
  const rest = parts.slice(1)
  const value = rest.length > 1 ? rest.slice(0, -1).join('') : rest[0]
  const extra = rest.length > 1 ? rest[rest.length - 1] : ''

  return { label: clean(label), value: clean(value), extra: clean(extra) }
}

/**
 * Computed cells — SPEC.md, round 12.
 *
 * A cell may be a call on the payload's OWN rows, so a total is computed rather than
 * authored:
 *
 *   Total=sum(Firmware, DSP, Web)      Web share=share(Web, Total)      Refunds=diff(Start, Net)
 *
 * Brace-free by construction — parens and commas are not reserved by the encoding — so a
 * call travels inside `d` untouched.  The names are the payload's own rows, a row's number
 * is the first number it carries, and a payload with no call in it comes back byte-identical.
 *
 * PURE and total, like everything else here: a call that cannot be resolved — an unknown
 * name, a non-numeric row, a cycle, a division by zero — is left EXACTLY as written, so the
 * drawing prints `sum(A, B)` instead of inventing a number for it. The agent half refuses
 * such a directive before it is delivered; the core simply never guesses.
 */

/** A cell whose whole value is a call, never part of one. */
const CALL = /^(sum|share|diff)\(([^()]*)\)$/

/** How many arguments each function takes; `null` is "one or more". */
const CALL_ARITY = { sum: null, share: 2, diff: 2 }

/** How many rows a chain of calls may run through before it counts as unresolved. */
const CALL_DEPTH = 8

/** The first number a text carries, or null.  Deliberately not "the whole text is a
 *  number": a row reads `1850 of 2200`, `12 ms` or `42%`, and the amount is the leading
 *  number in every one of those. */
function leadingNum(text) {
  const match = /[-+]?(?:\d+\.?\d*|\.\d+)/.exec(String(text === undefined || text === null ? '' : text))
  return match ? parseFloat(match[0]) : null
}

/** A computed number as text: an integer when it is one, else up to two decimals.
 *  Half away from zero, spelled out in integers — the SAME arithmetic `python/viz_expr.py`
 *  runs. A tie is exactly where two implementations diverge (`toFixed` rounds one way,
 *  Python's `%.2f` another), and a total that reads `0.13` here and `0.12` there is the
 *  drift `tests/cells.json` exists to catch. */
function fmtNum(value) {
  if (!Number.isFinite(value)) return ''
  const scaled = value * 100
  const cents = Math.floor(Math.abs(scaled) + 0.5)
  const frac = cents % 100
  const whole = (cents - frac) / 100
  const tail = frac ? ('.' + String(frac).padStart(2, '0')).replace(/0+$/, '').replace(/\.$/, '') : ''
  return (cents && scaled < 0 ? '-' : '') + String(whole) + tail
}

/** The name a row answers to: the label of its first cell. */
function callName(row) {
  const first = String(row).split('|')[0]
  const at = first.indexOf('=')
  return (at < 0 ? first : first.slice(0, at)).trim()
}

/** A `d` payload with its calls computed.  No call, no change — the text is returned as it
 *  arrived, so a payload the answer wrote by hand is never rewritten by this pass. */
function resolveCells(payload) {
  const raw = typeof payload === 'string' ? payload : ''
  if (!raw.includes('(')) return raw

  const rows = raw.split(';').filter(row => row.trim())
  const index = new Map()
  const memo = new Map()
  const busy = new Set()

  for (const row of rows) {
    if (row.slice(0, 2).toLowerCase() === 'h=') continue // a header names a column, not a value
    const name = callName(row)
    if (name && !index.has(name)) index.set(name, row)
  }

  /** The first number a row carries, through a call when the cell is one. */
  function rowValue(row, depth) {
    for (const cell of String(row).split('|')) {
      const at = cell.indexOf('=')
      const text = (at < 0 ? cell : cell.slice(at + 1)).trim()
      const call = CALL.exec(text)
      if (call) {
        const computed = callValue(call[1], call[2], depth + 1)
        if (computed !== null) return computed
        continue
      }
      const found = leadingNum(text)
      if (found !== null) return found
    }
    return null
  }

  function namedValue(name, depth) {
    if (memo.has(name)) return memo.get(name)
    if (depth > CALL_DEPTH || busy.has(name) || !index.has(name)) return null
    busy.add(name)
    const value = rowValue(index.get(name), depth)
    busy.delete(name)
    if (value !== null) memo.set(name, value)
    return value
  }

  function callValue(name, args, depth) {
    if (!(name in CALL_ARITY)) return null
    const names = args.split(',').map(part => part.trim()).filter(Boolean)
    const arity = CALL_ARITY[name]
    if (!names.length || (arity !== null && names.length !== arity)) return null
    const values = names.map(part => namedValue(part, depth))
    if (values.some(value => value === null)) return null
    if (name === 'sum') return values.reduce((total, value) => total + value, 0)
    if (name === 'diff') return values[0] - values[1]
    return values[1] ? (values[0] / values[1]) * 100 : null
  }

  const out = rows.map(row => {
    const header = row.slice(0, 2).toLowerCase() === 'h='
    const body = header ? row.slice(2) : row
    const cells = body.split('|').map(cell => {
      const at = cell.indexOf('=')
      const text = (at < 0 ? cell : cell.slice(at + 1)).trim()
      const call = CALL.exec(text)
      if (!call) return cell
      const computed = callValue(call[1], call[2], 1)
      if (computed === null) return cell
      return (at < 0 ? '' : cell.slice(0, at + 1)) + fmtNum(computed)
    })
    return (header ? 'h=' : '') + cells.join('|')
  })

  return out.join(';')
}

/** Split a `d` payload: rows on `;`, cells on `|`, a row starting `h=` is a header.
 *  Computed cells are resolved first, so every renderer below sees numbers and only numbers. */
function parseRows(payload) {
  const raw = resolveCells(typeof payload === 'string' ? payload : '')
  if (!raw) return []

  const rows = []

  for (const chunk of raw.split(';')) {
    let text = chunk
    let header = false

    if (text.slice(0, 2).toLowerCase() === 'h=') {
      header = true
      text = text.slice(2)
    }

    const cells = text.split('|').map(parseCell)

    if (cells.some(cell => cell.label || cell.value)) rows.push({ header, cells, raw: text })
  }

  return rows
}

/** `l=1|2` — a section's level. Anything other than an explicit `2` is level 1. */
function parseSectionLevel(value) {
  return clean(value) === '2' ? 2 : 1
}

/** Attrs -> `{ kind, rows, title, unit, palette, level }`. Never throws. */
function parseSpec(attrs) {
  const a = attrs && typeof attrs === 'object' ? attrs : {}
  return {
    kind: clean(a.k).toLowerCase(),
    rows: parseRows(a.d),
    title: clean(a.t),
    unit: clean(a.u),
    palette: clean(a.p),
    note: clean(a.n),
    level: parseSectionLevel(a.l)
  }
}

/** The prose fallback — a malformed spec must read as a sentence, not an empty frame. */
function fallback(opts, reason) {
  const source = opts && opts.source ? esc(opts.source) : ''
  const text = source || 'viz: nothing to draw'
  return `<p class="hv hv-prose" data-reason="${esc(reason)}">${text}</p>`
}

function dataRows(rows) {
  return Array.isArray(rows) ? rows.filter(row => row && !row.header) : []
}

function cellAt(row, index) {
  const cell = row && row.cells ? row.cells[index] : undefined
  return cell || { label: '', value: '', extra: '' }
}

/** A cell's magnitude: the value, or the label itself when the cell is a bare
 *  number (`d="12;18;9"`). Without this a series has no values and plots flat. */
function cellNum(cell) {
  return num(cell.value !== '' ? cell.value : cell.label)
}

/** The cell's text, preferring the value so `label=value` rows read right. */
function cellText(cell) {
  return cell.value || cell.label
}

/** The `of` form: `<value> of <target>`. Returns the value text and the
 *  numeric target, or a null target when there is nothing to measure against —
 *  in which case the row-max (or 0..100%) scale is the fallback. */
function splitOf(text) {
  const raw = String(text === undefined || text === null ? '' : text)
  const at = raw.search(/\s+of\s+/i)
  if (at < 0) return { value: raw, target: null }
  const target = num(raw.slice(at))
  return { value: raw.slice(0, at).trim(), target: target > 0 ? target : null }
}

/** Four even ticks from 0 to the domain — a real scale, labelled. */
function axisTicks(domain, count) {
  const out = []
  for (let i = 0; i <= count; i++) out.push(round((domain * i) / count))
  return out
}

/** The shared scale a bar/range row draws against: 0 at the start, the domain
 *  cap at the end, ticks between. */
function renderAxis(domain, opts) {
  const values = axisTicks(domain, 4)
  const last = values.length - 1
  const ticks = values
    .map((value, i) => {
      const cls = i === 0 ? 'hv-tick hv-axis-lo' : i === last ? 'hv-tick hv-axis-hi' : 'hv-tick'
      const unit = i === last ? unitSuffix(opts) : ''
      return `<span class="${cls}">${value}${unit}</span>`
    })
    .join('')

  return (
    `<div class="hv-axis">` +
    `<span class="hv-axis-pad" aria-hidden="true"></span>` +
    `<span class="hv-axis-scale">${ticks}</span>` +
    `<span class="hv-axis-pad hv-axis-pad--end" aria-hidden="true"></span>` +
    `</div>`
  )
}

/** KPI tiles — emitted as bare grid children so the widget grid lays them out. */
function renderKpi(rows, opts) {
  return dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const delta = cell.extra
        ? `<span class="hv-kpi-delta hv-kpi-delta--${cell.extra.startsWith('-') ? 'down' : 'up'}">` +
          `${cell.extra.startsWith('-') ? GLYPHS.down : GLYPHS.up} ${esc(cell.extra)}</span>`
        : ''
      return (
        `<div class="hv-kpi-tile" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-kpi-label">${esc(cell.label)}</span>` +
        `<span class="hv-kpi-value">${esc(cell.value)}${unitSuffix(opts)}</span>` +
        delta +
        `</div>`
      )
    })
    .join('')
}

/** The bar domain: `u="%"` is a real 0..100 scale; every other unit scales to
 *  the row maximum. Either way the length encodes a number with a stated cap. */
function barsDomain(values, opts) {
  const top = Math.max(...values, 0)
  return opts && opts.unit === '%' ? 100 : top || 1
}

function renderBars(rows, opts, root) {
  const data = dataRows(rows)
  const unit = opts && opts.unit ? opts.unit : ''
  // the `of` form: a row value with something to measure it against. The
  // target is that row's own track end and its share is named; a row with no
  // target falls back to the shared row-max (or 0..100%) scale.
  const parsed = data.map(row => {
    const cell = cellAt(row, 0)
    const split = splitOf(cell.value)
    return { cell, value: split.value, target: split.target, n: num(split.value) }
  })
  const values = parsed.map(row => row.n)
  const domain = barsDomain(values, opts)
  const total = values.reduce((sum, value) => sum + Math.max(0, value), 0)
  // When the values already are percentages, a second percent (their share of the
  // total) contradicts the bar's own length and the axis. Only non-percent units
  // need the share to carry the comparison.
  const showShare = !(opts && opts.unit === '%')
  const hasTarget = parsed.some(row => row.target !== null)

  const items = parsed
    .map((row, i) => {
      const cell = row.cell
      // Against a target the bar fills to that target; otherwise the shared scale.
      const pct = row.target
        ? Math.max(0, Math.min(100, (row.n / row.target) * 100))
        : Math.max(0, Math.min(100, (values[i] / domain) * 100))
      const share = row.target
        ? Math.round((row.n / row.target) * 100)
        : total > 0
          ? Math.round((Math.max(0, values[i]) / total) * 100)
          : 0
      const shareCell = row.target || showShare ? `<span class="hv-row-share">${share}%</span>` : ''
      const targetCell = row.target ? `<span class="hv-row-target">of ${row.target}</span>` : ''
      return (
        `<div class="hv-row" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-row-label">${esc(cell.label)}</span>` +
        `<span class="hv-bar"><span class="hv-bar-fill ${slot(i)}"${growBar(i, `width:${round(pct)}%`)}></span></span>` +
        `<span class="hv-row-meta">` +
        `<span class="hv-row-value">${esc(row.value)}${unitSuffix(opts)}</span>` +
        targetCell +
        shareCell +
        `</span>` +
        `</div>`
      )
    })
    .join('')

  // A per-row target is its own track end, so one shared axis no longer describes
  // the bars: each row names its own reference instead.
  const axis = hasTarget ? '' : renderAxis(domain, opts)

  return `<div class="hv ${root || 'hv-bars'}">${items}${axis}</div>`
}

/** The series values across data rows — bare numbers count. */
function seriesValues(rows) {
  return dataRows(rows).map(row => cellNum(cellAt(row, 0)))
}

/** Polyline points across a 100-unit-wide viewBox. */
function seriesPoints(rows, height) {
  const values = seriesValues(rows)
  if (values.length === 0) return ''
  if (values.length === 1) return `0,${round(height / 2)} 100,${round(height / 2)}`

  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = max - min || 1

  return values
    .map((value, i) => {
      const x = (i / (values.length - 1)) * 100
      const y = height - ((value - min) / span) * (height - 2) - 1
      return `${round(x)},${round(y)}`
    })
    .join(' ')
}

/** The area under a series, closed to the chart floor, so the shape has weight. */
function seriesArea(points, height) {
  return points ? `${points} 100,${round(height)} 0,${round(height)}` : ''
}

/** One vertical cross-tick per point, carrying its own hover detail. */
function seriesMarkers(points, values, data, opts) {
  if (!points) return ''
  return points
    .split(' ')
    .map((point, i) => {
      const [x, y] = point.split(',')
      const cell = cellAt(data[i], 0)
      // A bare-number series has no label of its own — the number IS the value,
      // so the point is named by its index instead of repeating itself.
      const label = cell.value !== '' ? cell.label || `#${i + 1}` : `#${i + 1}`
      const unit = opts && opts.unit ? opts.unit : ''
      return (
        `<line class="hv-line-point" x1="${x}" y1="${round(Number(y) - 1.6)}" x2="${x}" y2="${round(Number(y) + 1.6)}">` +
        `<title>${esc(label)}: ${round(values[i])}${esc(unit)}</title></line>`
      )
    })
    .join('')
}

function renderLine(rows, opts) {
  const data = dataRows(rows)
  const values = seriesValues(rows)
  const height = 36
  const points = seriesPoints(rows, height)
  const lo = values.length ? Math.min(...values) : 0
  const hi = values.length ? Math.max(...values) : 0

  // The y scale is the axis — the high value, with its unit, is the readable cap.
  const yTicks =
    values.length > 1
      ? `<div class="hv-line-y">` +
        `<span class="hv-tick">${round(hi)}${unitSuffix(opts)}</span>` +
        `<span class="hv-tick">${round((lo + hi) / 2)}</span>` +
        `<span class="hv-tick">${round(lo)}</span>` +
        `</div>`
      : ''

  // The x labels: each row's own label, else its index.
  const xLabels =
    data.length > 1
      ? `<div class="hv-line-x">` +
        data.map((row, i) => {
          const cell = cellAt(row, 0)
          return `<span class="hv-tick">${esc(cell.value !== '' ? cell.label || String(i + 1) : String(i + 1))}</span>`
        }).join('') +
        `</div>`
      : ''

  return (
    `<div class="hv hv-line">` +
    `<div class="hv-line-plot">` +
    yTicks +
    `<svg class="hv-svg" viewBox="0 0 100 ${height}" preserveAspectRatio="none" role="img">` +
    `<line class="hv-line-floor" x1="0" y1="${height}" x2="100" y2="${height}"></line>` +
    `<polygon class="hv-line-area" points="${seriesArea(points, height)}"></polygon>` +
    `<polyline class="hv-line-path" points="${points}" fill="none"></polyline>` +
    seriesMarkers(points, values, data, opts) +
    `</svg></div>` +
    xLabels +
    `</div>`
  )
}

function renderSparkline(rows, opts) {
  const values = seriesValues(rows)
  const points = seriesPoints(rows, 24)
  const lo = values.length ? Math.min(...values) : 0
  const hi = values.length ? Math.max(...values) : 0
  const unit = opts && opts.unit ? opts.unit : ''
  const title = `trend: ${round(lo)} to ${round(hi)}${unit} over ${values.length} points`
  // The baseline is the series' own floor — the min value's y — so the shape has
  // a reference instead of floating. The meta names both ends of the range.
  const floorY = points
    ? Math.max(...points.split(' ').map(point => Number(point.split(',')[1])))
    : 23

  return (
    `<div class="hv hv-sparkline">` +
    `<svg class="hv-svg" viewBox="0 0 100 24" preserveAspectRatio="none" role="img">` +
    `<title>${esc(title)}</title>` +
    `<line class="hv-spark-base" x1="0" y1="${round(floorY)}" x2="100" y2="${round(floorY)}"></line>` +
    `<line class="hv-line-floor" x1="0" y1="24" x2="100" y2="24"></line>` +
    `<polygon class="hv-spark-area" points="${seriesArea(points, 24)}"></polygon>` +
    `<polyline class="hv-spark-path" points="${points}" fill="none"></polyline>` +
    `</svg>` +
    `<div class="hv-spark-meta">` +
    `<span class="hv-tick hv-axis-lo">min ${round(lo)}${unit}</span>` +
    `<span class="hv-tick hv-axis-hi">max ${round(hi)}${unitSuffix(opts)}</span>` +
    `</div></div>`
  )
}

function renderDonut(rows, opts) {
  const data = dataRows(rows)
  const values = data.map(row => Math.max(0, num(cellAt(row, 0).value)))
  const total = values.reduce((sum, value) => sum + value, 0)

  const r = 15.9155
  const c = 2 * Math.PI * r

  // Consecutive segments are pulled apart by a gap so a slice boundary is
  // legible as shape, not only as tone — but the gap is capped at a third of the
  // shortest arc so a small slice is separated, never erased.
  const GAP = 1.6
  const slices = values.filter(value => value > 0).length
  const smallest = total > 0 ? Math.min(...values.filter(value => value > 0).map(value => (value / total) * c)) : 0
  const step = slices > 1 ? Math.min(GAP, smallest / 3) : 0

  let offset = 0
  let segments = ''

  for (let i = 0; i < values.length; i++) {
    const length = total > 0 ? (values[i] / total) * c : 0
    const drawn = Math.max(0, length - step)
    const cell = cellAt(data[i], 0)
    segments +=
      `<circle class="hv-donut-seg ${slot(i)}" cx="18" cy="18" r="${r}" fill="none" ` +
      `stroke-dasharray="${round(drawn)} ${round(c)}" stroke-dashoffset="${round(-offset)}">` +
      `<title>${esc(cell.label)}: ${esc(cell.value)}${esc(opts && opts.unit ? opts.unit : '')}</title></circle>`
    offset += length
  }

  const centre =
    (data.length === 1 ? cellAt(data[0], 0).value : String(round(total))) +
    (opts && opts.unit ? opts.unit : '')

  const svg =
    `<svg class="hv-donut-svg" viewBox="0 0 36 36" role="img">` +
    `<g transform="rotate(-90 18 18)">` +
    `<circle class="hv-donut-track" cx="18" cy="18" r="${r}" fill="none"></circle>` +
    `${segments}</g>` +
    `<text class="hv-donut-center" x="18" y="18">${esc(centre)}</text>` +
    `</svg>`

  const legend = data
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const share = total > 0 ? Math.round((values[i] / total) * 100) : 0
      return (
        `<span class="hv-legend-item" tabindex="0"${riseRow(i)}>` +
        `<span class="hv-legend-dot ${slot(i)}"></span>` +
        `<span class="hv-legend-key">${esc(cell.label)}</span>` +
        `<span class="hv-legend-val">${esc(cell.value)}${unitSuffix(opts)}</span>` +
        `<span class="hv-legend-share">${share}%</span>` +
        `</span>`
      )
    })
    .join('')

  return `<div class="hv hv-donut">${svg}<div class="hv-legend">${legend}</div></div>`
}

function renderSteps(rows, opts) {
  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const text = cell.value || cell.label
      return (
        `<li class="hv-step" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-step-n" aria-hidden="true">${i + 1}</span>` +
        `<span class="hv-step-t">${esc(text)}</span>` +
        `</li>`
      )
    })
    .join('')

  return `<div class="hv hv-steps"><ol class="hv-step-list">${items}</ol></div>`
}

function renderTable(rows, opts) {
  const list = Array.isArray(rows) ? rows.filter(Boolean) : []
  const header = list.find(row => row.header)
  const body = list.filter(row => !row.header)

  // Headers stay plain text — a header names a column, it is not a value. A body
  // cell that is a URL or a rooted path is drawn as the host's reference.
  const text = cell => esc(cellText(cell))
  const cell = entry => cellHtml(entry)
  const head = header
    ? `<thead><tr>${header.cells.map(entry => `<th>${text(entry)}</th>`).join('')}</tr></thead>`
    : ''
  const tbody = `<tbody>${body
    .map((row, i) => `<tr${riseRow(i)} tabindex="0">${row.cells.map(entry => `<td>${cell(entry)}</td>`).join('')}</tr>`)
    .join('')}</tbody>`

  return `<div class="hv hv-table-wrap"><table class="hv-table">${head}${tbody}</table></div>`
}

/** A bill of materials: the last column is a quantity, right-aligned. */
function renderParts(rows, opts) {
  const list = Array.isArray(rows) ? rows.filter(Boolean) : []
  const header = list.find(row => row.header)
  const body = list.filter(row => !row.header)

  const text = cell => esc(cellText(cell))
  const head = header
    ? `<thead><tr>${header.cells
        .map((cell, i, all) => `<th${i === all.length - 1 ? ' class="hv-part-qty"' : ''}>${text(cell)}</th>`)
        .join('')}</tr></thead>`
    : ''
  const tbody = `<tbody>${body
    .map(
      (row, i) =>
        `<tr${riseRow(i)} tabindex="0">${row.cells
          .map((cell, i, all) => `<td${i === all.length - 1 ? ' class="hv-part-qty"' : ''}>${text(cell)}</td>`)
          .join('')}</tr>`
    )
    .join('')}</tbody>`

  return `<div class="hv hv-table-wrap"><table class="hv-table hv-parts">${head}${tbody}</table></div>`
}

function renderProgress(rows, opts) {
  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const pct = Math.max(0, Math.min(100, num(cell.value)))
      return (
        `<div class="hv-prog" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-prog-label">${esc(cell.label)}</span>` +
        `<span class="hv-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${round(pct)}">` +
        `<span class="hv-fill ${slot(i)}"${growBar(i, `width:${round(pct)}%`)}></span></span>` +
        `<span class="hv-prog-value">${round(pct)}%</span>` +
        `</div>`
      )
    })
    .join('')

  // A percentage with no scale is a number, not a reading. Every row is a 0..100
  // share, so the whole widget draws one shared 0..100% axis beneath it.
  return `<div class="hv hv-progress">${items}${renderAxis(100, { unit: '%' })}</div>`
}

/** The state glyphs a checklist row can carry. */
const CHECK_STATES = { done: GLYPHS.done, doing: GLYPHS.doing, todo: GLYPHS.todo, blocked: GLYPHS.blocked }

function renderChecklist(rows) {
  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const wanted = String(cell.value || 'todo').toLowerCase()
      const state = CHECK_STATES[wanted] ? wanted : 'todo'
      return (
        `<li class="hv-check hv-check--${state}" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-check-glyph" aria-hidden="true">${CHECK_STATES[state]}</span>` +
        `<span class="hv-check-label">${esc(cell.label)}</span>` +
        `</li>`
      )
    })
    .join('')

  return `<div class="hv hv-checklist"><ul class="hv-check-list">${items}</ul></div>`
}

/** A file's own name: the last segment, with a trailing slash ignored. */
function basename(path) {
  const trimmed = String(path === undefined || path === null ? '' : path).replace(/\/+$/, '')
  const at = trimmed.lastIndexOf('/')
  return at === -1 ? trimmed : trimmed.slice(at + 1)
}

/** The green `+a` / red `-b` pair, with a zero side left out — the host's
 *  `DiffCount` does the same, so a pure addition never reads as `+8 -0`. */
function diffCount(adds, dels) {
  return (
    `<span class="hv-change-counts">` +
    (adds > 0 ? `<span class="hv-add">+${adds}</span>` : '') +
    (dels > 0 ? `<span class="hv-del">-${dels}</span>` : '') +
    `</span>`
  )
}

/**
 * The changed-files list, in the HOST's own shape.
 *
 * The host already solved this card (`components/assistant-ui/thread/
 * changed-files-card.tsx`), so this is that card: one row per file, the file's
 * own name under a type glyph, the green `+a` and red `-b` at the row's end,
 * the full path one hover away rather than printed, and the row itself the
 * thing you click. A column of absolute paths is noise — the basename
 * identifies the file, the path is what you want only once you have picked one.
 *
 * It draws no proportional bar: the host's card has none, and the counts are
 * the data. No row withholds a number either — the card's footer carries the
 * totals — and no renderer derives a hover label in any case.
 */
function renderChanges(rows) {
  const files = dataRows(rows).map(row => {
    const cell = cellAt(row, 0)
    return {
      path: cell.label,
      name: basename(cell.label),
      adds: Math.abs(num(cell.value)),
      dels: Math.abs(num(cell.extra))
    }
  })
  const totalAdds = files.reduce((sum, file) => sum + file.adds, 0)
  const totalDels = files.reduce((sum, file) => sum + file.dels, 0)

  const items = files
    .map(
      (file, i) =>
        `<button type="button" class="hv-change" tabindex="0"${riseRow(i)}${ROW}` +
        ` data-hv-link="file" data-hv-value="${esc(file.path)}" title="${esc(file.path)}">` +
        `<span class="hv-change-glyph" aria-hidden="true">${fileGlyph(file.path)}</span>` +
        `<span class="hv-change-name">${esc(file.name)}</span>` +
        diffCount(file.adds, file.dels) +
        `</button>`
    )
    .join('')

  const total =
    `<div class="hv-change-total">` +
    `<span class="hv-change-total-label">${files.length === 1 ? '1 file changed' : `${files.length} files changed`}</span>` +
    diffCount(totalAdds, totalDels) +
    `</div>`

  return `<div class="hv hv-changes">${items}${total}</div>`
}

function renderOutline(rows) {
  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const depth = Math.max(0, (cell.label.match(/\./g) || []).length)
      const text = cellText(cell)
      const num = cell.value ? cell.label : ''
      return (
        `<li class="hv-outline-item" tabindex="0"${riseRow(i, `padding-left:${round(depth * 1.1)}rem`)}${ROW}>` +
        `<span class="hv-outline-num">${esc(num)}</span>` +
        `<span class="hv-outline-t">${esc(text)}</span>` +
        `</li>`
      )
    })
    .join('')

  return `<div class="hv hv-outline"><ul class="hv-outline-list">${items}</ul></div>`
}

function renderFacts(rows) {
  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      return (
        `<div class="hv-fact" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-fact-label">${esc(cell.label)}</span>` +
        `<span class="hv-fact-value">${esc(cellText(cell))}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-facts">${items}</div>`
}

/** A single glyph per file kind — the path itself still reads. */
const FILE_GLYPHS = { py: GLYPHS.code, js: GLYPHS.code, mjs: GLYPHS.code, ts: GLYPHS.code, md: GLYPHS.document, json: GLYPHS.document, yml: GLYPHS.next, yaml: GLYPHS.next, sh: GLYPHS.next, html: GLYPHS.document }

function fileGlyph(path) {
  const ext = String(path).toLowerCase().split('.').pop()
  return FILE_GLYPHS[ext] || GLYPHS.unknown
}

function renderFiles(rows) {
  const cells = dataRows(rows).map(row => cellAt(row, 0))

  const items = cells
    .map((cell, i) => {
      return (
        `<div class="hv-file" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-file-glyph" aria-hidden="true">${fileGlyph(cell.label)}</span>` +
        `<span class="hv-file-path">${cellHtml({ label: cell.label, value: '' }, false)}</span>` +
        `<span class="hv-file-meta">${esc(cell.value)}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-files">${items}</div>`
}

function renderSettings(rows) {
  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const on = /^(on|true|1)$/i.test(cell.value)
      return (
        `<div class="hv-setting" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-setting-label">${esc(cell.label)}</span>` +
        `<span class="hv-pill hv-pill--${on ? 'on' : 'off'}">${esc(cell.value || 'off')}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-settings">${items}</div>`
}

/** The `events` skins: the shape's own classes, the timeline's, the route's. */
const EVENT_SKIN = {
  root: 'hv-timeline', list: 'hv-tl-list', item: 'hv-tl-item',
  when: 'hv-tl-when', body: 'hv-tl-body', label: 'hv-tl-label', detail: 'hv-tl-detail'
}

const ROUTE_SKIN = {
  root: 'hv-route', list: 'hv-route-list', item: 'hv-route-stop',
  when: 'hv-route-time', body: 'hv-route-body', label: 'hv-route-place', detail: 'hv-route-detail'
}

/** `events` — a time or date plus a label, on one rail. This is the shape engine;
 *  `timeline` and `route` are the same engine with their own class names. */
function renderEvents(rows, opts, skin) {
  const s = skin || EVENT_SKIN
  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const detail = cell.extra ? `<span class="${s.detail}">${esc(cell.extra)}</span>` : ''
      return (
        `<li class="${s.item}" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="${s.when}">${esc(cell.label)}</span>` +
        `<span class="${s.body}">` +
        `<span class="${s.label}">${esc(cell.value)}</span>` +
        detail +
        `</span></li>`
      )
    })
    .join('')

  return `<div class="hv ${s.root}"><ol class="${s.list}">${items}</ol></div>`
}

function renderTimeline(rows) {
  return renderEvents(rows, {}, EVENT_SKIN)
}

/** `label=lo..hi` -> a span on one shared scale. */
function rangeOf(cell) {
  const raw = cell.value || cell.label
  const parts = String(raw).split('..')
  const a = num(parts[0])
  const b = parts.length > 1 ? num(parts[1]) : a
  return { lo: Math.min(a, b), hi: Math.max(a, b) }
}

function renderRanges(rows, opts) {
  const data = dataRows(rows)
  const spans = data.map(row => rangeOf(cellAt(row, 0)))
  const domain = Math.max(1, ...spans.map(span => span.hi))
  const unit = opts && opts.unit ? opts.unit : ''

  const items = data
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const span = spans[i]
      const left = round((span.lo / domain) * 100)
      const width = Math.max(1, round(((span.hi - span.lo) / domain) * 100))
      return (
        `<div class="hv-row"${ROW}>` +
        `<span class="hv-row-label">${esc(cell.label)}</span>` +
        `<span class="hv-bar hv-range-track">` +
        `<span class="hv-range-span ${slot(i)}"${growBar(i, `left:${left}%;width:${width}%`)}></span>` +
        `</span>` +
        `<span class="hv-row-meta"><span class="hv-row-value">${span.lo}–${span.hi}${unitSuffix(opts)}</span></span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-ranges">${items}${renderAxis(domain, opts)}</div>`
}

function renderMetrics(rows, opts) {
  const data = dataRows(rows)
  // the `of` form reaches metrics too: a target is the metric's own track
  // end and its share is named. Absent a target, one delta domain across the card
  // remains the reference, so a +12 draws longer than a +3.
  const parsed = data.map(row => {
    const cell = cellAt(row, 0)
    const split = splitOf(cell.value)
    return { cell, value: split.value, target: split.target, n: num(split.value) }
  })
  const deltas = parsed.map(row => Math.abs(num(row.cell.extra)))
  const maxDelta = Math.max(1, ...deltas)

  const items = parsed
    .map((row, i) => {
      const cell = row.cell
      const down = cell.extra.startsWith('-')
      const delta = cell.extra
        ? `<span class="hv-metric-delta hv-kpi-delta--${down ? 'down' : 'up'}">${esc(cell.extra)}</span>`
        : ''
      const pct = row.target
        ? Math.max(0, Math.min(100, (row.n / row.target) * 100))
        : (deltas[i] / maxDelta) * 100
      const scale =
        row.target || cell.extra
          ? `<span class="hv-metric-scale" aria-hidden="true">` +
            `<span class="hv-metric-scale-fill${row.target ? '' : ` hv-metric-scale-fill--${down ? 'down' : 'up'}`}"` +
            `${growBar(i, `width:${round(pct)}%`)}></span></span>`
          : ''
      const reference = row.target
        ? `<span class="hv-metric-target">of ${row.target}</span>` +
          `<span class="hv-metric-share">${round(pct)}%</span>`
        : ''
      return (
        `<div class="hv-metric" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-metric-caption">${esc(cell.label)}</span>` +
        `<span class="hv-metric-value">${esc(row.value)}${unitSuffix(opts)}</span>` +
        `</div>` +
        `<div class="hv-metric-foot">${scale}${delta}${reference}</div>`
      )
    })
    .join('')

  return `<div class="hv hv-metrics">${items}</div>`
}

/** `a|b|c` -> a bordered cell grid. A matrix, not a table: no header row. */
function renderArray(rows) {
  const data = dataRows(rows)
  let cols = 1
  for (const row of data) cols = Math.max(cols, row.cells.filter(cell => cell.label || cell.value).length)

  let cellIndex = 0
  const cells = data
    .map(row =>
      row.cells
        .filter(cell => cell.label || cell.value)
        .map(cell => `<span class="hv-cell" tabindex="0"${riseRow(cellIndex++)}>${esc(cellText(cell))}</span>`)
        .join('')
    )
    .join('')

  return `<div class="hv hv-array" style="grid-template-columns:repeat(${cols}, minmax(0, 1fr))">${cells}</div>`
}

function renderHeatmap(rows) {
  const data = dataRows(rows)
  const values = data.map(row => Math.abs(cellNum(cellAt(row, 0))))
  const max = Math.max(1, ...values)

  const cells = data
    .map((row, i) => {
      const cell = cellAt(row, 0)
      // A ramp on --hv-1 against the track token: the value is printed too, so
      // the colour ranks the cells, it does not encode them.
      const strength = round(12 + (values[i] / max) * 88)
      return (
        `<span class="hv-heat-cell" tabindex="0"${riseRow(i, `background:color-mix(in srgb, var(--hv-1) ${strength}%, var(--dt-muted))`)}` +
        `${ROW}>` +
        `<span class="hv-heat-label">${esc(cell.label)}</span>` +
        `<span class="hv-heat-value">${values[i]}</span>` +
        `</span>`
      )
    })
    .join('')

  const legend =
    `<div class="hv-ramp"><span class="hv-tick">0</span>` +
    `<span class="hv-ramp-bar" aria-hidden="true"></span>` +
    `<span class="hv-tick hv-axis-hi">${max}</span></div>`

  return `<div class="hv hv-heatmap">${cells}${legend}</div>`
}

/** The block kinds a wireframe knows. Anything else still draws, as `block`. */
const WF_BLOCKS = ['btn', 'field', 'text', 'img', 'item', 'card', 'chart', 'circle']

/** `block:count,block:count` -> a list of proportional, labelled blocks. */
function wireBlocks(value) {
  return String(value === undefined || value === null ? '' : value)
    .split(',')
    .map(chunk => {
      const [rawType, rawCount] = String(chunk).split(':')
      const type = clean(rawType).toLowerCase()
      if (!type) return null
      return {
        type,
        shape: WF_BLOCKS.includes(type) ? type : 'block',
        count: Math.max(1, Math.round(num(rawCount)) || 1)
      }
    })
    .filter(Boolean)
}

/** A UI mock: rows of proportional, labelled blocks. Reads as a mock, not a legend. */
function renderWireframe(rows) {
  const seen = {}
  const slotFor = type => {
    if (!(type in seen)) seen[type] = Object.keys(seen).length
    return slot(seen[type])
  }

  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const drawn = wireBlocks(cell.value)
        .map((block, bi) => {
          const label = block.count > 1 ? `${block.type} ×${block.count}` : block.type
          return (
            `<span class="hv-wf-block hv-wf-block--${block.shape} ${slotFor(block.type)}" ` +
            `${growBar(bi, `flex-grow:${block.count}`)}${ROW}>` +
            `<span class="hv-wf-block-label">${esc(label)}</span></span>`
          )
        })
        .join('')
      // The row label sits beside the block track, never inside it, so a squeeze
      // can never hide it: the mock stays readable at any width.
      return (
        `<div class="hv-wf-row" tabindex="0"${riseRow(i)}>` +
        `<span class="hv-wf-label">${esc(cell.label)}</span>` +
        `<span class="hv-wf-blocks">${drawn}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-wireframe">${items}</div>`
}

/** `open:high:low:close`, tolerating a missing close. */
function candleOf(cell) {
  const raw = String(cell.value !== '' ? cell.value : cell.label)
  const parts = raw.split(':').map(num)
  const open = parts[0] || 0
  const high = Math.max(open, parts.length > 1 ? parts[1] : open)
  const low = Math.min(open, parts.length > 2 ? parts[2] : open)
  const close = parts.length > 3 ? parts[3] : open
  return { open, high: Math.max(high, open, close), low: Math.min(low, open, close), close }
}

/** OHLC candles on one shared price scale, the closes joined by a line. */
function renderCandlestick(rows, opts) {
  const marks = dataRows(rows).map(row => ({ cell: cellAt(row, 0), ...candleOf(cellAt(row, 0)) }))
  const hi = Math.max(...marks.map(mark => mark.high), 1)
  const lo = Math.min(...marks.map(mark => mark.low))
  const span = hi - lo || 1
  const H = 48
  const y = value => round(H - ((value - lo) / span) * (H - 2) - 1)
  const step = 100 / Math.max(1, marks.length)
  const bodyW = Math.max(2, step * 0.54)
  const midOf = i => step * (i + 0.5)
  const dirOf = mark => (mark.close >= mark.open ? 'up' : 'down')

  const wicks = marks
    .map((mark, i) => {
      const x = round(midOf(i))
      return (
        `<line class="hv-candle-wick hv-candle-wick--${dirOf(mark)}" ` +
        `x1="${x}" y1="${y(mark.high)}" x2="${x}" y2="${y(mark.low)}"></line>`
      )
    })
    .join('')

  const bodies = marks
    .map((mark, i) => {
      const x = round(midOf(i) - bodyW / 2)
      const yo = y(mark.open)
      const yc = y(mark.close)
      let top = Math.min(yo, yc)
      let bottom = Math.max(yo, yc)
      // A doji is open == close, so the body would vanish. A 1.4-unit floor
      // keeps a visible body centred on the close.
      if (bottom - top < 1.4) {
        const mid = (top + bottom) / 2
        top = mid - 0.7
        bottom = mid + 0.7
      }
      const dir = dirOf(mark)
      return (
        `<rect class="hv-candle hv-candle--${dir}" x="${x}" y="${round(top)}" ` +
        `width="${round(bodyW)}" height="${round(bottom - top)}" rx="0.4">` +
        `<title>${esc(`${mark.cell.label}: o ${mark.open} h ${mark.high} l ${mark.low} c ${mark.close}`)}</title></rect>`
      )
    })
    .join('')

  const closeLine = marks.map((mark, i) => `${round(midOf(i))},${y(mark.close)}`).join(' ')

  const yTicks =
    `<div class="hv-line-y">` +
    `<span class="hv-tick">${round(hi)}${unitSuffix(opts)}</span>` +
    `<span class="hv-tick">${round((lo + hi) / 2)}</span>` +
    `<span class="hv-tick">${round(lo)}</span>` +
    `</div>`

  const xTicks =
    `<div class="hv-line-x">` +
    marks.map(mark => `<span class="hv-tick">${esc(mark.cell.label)}</span>`).join('') +
    `</div>`

  return (
    `<div class="hv hv-candlestick">` +
    `<div class="hv-line-plot">` +
    yTicks +
    `<svg class="hv-svg" viewBox="0 0 100 ${H}" preserveAspectRatio="none" role="img">` +
    `<line class="hv-line-floor" x1="0" y1="${H}" x2="100" y2="${H}"></line>` +
    `<polyline class="hv-candle-close" points="${closeLine}" fill="none"></polyline>` +
    `${wicks}${bodies}` +
    `</svg></div>` +
    xTicks +
    `</div>`
  )
}

/** `records` with FOUR cells — the word, its pronunciation, its meaning, its use.
 *  Rows are `word=[say]=meaning=example` and a row with no `=` is a heading; the
 *  `records` engine wearing the words' classes. No second engine. */
const WORDS_SKIN = {
  root: 'hv-words',
  list: 'hv-word-list',
  item: 'hv-word',
  head: 'hv-words-head',
  flat: true,
  lead: 2,
  leadClass: 'hv-word-lead',
  cells: ['hv-word-w', 'hv-word-say', 'hv-word-meaning', 'hv-word-example'],
  tip: parts => `${parts[0]}: ${parts[2]}`
}

function renderWords(rows) {
  return renderRecords(rows, {}, WORDS_SKIN)
}

/** `h=Ingredient|amount|note;…` -> like `parts`, but a row whose first cell
 *  starts with `!` is a warning, flagged by a glyph as well as by weight — never
 *  by colour alone. */
function renderRecipe(rows) {
  const list = Array.isArray(rows) ? rows.filter(Boolean) : []
  const header = list.find(row => row.header)
  const body = list.filter(row => !row.header)
  const cols = header ? header.cells.length : Math.max(1, ...body.map(row => row.cells.length))
  const isWarn = row => Boolean(row.cells[0] && row.cells[0].label.startsWith('!'))

  const text = (row, cell, i) => {
    if (i === 0 && isWarn(row)) {
      return `<span class="hv-recipe-warn-glyph" aria-hidden="true">${GLYPHS.up}</span>${esc(cell.label.slice(1))}`
    }
    return esc(cellText(cell))
  }

  const head = header
    ? `<thead><tr>${header.cells
        .map((cell, i) => `<th${i === cols - 1 ? ' class="hv-part-qty"' : ''}>${esc(cellText(cell))}</th>`)
        .join('')}</tr></thead>`
    : ''
  const tbody = `<tbody>${body
    .map((row, i) => {
      const warn = isWarn(row)
      return (
        `<tr${warn ? ' class="hv-recipe-warn"' : ''}${riseRow(i)} tabindex="0">` +
        row.cells
          .map((cell, i) => `<td${i === cols - 1 ? ' class="hv-part-qty"' : ''}>${text(row, cell, i)}</td>`)
          .join('') +
        `</tr>`
      )
    })
    .join('')}</tbody>`

  return `<div class="hv hv-table-wrap"><table class="hv-table hv-parts hv-recipe">${head}${tbody}</table></div>`
}

/** `time=stop=detail` -> an itinerary, the `events` shape wearing the route's
 *  classes. Kept as a named kind for travel data. */
function renderRoute(rows) {
  return renderEvents(rows, {}, ROUTE_SKIN)
}

/** Macros against their targets, in the same `of` form `bars` already draws:
 *  the value, its target and the share are named, so this reuses that renderer. */
function renderNutrition(rows, opts) {
  return renderBars(rows, opts, 'hv-nutrition')
}

/** `when=home away=tournament` -> results and fixtures, the `groups` shape with
 *  a score-aware row: a result carries a score, a fixture only a time. */
function matchRow(cell, i) {
  const teams = cell.value || cell.label
  const scored = /\d+\s*[-–]\s*\d+/.test(teams)
  const body = scored
    ? esc(teams).replace(/(\d+)\s*[-–]\s*(\d+)/, '<span class="hv-match-score">$1–$2</span>')
    : esc(teams)
  return (
    `<li class="hv-match hv-match--${scored ? 'result' : 'fixture'}" tabindex="0"${riseRow(i)}${ROW}>` +
    `<span class="hv-match-when">${esc(cell.label)}</span>` +
    `<span class="hv-match-teams">${body}</span>` +
    `</li>`
  )
}

const MATCHES_SKIN = {
  root: 'hv-matches', list: 'hv-match-list', group: 'hv-match-group', row: matchRow
}

function renderMatches(rows) {
  return renderGroups(rows, {}, MATCHES_SKIN)
}

/** One bracket round: `winner>loser,winner>loser`. */
function bracketRound(cell) {
  const pairings = String(cell.value)
    .split(',')
    .map(chunk => String(chunk).trim())
    .filter(Boolean)
    .map(chunk => {
      const at = chunk.indexOf('>')
      if (at < 0) return { winner: clean(chunk), loser: '' }
      return { winner: clean(chunk.slice(0, at)), loser: clean(chunk.slice(at + 1)) }
    })
  return { round: cell.label, pairings }
}

/** `round=winner>loser,winner>loser` -> a knockout bracket: rounds as columns,
 *  winners carried forward. A round that names someone who did not win the
 *  previous round is flagged IN PLACE — the bracket shows what the payload says,
 *  so a contradiction is legible rather than silently redrawn. */
function renderBracket(rows) {
  const rounds = dataRows(rows).map(row => bracketRound(cellAt(row, 0)))

  const columns = rounds
    .map((entry, i) => {
      const earlier = i > 0 ? new Set(rounds[i - 1].pairings.map(pair => pair.winner)) : null
      const bad = []

      const side = (name, role) => {
        if (!name) return ''
        const flagged = earlier ? !earlier.has(name) : false
        if (flagged) bad.push(name)
        return (
          `<span class="hv-bracket-side hv-bracket-${role}${flagged ? ' hv-bracket-bad' : ''}"` +
          `${flagged ? ROW : ''}>${esc(name)}</span>`
        )
      }

      const pairings = entry.pairings
        .map(pair =>
          `<div class="hv-bracket-match">` +
          side(pair.winner, 'win') +
          (pair.loser ? `<span class="hv-bracket-gt" aria-hidden="true">${GLYPHS.next}</span>` : '') +
          side(pair.loser, 'lose') +
          `</div>`
        )
        .join('')

      const flagged = [...new Set(bad)]
      const note = flagged.length
        ? `<div class="hv-bracket-inconsistent"><span class="hv-bracket-flag" aria-hidden="true">${GLYPHS.blocked}</span>` +
          `${esc(flagged.join(', '))} did not win ${esc(rounds[i - 1].round)}</div>`
        : ''

      return (
        `<div class="hv-bracket-round${flagged.length ? ' hv-bracket-round--bad' : ''}" tabindex="0"${riseRow(i)}>` +
        `<div class="hv-bracket-head"><span class="hv-bracket-key ${slot(i)}" aria-hidden="true"></span>` +
        `<span class="hv-bracket-name">${esc(entry.round)}</span></div>` +
        `<div class="hv-bracket-matches">${pairings}</div>` +
        note +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-bracket">${columns}</div>`
}

/** `source=gloss=note` -> interlinear glossing: a source line above its
 *  word-by-word gloss, aligned column by column where the two word counts match.
 *  When they differ the row is shown UNALIGNED — a forced alignment would
 *  misstate the data, which is the one thing this kind exists to avoid. */
function renderGloss(rows) {
  const word = (text, cls) => `<span class="hv-gloss-${cls}">${esc(text)}</span>`

  const items = dataRows(rows)
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const source = cell.label
      const gloss = cell.value
      const flag = cell.extra
      if (!source && !gloss) return ''

      const src = source ? source.split(/\s+/).filter(Boolean) : []
      const gls = gloss ? gloss.split(/\s+/).filter(Boolean) : []
      const noteTag = flag ? `<span class="hv-gloss-note">${esc(flag)}</span>` : ''

      // Same word count -> interlinear columns, source over gloss.
      if (src.length && src.length === gls.length) {
        const columns = src
          .map((text, i) => `<span class="hv-gloss-col">${word(text, 'src')}${word(gls[i], 'word')}</span>`)
          .join('')
        return (
          `<div class="hv-gloss-row" tabindex="0"${riseRow(i)}${ROW}>` +
          `<span class="hv-gloss-aligned">${columns}</span>${noteTag}</div>`
        )
      }

      // Counts differ (or there is no gloss at all): shown unaligned, and the
      // mismatch is named rather than hidden.
      return (
        `<div class="hv-gloss-row hv-gloss-row--unaligned" tabindex="0"${riseRow(i)}${ROW}>` +
        `<span class="hv-gloss-unaligned">${word(source, 'src')}${gloss ? word(gloss, 'word') : ''}</span>` +
        (gloss ? `<span class="hv-gloss-mismatch">${src.length} vs ${gls.length} words</span>` : '') +
        noteTag +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-gloss">${items}</div>`
}

/** `h=person|singular|plural;…` -> a paradigm, drawn as the `grid` shape with the
 *  paradigm's own cell classes. A grid of cells, not a table. */
const FORMS_SKIN = {
  root: 'hv-forms', cell: 'hv-form-cell', head: 'hv-form-head',
  axis: 'hv-form-axis', label: 'hv-form-label'
}

function renderForms(rows) {
  return renderGrid(rows, {}, FORMS_SKIN)
}

/** A staged funnel: `stage=count;…`, kept in payload order. Each bar's length is
 *  its share of the first (widest) stage, and the share LOST between one stage
 *  and the next is named — the drop is the point of the kind, so a funnel that
 *  drew only the bars would have missed it. */
function renderFunnel(rows, opts, root) {
  const unit = opts && opts.unit ? opts.unit : ''
  const stages = dataRows(rows).map(row => {
    const cell = cellAt(row, 0)
    return { cell, value: cellText(cell), n: Math.max(0, num(cell.value !== '' ? cell.value : cell.label)) }
  })
  const base = Math.max(1, stages.length ? stages[0].n : 0)

  const items = []
  stages.forEach((stage, i) => {
    const pct = round(Math.max(0, Math.min(100, (stage.n / base) * 100)))
    const share = Math.round((stage.n / base) * 100)
    items.push(
      `<div class="hv-funnel-stage"${ROW}>` +
      `<span class="hv-funnel-label">${esc(stage.cell.label)}</span>` +
      `<span class="hv-funnel-bar"><span class="hv-funnel-fill ${slot(i)}"${growBar(i, `width:${pct}%`)}></span></span>` +
      `<span class="hv-funnel-meta">` +
      `<span class="hv-funnel-value">${esc(stage.value)}${unitSuffix(opts)}</span>` +
      `<span class="hv-funnel-share">${share}%</span>` +
      `</span></div>`
    )
    if (i < stages.length - 1) {
      const next = stages[i + 1]
      const drop = stage.n - next.n
      const dropPct = stage.n > 0 ? Math.round((drop / stage.n) * 100) : 0
      const gained = drop < 0
      items.push(
        `<div class="hv-funnel-drop"${ROW}>` +
        `<span class="hv-funnel-drop-glyph" aria-hidden="true">${gained ? GLYPHS.up : GLYPHS.down}</span>` +
        `<span class="hv-funnel-drop-text">${gained ? 'gained' : 'lost'} ${Math.abs(round(drop))}${esc(unit)} ` +
        `\u00b7 ${Math.abs(dropPct)}% ${gained ? 'above' : 'of'} ${esc(stage.cell.label)}</span>` +
        `</div>`
      )
    }
  })

  return `<div class="hv ${root || 'hv-funnel'}">${items.join('')}</div>`
}

/** `x=y` points on two axes. Both axes carry a range and ticks, and every point
 *  prints its own coordinate beside it, so the reading never depends on a
 *  hover. */
function renderScatter(rows, opts, root) {
  const unit = opts && opts.unit ? opts.unit : ''
  const numeric = /^\s*[-+]?\d+(?:\.\d+)?\s*$/
  const pts = dataRows(rows).map((row, i) => {
    const cell = cellAt(row, 0)
    const label = cell.label || String(i + 1)
    const y = num(cell.value !== '' ? cell.value : cell.label)
    const x = numeric.test(label) ? num(label) : i + 1
    return { cell, label, x, y }
  })
  const xs = pts.map(p => p.x)
  const ys = pts.map(p => p.y)
  const xLo = Math.min(...xs)
  const xHi = Math.max(...xs)
  const yLo = Math.min(...ys)
  const yHi = Math.max(...ys)
  const xSpan = xHi - xLo || 1
  const ySpan = yHi - yLo || 1

  const yTicks =
    `<div class="hv-line-y">` +
    `<span class="hv-tick">${round(yHi)}${unitSuffix(opts)}</span>` +
    `<span class="hv-tick">${round((yLo + yHi) / 2)}</span>` +
    `<span class="hv-tick">${round(yLo)}</span>` +
    `</div>`

  const marks = pts
    .map((p, i) => {
      const left = round(((p.x - xLo) / xSpan) * 100)
      const top = round(100 - ((p.y - yLo) / ySpan) * 100)
      return (
        `<span class="hv-scatter-dot ${slot(i)}" style="left:${left}%;top:${top}%" ` +
        `title="${esc(`${p.label}: ${p.y}${unit}`)}"></span>` +
        `<span class="hv-scatter-tag" style="left:${left}%;top:${top}%">${esc(p.label)} \u00b7 ${round(p.y)}</span>`
      )
    })
    .join('')

  const xTicks =
    `<div class="hv-line-x">` + pts.map(p => `<span class="hv-tick">${esc(p.label)}</span>`).join('') + `</div>`

  return (
    `<div class="hv ${root || 'hv-scatter'}">` +
    `<div class="hv-line-plot">` +
    yTicks +
    `<span class="hv-scatter-field" role="img">${marks}</span>` +
    `</div>` +
    xTicks +
    `</div>`
  )
}

/** `label=+n|-n` -> a waterfall: each bar steps from the running total, so a
 *  rise and a fall are drawn in OPPOSITE directions and the sign reads with
 *  colour switched off — the direction and the printed sign carry it, never the
 *  hue alone. */
function renderWaterfall(rows, opts) {
  const unit = opts && opts.unit ? opts.unit : ''
  const steps = []
  let level = 0
  for (const row of dataRows(rows)) {
    const cell = cellAt(row, 0)
    const delta = num(cell.value !== '' ? cell.value : cell.label)
    const from = level
    const to = level + delta
    steps.push({ cell, delta, from, to })
    level = to
  }

  const levels = [0, ...steps.map(step => step.from), ...steps.map(step => step.to)]
  const lo = Math.min(...levels)
  const hi = Math.max(...levels)
  const span = hi - lo || 1
  const n = Math.max(1, steps.length)
  const y = value => round(100 - ((value - lo) / span) * 100)

  const bars = steps
    .map((step, i) => {
      const up = step.delta >= 0
      const top = y(Math.max(step.from, step.to))
      const bottom = y(Math.min(step.from, step.to))
      const x = round((100 / n) * i + (100 / n) * 0.16)
      const width = round((100 / n) * 0.68)
      const height = Math.max(0.8, round(bottom - top))
      const detail = `${step.cell.label}: ${up ? '+' : ''}${step.delta} (${round(step.from)} \u2192 ${round(step.to)})`
      return (
        `<rect class="hv-wf-bar hv-wf-bar--${up ? 'up' : 'down'}" x="${x}" y="${top}" ` +
        `width="${width}" height="${height}" rx="0.5">` +
        `<title>${esc(detail)}</title></rect>`
      )
    })
    .join('')

  const links = steps
    .slice(1)
    .map((step, i) => {
      const x1 = round((100 / n) * i + (100 / n) * 0.84)
      const x2 = round((100 / n) * (i + 1) + (100 / n) * 0.16)
      const yy = y(step.from)
      return `<line class="hv-wf-link" x1="${x1}" y1="${yy}" x2="${x2}" y2="${yy}"></line>`
    })
    .join('')

  const plot =
    `<div class="hv-wf-plot">` +
    `<svg class="hv-wf-svg" viewBox="0 0 100 100" preserveAspectRatio="none" role="img">` +
    `<line class="hv-wf-base" x1="0" y1="${y(0)}" x2="100" y2="${y(0)}"></line>` +
    `${links}${bars}` +
    `</svg></div>`

  const ticks = steps
    .map(step => {
      const up = step.delta >= 0
      return (
        `<span class="hv-wf-tick"${ROW}>` +
        `<span class="hv-wf-glyph hv-wf-glyph--${up ? 'up' : 'down'}" aria-hidden="true">${up ? GLYPHS.up : GLYPHS.down}</span>` +
        `<span class="hv-wf-name">${esc(step.cell.label)}</span>` +
        `<span class="hv-wf-delta">${up ? '+' : ''}${step.delta}${esc(unit)}</span>` +
        `</span>`
      )
    })
    .join('')

  return `<div class="hv hv-waterfall">${plot}<div class="hv-wf-x">${ticks}</div></div>`
}

/* ---- the eight shapes ------------------------------------------------------
 * A shape is how data is arranged, not what it is about. Each is a kind, so a
 * rule with no subject kind to name still renders deliberately; each subject
 * kind above is one of these wearing its own class names. ------------------- */

/** `records` — rows of `label=value`, an optional third cell drawn as a secondary
 *  column: the shape for label/value data that has no subject name. A skin names
 *  the cells — `words` is four of them, `nutrition` is this measured. */
function renderRecords(rows, opts, skin) {
  const s = skin || {}
  const cellClass = s.cells || ['hv-rec-label', 'hv-rec-value', 'hv-rec-extra']
  const tip = s.tip || ((parts, cell) => `${cell.label}: ${cellText(cell)}`)

  const items = (Array.isArray(rows) ? rows.filter(Boolean) : [])
    .map((row, i) => {
      const raw = String(row.raw === undefined ? '' : row.raw)
      const cell = cellAt(row, 0)
      if (s.head && !raw.includes('=')) {
        const heading = clean(raw)
        return heading ? `<li class="${s.head}">${esc(heading)}</li>` : ''
      }
      // The shape reads the cell, so a value holding its own `=` is not torn; a
      // skin may split the raw row flat when every `=` is a cell boundary (words).
      const parts = s.flat ? raw.split('=').map(part => clean(part)) : [cell.label, cell.value, cell.extra]
      const spans = parts
        .map((part, i) => (part && cellClass[i] ? `<span class="${cellClass[i]}">${esc(part)}</span>` : ''))
        .filter(Boolean)
      const body =
        s.lead > 0
          ? `<span class="${s.leadClass}">${spans.slice(0, s.lead).join('')}</span>${spans.slice(s.lead).join('')}`
          : spans.join('')
      return `<li class="${s.item || 'hv-rec'}" tabindex="0"${riseRow(i)}${ROW}>${body}</li>`
    })
    .join('')

  return `<div class="hv ${s.root || 'hv-records'}"><ul class="${s.list || 'hv-rec-list'}">${items}</ul></div>`
}

/** `pairs` — `a=b` where both sides are numbers: points on two axes. */
function renderPairs(rows, opts) {
  return renderScatter(rows, opts, 'hv-pairs')
}

/** `series` — one ordered run of numbers: a line, or bars when the rows carry
 *  labels (an unordered category run reads better as bars). */
function renderSeries(rows, opts) {
  const labelled = dataRows(rows).some(row => cellAt(row, 0).value !== '')
  return labelled ? renderBars(rows, opts, 'hv-series') : renderLine(rows, opts)
}

/** `stages` — an ordered run of decreasing counts: a funnel, drop named. */
function renderStages(rows, opts) {
  return renderFunnel(rows, opts, 'hv-stages')
}

/** `steps` — an ordered run carrying done-ness: a checklist. A run with no state
 *  in it is still a run, so it draws as the numbered list rather than as a
 *  checklist of everything-todo. */
function renderStepsShape(rows, opts) {
  const carries = dataRows(rows).some(row => CHECK_STATES[String(cellAt(row, 0).value || '').toLowerCase()])
  return carries ? renderChecklist(rows) : renderSteps(rows, opts)
}

/** `grid` — a header row plus equal-width cells: a matrix, drawn as a CSS grid.
 *  A skin names the cells (`forms` is a paradigm). */
function renderGrid(rows, opts, skin) {
  const s = skin || {}
  const list = Array.isArray(rows) ? rows.filter(Boolean) : []
  const header = list.find(row => row.header)
  const body = list.filter(row => !row.header)
  const cols = Math.max(1, header ? header.cells.length : Math.max(1, ...body.map(row => row.cells.length)))
  const cellClass = s.cell || 'hv-grid-cell'
  const headClass = s.head || 'hv-grid-head'
  const labelClass = s.label || 'hv-grid-label'
  const axisClass = s.axis || 'hv-grid-axis'

  const cells = []
  if (header) {
    header.cells.forEach((cell, i) => {
      cells.push(
        `<span class="${cellClass} ${headClass}${i === 0 ? ` ${axisClass}` : ''}">${esc(cellText(cell))}</span>`
      )
    })
  }
  body.forEach(row => {
    row.cells.forEach((cell, i) => {
      cells.push(`<span class="${cellClass}${i === 0 ? ` ${labelClass}` : ''}">${esc(cellText(cell))}</span>`)
    })
  })

  return (
    `<div class="hv ${s.root || 'hv-matrix'}" style="grid-template-columns:repeat(${cols}, minmax(0, 1fr))">` +
    `${cells.join('')}</div>`
  )
}

/** `groups` — a label that repeats across rows is drawn once as a sub-heading,
 *  its rows under it. A skin supplies the row markup (`matches` scores them). */
function renderGroups(rows, opts, skin) {
  const s = skin || {}
  const items = []
  let group = null
  let rowIndex = 0

  for (const row of dataRows(rows)) {
    const cell = cellAt(row, 0)
    if (cell.extra && cell.extra !== group) {
      group = cell.extra
      items.push(`<li class="${s.group || 'hv-group-head'}">${esc(group)}</li>`)
    }
    items.push(
      s.row
        ? s.row(cell, rowIndex)
        : `<li class="hv-group-row" tabindex="0"${riseRow(rowIndex)}${ROW}>` +
          `<span class="hv-group-label">${esc(cell.label)}</span>` +
          `<span class="hv-group-value">${esc(cell.value || cell.label)}</span>` +
          `</li>`
    )
    rowIndex += 1
  }

  return `<div class="hv ${s.root || 'hv-groups'}"><ul class="${s.list || 'hv-group-list'}">${items.join('')}</ul></div>`
}

/** The header band: a heading over a hairline, an optional palette key beside it.
 *  Level 1 is the answer's own division; level 2 steps one type down and drops the key. */
function renderSection(opts) {
  const title = opts && opts.title ? opts.title : ''
  const lead = opts && opts.lead ? opts.lead : ''
  const level = opts && Number(opts.level) === 2 ? 2 : 1
  if (!title && !lead) return fallback(opts, 'no-rows')

  const band = title
    ? `<div class="hv-section-band">` +
      (level === 1 ? `<span class="hv-section-key ${slot(0)}" aria-hidden="true"></span>` : '') +
      `<span class="hv-section-title">${esc(title)}</span>` +
      `</div>`
    : ''
  const line = lead ? `<p class="hv-section-lead">${esc(lead)}</p>` : ''

  return `<div class="hv hv-section hv-section--l${level}">${band}${line}</div>`
}

/** A board section entry. Canonical form: `section:<heading>;l=<n>` — the heading is the
 *  first non-`l=` cell and an `l=2` cell anywhere sets level 2 (absent -> level 1).
 *  `section:2:<heading>` is accepted as a fallback spelling. */
function boardSection(payload) {
  const raw = String(payload)
  const leveled = raw.match(/^\s*([12])\s*:\s*([\s\S]*)$/)
  const cells = parseRows(leveled ? leveled[2] : raw).map(row => cellAt(row, 0))
  const heading = cells.find(cell => cell.label.toLowerCase() !== 'l')
  const marker = cells.find(cell => cell.label.toLowerCase() === 'l')
  const level = leveled
    ? Number(leveled[1])
    : marker && num(marker.value) === 2
      ? 2
      : 1
  return { level, heading: heading ? heading.label : '' }
}

/**
 * One board entry `kind:payload` -> markup. A malformed entry, an unknown kind
 * or missing rows falls back to prose for that cell alone — never an empty
 * frame, never a broken board. `payload` reuses the `;`/`|`/`=` encoding.
 */
function renderBoardEntry(text, opts) {
  const raw = String(text === undefined || text === null ? '' : text)
  const cut = raw.indexOf(':')
  if (cut < 0) return fallback({ source: raw }, 'malformed-spec')
  const kind = clean(raw.slice(0, cut)).toLowerCase()
  const payload = raw.slice(cut + 1)
  if (kind === 'section') {
    const section = boardSection(payload)
    return section.heading
      ? renderSection({ title: section.heading, level: section.level, source: raw })
      : fallback({ source: raw }, 'malformed-spec')
  }
  const rows = parseRows(payload)
  return renderKind(kind, rows, {
    unit: opts && opts.unit,
    palette: opts && opts.palette,
    source: raw
  })
}

/** The board column count follows the entry count: 1, 2 or 3, chosen so the last
 *  row is never a lone orphan where a smaller count would have balanced it. It is
 *  the COUNT that is chosen, never a width — the tracks stay `auto-fit`. */
function boardColumns(count) {
  const n = Number.isFinite(count) ? Math.max(0, Math.trunc(count)) : 0
  const top = Math.min(3, n)
  for (let cols = top; cols > 1; cols--) if (n % cols !== 1) return cols
  return 1
}

/** A board: `~`-separated widget entries laid out by the pane's own grid. */
function renderBoard(specs, opts) {
  const entries = Array.isArray(specs) ? specs : []
  // Each entry is one column: its markup is wrapped so a multi-tile kind (kpi) stays one widget.
  const cells = entries
    .map(entry => `<div class="hv hv-grid">${renderBoardEntry(entry, opts)}</div>`)
    .join('')
  if (!cells) return fallback(opts, 'no-rows')
  return `<div class="hv hv-grid hv-board" style="--hv-cols:${boardColumns(entries.length)}">${cells}</div>`
}

/** Split a board `d` payload into its `~`-separated entries. */
function boardEntries(payload) {
  const raw = typeof payload === 'string' ? payload : ''
  return raw.split('~').filter(entry => entry.trim())
}

/**
 * `kind` + parsed `rows` -> markup. Unknown kind, no rows, or a kind that needs
 * data it does not have returns the prose fallback, never an empty frame.
 * `board` receives its `~`-separated entry strings and lays them out in a grid.
 */
function renderKind(kind, rows, opts) {
  const k = clean(kind).toLowerCase()
  if (k === 'board') return renderBoard(rows, opts)

  const list = Array.isArray(rows) ? rows.filter(Boolean) : []
  const data = dataRows(list)

  if (!KINDS.includes(k)) return fallback(opts, 'unknown-kind')

  // A section needs no rows: its heading comes from `t`, its lead line from `d`.
  if (k === 'section') {
    const lead = (opts && opts.lead) || (data[0] ? cellText(cellAt(data[0], 0)) : '')
    const title = opts && opts.title ? opts.title : ''
    return title || lead
      ? renderSection({ title, lead, level: opts && opts.level, source: opts && opts.source })
      : fallback(opts, 'no-rows')
  }

  if (list.length === 0) return fallback(opts, 'no-rows')
  if (k !== 'table' && k !== 'parts' && data.length === 0) return fallback(opts, 'no-rows')

  switch (k) {
    case 'kpi':
      return renderKpi(list, opts)
    case 'bars':
      return renderBars(list, opts)
    case 'line':
      return renderLine(list, opts)
    case 'donut':
      return renderDonut(list, opts)
    case 'steps':
      return renderStepsShape(list, opts)
    case 'table':
      return renderTable(list, opts)
    case 'progress':
      return renderProgress(list, opts)
    case 'checklist':
      return renderChecklist(list, opts)
    case 'changes':
      return renderChanges(list, opts)
    case 'outline':
      return renderOutline(list, opts)
    case 'facts':
      return renderFacts(list, opts)
    case 'files':
      return renderFiles(list, opts)
    case 'parts':
      return renderParts(list, opts)
    case 'settings':
      return renderSettings(list, opts)
    case 'timeline':
      return renderTimeline(list, opts)
    case 'ranges':
      return renderRanges(list, opts)
    case 'metrics':
      return renderMetrics(list, opts)
    case 'array':
      return renderArray(list, opts)
    case 'heatmap':
      return renderHeatmap(list, opts)
    case 'wireframe':
      return renderWireframe(list, opts)
    case 'candlestick':
      return renderCandlestick(list, opts)
    case 'words':
      return renderWords(list, opts)
    case 'recipe':
      return renderRecipe(list, opts)
    case 'route':
      return renderRoute(list, opts)
    case 'nutrition':
      return renderNutrition(list, opts)
    case 'matches':
      return renderMatches(list, opts)
    case 'bracket':
      return renderBracket(list, opts)
    case 'gloss':
      return renderGloss(list, opts)
    case 'forms':
      return renderForms(list, opts)
    case 'funnel':
      return renderFunnel(list, opts)
    case 'scatter':
      return renderScatter(list, opts)
    case 'waterfall':
      return renderWaterfall(list, opts)
    case 'records':
      return renderRecords(list, opts)
    case 'pairs':
      return renderPairs(list, opts)
    case 'series':
      return renderSeries(list, opts)
    case 'stages':
      return renderStages(list, opts)
    case 'grid':
      return renderGrid(list, opts)
    case 'groups':
      return renderGroups(list, opts)
    case 'events':
      return renderEvents(list, opts)
    default:
      return renderSparkline(list, opts)
  }
}

/** Attrs -> the whole widget: caption, then one grid holding the kind's cells. */
function renderWidget(attrs) {
  const spec = parseSpec(attrs)
  const opts = { unit: spec.unit, source: attrs && typeof attrs.source === 'string' ? attrs.source : '' }
  // A section carries its own heading band, so it never gets the title too. The caption
  // carries ONE slot, and only when the answer asked for a hover note (`n=`) — an empty
  // caption span is chrome, and a label nobody asked for is worse. The core declares the
  // slot, the mount owns the behaviour, and the widget is complete without it.
  const body0 =
    spec.kind === 'board'
      ? renderKind('board', boardEntries(attrs && attrs.d), opts)
      : spec.kind === 'section'
        ? renderSection({ title: spec.title, lead: clean(attrs && attrs.d), level: spec.level, source: opts.source })
        : renderKind(spec.kind, spec.rows, opts)
  const slot = spec.note ? '<span class="hv-note" data-hv-note-slot></span>' : ''
  const caption =
    spec.title && spec.kind !== 'section'
      ? `<div class="hv-title"><span class="hv-title-text">${esc(spec.title)}</span>${slot}</div>`
      : `<div class="hv-caption">${slot}</div>`
  const inner = body0

  // A board IS the grid that spans the pane — its cells are the measured parts.
  // Every other kind is one widget whose content the measure caps.
  const body = spec.kind === 'board' ? inner : `<div class="hv-grid">${inner}</div>`

  return (
    `<div class="hv hv-widget"${noteAttr(spec.note)} data-kind="${esc(spec.kind || 'unknown')}">` +
    `${caption}${body}` +
    `</div>`
  )
}

/**
 * The widget stylesheet.
 *
 * SURFACE is themed by the five tokens the app defines — no literal colour and
 * no cap of any kind on the widget's own box. DATA is painted by the palette:
 * six hues declared once at the top, in `.hv-widget`, and nowhere else.
 * `--hv-1` IS `--dt-primary`, so a one-series widget still reads as the accent;
 * the other five sit beside it on the near-black surface. Colour ranks and
 * separates — every coloured element keeps its label or value, so colour never
 * carries meaning alone.
 *
 * WIDTH: the widget fills its grid cell and reflows, but its CONTENT is capped
 * by `--hv-measure` (42rem) and CENTRED — the earlier "no max-width anywhere"
 * test was overridden by the user, who asked for a table sized by content
 * instead of stretched, with the leftover split evenly. This is the standalone
 * cap (the fixture, any host without the body style); inside the app the mount
 * carries the answer's own measure, so a widget is exactly as wide as the prose
 * around it and the two numbers never have to agree. One pad, on all four sides
 * (`--hv-pad`). Nothing may touch the widget's own edge.
 *
 * Motion is a short staggered rise and a bar grow that reveals the data — all
 * of it removed under `prefers-reduced-motion`.
 */
const CSS = `
.hv-widget {
  /* The palette — six hues, declared once here and nowhere else. */
  --hv-1: var(--dt-primary);
  --hv-2: #5b9bd5;
  --hv-3: #57b284;
  --hv-4: #e0b64a;
  --hv-5: #a97ad9;
  --hv-6: #e0708f;
  /* The measure caps the content; the widget itself is never capped. */
  --hv-measure: 42rem;
  /* The board's column count: overridden inline per board, this is the default. */
  --hv-cols: 3;
  /* ONE pad, the same on all four sides, and it follows the WIDGET's own width:
     2.4% of it, capped at 1rem. A narrow pane gets a smaller gutter and a wide
     one never grows a slab of margin. A media query would read the window
     instead, and the pane is what the reader actually widened. */
  --hv-pad: min(1rem, 2.4%);
  color: var(--foreground);
  font-size: 0.8125rem;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
  padding: var(--hv-pad);
}
.hv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: 0.6rem; max-width: var(--hv-measure); margin-inline: auto; }
/* One vertical rhythm between board entries — clearly wider than the ~0.6rem
 * gap inside a widget, so several kinds read as one composed thing instead of a
 * single undifferentiated stack. Entries keep their own height (align-items:start).
 * The measure is untouched; the column count follows the entry count. */
/* The count is the chosen part: each track is at least (pane - gaps) / --hv-cols,
 * so at most that many columns fit, while the 24rem floor keeps the pane's own
 * reflow. The gaps are subtracted so the last column is not pushed off by them.
 * No width is ever chosen. */
.hv-board { grid-template-columns: repeat(auto-fit, minmax(max(24rem, calc((100% - (var(--hv-cols) - 1) * 0.75rem) / var(--hv-cols))), 1fr)); gap: 0.75rem; row-gap: 1.4rem; align-items: start; max-width: none; }
.hv-title { display: flex; align-items: baseline; gap: 0.5rem; margin: 0 auto 0.6rem; max-width: var(--hv-measure); color: var(--color-muted-foreground); font-size: 0.8125rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-caption { display: flex; margin: 0 auto; max-width: var(--hv-measure); }
/* The answer's own hover note, revealed by the mount. Never a derived label:
 * it is empty until the answer asked for one, and collapses to nothing while it is. */
.hv-note { margin-left: auto; color: var(--foreground); font-size: 0.75rem; font-weight: 600; letter-spacing: normal; text-transform: none; font-variant-numeric: tabular-nums; }
.hv-note:empty { display: none; }
.hv-prose { margin: 0; color: var(--color-muted-foreground); font-style: italic; }
.hv-unit { margin-left: 0.12em; color: var(--color-muted-foreground); font-size: 0.72em; font-weight: 500; }
.hv-kpi-tile { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; padding: 0.7rem 0.8rem; border: 1px solid var(--dt-border); border-radius: 0.6rem; box-shadow: inset 0 1px 0 color-mix(in srgb, var(--foreground) 7%, transparent); }
.hv-kpi-label { color: var(--color-muted-foreground); font-size: 0.6875rem; letter-spacing: 0.04em; }
.hv-kpi-value { color: var(--foreground); font-size: 1.625rem; font-weight: 650; letter-spacing: -0.02em; line-height: 1.05; }
.hv-kpi-delta { align-self: flex-start; padding: 0.08rem 0.4rem; border-radius: 999px; color: var(--color-muted-foreground); background: color-mix(in srgb, var(--color-muted-foreground) 12%, transparent); font-size: 0.6875rem; font-weight: 600; }
.hv-kpi-delta--up { color: var(--hv-3); background: color-mix(in srgb, var(--hv-3) 15%, transparent); }
.hv-kpi-delta--down { color: var(--hv-6); background: color-mix(in srgb, var(--hv-6) 15%, transparent); }
.hv-bars, .hv-progress, .hv-changes, .hv-ranges, .hv-nutrition { display: flex; flex-direction: column; gap: 0.45rem; }
.hv-row, .hv-prog { display: flex; align-items: center; gap: 0.6rem; min-width: 0; }
.hv-row-label, .hv-prog-label { flex: 0 0 auto; min-width: 5rem; color: var(--color-muted-foreground); font-size: 0.75rem; font-weight: 500; }
.hv-bar, .hv-track { position: relative; flex: 1 1 auto; min-width: 0; height: 0.5rem; border-radius: 999px; background: var(--dt-muted); overflow: hidden; }
.hv-bar-fill, .hv-fill { display: block; height: 100%; border-radius: 999px; background: var(--dt-primary); box-shadow: inset 0 1px 0 color-mix(in srgb, var(--foreground) 22%, transparent); transform-origin: left center; }
.hv-row-meta { display: flex; flex: 0 0 auto; align-items: baseline; justify-content: flex-end; gap: 0.4rem; min-width: 5rem; }
.hv-row-value, .hv-prog-value { flex: 0 0 auto; color: var(--foreground); font-weight: 600; }
.hv-row-target { flex: 0 0 auto; color: var(--color-muted-foreground); font-size: 0.6875rem; }
.hv-row-share { min-width: 2.4rem; color: var(--color-muted-foreground); font-size: 0.6875rem; text-align: right; }
.hv-axis { display: flex; align-items: baseline; gap: 0.6rem; margin-top: 0.3rem; }
.hv-axis-pad { flex: 0 0 auto; min-width: 5rem; }
.hv-axis-scale { flex: 1 1 auto; display: flex; justify-content: space-between; gap: 0.5rem; }
.hv-tick { color: var(--color-muted-foreground); font-size: 0.625rem; letter-spacing: 0.08em; }
.hv-axis-lo { text-align: left; }
.hv-axis-hi { color: var(--foreground); }
.hv-line { display: flex; flex-direction: column; }
.hv-line-plot { display: flex; align-items: stretch; gap: 0.5rem; }
.hv-line-y { display: flex; flex: 0 0 auto; flex-direction: column; justify-content: space-between; min-width: 2.4rem; text-align: right; }
.hv-line-x { display: flex; justify-content: space-between; gap: 0.5rem; margin-top: 0.3rem; }
.hv-line .hv-svg { flex: 1 1 auto; }
.hv-svg { display: block; width: 100%; }
.hv-line .hv-svg { height: 4.5rem; }
.hv-sparkline .hv-svg { height: 2.25rem; }
.hv-spark-meta { display: flex; justify-content: space-between; margin-top: 0.25rem; }
.hv-line-area, .hv-spark-area { stroke: none; fill: color-mix(in srgb, var(--hv-1) 26%, transparent); }
.hv-line-floor { stroke: var(--dt-border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.hv-line-point { stroke: var(--color-muted-foreground); stroke-width: 1; vector-effect: non-scaling-stroke; }
.hv-line-path, .hv-spark-path { stroke: var(--hv-1); stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.hv-line-path { stroke-width: 1.75; }
.hv-spark-path { stroke-width: 1.75; }
.hv-spark-base { stroke: var(--dt-border); stroke-width: 1; stroke-dasharray: 2 2; vector-effect: non-scaling-stroke; }
.hv-donut { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.hv-donut-svg { flex: 0 0 auto; width: 5rem; height: 5rem; }
.hv-donut-track { stroke: var(--dt-muted); stroke-width: 3.6; }
.hv-donut-seg { stroke-width: 3.6; }
.hv-donut-center { fill: var(--foreground); stroke: none; font-size: 5.4px; font-weight: 650; text-anchor: middle; dominant-baseline: central; }
.hv-legend { display: flex; flex: 1 1 10rem; flex-direction: column; gap: 0.35rem; min-width: 0; }
.hv-legend-item { display: flex; align-items: center; gap: 0.5rem; color: var(--color-muted-foreground); }
.hv-legend-dot { flex: 0 0 auto; width: 0.55rem; height: 0.55rem; border-radius: 3px; background: var(--dt-primary); }
.hv-legend-key { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hv-legend-val { margin-left: auto; color: var(--foreground); font-weight: 600; }
.hv-legend-share { flex: 0 0 auto; min-width: 2.4rem; color: var(--color-muted-foreground); font-size: 0.6875rem; text-align: right; }
.hv-step-list, .hv-check-list, .hv-outline-list, .hv-tl-list { display: flex; flex-direction: column; gap: 0.55rem; margin: 0; padding: 0; list-style: none; }
.hv-step { position: relative; display: flex; align-items: flex-start; gap: 0.65rem; }
.hv-step:not(:last-child)::after { content: ''; position: absolute; left: 0.78rem; top: 1.7rem; bottom: -0.55rem; width: 1px; background: var(--dt-border); }
.hv-step-n { position: relative; z-index: 1; flex: 0 0 auto; width: 1.55rem; height: 1.55rem; border: 1px solid var(--dt-border); border-radius: 50%; color: var(--foreground); background: var(--dt-muted); font-size: 0.6875rem; font-weight: 600; line-height: 1.55rem; text-align: center; }
.hv-step-t { flex: 1 1 auto; min-width: 0; padding-top: 0.2rem; }
.hv-table-wrap { overflow-x: auto; }
.hv-table { border-collapse: collapse; }
.hv-table th, .hv-table td { padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--dt-border); text-align: left; }
.hv-table th:not(:first-child), .hv-table td:not(:first-child) { text-align: right; }
.hv-table th { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-table td { color: var(--color-muted-foreground); }
.hv-table td:first-child { color: var(--foreground); font-weight: 550; }
.hv-table tbody tr:last-child td { border-bottom: none; }
.hv-parts .hv-part-qty { text-align: right; color: var(--foreground); font-weight: 600; }
.hv-section { display: flex; flex-direction: column; gap: 0.5rem; max-width: var(--hv-measure); margin-inline: auto; }
/* No rule of its own: hierarchy is carried by type size and weight alone, which
 * the tests assert with colour off. Level 1 keeps its muted key dot; nothing else. */
.hv-section-band { display: flex; align-items: center; gap: 0.6rem; }
.hv-section-key { flex: 0 0 auto; width: 0.5rem; height: 0.5rem; border-radius: 3px; }
.hv-section-title { color: var(--foreground); font-size: 1.25rem; font-weight: 700; letter-spacing: -0.015em; }
/* Level 2: one step down in type and weight, no palette key, and still no rule. */
.hv-section--l2 .hv-section-title { font-size: 0.9375rem; font-weight: 600; letter-spacing: 0; }
.hv-section-lead { margin: 0; color: var(--color-muted-foreground); }
.hv-check { display: flex; align-items: baseline; gap: 0.6rem; }
.hv-check-glyph { flex: 0 0 auto; width: 1.1rem; color: var(--hv-3); text-align: center; }
.hv-check--todo .hv-check-glyph { color: var(--color-muted-foreground); }
.hv-check--doing .hv-check-glyph { color: var(--hv-4); }
.hv-check--blocked .hv-check-glyph { color: var(--hv-6); }
.hv-check--done .hv-check-label { color: var(--color-muted-foreground); text-decoration: line-through; }
.hv-check-label { min-width: 0; }
.hv-change { display: flex; align-items: baseline; gap: 0.55rem; width: 100%; padding: 0; border: 0; background: none; font: inherit; color: inherit; text-align: left; cursor: pointer; }
.hv-change-glyph { flex: 0 0 auto; width: 1.1rem; color: var(--hv-2); text-align: center; }
.hv-change-name { min-width: 0; overflow-wrap: anywhere; }
.hv-change-counts { display: flex; flex: 0 0 auto; margin-left: auto; gap: 0.5rem; font-variant-numeric: tabular-nums; }
.hv-add { color: var(--hv-3); font-weight: 600; }
.hv-del { color: var(--hv-6); font-weight: 600; }
.hv-change-total { display: flex; align-items: baseline; gap: 0.6rem; padding-top: 0.35rem; border-top: 1px solid var(--dt-border); }
.hv-change-total-label { margin-right: auto; color: var(--color-muted-foreground); }
.hv-outline-item { display: flex; gap: 0.6rem; }
.hv-outline-num { flex: 0 0 auto; min-width: 2.2rem; color: var(--color-muted-foreground); font-variant-numeric: tabular-nums; }
.hv-outline-t { min-width: 0; color: var(--foreground); }
.hv-facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 0.6rem; }
.hv-fact { display: flex; flex-direction: column; gap: 0.15rem; min-width: 0; }
.hv-fact-label { color: var(--color-muted-foreground); font-size: 0.6875rem; letter-spacing: 0.04em; }
.hv-fact-value { color: var(--foreground); font-weight: 600; overflow-wrap: anywhere; }
.hv-files { display: flex; flex-direction: column; gap: 0.35rem; }
.hv-file { display: flex; align-items: baseline; gap: 0.55rem; }
.hv-file-glyph { flex: 0 0 auto; color: var(--hv-2); }
.hv-file-path { min-width: 0; overflow-wrap: anywhere; }
.hv-file-meta { margin-left: auto; color: var(--color-muted-foreground); font-size: 0.6875rem; }

/* A reference the core draws inside a widget (a URL cell, a file path). It is a
   button only so it can be activated by keyboard too — the chrome comes off, the
   text stays the text. The host's ref rules give it the kind's colour, the
   glyph's spacing and the hover underline; the numbers below repeat the host's
   own glyph metrics so a page without the host's stylesheet (the fixture) draws
   the same thing. Colour is never set here. */
.hv .hv-ref {
  padding: 0;
  border: 0;
  background: none;
  font: inherit;
  text-align: inherit;
  cursor: pointer;
}
.hv .hv-ref > svg {
  display: inline-block;
  width: 0.875em;
  height: 0.875em;
  vertical-align: -0.1em;
  margin-inline-end: 0.25em;
  opacity: 0.8;
}
.hv-settings { display: flex; flex-direction: column; gap: 0.4rem; }
.hv-setting { display: flex; align-items: center; gap: 0.6rem; }
.hv-setting-label { min-width: 0; }
.hv-pill { margin-left: auto; padding: 0.1rem 0.55rem; border: 1px solid var(--dt-border); border-radius: 999px; color: var(--color-muted-foreground); font-size: 0.6875rem; font-weight: 600; }
.hv-pill--on { color: var(--hv-3); border-color: var(--hv-3); }
.hv-tl-item { position: relative; display: flex; gap: 0.7rem; }
.hv-tl-item::before { content: ''; position: absolute; left: 0.3rem; top: 0.9rem; bottom: -0.55rem; width: 1px; background: var(--dt-border); }
.hv-tl-item:last-child::before { display: none; }
.hv-tl-item::after { content: ''; position: absolute; left: 0; top: 0.3rem; width: 0.6rem; height: 0.6rem; border-radius: 50%; background: var(--hv-1); }
.hv-tl-when { flex: 0 0 auto; min-width: 4rem; padding-left: 1.1rem; color: var(--color-muted-foreground); font-size: 0.75rem; }
.hv-tl-body { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
.hv-tl-label { color: var(--foreground); font-weight: 550; }
.hv-tl-detail { color: var(--color-muted-foreground); }
.hv-range-track { position: relative; }
.hv-range-span { position: absolute; top: 0; display: block; height: 100%; border-radius: 999px; }
.hv-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr)); gap: 0.7rem; }
.hv-metric { display: flex; flex-direction: column; gap: 0.2rem; min-width: 0; }
.hv-metric-caption { color: var(--color-muted-foreground); font-size: 0.6875rem; letter-spacing: 0.04em; }
.hv-metric-value { color: var(--foreground); font-size: 1.25rem; font-weight: 650; letter-spacing: -0.01em; }
.hv-metric-foot { display: flex; align-items: center; gap: 0.5rem; min-width: 0; }
.hv-metric-scale { position: relative; display: block; flex: 1 1 auto; min-width: 0; height: 0.3rem; border-radius: 999px; background: var(--dt-muted); overflow: hidden; }
.hv-metric-scale-fill { display: block; height: 100%; border-radius: 999px; background: var(--hv-3); transform-origin: left center; }
.hv-metric-scale-fill--down { background: var(--hv-6); }
.hv-metric-delta { flex: 0 0 auto; align-self: center; color: var(--hv-3); font-size: 0.6875rem; font-weight: 600; }
.hv-metric-delta.hv-kpi-delta--down { color: var(--hv-6); }
.hv-metric-target { flex: 0 0 auto; color: var(--color-muted-foreground); font-size: 0.6875rem; }
.hv-metric-share { flex: 0 0 auto; margin-left: auto; color: var(--foreground); font-size: 0.6875rem; font-weight: 600; }
.hv-array { display: grid; border: 1px solid var(--dt-border); border-radius: 0.5rem; overflow: hidden; }
.hv-cell { min-width: 0; padding: 0.35rem 0.6rem; border-right: 1px solid var(--dt-border); border-bottom: 1px solid var(--dt-border); overflow-wrap: anywhere; }
.hv-heatmap { display: grid; grid-template-columns: repeat(auto-fit, minmax(6rem, 1fr)); gap: 0.35rem; }
.hv-heat-cell { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; padding: 0.4rem 0.55rem; border: 1px solid var(--dt-border); border-radius: 0.4rem; }
.hv-heat-label { color: var(--color-muted-foreground); font-size: 0.6875rem; }
.hv-heat-value { color: var(--foreground); font-weight: 600; }
.hv-ramp { grid-column: 1 / -1; display: flex; align-items: center; gap: 0.5rem; margin-top: 0.2rem; }
.hv-ramp-bar { flex: 1 1 auto; height: 0.4rem; border-radius: 999px; background: linear-gradient(to right, color-mix(in srgb, var(--hv-1) 12%, var(--dt-muted)), var(--hv-1)); }
.hv-wireframe { display: flex; flex-direction: column; gap: 0.5rem; }
.hv-wf-row { display: flex; align-items: center; gap: 0.7rem; min-width: 0; }
/* The row label lives outside the block track: a squeeze can never hide it. */
.hv-wf-label { flex: 0 0 auto; min-width: 4.5rem; color: var(--color-muted-foreground); font-size: 0.75rem; font-weight: 500; overflow-wrap: anywhere; }
.hv-wf-blocks { display: flex; flex: 1 1 auto; min-width: 0; gap: 0.35rem; height: 1.8rem; }
.hv-wf-block { display: flex; align-items: center; justify-content: center; flex-basis: 0; min-width: 0; border: 1px solid var(--dt-border); border-radius: 0.35rem; overflow: hidden; transform-origin: left center; }
.hv-wf-block-label { padding: 0 0.4rem; color: var(--foreground); font-size: 0.625rem; letter-spacing: 0.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hv-wf-block--text { border-style: dashed; }
.hv-wf-block--btn { border-color: var(--color-muted-foreground); }
.hv-wf-block--img { box-shadow: inset 0 0 0 3px color-mix(in srgb, var(--foreground) 14%, transparent); }
.hv-wf-block--circle { border-radius: 999px; }
.hv-candlestick { display: flex; flex-direction: column; }
.hv-candlestick .hv-svg { height: 4.5rem; }
.hv-candle { stroke-width: 0.5; vector-effect: non-scaling-stroke; }
.hv-candle--up { fill: var(--hv-3); stroke: var(--hv-3); }
.hv-candle--down { fill: var(--hv-6); stroke: var(--hv-6); }
.hv-candle-wick { stroke-width: 1; vector-effect: non-scaling-stroke; }
.hv-candle-wick--up { stroke: var(--hv-3); }
.hv-candle-wick--down { stroke: var(--hv-6); }
.hv-candle-close { stroke: var(--hv-1); stroke-width: 1.5; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
/* Round 5: the five subject kinds. Surface tokens for structure, the palette for
 * data only — no rule, no background, nothing that carries meaning by colour alone. */
.hv-word-list, .hv-route-list, .hv-match-list { display: flex; flex-direction: column; gap: 0.5rem; margin: 0; padding: 0; list-style: none; }
.hv-words-head { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-word { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
.hv-word-lead { display: flex; align-items: baseline; gap: 0.5rem; min-width: 0; overflow-wrap: anywhere; }
.hv-word-w { color: var(--foreground); font-weight: 650; }
.hv-word-say { color: var(--hv-2); font-size: 0.75rem; }
.hv-word-meaning { color: var(--foreground); overflow-wrap: anywhere; }
.hv-word-example { color: var(--color-muted-foreground); font-style: italic; overflow-wrap: anywhere; }
.hv-recipe-warn td { color: var(--foreground); font-weight: 600; font-style: italic; }
.hv-recipe-warn-glyph { margin-right: 0.4rem; }
.hv-route-stop { position: relative; display: flex; gap: 0.7rem; }
.hv-route-stop::before { content: ''; position: absolute; left: 0.3rem; top: 0.9rem; bottom: -0.55rem; width: 1px; background: var(--dt-border); }
.hv-route-stop:last-child::before { display: none; }
.hv-route-stop::after { content: ''; position: absolute; left: 0; top: 0.3rem; width: 0.6rem; height: 0.6rem; border-radius: 50%; background: var(--hv-1); }
.hv-route-time { flex: 0 0 auto; min-width: 3.6rem; padding-left: 1.1rem; color: var(--color-muted-foreground); font-size: 0.75rem; font-variant-numeric: tabular-nums; }
.hv-route-body { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
.hv-route-place { color: var(--foreground); font-weight: 550; }
.hv-route-detail { color: var(--color-muted-foreground); }
.hv-match { display: flex; align-items: baseline; gap: 0.7rem; min-width: 0; }
.hv-match-when { flex: 0 0 auto; min-width: 3.6rem; color: var(--color-muted-foreground); font-size: 0.75rem; font-variant-numeric: tabular-nums; }
.hv-match-teams { min-width: 0; overflow-wrap: anywhere; }
.hv-match--result .hv-match-teams { color: var(--foreground); }
.hv-match-score { color: var(--foreground); font-weight: 700; }
.hv-match--fixture .hv-match-teams { color: var(--color-muted-foreground); }
.hv-match-group { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
/* Round 6: bracket, gloss, forms — the last three. Surface tokens carry the
 * structure and the palette only ranks a round and flags a contradiction; no
 * rule of its own anywhere, so no new decorative separator is introduced. */
.hv-bracket { display: flex; align-items: stretch; gap: 0.9rem; }
.hv-bracket-round { display: flex; flex: 1 1 0; flex-direction: column; gap: 0.5rem; min-width: 0; }
.hv-bracket-head { display: flex; align-items: center; gap: 0.45rem; }
.hv-bracket-key { flex: 0 0 auto; width: 0.5rem; height: 0.5rem; border-radius: 3px; }
.hv-bracket-name { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-bracket-matches { display: flex; flex: 1 1 auto; flex-direction: column; justify-content: space-around; gap: 0.45rem; }
.hv-bracket-match { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0.35rem; min-width: 0; }
.hv-bracket-side { min-width: 0; overflow-wrap: anywhere; }
.hv-bracket-win { color: var(--foreground); font-weight: 650; }
.hv-bracket-lose { color: var(--color-muted-foreground); }
.hv-bracket-gt { color: var(--color-muted-foreground); }
/* A participant who did not win the previous round: colour ranks it, but the
 * wavy underline and the note below carry the meaning without it. */
.hv-bracket-bad { color: var(--hv-6); text-decoration: underline wavy; }
.hv-bracket-inconsistent { display: flex; align-items: baseline; gap: 0.3rem; color: var(--hv-6); font-size: 0.6875rem; }
.hv-bracket-flag { font-weight: 700; }
.hv-gloss { display: flex; flex-direction: column; gap: 0.7rem; }
.hv-gloss-row { display: flex; align-items: baseline; gap: 0.7rem; min-width: 0; }
.hv-gloss-aligned { display: flex; flex: 1 1 auto; flex-wrap: wrap; gap: 0.35rem 0.9rem; min-width: 0; }
.hv-gloss-col { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 0.05rem; min-width: 0; }
.hv-gloss-src { color: var(--foreground); font-weight: 550; }
.hv-gloss-word { color: var(--color-muted-foreground); }
.hv-gloss-unaligned { display: flex; flex: 1 1 auto; flex-direction: column; gap: 0.05rem; min-width: 0; }
.hv-gloss-mismatch { flex: 0 0 auto; color: var(--color-muted-foreground); font-size: 0.6875rem; font-style: italic; }
.hv-gloss-note { flex: 0 0 auto; margin-left: auto; color: var(--color-muted-foreground); font-size: 0.6875rem; letter-spacing: 0.04em; }
.hv-forms { display: grid; border: 1px solid var(--dt-border); border-radius: 0.5rem; overflow: hidden; }
.hv-form-cell { min-width: 0; padding: 0.35rem 0.6rem; border-right: 1px solid var(--dt-border); border-bottom: 1px solid var(--dt-border); overflow-wrap: anywhere; }
.hv-form-head { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-form-axis { color: var(--color-muted-foreground); }
.hv-form-label { color: var(--foreground); font-weight: 550; }
/* The shape kinds, when no subject names the data. The same pieces the subject
 * skins use, under generic names, so unfamiliar rows read deliberately rather
 * than degrading to prose. */
.hv-rec-list, .hv-group-list { display: flex; flex-direction: column; gap: 0.3rem; }
.hv-rec { display: flex; align-items: baseline; gap: 0.6rem; min-width: 0; }
.hv-rec-label { flex: 0 0 auto; min-width: 5rem; color: var(--color-muted-foreground); }
.hv-rec-value { color: var(--foreground); font-weight: 550; }
.hv-rec-extra { margin-left: auto; color: var(--color-muted-foreground); font-size: 0.75rem; text-align: right; }
.hv-matrix { display: grid; border: 1px solid var(--dt-border); border-radius: 0.5rem; overflow: hidden; }
.hv-grid-cell { min-width: 0; padding: 0.35rem 0.6rem; border-right: 1px solid var(--dt-border); border-bottom: 1px solid var(--dt-border); overflow-wrap: anywhere; }
.hv-grid-head { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-grid-axis { color: var(--color-muted-foreground); }
.hv-grid-label { color: var(--foreground); font-weight: 550; }
.hv-group-head { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-group-row { display: flex; align-items: baseline; gap: 0.7rem; min-width: 0; }
.hv-group-label { flex: 0 0 auto; min-width: 5rem; color: var(--color-muted-foreground); }
.hv-group-value { min-width: 0; overflow-wrap: anywhere; color: var(--foreground); }
.hv-pairs { display: flex; flex-direction: column; }
.hv-stages { display: flex; flex-direction: column; gap: 0.3rem; }
/* Round 7: funnel, scatter, waterfall. Same surface tokens for structure, the
 * palette only ranks; every colour keeps its label or value, so colour never
 * carries meaning alone. The waterfall's SIGN is the direction of the bar plus
 * the printed sign — the hue never has to be read. */
.hv-funnel { display: flex; flex-direction: column; gap: 0.3rem; }
.hv-funnel-stage { display: flex; align-items: center; gap: 0.6rem; min-width: 0; }
.hv-funnel-label { flex: 0 0 auto; min-width: 5rem; color: var(--color-muted-foreground); font-size: 0.75rem; font-weight: 500; }
.hv-funnel-bar { position: relative; flex: 1 1 auto; min-width: 0; height: 0.7rem; border-radius: 0.2rem; background: var(--dt-muted); overflow: hidden; }
.hv-funnel-fill { display: block; height: 100%; border-radius: 0.2rem; transform-origin: left center; }
.hv-funnel-meta { display: flex; flex: 0 0 auto; align-items: baseline; justify-content: flex-end; gap: 0.4rem; min-width: 6rem; }
.hv-funnel-value { color: var(--foreground); font-weight: 600; }
.hv-funnel-share { min-width: 2.4rem; color: var(--color-muted-foreground); font-size: 0.6875rem; text-align: right; }
.hv-funnel-drop { display: flex; align-items: baseline; gap: 0.4rem; padding-left: 5.6rem; color: var(--color-muted-foreground); font-size: 0.6875rem; }
.hv-funnel-drop-glyph { color: var(--color-muted-foreground); }
.hv-scatter { display: flex; flex-direction: column; }
.hv-scatter-field { position: relative; display: block; flex: 1 1 auto; min-width: 0; height: 5rem; border-left: 1px solid var(--dt-border); border-bottom: 1px solid var(--dt-border); }
.hv-scatter-dot { position: absolute; width: 0.5rem; height: 0.5rem; border-radius: 999px; transform: translate(-50%, -50%); }
.hv-scatter-tag { position: absolute; transform: translate(0.4rem, -50%); color: var(--foreground); font-size: 0.6875rem; white-space: nowrap; }
.hv-waterfall { display: flex; flex-direction: column; }
.hv-wf-plot { position: relative; height: 5.5rem; }
.hv-wf-svg { display: block; width: 100%; height: 100%; }
.hv-wf-bar { stroke-width: 0.4; vector-effect: non-scaling-stroke; }
.hv-wf-bar--up { fill: var(--hv-3); stroke: var(--hv-3); }
.hv-wf-bar--down { fill: var(--hv-6); stroke: var(--hv-6); }
.hv-wf-link { stroke: var(--color-muted-foreground); stroke-width: 1; stroke-dasharray: 2 2; vector-effect: non-scaling-stroke; }
.hv-wf-base { stroke: var(--dt-border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.hv-wf-x { display: flex; justify-content: space-between; gap: 0.4rem; margin-top: 0.35rem; }
.hv-wf-tick { display: flex; flex: 1 1 0; flex-direction: column; align-items: center; min-width: 0; text-align: center; }
.hv-wf-glyph { font-size: 0.625rem; }
.hv-wf-glyph--up { color: var(--hv-3); }
.hv-wf-glyph--down { color: var(--hv-6); }
.hv-wf-name { color: var(--color-muted-foreground); font-size: 0.6875rem; overflow-wrap: anywhere; }
.hv-wf-delta { color: var(--foreground); font-weight: 600; font-size: 0.6875rem; }
/* The palette classes, applied by first-seen order. Last in the sheet so a
 * category hue overrides the single-accent default. */
.hv-c0 { stroke: var(--hv-1); background: var(--hv-1); }
.hv-c1 { stroke: var(--hv-2); background: var(--hv-2); }
.hv-c2 { stroke: var(--hv-3); background: var(--hv-3); }
.hv-c3 { stroke: var(--hv-4); background: var(--hv-4); }
.hv-c4 { stroke: var(--hv-5); background: var(--hv-5); }
.hv-c5 { stroke: var(--hv-6); background: var(--hv-6); }
/* Hover or focus focuses one row: the one under the pointer or the keyboard
 * stays at full strength and its siblings dim. Pure CSS, and :focus-visible gets
 * the same treatment as :hover so the keyboard is not a second-class reader. */
.hv-widget:hover [data-hv-row] { opacity: 0.55; }
.hv-widget [data-hv-row]:hover,
.hv-widget [data-hv-row]:focus-visible { opacity: 1; }
/* ALL motion lives under the no-preference media query, so the still rendering
 * is the default and the guard cannot be forgotten. Delay rides in the markup as
 * --d on a staggered row and --k on a growing bar, so a list of any length
 * animates — the six :nth-child delays this replaces stopped at the sixth row.
 * Motion is transform and opacity only: a widget never reflows while it arrives. */
@media (prefers-reduced-motion: no-preference) {
  @keyframes hv-rise { from { opacity: 0; transform: translateY(0.35rem); } to { opacity: 1; transform: translateY(0); } }
  @keyframes hv-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  .hv-kpi-tile, .hv-row, .hv-prog, .hv-step, .hv-legend-item, .hv-table tbody tr, .hv-check, .hv-outline-item, .hv-fact, .hv-file, .hv-setting, .hv-tl-item, .hv-metric, .hv-cell, .hv-heat-cell, .hv-section, .hv-section-lead, .hv-wf-row, .hv-word, .hv-route-stop, .hv-match, .hv-gloss-row, .hv-bracket-round, .hv-rec, .hv-group-row { animation: hv-rise 0.5s cubic-bezier(0.22, 1.12, 0.36, 1) calc(var(--d, 0) * 34ms) backwards; transition: opacity 0.18s ease; }
  .hv-bar-fill, .hv-fill, .hv-range-span, .hv-change-add, .hv-change-del, .hv-wf-block, .hv-funnel-fill { animation: hv-grow 0.7s cubic-bezier(0.22, 1.12, 0.36, 1) calc(var(--k, 0) * 45ms) backwards; }
  .hv-donut-svg, .hv-line .hv-svg, .hv-sparkline .hv-svg, .hv-candlestick .hv-svg { animation: hv-rise 0.6s cubic-bezier(0.22, 1.12, 0.36, 1) backwards; }
}
`
// <<< vendored-core

/** Mounts the core's markup into the app's React tree. No hooks: `render` is
 *  called as a plain function from inside the directive host component. */
function VizWidget({ attrs, source }) {
  const mount = useRef(null)
  const markup = renderWidget({
    k: attrs ? attrs.k : '',
    d: attrs ? attrs.d : '',
    t: attrs ? attrs.t : '',
    u: attrs ? attrs.u : '',
    p: attrs ? attrs.p : '',
    l: attrs ? attrs.l : '',
    source: typeof source === 'string' ? source : ''
  })

  // The mount owns the behaviour; the core only declares the affordance. ONE
  // pointerenter and ONE focusin on the element React already owns reveal the
  // answer's own hover note (`n=`), and leaving hides it. Only a widget that
  // asked for a note carries the slot, so a widget without one installs nothing.
  useEffect(() => {
    const node = mount.current
    if (!node) return undefined
    const slot = node.querySelector('[data-hv-note-slot]')
    if (!slot) return undefined
    const text = node.getAttribute('data-hv-note') || ''
    if (!text) return undefined

    const show = () => {
      slot.textContent = text
    }
    const hide = () => {
      slot.textContent = ''
    }

    node.addEventListener('pointerenter', show)
    node.addEventListener('focusin', show)
    node.addEventListener('pointerleave', hide)
    node.addEventListener('focusout', hide)
    return () => {
      node.removeEventListener('pointerenter', show)
      node.removeEventListener('focusin', show)
      node.removeEventListener('pointerleave', hide)
      node.removeEventListener('focusout', hide)
    }
  }, [markup])

  // The one thing a widget may DO on the host's behalf. The core draws a URL or
  // a path as the host's own kind of reference and declares the click with
  // `data-hv-link`; this listener performs it through the bridge the desktop app
  // puts on the window — `openExternal` for a URL, `revealPath` for a file or
  // folder, which the app checks on disk and hands to the OS file manager.
  // Neither is in the plugin SDK, so both are feature-detected: a host with
  // neither leaves the reference inert rather than throwing. Delegated, once per
  // mount, removed on unmount, and it never navigates the window the app owns.
  useEffect(() => {
    const node = mount.current
    if (!node) return undefined
    const bridge = typeof window === 'undefined' ? null : window.hermesDesktop

    const activate = event => {
      const el = event.target && event.target.closest ? event.target.closest('[data-hv-link]') : null
      if (!el || !bridge) return
      const value = el.getAttribute('data-hv-value') || ''
      const kind = el.getAttribute('data-hv-link')
      if (!value) return
      if (kind === 'url') {
        if (typeof bridge.openExternal === 'function') bridge.openExternal(value)
      } else if (typeof bridge.revealPath === 'function') {
        bridge.revealPath(value)
      }
    }

    node.addEventListener('click', activate)
    return () => node.removeEventListener('click', activate)
  }, [markup])

  // Safe by construction: the core builds this string itself and escapes every
  // model-supplied fragment (`esc`) before interpolating it. No raw attr value
  // reaches the markup — only tags the core wrote.
  return jsx('div', {
    className: 'hv-mount',
    ref: mount,
    dangerouslySetInnerHTML: { __html: markup }
  })
}

function renderViz(props) {
  const { attrs, source } = props || {}
  return jsx(VizWidget, { attrs, source })
}

function installStyle() {
  if (typeof document === 'undefined') return () => {}
  if (document.getElementById(STYLE_ID)) return () => {}

  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = CSS
  document.head.appendChild(style)

  return () => {
    if (style.parentNode) style.parentNode.removeChild(style)
  }
}

/** The answer body's typography. Its own tag, so with the setting OFF the
 *  injected stylesheet is byte-identical to the base one above.
 *
 *  The app already owns the transcript's typography — its line-height token, its
 *  paragraph gap, its heading sizes and margins, its marker and strong colours —
 *  so this copies none of it. Restating what the app sets is how a plugin ends
 *  up fighting the app it draws inside.
 *
 *  Two things the app does not do, and only those:
 *
 *  - **A measure, and one column.** The app's markdown root is `max-w-none`, so a
 *    line of prose runs the width of a wide window. The cap goes on the block, not
 *    on each element: one measure then holds the prose, the headings (which would
 *    otherwise measure their own, larger `ch`) and the widgets between them.
 *  - **A heading colour.** The app paints headings the same colour as the body
 *    (`prose-headings:text-foreground`), so structure reads only as size. They
 *    take the accent here, from the app's own token — never a literal.
 *
 *  Every selector is scoped under `.aui-md` and written `:where()`, one class of
 *  weight, so the app's own utilities still win a tie. Nothing sets a font size:
 *  the reader's choice is theirs. */
const BODY_STYLE_ID = 'hermes-viz-body-style'
const BODY_STYLE = `
.aui-md {
  /* The measure, on the block itself: one column for the prose, the headings and
     the widgets alike. It has to sit here rather than on each element — a length
     in ch resolves against the element's OWN font size, so a heading capped at
     68ch in its larger type came out wider than the paragraph beside it. Centred,
     so a wide pane splits the leftover evenly and a narrow one leaves none. */
  --hv-body-measure: 68ch;
  max-width: var(--hv-body-measure);
  margin-inline: auto;
}

/* Structure, not text: a heading carries the answer's shape, so it takes the
   accent. The app's own heading sizes, margins and weight are left alone. */
.aui-md :where(h1, h2, h3) { color: var(--dt-primary); }
`

function installBodyStyle() {
  if (typeof document === 'undefined') return
  if (document.getElementById(BODY_STYLE_ID)) return
  const style = document.createElement('style')
  style.id = BODY_STYLE_ID
  style.textContent = BODY_STYLE
  document.head.appendChild(style)
}

function removeBodyStyle() {
  if (typeof document === 'undefined') return
  const style = document.getElementById(BODY_STYLE_ID)
  if (style && style.parentNode) style.parentNode.removeChild(style)
}

// ---------------------------------------------------------------------------
// Settings ▸ Plugins — hermes-viz's own page.
//
// This is the desktop half's entry in Settings: one rail row ("Visuals") whose
// landing page is the plugin's real controls. The manifest declares no
// `config_schema`, so the app adds no auto-generated "Agent settings" sub-page
// beneath it — the plugin owns its definitions (dashboard/settings.json, read by
// this page's backend). Registering `ctx.registerSettingsPage` gives it the page.
//
// REUSE: the dashboard page (dashboard/dist/index.js) cannot be shared with
// this ctx. It is a hand-written IIFE bound to the *dashboard* SDK global
// (`window.__HERMES_PLUGIN_SDK__` with `{ React, hooks, components, fetchJSON }`)
// and registers a tab via `window.__HERMES_PLUGINS__.register`; the desktop half
// loads as a blob module whose only allowed specifiers are `@hermes/plugin-sdk`
// / `react*` (runtime-loader.ts), so a relative import — or any second-stage
// load of that bundle — is refused. Sharing would need a build step and a new
// dependency. The genuine reuse is one level down: `GET /settings` already
// ships the schema fields, the sectioned rule groups with their blurbs, and the
// per-group sample markup rendered from the pure core (samples.json). This page
// is a thin shell over that same payload, so the two surfaces cannot disagree.

const PALETTE_LABELS = {
  dark: 'Dark — dark-headed diagrams',
  light: 'Light — light-headed diagrams',
  mermaid: 'Follow the app — leave Mermaid’s own dark/light alone'
}

const SETTINGS_BLURB =
  'Widgets inside Hermes answers. The plugin reads the markdown an answer already contains and ' +
  'draws what it finds; nothing here is spent on a request unless you switch the format guide on.'

const SAMPLE_STYLE_ID = 'hermes-viz-settings-samples'

/** A rejection from `ctx.rest` is an Error; a thrown string is not. */
function messageOf(exc) {
  return String(exc && exc.message ? exc.message : exc)
}

function fieldByKey(fields, key) {
  return (fields || []).find(field => field.key === key) || {}
}

/** A palette dropdown, never free text. */
function paletteControl(current, options, busy, write) {
  if ((options || []).length < 2) {
    return jsx('p', {
      className: 'text-sm text-(--ui-text-tertiary)',
      children: 'The diagram palette follows the app — there is no alternative to choose here.'
    })
  }

  return jsxs(Select, {
    disabled: busy,
    onValueChange: value => write('palette', value),
    value: current,
    children: [
      jsx(SelectTrigger, { className: 'w-72 max-w-full', children: jsx(SelectValue, {}) }),
      jsx(SelectContent, {
        children: options.map(option =>
          jsx(SelectItem, { value: option, children: PALETTE_LABELS[option] || option }, option)
        )
      })
    ]
  })
}

/** The bounded widget cap, a dropdown — never an unbounded number field. */
function widgetControl(current, ceiling, fallback, busy, write) {
  const options = []
  for (let n = 0; n <= ceiling; n += 1) options.push(n)

  return jsxs(Select, {
    disabled: busy,
    onValueChange: value => write('max_widgets', Number(value)),
    value: String(current != null ? current : fallback),
    children: [
      jsx(SelectTrigger, { className: 'w-72 max-w-full', children: jsx(SelectValue, {}) }),
      jsx(SelectContent, {
        children: options.map(n => {
          let label = n + (n === 1 ? ' widget' : ' widgets')
          if (n === 0) label = '0 — draw nothing'
          else if (fallback === n) label = n + ' widgets (default)'
          return jsx(SelectItem, { value: String(n), children: label }, n)
        })
      })
    ]
  })
}

/** One rule group: a labelled switch with its blurb and, where the pure core
 *  already drew one, a live sample — so a toggle is never a name alone. */
function groupRow(group, busy, onToggle) {
  return jsx(
    ToggleRow,
    {
      checked: group.active,
      description: group.blurb || 'No description yet.',
      disabled: busy,
      label: group.title,
      onChange: on => onToggle(group, on),
      below: group.sample
        ? jsx('figure', {
            // Trusted: rendered at build time from the plugin's own pure core by
            // dashboard/make_samples.mjs and shipped as data — no request or user
            // input reaches it.
            'aria-hidden': 'true',
            className: 'mt-2 max-w-[28rem]',
            dangerouslySetInnerHTML: { __html: group.sample }
          })
        : null
    },
    group.id
  )
}

function VizSettingsPage({ ctx }) {
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(() => {
    return ctx
      .rest('/settings')
      .then(data => {
        setState(data)
        setError('')
      })
      .catch(exc => setError(messageOf(exc)))
  }, [ctx])

  useEffect(() => {
    void load()
  }, [load])

  const write = useCallback(
    (key, value) => {
      setBusy(key)
      setError('')
      return ctx
        .rest('/settings', { method: 'PUT', body: { key, value } })
        .then(data => {
          setState(data)
        })
        .catch(exc => setError(messageOf(exc)))
        .then(() => setBusy(''))
    },
    [ctx]
  )

  if (!state) {
    return jsxs('div', {
      className: 'grid gap-3',
      children: [
        jsx('p', { className: 'text-sm text-muted-foreground', children: error || 'Loading settings…' }),
        error ? jsx(Button, { onClick: load, size: 'sm', variant: 'outline', children: 'Retry' }) : null
      ]
    })
  }

  const { current = {}, fields = [], groups = [], sections = [], settings_path = '', rules_path = '' } = state
  const activeCount = groups.filter(group => group.active).length

  // What the prompt costs right now. The API recomposes the guide on every read *and* every write, so
  // a group toggled below moves this number in the same round trip — no constant to keep in step with
  // the guide's own text, and with the guide off it costs nothing and says so.
  const guide = state.guide || null
  const guideOn = current.format_guide === true
  const guideCost = guide ? (guideOn ? '≈ ' + guide.tokens + ' prompt tokens' : 'guide off — 0 tokens') : null
  const guideField = fieldByKey(fields, 'format_guide')
  const paletteField = fieldByKey(fields, 'palette')
  const widgetsField = fieldByKey(fields, 'max_widgets')
  const bodyField = fieldByKey(fields, 'body_style')
  const ceiling = state.max_widgets_ceiling || 10

  // rules.yaml decides the order, so the rewritten value keeps the declared
  // group sequence regardless of click order.
  const toggleGroup = (group, on) => {
    const ids = groups.filter(candidate => candidate.active).map(candidate => candidate.id)
    const at = ids.indexOf(group.id)
    if (on && at === -1) ids.push(group.id)
    if (!on && at !== -1) ids.splice(at, 1)
    const ordered = groups.filter(candidate => ids.indexOf(candidate.id) !== -1).map(candidate => candidate.id)
    void write('rule_groups', ordered.join(','))
  }

  return jsxs('div', {
    className: 'grid gap-6 max-w-[74rem]',
    children: [
      // The samples need the core's own stylesheet, which the desktop surface
      // does not carry; shipped with the samples so the two cannot drift.
      state.samples_css
        ? jsx('style', { id: SAMPLE_STYLE_ID, dangerouslySetInnerHTML: { __html: state.samples_css } })
        : null,

      jsxs('div', {
        className: 'grid gap-1.5',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              jsx('h2', { className: 'text-lg font-semibold', children: 'Visuals' }),
              jsx(Badge, { variant: 'secondary', children: activeCount + ' of ' + groups.length + ' groups on' }),
              guideCost ? jsx(Badge, { variant: 'secondary', children: guideCost }) : null,
              jsx(Badge, { variant: 'secondary', children: settings_path })
            ]
          }),
          jsx('p', {
            className: 'max-w-[80ch] text-sm leading-snug text-muted-foreground',
            children: SETTINGS_BLURB
          })
        ]
      }),

      error ? jsx(Badge, { className: 'self-start', variant: 'destructive', children: error }) : null,

      jsxs('div', {
        className: 'grid gap-1',
        children: [
          jsx('h3', { className: 'text-base font-semibold', children: 'Answer formatting' }),
          jsx('p', {
            className: 'max-w-[70ch] text-xs leading-snug text-muted-foreground',
            children: 'The settings that shape every answer, before any rule group is consulted.'
          }),
          jsx(ToggleRow, {
            checked: guideOn,
            description: guideField.description,
            disabled: busy === 'format_guide',
            label: guideField.label || 'Answer format guide',
            onChange: on => void write('format_guide', on === true)
          }),
          jsx(ListRow, {
            action: paletteControl(current.palette, state.palettes, busy === 'palette', write),
            description: paletteField.description,
            title: paletteField.label || 'Diagram palette'
          }),
          jsx(ListRow, {
            action: widgetControl(current.max_widgets, ceiling, widgetsField.default, busy === 'max_widgets', write),
            description: widgetsField.description,
            title: widgetsField.label || 'Widgets per answer'
          }),
          // Opt-in and off by default; read straight from the field's own value
          // (the same GET /settings payload the widget injection reads).
          jsx(ToggleRow, {
            checked: bodyField.value === true,
            description: bodyField.description,
            disabled: busy === 'body_style',
            label: bodyField.label || 'Style the answer body',
            onChange: on => void write('body_style', on === true)
          })
        ]
      }),

      sections.length === 0
        ? jsx('p', { className: 'text-sm text-muted-foreground', children: 'No rule groups found in rules.yaml.' })
        : sections.map(section =>
            jsxs(
              'section',
              {
                className: 'grid gap-1',
                children: [
                  jsx('h3', { className: 'text-base font-semibold', children: section.title }),
                  section.blurb
                    ? jsx('p', {
                        className: 'max-w-[70ch] text-xs leading-snug text-muted-foreground',
                        children: section.blurb
                      })
                    : null,
                  ...section.groups.map(group => groupRow(group, busy === 'rule_groups', toggleGroup))
                ]
              },
              section.id
            )
          ),

      jsxs('div', {
        className: 'grid gap-1 text-xs text-muted-foreground',
        children: [
          jsx('span', { children: 'Store: ' + settings_path }),
          jsx('span', { children: 'Rules: ' + rules_path }),
          jsx(Button, {
            className: 'mt-1 self-start',
            disabled: !!busy,
            onClick: load,
            size: 'sm',
            variant: 'outline',
            children: 'Reload settings'
          })
        ]
      })
    ].filter(Boolean)
  })
}

export default {
  id: 'hermes-viz',
  register(ctx) {
    if (!ctx || typeof ctx.register !== 'function') return

    const removeStyle = installStyle()
    if (typeof ctx.onDispose === 'function') ctx.onDispose(removeStyle)

    // body_style is read from the plugin's own settings API (the same GET the
    // settings page uses) and only then installed — a second tag, leaving the
    // base sheet byte-identical.
    if (typeof ctx.rest === 'function') {
      Promise.resolve(ctx.rest('/settings'))
        .then(data => {
          const field = ((data && data.fields) || []).find(entry => entry.key === 'body_style')
          if (field && field.value === true) installBodyStyle()
        })
        .catch(() => {})
      if (typeof ctx.onDispose === 'function') ctx.onDispose(removeBodyStyle)
    }

    ctx.register({
      id: 'hermes-viz:directive',
      area: TRANSCRIPT_DIRECTIVE_AREA,
      data: { name: 'viz', render: renderViz }
    })

    // Settings ▸ Plugins: the plugin's own page. Feature-detected so the plugin
    // still loads on hosts that predate the helper.
    ctx.registerSettingsPage?.({
      id: 'settings',
      title: 'Visuals',
      icon: 'graph',
      render: () => jsx(VizSettingsPage, { ctx })
    })
  }
}
