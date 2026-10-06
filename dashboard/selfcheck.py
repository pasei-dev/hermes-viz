#!/usr/bin/env python3
"""Self-check for the hermes-viz dashboard — the delegation dashboard has no equivalent, so this was
written for this page (the brief's "if it has no check, write one small one").

Runs on system python3 (3.9): stdlib only, no fastapi/import of the plugin API. It compiles the
backend for syntax, AST-scans it for the two routes, validates the manifest, and — when node is on
PATH — checks the bundle parses and registers under the manifest name.

    python3 hermes-viz/dashboard/selfcheck.py
"""

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
failures = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ((" — " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def main():
    print("hermes-viz dashboard self-check")

    # manifest ─────────────────────────────────────────────────────────────────
    manifest_path = HERE / "manifest.json"
    manifest = {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        check("manifest.json parses", False, str(exc))
    for key in ("name", "label", "description", "entry", "api", "tab"):
        check("manifest has %r" % key, key in manifest)
    check("manifest name is hermes-viz", manifest.get("name") == "hermes-viz", repr(manifest.get("name")))
    check("manifest declares an api", "api" in manifest)

    entry = HERE / str(manifest.get("entry") or "")
    api = HERE / str(manifest.get("api") or "")
    check("entry file exists", entry.is_file(), str(entry))
    check("api file exists", api.is_file(), str(api))

    # backend ──────────────────────────────────────────────────────────────────
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
        check("writes through the shared plugin writer", "save_plugin_settings" in api_src)

    # bundle ───────────────────────────────────────────────────────────────────
    bundle = entry.read_text(encoding="utf-8") if entry.is_file() else ""
    name = manifest.get("name", "")
    check("bundle registers under the manifest name",
          "register(" in bundle and ('"' + name + '"') in bundle)
    check("bundle targets the plugin API base", "/api/plugins/" in bundle)
    check("bundle resolves the host SDK global", "window.__HERMES_PLUGIN_SDK__" in bundle)

    node = shutil.which("node")
    if node:
        proc = subprocess.run([node, "--check", str(entry)], capture_output=True, text=True)
        check("bundle passes `node --check`", proc.returncode == 0, proc.stderr.strip()[:200])
    else:
        print("  SKIP  node --check (node not on PATH)")

    print()
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("All dashboard checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
