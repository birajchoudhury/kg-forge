# KG Forge – Copilot Instructions

## Project context
- This repo builds a CLI “KG Forge” as described in `docs/seed_product.md`.
- All technical design and constraints are in `docs/seed_architecture.md`.

## When generating code
- Follow the CLI shape: `ingest`, `query`, `render` (and helper commands) as defined in `seed_architecture.md`.
- Respect the Neo4j schema (`:Doc`, `:Entity`, `MENTIONS`, typed relations, namespace).
- Prefer adding tests under `tests/` that exercise the behaviours described in `seed_architecture.md`.

## When creating new features
- First check whether the architeture_spec.md has changed if yes then look at the steps in 11. Implementation Plan (Steps 0–8)
- Check which steps spec needs to be modified, modify the spec once you have modified check all the step specs reflect what is written in architecture_spec.md
- Follow the implementation plan steps to implement the feature.
- Add tests under `tests/` that exercise the new feature.
- Update documentation under `docs/` as needed.
- Ensure code is clean, well structured, and follows best practices.
- Dont leave behind dead code or code that still has some parts of implementation from the previous spec, ensure code is always up to date with the latest spec.
- Ensure all existing and new tests pass before finalizing the changes.
