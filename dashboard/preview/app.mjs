/*
 * Preview harness for the hermes-viz settings page.
 *
 * The page is a plugin bundle: it renders nothing without the host's SDK globals and a live API.
 * This file supplies both so the *real* `dashboard/dist/index.js` can be screenshotted — the page's
 * own markup, the page's own classes, and the API payload from `fixture.py`. The components are
 * minimal stand-ins for the host's (the host's real ones live in an un-published design system), but
 * they carry the same roles, labels and Tailwind classes the page targets, so the layout, the
 * hierarchy and the overflow behaviour are the page's, not the harness's.
 *
 * Built by `build.mjs`; loaded by the generated `preview.html`, then `dist/index.js`, then mounted.
 */
import * as React from 'react'
import { createRoot } from 'react-dom/client'

const h = React.createElement

function cn() {
  return Array.prototype.slice.call(arguments).filter(Boolean).join(' ')
}

const Card = ({ className, children }) =>
  h('div', { className: cn('rounded-xl border bg-card text-card-foreground shadow-sm', className) }, children)
const CardHeader = ({ className, children }) => h('div', { className: cn('p-6', className) }, children)
const CardTitle = ({ className, children }) => h('div', { className: cn('font-semibold leading-none tracking-tight', className) }, children)
const CardContent = ({ className, children }) => h('div', { className: cn('p-6 pt-0', className) }, children)
const Badge = ({ className, variant, children }) =>
  h('span', { className: cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', className) }, children)
const Button = ({ className, variant, size, disabled, onClick, children }) =>
  h('button', { type: 'button', className: cn('inline-flex items-center justify-center rounded-md border px-3 py-1.5 text-sm font-medium', className), disabled, onClick }, children)
const Label = ({ className, children, ...rest }) => h('label', { className, ...rest }, children)
const Separator = () => h('div', { className: 'h-px bg-border' })

const Checkbox = ({ checked, onCheckedChange, disabled, className, ...rest }) =>
  h('input', {
    type: 'checkbox',
    className: cn('h-4 w-4', className),
    checked: !!checked,
    disabled: !!disabled,
    onChange: (e) => onCheckedChange && onCheckedChange(e.target.checked),
    ...rest
  })

const Select = ({ value, onValueChange, className, disabled, children }) =>
  h('select', {
    className: cn('h-9 rounded-md border bg-background px-2 text-sm', className),
    value,
    disabled: !!disabled,
    onChange: (e) => onValueChange && onValueChange(e.target.value)
  }, children)

const SelectOption = ({ value, children }) => h('option', { value }, children)

const components = {
  Card, CardHeader, CardTitle, CardContent, Badge, Button, Label, Separator, Checkbox, Select, SelectOption
}

window.__HERMES_PLUGIN_SDK__ = {
  sdkVersion: 'preview',
  React,
  hooks: {
    useState: React.useState,
    useEffect: React.useEffect,
    useCallback: React.useCallback,
    useMemo: React.useMemo,
    useRef: React.useRef
  },
  components,
  fetchJSON: () => Promise.resolve(window.__HV_FIXTURE__)
}

window.__HERMES_PLUGINS__ = {
  register: (name, component) => { window.__HV_PAGE__ = component }
}

window.__HV_MOUNT__ = () => {
  const root = createRoot(document.getElementById('root'))
  root.render(h(window.__HV_PAGE__ || (() => h('p', null, 'page did not register'))))
}
