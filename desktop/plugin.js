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
/** Every kind this plugin draws itself. `board` is the multi-widget form and is
 *  dispatched before this list is consulted. */
const KINDS = [
  'kpi', 'bars', 'line', 'donut', 'steps', 'table', 'progress', 'sparkline',
  'section',
  'checklist', 'changes', 'outline', 'facts', 'files', 'parts', 'settings',
  'timeline', 'ranges', 'metrics', 'array', 'heatmap',
  'wireframe', 'candlestick',
  'words', 'recipe', 'route', 'nutrition', 'matches',
  'bracket', 'gloss', 'forms'
]

/** Six palette slots, declared once in the CSS as `--hv-1` … `--hv-6`. */
const PALETTE = 6

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

/** The palette slot for a category, by first-seen order. Same payload -> same
 *  colours; past six categories the ramp wraps, deterministically. */
function slot(index) {
  const i = Number.isFinite(index) ? Math.trunc(index) : 0
  return `hv-c${((i % PALETTE) + PALETTE) % PALETTE}`
}

/** Per-element detail on hover/focus — the data is already readable without it. */
function hover(text) {
  return ` title="${esc(text)}"`
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
    .map(row => {
      const cell = cellAt(row, 0)
      const delta = cell.extra
        ? `<span class="hv-kpi-delta hv-kpi-delta--${cell.extra.startsWith('-') ? 'down' : 'up'}">` +
          `${cell.extra.startsWith('-') ? '\u25bc' : '\u25b2'} ${esc(cell.extra)}</span>`
        : ''
      return (
        `<div class="hv-kpi-tile"${hover(`${cell.label}: ${cell.value}`)}>` +
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
      const detail = `${cell.label}: ${row.value}${unit}${row.target ? ` of ${row.target}${unit}` : ''}`
      return (
        `<div class="hv-row"${hover(detail)}>` +
        `<span class="hv-row-label">${esc(cell.label)}</span>` +
        `<span class="hv-bar"><span class="hv-bar-fill ${slot(i)}" style="width:${round(pct)}%"></span></span>` +
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
        `<span class="hv-legend-item">` +
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
        `<li class="hv-step"${hover(text)}>` +
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

  const text = cell => esc(cellText(cell))
  const head = header
    ? `<thead><tr>${header.cells.map(cell => `<th>${text(cell)}</th>`).join('')}</tr></thead>`
    : ''
  const tbody = `<tbody>${body
    .map(row => `<tr>${row.cells.map(cell => `<td>${text(cell)}</td>`).join('')}</tr>`)
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
      row =>
        `<tr>${row.cells
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
        `<div class="hv-prog"${hover(`${cell.label}: ${round(pct)}%`)}>` +
        `<span class="hv-prog-label">${esc(cell.label)}</span>` +
        `<span class="hv-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${round(pct)}">` +
        `<span class="hv-fill ${slot(i)}" style="width:${round(pct)}%"></span></span>` +
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
const CHECK_STATES = { done: '\u2713', doing: '\u25d0', todo: '\u25cb', blocked: '\u2715' }

function renderChecklist(rows) {
  const items = dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      const wanted = String(cell.value || 'todo').toLowerCase()
      const state = CHECK_STATES[wanted] ? wanted : 'todo'
      return (
        `<li class="hv-check hv-check--${state}"${hover(`${cell.label}: ${state}`)}>` +
        `<span class="hv-check-glyph" aria-hidden="true">${CHECK_STATES[state]}</span>` +
        `<span class="hv-check-label">${esc(cell.label)}</span>` +
        `</li>`
      )
    })
    .join('')

  return `<div class="hv hv-checklist"><ul class="hv-check-list">${items}</ul></div>`
}

/** `path=+adds=-dels` -> a per-file diff bar plus the totals. */
function renderChanges(rows) {
  const files = dataRows(rows).map(row => {
    const cell = cellAt(row, 0)
    return { path: cell.label, adds: Math.abs(num(cell.value)), dels: Math.abs(num(cell.extra)) }
  })
  const max = Math.max(1, ...files.map(file => file.adds + file.dels))
  const totalAdds = files.reduce((sum, file) => sum + file.adds, 0)
  const totalDels = files.reduce((sum, file) => sum + file.dels, 0)

  const items = files
    .map(file => {
      const span = file.adds + file.dels
      const width = round((span / max) * 100)
      const addShare = span > 0 ? file.adds / span : 0
      return (
        `<div class="hv-row"${hover(`${file.path}: +${file.adds} -${file.dels}`)}>` +
        `<span class="hv-row-label hv-change-path">${esc(file.path)}</span>` +
        `<span class="hv-bar hv-change-bar">` +
        `<span class="hv-change-add ${slot(0)}" style="width:${round(width * addShare)}%"></span>` +
        `<span class="hv-change-del ${slot(5)}" style="width:${round(width * (1 - addShare))}%"></span>` +
        `</span>` +
        `<span class="hv-row-meta hv-change-counts">` +
        `<span class="hv-add">+${file.adds}</span><span class="hv-del">-${file.dels}</span>` +
        `</span>` +
        `</div>`
      )
    })
    .join('')

  const total =
    `<div class="hv-change-total">` +
    `<span class="hv-change-total-label">${files.length} files</span>` +
    `<span class="hv-add">+${totalAdds}</span><span class="hv-del">-${totalDels}</span>` +
    `</div>`

  return `<div class="hv hv-changes">${items}${total}</div>`
}

function renderOutline(rows) {
  const items = dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      const depth = Math.max(0, (cell.label.match(/\./g) || []).length)
      const text = cellText(cell)
      const num = cell.value ? cell.label : ''
      return (
        `<li class="hv-outline-item" style="padding-left:${round(depth * 1.1)}rem"${hover(cell.label)}>` +
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
    .map(row => {
      const cell = cellAt(row, 0)
      return (
        `<div class="hv-fact"${hover(`${cell.label}: ${cell.value}`)}>` +
        `<span class="hv-fact-label">${esc(cell.label)}</span>` +
        `<span class="hv-fact-value">${esc(cellText(cell))}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-facts">${items}</div>`
}

/** A single glyph per file kind — the path itself still reads. */
const FILE_GLYPHS = { py: '\u25c8', js: '\u25c8', mjs: '\u25c8', ts: '\u25c8', md: '\u25a4', json: '\u25a4', yml: '\u25b8', yaml: '\u25b8', sh: '\u25b8', html: '\u25a4' }

function fileGlyph(path) {
  const ext = String(path).toLowerCase().split('.').pop()
  return FILE_GLYPHS[ext] || '\u25a1'
}

function renderFiles(rows) {
  const items = dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      return (
        `<div class="hv-file"${hover(cell.value ? `${cell.label} — ${cell.value}` : cell.label)}>` +
        `<span class="hv-file-glyph" aria-hidden="true">${fileGlyph(cell.label)}</span>` +
        `<span class="hv-file-path">${esc(cell.label)}</span>` +
        `<span class="hv-file-meta">${esc(cell.value)}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-files">${items}</div>`
}

function renderSettings(rows) {
  const items = dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      const on = /^(on|true|1)$/i.test(cell.value)
      return (
        `<div class="hv-setting"${hover(`${cell.label}: ${cell.value}`)}>` +
        `<span class="hv-setting-label">${esc(cell.label)}</span>` +
        `<span class="hv-pill hv-pill--${on ? 'on' : 'off'}">${esc(cell.value || 'off')}</span>` +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-settings">${items}</div>`
}

function renderTimeline(rows) {
  const items = dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      const detail = cell.extra ? `<span class="hv-tl-detail">${esc(cell.extra)}</span>` : ''
      return (
        `<li class="hv-tl-item"${hover(`${cell.label} ${cell.value} ${cell.extra}`)}>` +
        `<span class="hv-tl-when">${esc(cell.label)}</span>` +
        `<span class="hv-tl-body">` +
        `<span class="hv-tl-label">${esc(cell.value)}</span>` +
        detail +
        `</span></li>`
      )
    })
    .join('')

  return `<div class="hv hv-timeline"><ol class="hv-tl-list">${items}</ol></div>`
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
        `<div class="hv-row"${hover(`${cell.label}: ${span.lo}–${span.hi}${unit}`)}>` +
        `<span class="hv-row-label">${esc(cell.label)}</span>` +
        `<span class="hv-bar hv-range-track">` +
        `<span class="hv-range-span ${slot(i)}" style="left:${left}%;width:${width}%"></span>` +
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
            `<span class="hv-metric-scale-fill${row.target ? '' : ` hv-metric-scale-fill--${down ? 'down' : 'up'}`}" ` +
            `style="width:${round(pct)}%"></span></span>`
          : ''
      const reference = row.target
        ? `<span class="hv-metric-target">of ${row.target}</span>` +
          `<span class="hv-metric-share">${round(pct)}%</span>`
        : ''
      return (
        `<div class="hv-metric"${hover(`${cell.label}: ${cell.value}${cell.extra ? ' ' + cell.extra : ''}`)}>` +
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

  const cells = data
    .map(row =>
      row.cells
        .filter(cell => cell.label || cell.value)
        .map(cell => `<span class="hv-cell">${esc(cellText(cell))}</span>`)
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
        `<span class="hv-heat-cell" style="background:color-mix(in srgb, var(--hv-1) ${strength}%, var(--dt-muted))"` +
        `${hover(`${cell.label}: ${values[i]}`)}>` +
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
    .map(row => {
      const cell = cellAt(row, 0)
      const drawn = wireBlocks(cell.value)
        .map(block => {
          const label = block.count > 1 ? `${block.type} ×${block.count}` : block.type
          return (
            `<span class="hv-wf-block hv-wf-block--${block.shape} ${slotFor(block.type)}" ` +
            `style="flex-grow:${block.count}"${hover(`${cell.label}: ${block.type} ×${block.count}`)}>` +
            `<span class="hv-wf-block-label">${esc(label)}</span></span>`
          )
        })
        .join('')
      // The row label sits beside the block track, never inside it, so a squeeze
      // can never hide it: the mock stays readable at any width.
      return (
        `<div class="hv-wf-row">` +
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

/** Vocabulary rows: `word=[say]=meaning=example`. A row with no `=` is a heading. */
function renderWords(rows) {
  const items = (Array.isArray(rows) ? rows.filter(Boolean) : [])
    .map(row => {
      const raw = String(row.raw === undefined ? '' : row.raw)
      if (!raw.includes('=')) {
        const heading = clean(raw)
        return heading ? `<li class="hv-words-head">${esc(heading)}</li>` : ''
      }
      const [word, say, meaning, example] = raw.split('=').map(part => clean(part))
      const pron = say ? `<span class="hv-word-say">${esc(say)}</span>` : ''
      const def = meaning ? `<span class="hv-word-meaning">${esc(meaning)}</span>` : ''
      const use = example ? `<span class="hv-word-example">${esc(example)}</span>` : ''
      return (
        `<li class="hv-word"${hover(`${word}: ${meaning}`)}>` +
        `<span class="hv-word-lead"><span class="hv-word-w">${esc(word)}</span>${pron}</span>` +
        def + use +
        `</li>`
      )
    })
    .join('')

  return `<div class="hv hv-words"><ul class="hv-word-list">${items}</ul></div>`
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
      return `<span class="hv-recipe-warn-glyph" aria-hidden="true">\u26a0</span>${esc(cell.label.slice(1))}`
    }
    return esc(cellText(cell))
  }

  const head = header
    ? `<thead><tr>${header.cells
        .map((cell, i) => `<th${i === cols - 1 ? ' class="hv-part-qty"' : ''}>${esc(cellText(cell))}</th>`)
        .join('')}</tr></thead>`
    : ''
  const tbody = `<tbody>${body
    .map(row => {
      const warn = isWarn(row)
      return (
        `<tr${warn ? ' class="hv-recipe-warn"' : ''}>` +
        row.cells
          .map((cell, i) => `<td${i === cols - 1 ? ' class="hv-part-qty"' : ''}>${text(row, cell, i)}</td>`)
          .join('') +
        `</tr>`
      )
    })
    .join('')}</tbody>`

  return `<div class="hv hv-table-wrap"><table class="hv-table hv-parts hv-recipe">${head}${tbody}</table></div>`
}

/** `time=stop=detail` -> an itinerary: stops on one rail, each with its time. */
function renderRoute(rows) {
  const items = dataRows(rows)
    .map(row => {
      const cell = cellAt(row, 0)
      const detail = cell.extra ? `<span class="hv-route-detail">${esc(cell.extra)}</span>` : ''
      return (
        `<li class="hv-route-stop"${hover(`${cell.label} ${cell.value} ${cell.extra}`)}>` +
        `<span class="hv-route-time">${esc(cell.label)}</span>` +
        `<span class="hv-route-body"><span class="hv-route-place">${esc(cell.value)}</span>${detail}</span>` +
        `</li>`
      )
    })
    .join('')

  return `<div class="hv hv-route"><ol class="hv-route-list">${items}</ol></div>`
}

/** Macros against their targets, in the same `of` form `bars` already draws:
 *  the value, its target and the share are named, so this reuses that renderer. */
function renderNutrition(rows, opts) {
  return renderBars(rows, opts, 'hv-nutrition')
}

/** `when=home away=tournament` -> results and fixtures, grouped by tournament.
 *  A result carries a score; a fixture only a time, so the two read apart. */
function renderMatches(rows) {
  const items = []
  let group = null

  for (const row of dataRows(rows)) {
    const cell = cellAt(row, 0)
    if (cell.extra && cell.extra !== group) {
      group = cell.extra
      items.push(`<li class="hv-match-group">${esc(group)}</li>`)
    }
    const teams = cell.value || cell.label
    const scored = /\d+\s*[-\u2013]\s*\d+/.test(teams)
    const body = scored
      ? esc(teams).replace(/(\d+)\s*[-\u2013]\s*(\d+)/, '<span class="hv-match-score">$1\u2013$2</span>')
      : esc(teams)
    items.push(
      `<li class="hv-match hv-match--${scored ? 'result' : 'fixture'}"${hover(`${cell.label} ${teams}`)}>` +
      `<span class="hv-match-when">${esc(cell.label)}</span>` +
      `<span class="hv-match-teams">${body}</span>` +
      `</li>`
    )
  }

  return `<div class="hv hv-matches"><ul class="hv-match-list">${items.join('')}</ul></div>`
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
          `${flagged ? hover(`${name}: did not win ${rounds[i - 1].round}`) : ''}>${esc(name)}</span>`
        )
      }

      const pairings = entry.pairings
        .map(pair =>
          `<div class="hv-bracket-match">` +
          side(pair.winner, 'win') +
          (pair.loser ? `<span class="hv-bracket-gt" aria-hidden="true">\u203a</span>` : '') +
          side(pair.loser, 'lose') +
          `</div>`
        )
        .join('')

      const flagged = [...new Set(bad)]
      const note = flagged.length
        ? `<div class="hv-bracket-inconsistent"><span class="hv-bracket-flag" aria-hidden="true">\u2717</span>` +
          `${esc(flagged.join(', '))} did not win ${esc(rounds[i - 1].round)}</div>`
        : ''

      return (
        `<div class="hv-bracket-round${flagged.length ? ' hv-bracket-round--bad' : ''}">` +
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
    .map(row => {
      const cell = cellAt(row, 0)
      const source = cell.label
      const gloss = cell.value
      const note = cell.extra
      if (!source && !gloss) return ''

      const src = source ? source.split(/\s+/).filter(Boolean) : []
      const gls = gloss ? gloss.split(/\s+/).filter(Boolean) : []
      const noteTag = note ? `<span class="hv-gloss-note">${esc(note)}</span>` : ''
      const detail = `${source}${gloss ? ` = ${gloss}` : ''}${note ? ` (${note})` : ''}`

      // Same word count -> interlinear columns, source over gloss.
      if (src.length && src.length === gls.length) {
        const columns = src
          .map((text, i) => `<span class="hv-gloss-col">${word(text, 'src')}${word(gls[i], 'word')}</span>`)
          .join('')
        return (
          `<div class="hv-gloss-row"${hover(detail)}>` +
          `<span class="hv-gloss-aligned">${columns}</span>${noteTag}</div>`
        )
      }

      // Counts differ (or there is no gloss at all): shown unaligned, and the
      // mismatch is named rather than hidden.
      return (
        `<div class="hv-gloss-row hv-gloss-row--unaligned"${hover(detail)}>` +
        `<span class="hv-gloss-unaligned">${word(source, 'src')}${gloss ? word(gloss, 'word') : ''}</span>` +
        (gloss ? `<span class="hv-gloss-mismatch">${src.length} vs ${gls.length} words</span>` : '') +
        noteTag +
        `</div>`
      )
    })
    .join('')

  return `<div class="hv hv-gloss">${items}</div>`
}

/** `h=person|singular|plural;…` -> a paradigm grid: header names the axes, each
 *  row is one form. A grid of cells, not a table — like `parts`, a paradigm. */
function renderForms(rows) {
  const list = Array.isArray(rows) ? rows.filter(Boolean) : []
  const header = list.find(row => row.header)
  const body = list.filter(row => !row.header)
  const cols = Math.max(1, header ? header.cells.length : Math.max(1, ...body.map(row => row.cells.length)))

  const cells = []
  if (header) {
    header.cells.forEach((cell, i) => {
      cells.push(
        `<span class="hv-form-cell hv-form-head${i === 0 ? ' hv-form-axis' : ''}">${esc(cellText(cell))}</span>`
      )
    })
  }
  body.forEach(row => {
    row.cells.forEach((cell, i) => {
      cells.push(`<span class="hv-form-cell${i === 0 ? ' hv-form-label' : ''}">${esc(cellText(cell))}</span>`)
    })
  })

  return (
    `<div class="hv hv-forms" style="grid-template-columns:repeat(${cols}, minmax(0, 1fr))">` +
    `${cells.join('')}</div>`
  )
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
      return renderSteps(list, opts)
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
    default:
      return renderSparkline(list, opts)
  }
}

/** Attrs -> the whole widget: caption, then one grid holding the kind's cells. */
function renderWidget(attrs) {
  const spec = parseSpec(attrs)
  const opts = { unit: spec.unit, source: attrs && typeof attrs.source === 'string' ? attrs.source : '' }
  // A section carries its own heading band, so it never gets the caption too.
  const title = spec.title && spec.kind !== 'section' ? `<div class="hv-title">${esc(spec.title)}</div>` : ''
  const inner =
    spec.kind === 'board'
      ? renderKind('board', boardEntries(attrs && attrs.d), opts)
      : spec.kind === 'section'
        ? renderSection({ title: spec.title, lead: clean(attrs && attrs.d), level: spec.level, source: opts.source })
        : renderKind(spec.kind, spec.rows, opts)

  // A board IS the grid that spans the pane — its cells are the measured parts.
  // Every other kind is one widget whose content the measure caps.
  const body = spec.kind === 'board' ? inner : `<div class="hv-grid">${inner}</div>`

  return (
    `<div class="hv hv-widget" data-kind="${esc(spec.kind || 'unknown')}">` +
    `${title}${body}` +
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
 * by `--hv-measure` (42rem) — the rule the earlier "no max-width anywhere"
 * test encoded was overridden by the user, who asked for exactly this: a table
 * whose columns are sized by content instead of stretched, so info is not flung
 * far apart on a wide pane. Padding is per widget and per side: 14/16px at the
 * base, 20/24px from 48rem. Nothing may touch the widget's own edge.
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
  --hv-pad-y: 14px;
  --hv-pad-x: 16px;
  color: var(--foreground);
  font-size: 0.8125rem;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
  padding: var(--hv-pad-y) var(--hv-pad-x);
}
@media (min-width: 48rem) {
  .hv-widget { --hv-pad-y: 20px; --hv-pad-x: 24px; }
}
.hv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: 0.6rem; max-width: var(--hv-measure); }
/* One vertical rhythm between board entries — clearly wider than the ~0.6rem
 * gap inside a widget, so several kinds read as one composed thing instead of a
 * single undifferentiated stack. Entries keep their own height (align-items:start).
 * The measure is untouched; the column count follows the entry count. */
/* The count is the chosen part: each track is at least (pane - gaps) / --hv-cols,
 * so at most that many columns fit, while the 24rem floor keeps the pane's own
 * reflow. The gaps are subtracted so the last column is not pushed off by them.
 * No width is ever chosen. */
.hv-board { grid-template-columns: repeat(auto-fit, minmax(max(24rem, calc((100% - (var(--hv-cols) - 1) * 0.75rem) / var(--hv-cols))), 1fr)); gap: 0.75rem; row-gap: 1.4rem; align-items: start; max-width: none; }
.hv-title { margin: 0 0 0.6rem; max-width: var(--hv-measure); color: var(--color-muted-foreground); font-size: 0.8125rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
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
.hv-section { display: flex; flex-direction: column; gap: 0.5rem; max-width: var(--hv-measure); }
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
.hv-change-bar { display: flex; }
.hv-change-add, .hv-change-del { display: block; height: 100%; }
.hv-change-add { background: var(--hv-3); }
.hv-change-del { background: var(--hv-6); }
.hv-change-counts { gap: 0.5rem; }
.hv-add { color: var(--hv-3); font-weight: 600; }
.hv-del { color: var(--hv-6); font-weight: 600; }
.hv-change-total { display: flex; justify-content: flex-end; gap: 0.6rem; padding-top: 0.35rem; border-top: 1px solid var(--dt-border); }
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
/* The palette classes, applied by first-seen order. Last in the sheet so a
 * category hue overrides the single-accent default. */
.hv-c0 { stroke: var(--hv-1); background: var(--hv-1); }
.hv-c1 { stroke: var(--hv-2); background: var(--hv-2); }
.hv-c2 { stroke: var(--hv-3); background: var(--hv-3); }
.hv-c3 { stroke: var(--hv-4); background: var(--hv-4); }
.hv-c4 { stroke: var(--hv-5); background: var(--hv-5); }
.hv-c5 { stroke: var(--hv-6); background: var(--hv-6); }
@keyframes hv-rise { from { opacity: 0; transform: translateY(0.35rem); } to { opacity: 1; transform: translateY(0); } }
@keyframes hv-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.hv-kpi-tile, .hv-row, .hv-prog, .hv-step, .hv-legend-item, .hv-table tbody tr, .hv-check, .hv-outline-item, .hv-fact, .hv-file, .hv-setting, .hv-tl-item, .hv-metric, .hv-cell, .hv-heat-cell, .hv-section, .hv-section-lead, .hv-wf-row, .hv-word, .hv-route-stop, .hv-match, .hv-gloss-row, .hv-bracket-round { animation: hv-rise 0.5s cubic-bezier(0.22, 1.12, 0.36, 1) backwards; }
.hv-bar-fill, .hv-fill, .hv-range-span, .hv-change-add, .hv-change-del, .hv-wf-block { animation: hv-grow 0.7s cubic-bezier(0.22, 1.12, 0.36, 1) 0.06s backwards; }
.hv-donut-svg, .hv-line .hv-svg, .hv-sparkline .hv-svg, .hv-candlestick .hv-svg { animation: hv-rise 0.6s cubic-bezier(0.22, 1.12, 0.36, 1) backwards; }
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
    l: attrs ? attrs.l : '',
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
