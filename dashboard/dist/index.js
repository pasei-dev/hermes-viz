/*
 * hermes-viz dashboard bundle — the settings page, hand-written (no build step).
 *
 * Mirrors the pasei-delegation dashboard's shape: one IIFE that resolves the host globals
 * (window.__HERMES_PLUGIN_SDK__ / window.__HERMES_PLUGINS__), builds the tab component with
 * React.createElement, and registers it under the manifest name. Nothing here imports React or the
 * API client — the host injects both, so a second copy can never drift from the app's singletons.
 *
 * Design rule for this page: no control is a bare text field and no switch is a name on its own.
 *   - every rule group is a labelled toggle with a one-line, plain-language blurb of what it draws
 *     and a live sample rendered from the plugin's own drawing core (GET /settings ships both);
 *   - the groups are folded into four sections ("structuring / numeric charts / cards / diagrams"),
 *     so a wall of 30 switches reads as a few decisions;
 *   - enums are dropdowns (palette) and bounded numbers are bounded dropdowns (max_widgets);
 *   - booleans are toggles whose labels carry their cost (format_guide);
 *   - one column, real spacing, and no decorative rules anywhere — the plugin bans them in a widget
 *     and the settings page will not contradict it.
 *
 * The page is a thin shell: GET /settings returns the schema fields, the palettes, the sections and
 * the rendered samples; every control PUTs one key back into plugins.entries.hermes-viz.settings.
 * No value is hard-coded except the fallback labels shown before the first fetch resolves.
 */
(function () {
  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) {
    return;
  }
  var React = SDK.React;
  var hooks = SDK.hooks || {};
  var useState = hooks.useState;
  var useEffect = hooks.useEffect;
  var useCallback = hooks.useCallback;
  var C = SDK.components || {};
  var h = React.createElement;

  var PLUGIN_NAME = "hermes-viz";
  var API = "/api/plugins/" + PLUGIN_NAME;

  // Prefer the host's authenticated JSON fetch (handles loopback-token / gated-cookie auth);
  // fall back to a plain fetch so the page still works on an older SDK surface.
  function jsonFetch(url, init) {
    if (typeof SDK.fetchJSON === "function") {
      return SDK.fetchJSON(url, init);
    }
    return fetch(url, init).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (body) {
          throw new Error(res.status + ": " + body);
        });
      }
      return res.json();
    });
  }

  // The declared default for a key, from the schema fields the API returns.
  function fieldFor(fields, key) {
    return (fields || []).filter(function (f) { return f.key === key; })[0] || {};
  }

  // The on/off control. The host SDK exposes Checkbox; a newer surface that adds a real Switch is
  // picked up for free, and the row around it never changes.
  var OnOff = C.Switch || C.Toggle || C.Checkbox;

  // Plain-language option labels, because "dark | light | mermaid" names nothing to a reader.
  var PALETTE_LABELS = {
    dark: "Dark \u2014 dark-headed diagrams",
    light: "Light \u2014 light-headed diagrams",
    mermaid: "Follow the app \u2014 leave Mermaid's own dark/light alone"
  };

  function Message(props) {
    if (!props.text) {
      return null;
    }
    return h(
      C.Badge,
      { variant: props.error ? "destructive" : "secondary", className: "self-start" },
      props.text
    );
  }

  /* A heading + one line, used for every setting so nothing is a control with no explanation. */
  function FieldShell(props) {
    return h(
      "div",
      { className: "grid gap-1.5" },
      h(
        "div",
        { className: "flex items-baseline gap-2 flex-wrap" },
        h("span", { className: "text-sm font-medium" }, props.title),
        props.badge || null
      ),
      props.blurb ? h("p", { className: "text-xs text-muted-foreground leading-snug max-w-[60ch]" }, props.blurb) : null,
      props.children
    );
  }

  /* One setting row: the control, its name, its one-line meaning, and (where the core drew one) a
   * live sample of the group. `sample` is markup from desktop/render/core.mjs, shipped as data. */
  function ToggleRow(props) {
    var group = props.group;
    var busy = props.busy;
    var sample = group.sample
      // Trusted: this markup is rendered at build time from the plugin's own pure core
      // (desktop/render/core.mjs) by dashboard/make_samples.mjs and shipped as data — no request or
      // user input reaches it, and selfcheck.py fails if it drifts from the core.
      ? h("div", {
          className:
            "hv-sample hidden md:block shrink-0 w-80 self-start overflow-hidden rounded-md bg-muted/40 p-3",
          "aria-hidden": "true",
          dangerouslySetInnerHTML: { __html: group.sample }
        })
      : h(
          "div",
          {
            className:
              "hidden md:flex shrink-0 w-80 self-start items-center justify-center rounded-md bg-muted/40 p-3 text-xs text-muted-foreground"
          },
          "Drawn by Mermaid"
        );

    return h(
      "div",
      { className: "flex items-start gap-5 py-4" },
      h(
        "div",
        { className: "flex items-start gap-3 flex-1 min-w-0" },
        h(OnOff, {
          className: "mt-0.5",
          checked: group.active,
          onCheckedChange: function (on) { props.onToggle(on === true); },
          disabled: busy,
          "aria-label": group.title
        }),
        h(
          "div",
          { className: "grid gap-1 min-w-0" },
          h(
            "div",
            { className: "flex items-baseline gap-2 flex-wrap" },
            h("span", { className: "text-sm font-medium" }, group.title),
            h(
              "span",
              { className: "font-mono text-[11px] text-muted-foreground" },
              group.id + " \u00b7 " + group.rules + (group.rules === 1 ? " rule" : " rules")
            )
          ),
          h(
            "p",
            { className: "text-xs text-muted-foreground leading-snug max-w-[60ch]" },
            group.blurb || "No description yet."
          )
        )
      ),
      sample
    );
  }

  function SectionBlock(props) {
    var section = props.section;
    var on = section.groups.filter(function (g) { return g.active; }).length;
    var total = section.groups.length;

    return h(
      C.Card,
      null,
      h(
        C.CardHeader,
        { className: "flex flex-row items-start justify-between gap-3" },
        h(
          "div",
          { className: "grid gap-1" },
          h("div", { className: "flex items-baseline gap-2 flex-wrap" },
            h(C.CardTitle, { className: "text-base" }, section.title),
            h(C.Badge, { variant: "secondary" }, on + " of " + total + " on")
          ),
          section.blurb
            ? h("p", { className: "text-xs text-muted-foreground leading-snug max-w-[70ch]" }, section.blurb)
            : null
        ),
        h(
          "div",
          { className: "flex items-center gap-2 shrink-0" },
          h(
            C.Button,
            {
              variant: "outline",
              size: "sm",
              disabled: props.busy || on === total,
              onClick: function () { props.onAll(section.groups, true); }
            },
            "All on"
          ),
          h(
            C.Button,
            {
              variant: "outline",
              size: "sm",
              disabled: props.busy || on === 0,
              onClick: function () { props.onAll(section.groups, false); }
            },
            "All off"
          )
        )
      ),
      h(
        C.CardContent,
        { className: "grid gap-0" },
        section.groups.map(function (g) {
          return h(ToggleRow, {
            key: g.id,
            group: g,
            busy: props.busy,
            onToggle: function (on) { props.onToggle(g, on); }
          });
        })
      )
    );
  }

  function SettingsPage() {
    var _state = useState(null);
    var state = _state[0];
    var setState = _state[1];

    var _error = useState("");
    var error = _error[0];
    var setError = _error[1];

    var _notice = useState("");
    var notice = _notice[0];
    var setNotice = _notice[1];

    var _busy = useState("");
    var busy = _busy[0];
    var setBusy = _busy[1];

    var load = useCallback(function () {
      return jsonFetch(API + "/settings")
        .then(function (data) {
          setState(data);
          setError("");
        })
        .catch(function (exc) {
          setError(String((exc && exc.message) || exc));
        });
    }, []);

    useEffect(function () {
      load();
    }, [load]);

    var write = useCallback(function (key, value) {
      setBusy(key);
      setError("");
      setNotice("");
      return jsonFetch(API + "/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: key, value: value })
      })
        .then(function (data) {
          setState(data);
          setNotice(key + " saved");
        })
        .catch(function (exc) {
          setError(String((exc && exc.message) || exc));
        })
        .then(function () {
          setBusy("");
        });
    }, []);

    if (!state) {
      return h(
        C.Card,
        null,
        h(C.CardHeader, null, h(C.CardTitle, null, "Visuals")),
        h(
          C.CardContent,
          { className: "grid gap-3" },
          h("p", { className: "text-sm text-muted-foreground" }, error || "Loading settings\u2026"),
          error ? h(C.Button, { onClick: load }, "Retry") : null
        )
      );
    }

    var current = state.current || {};
    var fields = state.fields || [];
    var sections = state.sections || [];
    var groups = state.groups || [];
    var activeCount = groups.filter(function (g) { return g.active; }).length;

    var paletteField = fieldFor(fields, "palette");
    var widgetsField = fieldFor(fields, "max_widgets");
    var guideField = fieldFor(fields, "format_guide");
    var widgetCeiling = state.max_widgets_ceiling || 10;
    var widgetOptions = [];
    for (var n = 0; n <= widgetCeiling; n++) { widgetOptions.push(n); }

    // rules.yaml decides the order, so the rewritten value keeps the declared group sequence
    // regardless of click order.
    function applyGroups(nextActive) {
      var ordered = groups
        .filter(function (g) { return nextActive.indexOf(g.id) !== -1; })
        .map(function (g) { return g.id; });
      write("rule_groups", ordered.join(","));
    }

    function activeIds() {
      return groups.filter(function (g) { return g.active; }).map(function (g) { return g.id; });
    }

    function toggleGroup(group, on) {
      var ids = activeIds();
      var at = ids.indexOf(group.id);
      if (on && at === -1) { ids.push(group.id); }
      if (!on && at !== -1) { ids.splice(at, 1); }
      applyGroups(ids);
    }

    function setSection(sectionGroups, on) {
      var ids = activeIds();
      sectionGroups.forEach(function (g) {
        var at = ids.indexOf(g.id);
        if (on && at === -1) { ids.push(g.id); }
        if (!on && at !== -1) { ids.splice(at, 1); }
      });
      applyGroups(ids);
    }

    return h(
      "div",
      { className: "grid gap-6 max-w-[74rem]" },

      // The samples need the core's own CSS, which the dashboard surface does not carry. One style
      // tag, shipped with the samples so the two can never drift apart.
      state.samples_css ? h("style", { dangerouslySetInnerHTML: { __html: state.samples_css } }) : null,

      // ── header ────────────────────────────────────────────────────────────
      h(
        "div",
        { className: "grid gap-1.5" },
        h(
          "div",
          { className: "flex items-center gap-2 flex-wrap" },
          h("h2", { className: "text-lg font-semibold" }, "Visuals"),
          h(C.Badge, { variant: "secondary" }, activeCount + " of " + groups.length + " groups on"),
          h(C.Badge, { variant: "secondary" }, state.settings_path)
        ),
        h(
          "p",
          { className: "text-sm text-muted-foreground leading-snug max-w-[80ch]" },
          "Widgets inside Hermes answers. The plugin reads the markdown an answer already contains and draws what it finds; nothing here is spent on a request unless you switch the format guide on."
        )
      ),

      h(Message, { text: error, error: true }),
      h(Message, { text: notice }),

      // ── answer formatting (the non-group settings) ──────────────────────────
      h(
        C.Card,
        null,
        h(
          C.CardHeader,
          { className: "grid gap-1" },
          h(C.CardTitle, { className: "text-base" }, "Answer formatting"),
          h(
            "p",
            { className: "text-xs text-muted-foreground leading-snug max-w-[70ch]" },
            "The three settings that shape every answer, before any rule group below is consulted."
          )
        ),
        h(
          C.CardContent,
          { className: "grid gap-5" },

          // format guide — a toggle whose label states its cost
          h(
            "div",
            { className: "flex items-start gap-3 py-1" },
            h(OnOff, {
              className: "mt-0.5",
              checked: current.format_guide === true,
              onCheckedChange: function (on) { write("format_guide", on === true); },
              disabled: busy === "format_guide",
              "aria-label": guideField.label || "Answer format guide"
            }),
            h(
              FieldShell,
              {
                title: guideField.label || "Answer format guide",
                badge: h(C.Badge, { variant: "outline" }, "costs \u2248 260 tokens per request"),
                blurb: guideField.description
              }
            )
          ),

          // palette — a dropdown, never free text
          h(
            FieldShell,
            {
              title: paletteField.label || "Diagram palette",
              badge: h(C.Badge, { variant: "secondary" }, current.palette || "dark"),
              blurb: paletteField.description
            },
            h(
              C.Select,
              {
                value: current.palette,
                onValueChange: function (v) { write("palette", v); },
                disabled: busy === "palette",
                className: "w-80 max-w-full"
              },
              (state.palettes || []).map(function (p) {
                return h(C.SelectOption, { key: p, value: p }, PALETTE_LABELS[p] || p);
              })
            )
          ),

          // widget cap — a bounded dropdown, never a free number
          h(
            FieldShell,
            {
              title: widgetsField.label || "Widgets per answer",
              badge:
                widgetsField.default !== undefined
                  ? h(C.Badge, { variant: "secondary" }, "default " + widgetsField.default)
                  : null,
              blurb: widgetsField.description
            },
            h(
              C.Select,
              {
                value: String(current.max_widgets != null ? current.max_widgets : widgetsField.default),
                onValueChange: function (v) { write("max_widgets", Number(v)); },
                disabled: busy === "max_widgets",
                className: "w-80 max-w-full"
              },
              widgetOptions.map(function (n) {
                var label = n + (n === 1 ? " widget" : " widgets");
                if (n === 0) { label = "0 \u2014 draw nothing"; }
                if (widgetsField.default === n && n !== 0) { label = n + " widgets (default)"; }
                return h(C.SelectOption, { key: n, value: String(n) }, label);
              })
            )
          )
        )
      ),

      // ── the rule groups, folded into their sections ─────────────────────────
      sections.length === 0
        ? h(
            C.Card,
            null,
            h(C.CardHeader, null, h(C.CardTitle, { className: "text-base" }, "Rule groups")),
            h("p", { className: "text-sm text-muted-foreground" }, "No rule groups found in rules.yaml.")
          )
        : sections.map(function (section) {
            return h(SectionBlock, {
              key: section.id,
              section: section,
              busy: !!busy,
              onToggle: toggleGroup,
              onAll: setSection
            });
          }),

      // ── provenance ────────────────────────────────────────────────────────
      h(
        "div",
        { className: "grid gap-1 text-xs text-muted-foreground" },
        h("span", null, "Store: " + state.settings_path),
        h("span", null, "Rules: " + state.rules_path),
        h("span", null, "Config: " + state.config_path),
        h(
          C.Button,
          { variant: "outline", size: "sm", className: "self-start mt-2", onClick: load, disabled: !!busy },
          "Reload"
        )
      )
    );
  }

  window.__HERMES_PLUGINS__.register(PLUGIN_NAME, SettingsPage);
})();
