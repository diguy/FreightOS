# Project Working Agreements

## Scope

These rules apply to the application code and tests in this repository.
The `vendor/` directory is third-party code and should not be changed unless
the user explicitly requests it.

## Development Workflow

- Read the relevant existing modules and tests before editing.
- Keep changes minimal and modular; avoid unrelated refactors or speculative
  features.
- Prefer existing project patterns, services, schemas, and adapters before
  introducing new abstractions.
- Keep responsibilities separated:
  - Dify handles current-message intent recognition and workflow output.
  - The Python agent layer parses, validates, stores, and merges conversation
    state.
  - Business services remain the source of truth for orders and tickets.
  - Routes adapt HTTP requests and responses; they do not contain business
    orchestration.
- Treat `IntentResult` as a current-turn contract. Cross-turn data belongs in
  session models and session services.
- Keep external integrations injectable so tests do not require live Dify,
  RAGFlow, or other network services.

## Clarification and Assumptions

- Do not assume the user's requirement is unambiguous. When ambiguity could
  change behavior, state the interpretation, assumptions, and acceptance
  criteria before editing.
- For multi-step work, complete and verify one module before connecting it to
  the next module.
- Do not silently expand scope. Record useful future optimizations separately
  from the current implementation.

## Testing and Verification

- Write or update focused tests with behavior changes.
- Run module-level tests first, then integration or route tests, then the
  project test suite when practical.
- After edits, report the exact verification commands and results.
- Include manual verification steps for Dify or other external systems when
  automated tests use fakes.
- If the repository-wide test command collects unrelated vendor tests or
  depends on unavailable external services, report that separately and run
  the project's own test paths explicitly.

## Change Safety

- Preserve existing user changes and dirty worktree state.
- Never reset, revert, or delete unrelated changes without explicit approval.
- Do not create commits automatically unless the user explicitly asks for a
  commit. When commits are requested, keep them focused and descriptive.
- Before editing Dify DSL, preserve the previous file and create a clearly
  named revision.

## Completion Format

After a change, summarize:

1. What changed.
2. What was tested and the result.
3. Any remaining risk or limitation.
4. The next optimization or integration step, if one is needed.
