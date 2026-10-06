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

import { TRANSCRIPT_DIRECTIVE_AREA } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const STYLE_ID = 'hermes-viz-widgets'

// >>> vendored-core
/** The eight kinds this plugin draws itself. */
const KINDS = ['kpi', 'bars', 'line', 'donut', 'steps', 'table', 'progress', 'sparkline']

const SEG_MARKERS = 4

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

/** Split a `d` payload: rows on `;`, cells on `|`, a row starting `h=` is a header. */
function parseRows(payload) {
  const raw = typeof payload === 'string' ? payload : ''
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

    if (cells.some(cell => cell.label || cell.value)) rows.push({ header, cells })
  }

  return rows
}

/** Attrs -> `{ kind, rows, title, unit, palette }`. Never throws. */
function parseSpec(attrs) {
  const a = attrs && typeof attrs === 'object' ? attrs : {}
  return {
    kind: clean(a.k).toLowerCase(),
    rows: parseRows(a.d),
    title: clean(a.t),
    unit: clean(a.u),
    palette: clean(a.p)
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

/** KPI tiles — emitted as bare grid children so the widget grid lays them out. */
function renderKpi(rows, opts) {
  return dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      const delta = cell.extra
        ? `<span class="hv-kpi-delta hv-kpi-delta--${cell.extra.startsWith('-') ? 'down' : 'up'}">` +
          `${cell.extra.startsWith('-') ? '\u25bc' : '\u25b2'} ${esc(cell.extra)}</span>`
        : ''
      return (
        `<div class="hv-kpi-tile">` +
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

function renderBars(rows, opts) {
  const data = dataRows(rows)
  const values = data.map(row => cellNum(cellAt(row, 0)))
  const domain = barsDomain(values, opts)
  const total = values.reduce((sum, value) => sum + Math.max(0, value), 0)
  // When the values already are percentages, a second percent (their share of the
  // total) contradicts the bar's own length and the axis. Only non-percent units
  // need the share to carry the comparison.
  const showShare = !(opts && opts.unit === '%')

  const items = data
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const pct = Math.max(0, Math.min(100, (values[i] / domain) * 100))
      const share = total > 0 ? Math.round((Math.max(0, values[i]) / total) * 100) : 0
      const shareCell = showShare ? `<span class="hv-row-share">${share}%</span>` : ''
      return (
        `<div class="hv-row">` +
        `<span class="hv-row-label">${esc(cell.label)}</span>` +
        `<span class="hv-bar"><span class="hv-bar-fill" style="width:${round(pct)}%"></span></span>` +
        `<span class="hv-row-meta">` +
        `<span class="hv-row-value">${esc(cell.value)}${unitSuffix(opts)}</span>` +
        shareCell +
        `</span>` +
        `</div>`
      )
    })
    .join('')

  // The labelled baseline: 0 at the track's start, the domain cap at its end.
  const axis =
    `<div class="hv-axis">` +
    `<span class="hv-axis-pad" aria-hidden="true"></span>` +
    `<span class="hv-axis-lo">0</span>` +
    `<span class="hv-axis-hi">${round(domain)}${unitSuffix(opts)}</span>` +
    `<span class="hv-axis-pad hv-axis-pad--end" aria-hidden="true"></span>` +
    `</div>`

  return `<div class="hv hv-bars">${items}${axis}</div>`
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

function renderLine(rows, opts) {
  const values = seriesValues(rows)
  const height = 36
  const points = seriesPoints(rows, height)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const meta =
    values.length > 1
      ? `<div class="hv-line-meta">` +
        `<span class="hv-line-lo">${round(lo)}</span>` +
        `<span class="hv-line-hi">${round(hi)}${unitSuffix(opts)}</span>` +
        `</div>`
      : ''
  return (
    `<div class="hv hv-line">` +
    meta +
    `<svg class="hv-svg" viewBox="0 0 100 ${height}" preserveAspectRatio="none" role="img">` +
    `<line class="hv-line-floor" x1="0" y1="${height}" x2="100" y2="${height}"></line>` +
    `<polygon class="hv-line-area" points="${seriesArea(points, height)}"></polygon>` +
    `<polyline class="hv-line-path" points="${points}" fill="none"></polyline>` +
    `</svg></div>`
  )
}

function renderSparkline(rows, opts) {
  const points = seriesPoints(rows, 24)
  return (
    `<div class="hv hv-sparkline">` +
    `<svg class="hv-svg" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true">` +
    `<polygon class="hv-spark-area" points="${seriesArea(points, 24)}"></polygon>` +
    `<polyline class="hv-spark-path" points="${points}" fill="none"></polyline>` +
    `</svg></div>`
  )
}

function renderDonut(rows, opts) {
  const data = dataRows(rows)
  const values = data.map(row => Math.max(0, num(cellAt(row, 0).value)))
  const total = values.reduce((sum, value) => sum + value, 0)

  const r = 15.9155
  const c = 2 * Math.PI * r

  // Consecutive segments are pulled apart by a fixed gap so a slice boundary is
  // legible as shape, not only as tone — the one thing a colour ramp cannot do.
  const GAP = 1.6
  const slices = values.filter(value => value > 0).length
  const step = slices > 1 ? GAP : 0

  let offset = 0
  let segments = ''

  for (let i = 0; i < values.length; i++) {
    const length = total > 0 ? (values[i] / total) * c : 0
    const drawn = Math.max(0, length - step)
    segments +=
      `<circle class="hv-donut-seg hv-seg-${i % SEG_MARKERS}" cx="18" cy="18" r="${r}" fill="none" ` +
      `stroke-dasharray="${round(drawn)} ${round(c)}" stroke-dashoffset="${round(-offset)}"></circle>`
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
      return (
        `<span class="hv-legend-item">` +
        `<span class="hv-legend-dot hv-seg-${i % SEG_MARKERS}"></span>` +
        `${esc(cell.label)}` +
        `<span class="hv-legend-val">${esc(cell.value)}${unitSuffix(opts)}</span>` +
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
        `<li class="hv-step">` +
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

  const text = cell => esc(cell.value || cell.label)
  const head = header
    ? `<thead><tr>${header.cells.map(cell => `<th>${text(cell)}</th>`).join('')}</tr></thead>`
    : ''
  const tbody = `<tbody>${body
    .map(row => `<tr>${row.cells.map(cell => `<td>${text(cell)}</td>`).join('')}</tr>`)
    .join('')}</tbody>`

  return `<div class="hv hv-table-wrap"><table class="hv-table">${head}${tbody}</table></div>`
}

function renderProgress(rows, opts) {
  const items = dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      const pct = Math.max(0, Math.min(100, num(cell.value)))
      return (
        `<div class="hv-prog">` +
        `<span class="hv-prog-label">${esc(cell.label)}</span>` +
        `<span class="hv-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${round(pct)}">` +
        `<span class="hv-fill" style="width:${round(pct)}%"></span></span>` +
        `<span class="hv-prog-value">${round(pct)}%</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-progress">${items}</div>`
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
  const rows = parseRows(raw.slice(cut + 1))
  return renderKind(kind, rows, {
    unit: opts && opts.unit,
    palette: opts && opts.palette,
    source: raw
  })
}

/** A board: `~`-separated widget entries laid out by the pane's own grid. */
function renderBoard(specs, opts) {
  const entries = Array.isArray(specs) ? specs : []
  // Each entry is one column: its markup is wrapped so a multi-tile kind (kpi) stays one widget.
  const cells = entries
    .map(entry => `<div class="hv hv-grid">${renderBoardEntry(entry, opts)}</div>`)
    .join('')
  if (!cells) return fallback(opts, 'no-rows')
  return `<div class="hv hv-grid hv-board">${cells}</div>`
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
  if (list.length === 0) return fallback(opts, 'no-rows')
  if (k !== 'table' && data.length === 0) return fallback(opts, 'no-rows')

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
      return renderSteps(list, opts)
    case 'table':
      return renderTable(list, opts)
    case 'progress':
      return renderProgress(list, opts)
    default:
      return renderSparkline(list, opts)
  }
}

/** Attrs -> the whole widget: caption, then one grid holding the kind's cells. */
function renderWidget(attrs) {
  const spec = parseSpec(attrs)
  const opts = { unit: spec.unit, source: attrs && typeof attrs.source === 'string' ? attrs.source : '' }
  const title = spec.title ? `<div class="hv-title">${esc(spec.title)}</div>` : ''
  const inner =
    spec.kind === 'board'
      ? renderKind('board', boardEntries(attrs && attrs.d), opts)
      : renderKind(spec.kind, spec.rows, opts)

  return (
    `<div class="hv hv-widget" data-kind="${esc(spec.kind || 'unknown')}">` +
    `${title}<div class="hv-grid">${inner}</div>` +
    `</div>`
  )
}

/**
 * The widget stylesheet. Only the five tokens the app defines — no literal
 * colour (`color-mix` builds every ramp step from them), and no cap of any kind
 * on the widget's own box: the grid reflows and the pane decides. The widget
 * surface itself stays transparent; only data tracks (`--dt-muted`), hairlines
 * (`--dt-border`) and the primary ramp paint.
 *
 * Hierarchy: an uppercase caption with a hairline rule, a deliberate type
 * scale, and one tonal family (primary) with a neutral for secondary text.
 * Depth is a hairline plus a single inset, never a shadow pile. Motion is a
 * short staggered rise and a bar grow that reveals the data — all of it removed
 * under `prefers-reduced-motion`.
 */
const CSS = `
.hv-widget { color: var(--foreground); font-size: 0.8125rem; line-height: 1.4; font-variant-numeric: tabular-nums; }
.hv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 0.6rem; }
.hv-board { grid-template-columns: repeat(auto-fit, minmax(24rem, 1fr)); gap: 0.75rem; }
.hv-title { margin: 0 0 0.6rem; padding-bottom: 0.4rem; border-bottom: 1px solid var(--dt-border); color: var(--color-muted-foreground); font-size: 0.6875rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }
.hv-prose { margin: 0; color: var(--color-muted-foreground); font-style: italic; }
.hv-unit { margin-left: 0.12em; color: var(--color-muted-foreground); font-size: 0.72em; font-weight: 500; }
.hv-kpi-tile { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; padding: 0.7rem 0.8rem; border: 1px solid var(--dt-border); border-radius: 0.6rem; box-shadow: inset 0 1px 0 color-mix(in srgb, var(--foreground) 7%, transparent); }
.hv-kpi-label { color: var(--color-muted-foreground); font-size: 0.6875rem; letter-spacing: 0.04em; }
.hv-kpi-value { color: var(--foreground); font-size: 1.625rem; font-weight: 650; letter-spacing: -0.02em; line-height: 1.05; }
.hv-kpi-delta { align-self: flex-start; padding: 0.08rem 0.4rem; border-radius: 999px; color: var(--color-muted-foreground); background: color-mix(in srgb, var(--color-muted-foreground) 12%, transparent); font-size: 0.6875rem; font-weight: 600; }
.hv-kpi-delta--up { color: var(--dt-primary); background: color-mix(in srgb, var(--dt-primary) 15%, transparent); }
.hv-kpi-delta--down { color: var(--color-muted-foreground); }
.hv-bars, .hv-progress { display: flex; flex-direction: column; gap: 0.45rem; }
.hv-row, .hv-prog { display: flex; align-items: center; gap: 0.6rem; min-width: 0; }
.hv-row-label, .hv-prog-label { flex: 0 0 auto; min-width: 5rem; color: var(--color-muted-foreground); }
.hv-bar, .hv-track { position: relative; flex: 1 1 auto; min-width: 0; height: 0.5rem; border-radius: 999px; background: var(--dt-muted); overflow: hidden; }
.hv-bar-fill, .hv-fill { display: block; height: 100%; border-radius: 999px; background: var(--dt-primary); box-shadow: inset 0 1px 0 color-mix(in srgb, var(--foreground) 22%, transparent); transform-origin: left center; }
.hv-row-meta { display: flex; flex: 0 0 auto; align-items: baseline; justify-content: flex-end; gap: 0.4rem; min-width: 5rem; }
.hv-row-value, .hv-prog-value { flex: 0 0 auto; color: var(--foreground); font-weight: 600; }
.hv-row-share { min-width: 2.4rem; color: var(--color-muted-foreground); font-size: 0.6875rem; text-align: right; }
.hv-axis { display: flex; align-items: baseline; gap: 0.6rem; margin-top: 0.15rem; }
.hv-axis-pad { flex: 0 0 auto; min-width: 5rem; }
.hv-axis-lo { flex: 1 1 auto; color: var(--color-muted-foreground); font-size: 0.625rem; letter-spacing: 0.08em; }
.hv-axis-hi { flex: 0 0 auto; color: var(--color-muted-foreground); font-size: 0.625rem; letter-spacing: 0.08em; }
.hv-line-meta { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 0.3rem; color: var(--color-muted-foreground); font-size: 0.625rem; letter-spacing: 0.08em; text-transform: uppercase; }
.hv-line-hi { color: var(--foreground); font-weight: 600; font-size: 0.8125rem; }
.hv-svg { display: block; width: 100%; }
.hv-line .hv-svg { height: 4.5rem; }
.hv-sparkline .hv-svg { height: 2.25rem; }
.hv-line-area, .hv-spark-area { stroke: none; fill: color-mix(in srgb, var(--dt-primary) 26%, transparent); }
.hv-line-floor { stroke: var(--dt-border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.hv-line-path, .hv-spark-path { stroke: var(--dt-primary); stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.hv-line-path { stroke-width: 1.75; }
.hv-spark-path { stroke-width: 1.75; }
.hv-donut { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.hv-donut-svg { flex: 0 0 auto; width: 5rem; height: 5rem; }
.hv-donut-track { stroke: var(--dt-muted); stroke-width: 3.6; }
.hv-donut-seg { stroke-width: 3.6; }
.hv-donut-center { fill: var(--foreground); stroke: none; font-size: 5.4px; font-weight: 650; text-anchor: middle; dominant-baseline: central; }
.hv-legend { display: flex; flex: 1 1 10rem; flex-direction: column; gap: 0.35rem; min-width: 0; }
.hv-legend-item { display: flex; align-items: center; gap: 0.5rem; color: var(--color-muted-foreground); }
.hv-legend-dot { flex: 0 0 auto; width: 0.55rem; height: 0.55rem; border-radius: 3px; background: var(--dt-primary); }
.hv-legend-val { margin-left: auto; color: var(--foreground); font-weight: 600; }
/* One tonal family, stepped LIGHTER rather than darker. Both --dt-muted and
 * --color-muted-foreground are near the surface in value, so mixing down went
 * brown-toward-black and the low steps became hard to tell apart. Stepping up into
 * --foreground gives four tones whose contrast on the dark surface rises then falls
 * to the app's neutral, so every step stays legible. */
.hv-seg-0 { stroke: var(--dt-primary); background: var(--dt-primary); }
.hv-seg-1 { stroke: color-mix(in srgb, var(--dt-primary) 58%, var(--foreground)); background: color-mix(in srgb, var(--dt-primary) 58%, var(--foreground)); }
.hv-seg-2 { stroke: color-mix(in srgb, var(--dt-primary) 22%, var(--foreground)); background: color-mix(in srgb, var(--dt-primary) 22%, var(--foreground)); }
.hv-seg-3 { stroke: var(--color-muted-foreground); background: var(--color-muted-foreground); }
.hv-step-list { display: flex; flex-direction: column; gap: 0.55rem; margin: 0; padding: 0; list-style: none; }
.hv-step { position: relative; display: flex; align-items: flex-start; gap: 0.65rem; }
.hv-step:not(:last-child)::after { content: ''; position: absolute; left: 0.78rem; top: 1.7rem; bottom: -0.55rem; width: 1px; background: var(--dt-border); }
.hv-step-n { position: relative; z-index: 1; flex: 0 0 auto; width: 1.55rem; height: 1.55rem; border: 1px solid var(--dt-border); border-radius: 50%; color: var(--foreground); background: var(--dt-muted); font-size: 0.6875rem; font-weight: 600; line-height: 1.55rem; text-align: center; }
.hv-step-t { flex: 1 1 auto; min-width: 0; padding-top: 0.2rem; }
.hv-table { width: 100%; border-collapse: collapse; }
.hv-table th, .hv-table td { padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--dt-border); text-align: left; }
.hv-table th:not(:first-child), .hv-table td:not(:first-child) { text-align: right; }
.hv-table th { color: var(--color-muted-foreground); font-size: 0.625rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.hv-table td { color: var(--color-muted-foreground); }
.hv-table td:first-child { color: var(--foreground); font-weight: 550; }
.hv-table tbody tr:last-child td { border-bottom: none; }
@keyframes hv-rise { from { opacity: 0; transform: translateY(0.35rem); } to { opacity: 1; transform: translateY(0); } }
@keyframes hv-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.hv-kpi-tile, .hv-row, .hv-prog, .hv-step, .hv-legend-item, .hv-line-meta, .hv-table tbody tr { animation: hv-rise 0.5s cubic-bezier(0.22, 1.12, 0.36, 1) backwards; }
.hv-bar-fill, .hv-fill { animation: hv-grow 0.7s cubic-bezier(0.22, 1.12, 0.36, 1) 0.06s backwards; }
.hv-donut-svg, .hv-line .hv-svg, .hv-sparkline .hv-svg { animation: hv-rise 0.6s cubic-bezier(0.22, 1.12, 0.36, 1) backwards; }
.hv-kpi-tile:nth-child(1), .hv-row:nth-child(1), .hv-prog:nth-child(1), .hv-step:nth-child(1), .hv-legend-item:nth-child(1), .hv-table tbody tr:nth-child(1) { animation-delay: 0.04s; }
.hv-kpi-tile:nth-child(2), .hv-row:nth-child(2), .hv-prog:nth-child(2), .hv-step:nth-child(2), .hv-legend-item:nth-child(2), .hv-table tbody tr:nth-child(2) { animation-delay: 0.09s; }
.hv-kpi-tile:nth-child(3), .hv-row:nth-child(3), .hv-prog:nth-child(3), .hv-step:nth-child(3), .hv-legend-item:nth-child(3), .hv-table tbody tr:nth-child(3) { animation-delay: 0.14s; }
.hv-kpi-tile:nth-child(4), .hv-row:nth-child(4), .hv-prog:nth-child(4), .hv-step:nth-child(4), .hv-legend-item:nth-child(4), .hv-table tbody tr:nth-child(4) { animation-delay: 0.19s; }
.hv-kpi-tile:nth-child(5), .hv-row:nth-child(5), .hv-prog:nth-child(5), .hv-step:nth-child(5), .hv-legend-item:nth-child(5), .hv-table tbody tr:nth-child(5) { animation-delay: 0.24s; }
.hv-kpi-tile:nth-child(6), .hv-row:nth-child(6), .hv-prog:nth-child(6), .hv-step:nth-child(6), .hv-legend-item:nth-child(6), .hv-table tbody tr:nth-child(6) { animation-delay: 0.29s; }
@media (prefers-reduced-motion: reduce) {
  .hv-widget, .hv-widget * { animation: none !important; transition: none !important; }
}
`
// <<< vendored-core

/** Mounts the core's markup into the app's React tree. No hooks: `render` is
 *  called as a plain function from inside the directive host component. */
function VizWidget({ attrs, source }) {
  const markup = renderWidget({
    k: attrs ? attrs.k : '',
    d: attrs ? attrs.d : '',
    t: attrs ? attrs.t : '',
    u: attrs ? attrs.u : '',
    p: attrs ? attrs.p : '',
    source: typeof source === 'string' ? source : ''
  })

  // Safe by construction: the core builds this string itself and escapes every
  // model-supplied fragment (`esc`) before interpolating it. No raw attr value
  // reaches the markup — only tags the core wrote.
  return jsx('div', {
    className: 'hv-mount',
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

export default {
  id: 'hermes-viz',
  register(ctx) {
    if (!ctx || typeof ctx.register !== 'function') return

    const removeStyle = installStyle()
    if (typeof ctx.onDispose === 'function') ctx.onDispose(removeStyle)

    ctx.register({
      id: 'hermes-viz:directive',
      area: TRANSCRIPT_DIRECTIVE_AREA,
      data: { name: 'viz', render: renderViz }
    })
  }
}
