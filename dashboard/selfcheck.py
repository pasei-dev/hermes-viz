#!/usr/bin/env python3
"""Self-check for the hermes-viz dashboard — the delegation dashboard has no equivalent, so this was
written for this page (the brief's "if it has no check, write one small one").

Runs on system python3 (3.9): stdlib only, no fastapi/import of the plugin API. It compiles the
backend for syntax, AST-scans it for the two routes, validates the manifest, checks that every rule
group in rules.yaml is *named and explained* in groups.json and *has a sample* where one can be drawn,
and — when node is on PATH — re-renders the samples from the drawing core (drift guard) and checks the
bundle parses and registers under the manifest name.

    python3 hermes-viz/dashboard/selfcheck.py
"""

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_DIR = HERE.parent
RULES_PATH = PLUGIN_DIR / "rules.yaml"
GROUPS_PATH = HERE / "groups.json"
SAMPLES_PATH = HERE / "samples.json"

failures = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ((" — " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:  # noqa: BLE001 — the message is the point
        return None, str(exc)


def group_ids_in_rules():
    """The distinct `group:` values in rules.yaml, in declaration order — the shape the page renders."""
    if not RULES_PATH.is_file():
        return []
    ids = []
    for line in RULES_PATH.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*group:\s*([A-Za-z0-9_.-]+)\s*$", line)
        if match and match.group(1) not in ids:
            ids.append(match.group(1))
    return ids


def main():
    print("hermes-viz dashboard self-check")

    # manifest ─────────────────────────────────────────────────────────────────
    manifest, err = load_json(HERE / "manifest.json")
    if manifest is None:
        check("manifest.json parses", False, err)
        manifest = {}
    else:
        check("manifest.json parses", True)
    for key in ("name", "label", "description", "entry", "api", "tab"):
        check("manifest has %r" % key, key in manifest)
    check("manifest name is hermes-viz", manifest.get("name") == "hermes-viz", repr(manifest.get("name")))
    check("manifest declares an api", "api" in manifest)

    entry = HERE / str(manifest.get("entry") or "")
    api = HERE / str(manifest.get("api") or "")
    check("entry file exists", entry.is_file(), str(entry))
    check("api file exists", api.is_file(), str(api))

    # version guard ────────────────────────────────────────────────────────────
    # The app keys a plugin's dashboard bundle on the version, so a manifest and
    # plugin.yaml that disagree is how a settings page keeps serving the old page
    # after the code changed. Both must carry one, non-empty, identical value.
    plugin_yaml = PLUGIN_DIR / "plugin.yaml"
    plugin_text = plugin_yaml.read_text(encoding="utf-8") if plugin_yaml.is_file() else ""
    match = None
    if plugin_text:
        match = re.search(r'^version:\s*["\']?([^"\'\s#]+)', plugin_text, re.M)
    plugin_version = match.group(1) if match else ""
    manifest_version = str(manifest.get("version") or "").strip()
    check("plugin.yaml declares a version", bool(plugin_version), repr(plugin_version))
    check("manifest.json declares a version", bool(manifest_version), repr(manifest_version))
    check("plugin.yaml and manifest.json versions agree",
          bool(plugin_version) and plugin_version == manifest_version,
          "plugin.yaml=%r manifest.json=%r" % (plugin_version, manifest_version))

    # no config_schema ─────────────────────────────────────────────────────────
    # The app folds an agent plugin's schema form under the plugin's own Settings
    # page whenever the manifest declares `config_schema`. The plugin declares
    # none: it owns its own definitions in dashboard/settings.json, so there is
    # no auto-generated "Agent settings" sub-page to fold.
    check("plugin.yaml carries no config_schema", "config_schema" not in plugin_text)

    # body_style reaches into the host app's DOM, so it is unverifiable here and
    # ships off; its description has to say both plainly.
    _body_desc = ""
    _defs, _ = load_json(HERE / "settings.json")
    if isinstance(_defs, dict):
        _body_desc = str(((_defs.get("settings") or {}).get("body_style") or {}).get("description") or "")
    check("body_style says it is unverifiable in CI", "CI" in _body_desc)
    check("body_style says it styles the host app's DOM", "DOM" in _body_desc)

    definitions, err = load_json(HERE / "settings.json")
    if definitions is None:
        check("dashboard/settings.json parses", False, err)
        definitions = {}
    else:
        check("dashboard/settings.json parses", True)
    declared = (definitions.get("settings") or {}) if isinstance(definitions, dict) else {}

    # The backend ──────────────────────────────────────────────────────────────
    api_src = api.read_text(encoding="utf-8") if api.is_file() else ""
    try:
        tree = ast.parse(api_src, filename=str(api))
        check("plugin_api.py parses", True)
    except SyntaxError as exc:
        tree = None
        check("plugin_api.py parses", False, str(exc))

    if tree is not None:
        routes = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if isinstance(dec.func.value, ast.Name) and dec.func.value.id == "router":
                            if dec.args and isinstance(dec.args[0], ast.Constant):
                                routes.add((dec.func.attr, dec.args[0].value))
        check("declares GET /settings", ("get", "/settings") in routes, repr(sorted(routes)))
        check("declares PUT /settings", ("put", "/settings") in routes)
        check("reads the plugin settings store", "plugins.entries." in api_src and "settings" in api_src)
        check("derives rule groups from rules.yaml", "rules.yaml" in api_src)
        check("writes through the low-level plugin writer", "save_plugin_setting(" in api_src)
        check("does not gate writes on a manifest schema", "save_plugin_settings" not in api_src)
        check("reads its own settings definitions", "settings.json" in api_src)
        check("reads the per-group notes", "groups.json" in api_src)
        check("reads the rendered samples", "samples.json" in api_src)
        check("folds groups into named sections", "_sections" in api_src)
        check("accepts the format_guide toggle", "format_guide" in api_src)
        check("validates against the declared definitions", "_coerce" in api_src and "_definitions" in api_src)

    # the plugin's own definitions ─────────────────────────────────────────────
    expected = {"palette", "max_widgets", "rule_groups", "format_guide", "body_style"}
    check("settings.json declares the five settings", set(declared) == expected, repr(sorted(declared)))
    check("every setting has a label", all(str(spec.get("label") or "").strip() for spec in declared.values()))
    check("every setting carries a default", all("default" in spec for spec in declared.values()))
    check("max_widgets declares its bounds", all(
        isinstance(declared.get("max_widgets"), dict) and name in declared["max_widgets"]
        for name in ("min", "max")))
    check("palette declares its choices",
          bool((declared.get("palette") or {}).get("choices")))

    # notes: every group named and explained ────────────────────────────────────
    notes, err = load_json(GROUPS_PATH)
    if notes is None:
        check("groups.json parses", False, err)
        notes = {}
    else:
        check("groups.json parses", True)

    categories = [c.get("id") for c in (notes.get("categories") or []) if isinstance(c, dict)]
    check("groups.json declares sections", len(categories) > 0, repr(categories))
    note_groups = notes.get("groups") or {}

    rules_groups = group_ids_in_rules()
    check("rules.yaml exposes rule groups to the page", len(rules_groups) > 0, repr(rules_groups))

    unnamed, unexplained, unplaced, bad_category = [], [], [], []
    for gid in rules_groups:
        note = note_groups.get(gid)
        if not isinstance(note, dict):
            unnamed.append(gid)
            continue
        if not str(note.get("title") or "").strip():
            unnamed.append(gid)
        if not str(note.get("blurb") or "").strip():
            unexplained.append(gid)
        if not str(note.get("category") or "").strip():
            unplaced.append(gid)
        elif note.get("category") not in categories:
            bad_category.append(gid)
    check("every group has a visible title", not unnamed, repr(unnamed))
    check("every group has a one-line explanation", not unexplained, repr(unexplained))
    titles = [str((note_groups.get(gid) or {}).get("title") or "").strip() for gid in rules_groups]
    dupes = sorted({t for t in titles if t and titles.count(t) > 1})
    check("no two groups share a title", not dupes, repr(dupes))
    check("every group sits in a declared section", not unplaced, repr(unplaced))
    check("every group's section exists", not bad_category, repr(bad_category))
    check("no note describes a group rules.yaml does not have",
          not [g for g in note_groups if g not in rules_groups],
          repr([g for g in note_groups if g not in rules_groups]))

    # samples: rendered from the core, one per group where the core can draw it ─
    samples, err = load_json(SAMPLES_PATH)
    if samples is None:
        check("samples.json parses", False, err)
        samples = {}
    else:
        check("samples.json parses", True)
    markup = samples.get("markup") or {}
    check("samples.json carries the core stylesheet", bool(str(samples.get("css") or "").strip()))
    check("samples.json is generated, not hand-edited",
          "core.mjs" in str(samples.get("_about") or ""))

    missing = []
    for gid, note in note_groups.items():
        if isinstance(note, dict) and note.get("sample") and gid not in markup:
            missing.append(gid)
    check("every drawable group has a rendered sample", not missing, repr(missing))
    check("every sample is non-empty markup",
          all(str(v).strip() for v in markup.values()), repr([k for k, v in markup.items() if not str(v).strip()]))

    # bundle ───────────────────────────────────────────────────────────────────
    bundle = entry.read_text(encoding="utf-8") if entry.is_file() else ""
    name = manifest.get("name", "")
    check("bundle registers under the manifest name",
          "register(" in bundle and ('"' + name + '"') in bundle)
    check("bundle targets the plugin API base", "/api/plugins/" in bundle)
    check("bundle resolves the host SDK global", "window.__HERMES_PLUGIN_SDK__" in bundle)
    check("bundle renders the named sections", "sections" in bundle)
    check("bundle exposes the format_guide toggle", "format_guide" in bundle)
    check("bundle exposes the body_style toggle", "body_style" in bundle)
    check("bundle shows a per-group sample", "sample" in bundle and "hv-sample" in bundle)
    check("no setting is a bare text field (toggles & dropdowns only)",
          "C.Input" not in bundle, "C.Input is present" if "C.Input" in bundle else "")
    check("groups are toggles, not text", "onCheckedChange" in bundle)
    check("enums and bounded numbers are dropdowns", bundle.count("SelectOption") >= 2)
    check("bundle has a group filter input", 'type: "search"' in bundle)
    check("sections collapse and expand", "onToggleCollapse" in bundle)

    node = shutil.which("node")
    if node:
        proc = subprocess.run([node, "--check", str(entry)], capture_output=True, text=True)
        check("bundle passes `node --check`", proc.returncode == 0, proc.stderr.strip()[:200])

        gen = HERE / "make_samples.mjs"
        if gen.is_file():
            proc = subprocess.run([node, str(gen), "--check"], capture_output=True, text=True, cwd=str(PLUGIN_DIR))
            detail = (proc.stdout + proc.stderr).strip().splitlines()
            check("samples.json matches the drawing core", proc.returncode == 0,
                  detail[0] if detail else "")
        else:
            check("dashboard/make_samples.mjs exists", False)
    else:
        print("  SKIP  node checks (node not on PATH)")

    print()
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("All dashboard checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
