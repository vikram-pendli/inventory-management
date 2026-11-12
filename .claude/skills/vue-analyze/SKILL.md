---
name: vue-analyze
description: Analyze Vue 3 component structure and suggest performance and code-reuse optimizations. Use when the user asks to analyze, audit, or optimize Vue components, find duplicated code across views, or review component size and reactivity. Read-only: reports findings and does not edit files unless asked.
---

# Vue Component Analysis

Analyze components in `client/src/` and report prioritized, evidence-backed optimizations. This skill only reads and reports. Applying fixes to any `.vue` file must be delegated to the **vue-expert** subagent (project rule).

## Scope

- With an argument (a file or directory), analyze only that target.
- With no argument, analyze `client/src/views/`, `client/src/components/`, and `client/src/App.vue`, plus `composables/` and `utils/` as reuse targets.

## Step 1: Inventory

For each `.vue` file collect, using Grep and Read (do not read whole large files when a search answers it):

- Line count, split into template / script / style
- API style: `<script setup>`, Options-style `setup()`, or Options API
- Props, emits, and child components used
- Reactive state: `ref`, `reactive`, `computed`, `watch`, `watchEffect`
- Data fetching: calls through `client/src/api.js` versus direct `axios`/`fetch`
- Lifecycle hooks and any listeners or timers they create

Present this as a compact table before the findings.

## Step 2: Performance checks

Report only what you can point to by file and line.

| Check | What to look for |
|---|---|
| Template work | Function calls or `.filter/.map/.sort/.reduce` inside `v-for` or interpolations that should be `computed` |
| v-for keys | `:key="index"` or missing keys (project rule: use `sku`, `month`, etc.) |
| v-if with v-for | `v-for` and `v-if` on the same element |
| Over-broad reactivity | Large arrays in deep `ref`/`reactive` that are only replaced, never mutated (candidate for `shallowRef`) |
| Watchers | `watch` that recomputes derived data (should be `computed`); missing cleanup; `deep: true` on large objects; watchers that refetch on unrelated filter changes |
| Fetching | Sequential awaits that could be `Promise.all`; refetch on every mount of cached data; no race protection when params change quickly |
| Leaks | `addEventListener`, `setInterval`, observers without matching removal in `onUnmounted` |
| Render cost | Huge single templates (over about 400 lines) where a subtree could be a child component; heavy list rendering that could use `v-memo` or pagination; inline SVG chart code recomputed on each render |
| Loading | Heavy modals or rarely used views imported eagerly instead of via `defineAsyncComponent` / lazy routes |

Skip micro-optimizations with no measurable effect. Do not recommend `v-memo` or `shallowRef` without naming the specific list or ref and why it qualifies.

## Step 3: Code-reuse checks

- **Duplicated helpers**: the same function (date, currency, cost formatting, status translation) defined in several files. Grep for the names and compare bodies. Note what already exists in `client/src/utils/` and `client/src/composables/` before proposing a new module.
- **Duplicated markup and styles**: repeated stat-card, table, badge, modal-shell, or loading/error blocks. Count occurrences and name the candidate component.
- **Duplicated logic**: repeated fetch-and-filter patterns or loading/error state handling that fits a composable.
- **Inconsistent patterns**: mixed API styles, components bypassing `api.js`, props drilled through more than two levels where a composable already holds the state (for example `useFilters`).
- **Dead code**: components that are never imported or routed, and API client functions with no server route.

For each reuse finding give the number of occurrences, the files, and a proposed name and signature for the shared piece.

## Step 4: Report

Output, in this order:

1. **Summary table**: one row per analyzed file (lines, API style, notable issues count).
2. **Findings**, grouped High / Medium / Low by expected payoff versus effort. Each finding has:
   - Location as `path:line`
   - What is wrong, in one sentence
   - Suggested change, in one or two sentences, with a short snippet only if it is not obvious
   - Type: performance or reuse
3. **Suggested order of work**: at most five steps, highest payoff first, noting which steps change `.vue` files (and so go to vue-expert).

## Rules

- Evidence over opinion: every finding cites a file and line. Drop anything you cannot cite.
- Do not flag something as slow without saying why it costs time at this app's data size (it uses small in-memory mock data); weigh findings accordingly and say so when a fix is for maintainability rather than speed.
- Respect project conventions: no emojis in UI, slate/gray design system, unique `v-for` keys, validate dates before `.getMonth()`.
- Do not edit files. Offer to hand the chosen fixes to vue-expert and, afterward, to code-reviewer.
- Keep the report concise; do not paste large code blocks from the analyzed files.
