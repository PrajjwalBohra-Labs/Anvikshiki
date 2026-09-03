# Step 70 — Frontend integration and design system

## Contract

The frontend is a client of the existing authenticated FastAPI services. Step 70
does not add backend endpoints, persistence, or authorization logic. Research,
evidence, provenance, export, and ownership remain backend-authoritative.

## Integrated surfaces

- Existing research workspace, streamed research activity, evidence search,
  dialogue, research history, claims, and provenance traces remain available.
- Existing source/document ingestion and memory views remain available.
- The provenance graph is available at `/knowledge-graph` and
  `/knowledge-graph/{run_id}` using the existing graph endpoint. Nodes and edges
  are rendered only when returned by the backend; selected nodes expose returned
  metadata.
- Research export is available through the existing export service and is
  downloaded as the backend JSON response.
- `/notebook` is an honest entry surface. Durable notebook persistence is not
  present in this checkout, so the UI does not pretend that client-only notes are
  saved.

## Interaction and visual system

The existing token system uses an obsidian background, layered dark surfaces,
warm archival accents, restrained semantic evidence/interpretation/memory/
validation colors, serif research text, and monospace metadata. Focus rings,
reduced-motion behavior, responsive sidebar navigation, and explicit loading,
empty, error, and unauthorized states are preserved.

The command registry in `frontend/src/components/command/CommandPalette.tsx`
provides deterministic route commands. Ctrl-K/Cmd-K opens an accessible dialog;
Arrow Up/Down changes the selected option, Enter executes it, and Escape closes
it. Commands navigate through the existing router and never bypass API
authorization.

## Verification

Frontend tests, TypeScript, production build, and dependency validation pass.
No browser automation dependency or repository browser harness is present, so
authenticated visual/browser verification remains an environment limitation for
this step.
