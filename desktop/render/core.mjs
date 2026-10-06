/**
 * hermes-viz — the drawing core.
 *
 * PURE. Strings in, markup strings out: no DOM, no React, no globals, no I/O.
 * That is what makes the widget appearance verifiable without a CDP port — the
 * node test and the screenshot fixture both drive exactly this module.
 *
 * The runtime plugin (`../plugin.js`) may only import `@hermes/plugin-sdk`,
 * `react` and `react/jsx-runtime` (the loader refuses every other specifier,
 * including relative ones), so `plugin.js` carries this region verbatim and
 * the test asserts the two copies match. Everything between the two
 * `vendored-core` markers is the canonical source of truth.
 */

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

function renderBars(rows, opts) {
  const data = dataRows(rows)
  const values = data.map(row => num(cellAt(row, 0).value))
  const max = opts && opts.unit === '%' ? 100 : Math.max(...values, 1)

  const items = data
    .map((row, i) => {
      const cell = cellAt(row, 0)
      const pct = Math.max(0, Math.min(100, (values[i] / max) * 100))
      return (
        `<div class="hv-row">` +
        `<span class="hv-row-label">${esc(cell.label)}</span>` +
        `<span class="hv-bar"><span class="hv-bar-fill" style="width:${round(pct)}%"></span></span>` +
        `<span class="hv-row-value">${esc(cell.value)}${unitSuffix(opts)}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-bars">${items}</div>`
}

/** Polyline points across a 100-unit-wide viewBox. */
function seriesPoints(rows, height) {
  const values = dataRows(rows).map(row => num(cellAt(row, 0).value))
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

function renderLine(rows, opts) {
  const points = seriesPoints(rows, 32)
  return (
    `<div class="hv hv-line">` +
    `<svg class="hv-svg" viewBox="0 0 100 32" preserveAspectRatio="none" role="img">` +
    `<polyline class="hv-line-path" points="${points}" fill="none"></polyline>` +
    `</svg></div>`
  )
}

function renderSparkline(rows, opts) {
  const points = seriesPoints(rows, 24)
  return (
    `<div class="hv hv-sparkline">` +
    `<svg class="hv-svg" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true">` +
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

  let offset = 0
  let segments = ''

  for (let i = 0; i < values.length; i++) {
    const length = total > 0 ? (values[i] / total) * c : 0
    segments +=
      `<circle class="hv-donut-seg hv-seg-${i % SEG_MARKERS}" cx="18" cy="18" r="${r}" fill="none" ` +
      `stroke-dasharray="${round(length)} ${round(c)}" stroke-dashoffset="${round(-offset)}"></circle>`
    offset += length
  }

  const centre = data.length === 1 ? cellAt(data[0], 0).value : String(round(total))

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
 * The widget stylesheet. Tokens only — no literal colour, and no width or
 * height cap of any kind: the grid reflows and the pane decides. The widget
 * surface itself stays transparent; only data tracks (`--card`) and hairlines
 * paint.
 */
const CSS = `
.hv-widget { color: var(--foreground); font-size: 0.8125rem; line-height: 1.35; }
.hv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 0.5rem; }
.hv-board { grid-template-columns: repeat(auto-fit, minmax(24rem, 1fr)); }
.hv-title { margin: 0 0 0.35rem; color: var(--muted-foreground); font-size: 0.6875rem; letter-spacing: 0.06em; text-transform: uppercase; }
.hv-prose { margin: 0; color: var(--muted-foreground); font-style: italic; }
.hv-unit { margin-left: 0.1em; color: var(--muted-foreground); font-size: 0.72em; }
.hv-kpi-tile { display: flex; flex-direction: column; gap: 0.15rem; min-width: 0; padding: 0.55rem 0.7rem; border: 1px solid var(--border); border-radius: 0.5rem; }
.hv-kpi-label { color: var(--muted-foreground); font-size: 0.6875rem; }
.hv-kpi-value { color: var(--foreground); font-size: 1.3rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.hv-kpi-delta { font-size: 0.6875rem; font-variant-numeric: tabular-nums; }
.hv-kpi-delta--up { color: var(--accent); }
.hv-kpi-delta--down { color: var(--muted-foreground); }
.hv-bars, .hv-progress { display: flex; flex-direction: column; gap: 0.3rem; }
.hv-row, .hv-prog { display: flex; align-items: center; gap: 0.5rem; min-width: 0; }
.hv-row-label, .hv-prog-label { flex: 0 0 auto; min-width: 5rem; color: var(--muted-foreground); }
.hv-bar, .hv-track { position: relative; flex: 1 1 auto; min-width: 0; height: 0.5rem; border-radius: 999px; background: var(--card); overflow: hidden; }
.hv-bar-fill, .hv-fill { display: block; height: 100%; border-radius: 999px; background: var(--accent); }
.hv-row-value, .hv-prog-value { flex: 0 0 auto; color: var(--foreground); font-variant-numeric: tabular-nums; }
.hv-svg { display: block; width: 100%; }
.hv-line .hv-svg { height: 3.25rem; }
.hv-sparkline .hv-svg { height: 1.5rem; }
.hv-line-path { stroke: var(--accent); stroke-width: 1.5; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.hv-spark-path { stroke: var(--accent); stroke-width: 1.25; vector-effect: non-scaling-stroke; }
.hv-donut { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.hv-donut-svg { flex: 0 0 auto; width: 4.5rem; height: 4.5rem; }
.hv-donut-track { stroke: var(--border); stroke-width: 3; }
.hv-donut-seg { stroke-width: 3; }
.hv-donut-center { fill: var(--foreground); stroke: none; font-size: 6px; text-anchor: middle; dominant-baseline: central; font-variant-numeric: tabular-nums; }
.hv-legend { display: flex; flex: 1 1 8rem; flex-direction: column; gap: 0.15rem; min-width: 0; }
.hv-legend-item { display: flex; align-items: center; gap: 0.4rem; color: var(--muted-foreground); }
.hv-legend-dot { flex: 0 0 auto; width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--accent); }
.hv-legend-val { margin-left: auto; color: var(--foreground); font-variant-numeric: tabular-nums; }
.hv-seg-0 { stroke: var(--accent); background: var(--accent); }
.hv-seg-1 { stroke: var(--accent); background: var(--accent); opacity: 0.6; }
.hv-seg-2 { stroke: var(--foreground); background: var(--foreground); opacity: 0.45; }
.hv-seg-3 { stroke: var(--muted-foreground); background: var(--muted-foreground); }
.hv-step-list { display: flex; flex-direction: column; gap: 0.3rem; margin: 0; padding: 0; list-style: none; }
.hv-step { display: flex; align-items: flex-start; gap: 0.5rem; }
.hv-step-n { flex: 0 0 auto; width: 1.35rem; height: 1.35rem; border: 1px solid var(--border); border-radius: 50%; color: var(--muted-foreground); font-size: 0.6875rem; line-height: 1.35rem; text-align: center; font-variant-numeric: tabular-nums; }
.hv-step-t { flex: 1 1 auto; min-width: 0; }
.hv-table { width: 100%; border-collapse: collapse; }
.hv-table th, .hv-table td { padding: 0.25rem 0.5rem; border-bottom: 1px solid var(--border); text-align: left; }
.hv-table th { color: var(--muted-foreground); font-size: 0.6875rem; font-weight: 500; letter-spacing: 0.05em; text-transform: uppercase; }
.hv-table td { color: var(--foreground); font-variant-numeric: tabular-nums; }
`
// <<< vendored-core

export { KINDS, CSS, parseSpec, renderKind, renderWidget }
