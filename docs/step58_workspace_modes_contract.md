# Step 58 — Workspace Modes Contract

## Specification discovery

An exhaustive search of the current repository, reachable history, and prior
frontend implementations found no authoritative Step 58 specification or
workspace-mode implementation. The old JavaScript workspace and command
palette code does not define modes for the current typed application.

This document establishes the smallest Step 58 contract supported by the
current architecture. It is a new project contract, not a reconstruction of a
missing historical requirement.

## Contract

Workspace modes are transient, route-derived shell composition contexts. They
mirror the four navigation groups already present in
`frontend/src/components/shell/AnvikshikiShell.tsx`:

| Mode | Existing destinations | Default route |
| --- | --- | --- |
| Investigation | Research, research runs, questions | `/research` |
| Library | Library, sources, documents | `/library/sources` |
| Knowledge | Memory, knowledge graph, notebook, dialogue | `/memory` |
| System | Settings | `/settings` |

The route remains the source of truth. Selecting a mode navigates to its
existing default route and shows that mode's existing navigation group. Deep
links derive the appropriate mode from the existing `AppView`; no new URL,
query parameter, or routing system is added.

There is no persistence requirement. Mode selection is intentionally transient
React/UI state represented by the current route. No backend, database,
localStorage, or mode-specific research behavior is introduced.

## Command palette integration

The Step 57 command palette remains global and unchanged. Its existing route
commands remain available inside the authenticated shell. Modes do not add a
second command registry or mode-specific command behavior.

## Accessibility and security

The shell exposes modes as a labelled `tablist` with `tab` buttons and an
`aria-selected` state. Each mode has a visible focusable control and a title
describing its existing destinations. Navigation continues through the
existing authenticated route boundary; no user identifiers, tokens, backend
operations, or resource ownership behavior are changed.

## Verification

Focused tests cover deterministic ordering, route-derived selection, default
route navigation, and mode-specific navigation visibility. Full frontend
tests, typecheck, production build, and browser runtime verification are
recorded in the Step 58 completion report.
