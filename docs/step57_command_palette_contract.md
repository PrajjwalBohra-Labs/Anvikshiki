# Step 57 — Command Palette Contract

## Specification discovery

Git history contains commit `d8ca9ce` (`Added Command palette`) with a
command palette for an earlier JavaScript application. That application and
its component routes are not part of the current typed frontend, so its
implementation cannot be copied directly. Its supported interaction contract
is retained: a global Ctrl/Cmd+K shortcut, an explicit sidebar trigger,
searchable real destinations, deterministic results, keyboard navigation,
Enter execution, and Escape dismissal.

The current application has no other command registry or command API. The
current Step 57 contract therefore maps only existing authenticated routes to
commands. Commands perform navigation through the existing `navigate` helper;
they do not add backend behavior or persistence.

## Registry

The registry is centralized in `frontend/src/commands/registry.ts`. Each
command has a stable ID, label, keywords, icon, and existing route. Registry
order is the deterministic default and filtered order.

Available commands are Research, New research, Research runs, Questions,
Sources, Documents, Memory, Knowledge graph, Notebook, Dialogue, and Settings.

## Interaction and accessibility

Ctrl+K and Cmd+K toggle the palette. Opening focuses the search field. Arrow
Up/Down (and Home/End) move the selected option, Enter executes it, and Escape
closes the dialog. The palette uses dialog, combobox, listbox, and option
semantics with visible focus and a no-results status.

The command palette is available only inside the existing authenticated app
boundary. It does not expose credentials, internal paths, or administrative
actions. No database migration or dependency is required.
