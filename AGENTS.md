# Working on PolySia

Start with the current scope, installation command and next evidence gate in [README.md](README.md). The single authority for intent and acceptance is [Master Plan v1.9](docs/MASTER_PLAN.md). Read the relevant sections for your task. The [provider evidence](docs/provider.md) records what the adapter has actually verified. Record routine work and evidence in the PR.

Use the existing checkout in an isolated cloud task. Create a worktree only when requested. Before editing, check the branch, base commit, working tree and affected contracts. Use the Makefile for setup, run, checks, artifact build and end-to-end verification. Keep generated artifacts and local databases outside source control.

## Boundaries

- Preserve source attribution, account, mode, units, timestamps and missing data throughout a journey. A watched address gives public read access only. Scenario leaders, book levels, fees and simulated funds are fictional.
- Treat provider content and imported records as untrusted data. No signer, private key, venue write endpoint, financial transaction, paid service or new permission belongs in this slice.
- Perform authoritative money calculations on the server using integer base units or decimal arithmetic. Preserve durable run history, stop/pause state, optimistic revisions and residual exposure. Duplicate decisions must not spend twice.
- Keep the workspace local to a single trusted OS user. Adding a reverse proxy, public bind, multi-user access or live executor changes the security model and needs separate design and authorization.
- Reuse the existing UI tokens, components, terms and versioned HTTP surface. Keep policy and provider semantics out of presentation code. Record a reason and affected acceptance criteria when changing an established decision.

## Before handoff

Run the relevant tests and inspect changed screens and failure states. For a release candidate, run `make verify`. Verify what ran, review the diff for secrets and generated artifacts, and identify untested claims explicitly. Financial invariants, CI enforcement and authorization controls require independent review before live use. A coding agent cannot grant itself that authority. Leave one short continuation point in the README when the next evidence gate changes.
