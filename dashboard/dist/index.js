/*
 * hermes-viz dashboard bundle — the settings page, hand-written (no build step).
 *
 * Mirrors the pasei-delegation dashboard's shape: one IIFE that resolves the host globals
 * (window.__HERMES_PLUGIN_SDK__ / window.__HERMES_PLUGINS__), builds the tab component with
 * React.createElement, and registers it under the manifest name. Nothing here imports React or the
 * API client — the host injects both, so a second copy can never drift from the app's singletons.
 *
 * The page is a thin shell: GET /settings returns the schema fields, the palette choices and the
 * rule groups (derived from rules.yaml); every control PUTs one key back. No value is hard-coded
 * except the fallback labels rendered before the first fetch resolves.
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
  function defaultFor(fields, key, fallback) {
    var match = (fields || []).filter(function (f) { return f.key === key; })[0];
    return match && match.default !== undefined ? match.default : fallback;
  }

  function Message(props) {
    if (!props.text) {
      return null;
    }
    var variant = props.error ? "destructive" : "secondary";
    return h(C.Badge, { variant: variant, className: "self-start" }, props.text);
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

    var _draft = useState("");
    var draft = _draft[0];
    var setDraft = _draft[1];

    var load = useCallback(function () {
      return jsonFetch(API + "/settings")
        .then(function (data) {
          setState(data);
          var mw = data.current && data.current.max_widgets;
          setDraft(String(mw != null ? mw : defaultFor(data.fields, "max_widgets", 3)));
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
          error
            ? h(C.Button, { onClick: load }, "Retry")
            : null
        )
      );
    }

    var current = state.current || {};
    var fields = state.fields || [];
    var fieldByKey = {};
    fields.forEach(function (f) {
      fieldByKey[f.key] = f;
    });
    var maxWidgetsField = fieldByKey.max_widgets || {};
    var groups = state.groups || [];
    var activeCount = groups.filter(function (g) { return g.active; }).length;

    function toggleGroup(id, on) {
      // rules.yaml decides the order, so the rewritten value keeps the declared group sequence
      // regardless of click order.
      var ordered = groups
        .filter(function (g) { return g.id === id ? on : g.active; })
        .map(function (g) { return g.id; });
      write("rule_groups", ordered.join(","));
    }

    return h(
      "div",
      { className: "grid gap-4" },

      // ── header ────────────────────────────────────────────────────────────
      h(
        "div",
        { className: "grid gap-1" },
        h(
          "div",
          { className: "flex items-center gap-2" },
          h("h2", { className: "text-lg font-semibold" }, "Visuals"),
          h(C.Badge, { variant: "secondary" }, state.settings_path)
        ),
        h(
          "p",
          { className: "text-sm text-muted-foreground" },
          "Widgets inside answers: the palette baked into derived diagrams, how many may appear per answer, and which rule groups may fire."
        )
      ),

      h(Message, { text: error, error: true }),
      h(Message, { text: notice }),

      // ── palette ───────────────────────────────────────────────────────────
      h(
        C.Card,
        null,
        h(
          C.CardHeader,
          null,
          h(C.CardTitle, { className: "text-base" }, fieldByKey.palette ? fieldByKey.palette.label : "Diagram palette")
        ),
        h(
          C.CardContent,
          { className: "grid gap-3" },
          h(
            "p",
            { className: "text-sm text-muted-foreground" },
            fieldByKey.palette ? fieldByKey.palette.description : ""
          ),
          h(
            C.Select,
            {
              value: current.palette,
              onValueChange: function (v) { write("palette", v); },
              disabled: busy === "palette"
            },
            (state.palettes || []).map(function (p) {
              return h(C.SelectOption, { key: p, value: p }, p);
            })
          )
        )
      ),

      // ── widget cap ────────────────────────────────────────────────────────
      h(
        C.Card,
        null,
        h(
          C.CardHeader,
          null,
          h(C.CardTitle, { className: "text-base" }, maxWidgetsField.label || "Widgets per answer")
        ),
        h(
          C.CardContent,
          { className: "grid gap-3" },
          h(
            "p",
            { className: "text-sm text-muted-foreground" },
            maxWidgetsField.description || ""
          ),
          h(
            "div",
            { className: "flex items-end gap-2" },
            h(
              "div",
              { className: "grid gap-2" },
              h(C.Label, { htmlFor: "hermes-viz-max-widgets" }, "Upper bound"),
              h(C.Input, {
                id: "hermes-viz-max-widgets",
                type: "number",
                min: "0",
                value: draft,
                onChange: function (e) { setDraft(e.target.value); },
                onKeyDown: function (e) {
                  if (e.key === "Enter") { write("max_widgets", Number(draft)); }
                },
                className: "w-32"
              })
            ),
            h(
              C.Button,
              {
                onClick: function () { write("max_widgets", Number(draft)); },
                disabled: busy === "max_widgets" || draft === "" || Number(draft) === current.max_widgets
              },
              "Save"
            ),
            maxWidgetsField.default !== undefined
              ? h(C.Badge, { variant: "secondary" }, "default " + maxWidgetsField.default)
              : null
          )
        )
      ),

      // ── rule groups ───────────────────────────────────────────────────────
      h(
        C.Card,
        null,
        h(
          C.CardHeader,
          { className: "flex flex-row items-center justify-between" },
          h(C.CardTitle, { className: "text-base" }, fieldByKey.rule_groups ? fieldByKey.rule_groups.label : "Active rule groups"),
          h(C.Badge, { variant: "secondary" }, activeCount + " of " + groups.length)
        ),
        h(
          C.CardContent,
          { className: "grid gap-3" },
          h(
            "p",
            { className: "text-sm text-muted-foreground" },
            (fieldByKey.rule_groups ? fieldByKey.rule_groups.description : "") +
              " The groups below are read from rules.yaml \u2014 add a rule with a new group and it appears here."
          ),
          groups.length === 0
            ? h("p", { className: "text-sm text-muted-foreground" }, "No rule groups found in rules.yaml.")
            : h(
                "div",
                { className: "grid gap-2" },
                groups.map(function (g) {
                  return h(
                    "label",
                    {
                      key: g.id,
                      className: "flex items-center gap-2 text-sm cursor-pointer"
                    },
                    h(C.Checkbox, {
                      checked: g.active,
                      onCheckedChange: function (on) { toggleGroup(g.id, on === true); },
                      disabled: busy === "rule_groups"
                    }),
                    h("span", { className: "font-medium" }, g.id),
                    h(
                      "span",
                      { className: "text-muted-foreground" },
                      g.rules + (g.rules === 1 ? " rule" : " rules")
                    )
                  );
                })
              )
        )
      ),

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
