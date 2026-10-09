/**
 * Build the settings-page preview: bundle the harness + real page, generate the API fixture, and
 * write a self-contained preview.html. The output lands in `dashboard/preview/.build/` (git-ignored);
 * only this script, app.mjs and fixture.py are committed.
 *
 *   node dashboard/preview/build.mjs
 *
 * React and the app stylesheet come from the local Hermes install (there is no published package to
 * fetch and the harness must not add a dependency). Override with HERMES_HOME if your install is
 * elsewhere.
 */
import { spawnSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const REPO = dirname(dirname(HERE))
const OUT = join(HERE, '.build')

const HERMES_HOME = process.env.HERMES_HOME || join(process.env.HOME || '', '.hermes', 'hermes-agent')
const NODE_MODULES = join(HERMES_HOME, 'node_modules')
// The plugin dashboard renders inside the desktop app, whose compiled Tailwind bundle is the one
// that actually carries the utilities the page targets (the web build purges responsive variants
// like `md:block` it never uses). Prefer it, globbing the hashed filename.
function findAppCss() {
  if (process.env.HERMES_APP_CSS) return process.env.HERMES_APP_CSS
  const assets = join(HERMES_HOME, 'apps', 'desktop', 'dist', 'assets')
  try {
    const candidates = readdirSync(assets)
      .filter((f) => /^index-.*\.css$/.test(f))
      .map((f) => ({ f, size: statSync(join(assets, f)).size }))
      .sort((a, b) => b.size - a.size)
    if (candidates.length) return join(assets, candidates[0].f)
  } catch { /* fall through to the web build */ }
  return join(HERMES_HOME, 'hermes_cli', 'web_dist', 'assets', 'index-ByAWV9qc.css')
}

function die(message) {
  console.error('build.mjs: ' + message)
  process.exit(1)
}

mkdirSync(OUT, { recursive: true })

// 1. the API fixture, straight from the real module ──────────────────────────
// The API composes the format guide through the plugin's root module, so the fixture needs an
// interpreter the plugin itself can run on (3.10+, per AGENTS.md). `python3` on PATH is not always
// one, and a bare `python3` would silently ship a payload with no guide cost. HERMES_PY overrides.
function findPython() {
  const wanted = process.env.HERMES_PY ? [process.env.HERMES_PY] : ['python3', 'python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3.10']
  for (const candidate of wanted) {
    const probe = spawnSync(candidate, ['-c', 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'], { encoding: 'utf8' })
    if (probe.status === 0) return candidate
  }
  die('no Python 3.10+ on PATH for the fixture (set HERMES_PY)')
}

const PYTHON = findPython()
const fixture = spawnSync(PYTHON, [join(HERE, 'fixture.py')], { encoding: 'utf8' })
if (fixture.status !== 0) die('fixture.py failed:\n' + (fixture.stderr || ''))
try {
  if (JSON.parse(fixture.stdout).guide == null) {
    die('fixture.py produced no guide cost — the settings page would show none')
  }
} catch (exc) {
  die('fixture.py did not produce JSON: ' + String((exc && exc.message) || exc))
}
writeFileSync(join(OUT, 'fixture.js'), 'window.__HV_FIXTURE__ = ' + fixture.stdout.trim() + ';\n')

// 2. bundle the harness with React from the local install ───────────────────
const esbuildMain = join(NODE_MODULES, 'esbuild', 'lib', 'main.js')
if (!existsSync(esbuildMain)) die('no esbuild at ' + esbuildMain + ' (set HERMES_HOME)')
const esbuild = (await import('file://' + esbuildMain)).default || (await import('file://' + esbuildMain))
try {
  await esbuild.build({
    entryPoints: [join(HERE, 'app.mjs')],
    bundle: true,
    format: 'iife',
    nodePaths: [NODE_MODULES],
    outfile: join(OUT, 'app.js'),
    logLevel: 'silent'
  })
} catch (exc) {
  die('esbuild failed:\n' + String((exc && exc.message) || exc))
}

// 3. the app stylesheet (Tailwind + theme tokens) ───────────────────────────
const css = findAppCss()
if (css && existsSync(css)) copyFileSync(css, join(OUT, 'app.css'))
else console.warn('build.mjs: no app stylesheet found — the preview will be unstyled')

// 4. preview.html ───────────────────────────────────────────────────────────
const files = ['app.js', 'fixture.js', join('..', '..', 'dist', 'index.js')]
const html = [
  '<!doctype html>',
  '<html lang="en"><head><meta charset="utf-8">',
  '<meta name="viewport" content="width=device-width, initial-scale=1">',
  '<title>hermes-viz settings — preview</title>',
  css ? '<link rel="stylesheet" href="app.css">' : '',
  '<style>',
  // The app applies its theme at runtime; the CSS alone carries the light surface, which is what
  // these tokens resolve to here. Harness-only.
  'body{margin:0;padding:1.5rem;background:var(--dt-background,#f8faff);color:var(--dt-foreground,#141414);}',
  '</style>',
  '</head><body><div id="root"></div>',
  files.map((f) => '<script src="' + f + '"></script>').join('\n'),
  '<script>window.__HV_MOUNT__();</script>',
  '</body></html>',
  ''
].join('\n')
writeFileSync(join(OUT, 'preview.html'), html)

console.log('wrote ' + join(OUT, 'preview.html'))
