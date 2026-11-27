# Working on PolySia

Start with the current scope, installation command and next evidence gate in [README.md](README.md). The single authority for intent and acceptance is [Master Plan v1.10](docs/MASTER_PLAN.md). Read the relevant sections for your task. The [provider evidence](docs/provider.md) records what the adapter has actually verified. Record routine work and evidence in the PR.

Use the existing checkout in the authorized local or cloud environment. Create a worktree only when requested. Before editing, check the branch, base commit, working tree and affected contracts. Use the Makefile for setup, run, checks, building the supported Linux artifact and verifying it end to end. Keep generated artifacts and local databases outside source control.

## Repository language

All contributors and AI agents must write project-maintained content in English, including documentation, UI and CLI text, comments, and examples (Master Plan section 5.4). Use short instructions, standard engineering terms, and commands readers can copy. In review, check that a reader with limited English can find the next action and recognize success. Preserve third-party text, user data, identifiers, and conventional notation. Adding a supported language requires an explicit owner decision.

## Boundaries

- Preserve source attribution, account, mode, units, timestamps and missing data throughout a journey. A watched address gives public read access only. Scenario leaders, book levels, fees and simulated funds are fictional.
- Treat provider content and imported records as untrusted data. No signer, private key, venue write endpoint, financial transaction, paid service or new permission belongs in this slice.
- Perform authoritative money calculations on the server using integer base units or decimal arithmetic. Preserve durable run history, stop/pause state, optimistic revisions and residual exposure. Duplicate decisions must not spend twice.
- Keep local mode on loopback for a single trusted OS user. The optional owner-authorized Cloudflare deployment uses an isolated service user, private Unix socket and an owner-specific verified Access assertion. Public origin binds, other proxies, multi-user access and live execution require separate design and authorization.
- Reuse the existing UI tokens, components, terms and versioned HTTP surface. Keep policy and provider semantics out of presentation code. Record a reason and affected acceptance criteria when changing an established decision.

## Before handoff

- Run the relevant tests and inspect changed screens and failure states.
- When a user journey changes, update its entry point and affected instructions with the change. In the PR record how you followed those instructions and where a first-time user needed help, if observed.
- For a release candidate, run `make verify`, then `make release-check` on the tested bundle. Repeat the latter with the anonymously downloaded release assets after publication (Master Plan A01 and A03).
- Verify what ran, review the diff for secrets and generated artifacts, and identify untested claims explicitly.
- Financial invariants, CI enforcement and authorization controls require independent review before live use. Controlled product work can proceed while provider evidence or live-use review is outstanding.
- Leave one short continuation point in the README when the next evidence gate changes.
