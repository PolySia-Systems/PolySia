# PolySia

Explore a leader’s history, compare a shortlist, and follow a simulated copy from a signal to its effect on cash and open positions. You can also inspect a public Polymarket trading address through a separate read-only watch. The local application requires no private keys or service accounts.

**Start with Discover.** Open Atlas Meridian, select **Preview shadow**, and inspect the allocation, fee and price limits. Start the run and choose **Observe next signal** twice. Compare the complete fill with the partial fill. Pause new entries, advance the scenario, then stop and inspect the shares you still hold. Run history includes downloadable evidence. All six discovery profiles and all replay events are fictional.

## Install the local application

The supported installation entry point is the bundled `polysia.pyz`. The Linux runtime needs Python 3.12 with SQLite. A source checkout additionally needs Node and npm to build the artifact. The development pins are in [the Python version file](.python-version), [the Node version file](.node-version) and [the web lockfile](apps/web/package-lock.json). From the repository root:

```sh
make build
python3 dist/polysia.pyz --prefix "$HOME/.local/share/polysia"
"$HOME/.local/share/polysia/current/polysia"
```

Open the local address printed by the launcher (default port 8765). The artifact includes the compiled interface, fonts and server. Installation works offline once the artifact is available. Rerun the same installer to refresh code in the same prefix. State lives in `data/workspace.sqlite3` under the prefix. Stop the foreground server with Ctrl-C. Use `--port PORT` on the launcher if the port is occupied.

This is an English-language, single-operator application for a trusted local machine. It binds to loopback. Anyone with access to that OS user can use the workspace. Remote hosting, authentication, signing and real trading require separate milestones.

## Develop and verify

```sh
make setup         # Install locked web dependencies and compile the UI
make run           # Serve UI + API; development state is under .polysia/
make check         # Python domain, provider-contract and HTTP tests
make verify        # Also run the Chromium journey and offline installation checks
```

The browser checks use system Chromium (`CHROMIUM_PATH` selects another binary) and pinned Python test dependencies. To retain review screenshots, run `make browser-test BROWSER_ARGS="--screenshots /tmp/polysia-review"`. The shipped application has no Python package dependencies. `GET /api/v1/health` checks local storage and reports the software version. The Status screen shows runtime health separately from provider coverage.

## Current state and next proof

Development baseline **0.1.0**, [PolySia-Systems/PolySia](https://github.com/PolySia-Systems/PolySia). Use `git rev-parse HEAD` to identify a checkout and the installer's SHA-256 identifier to identify a built artifact. No hosted release is certified.

| Journey | Evidence and boundary |
| --- | --- |
| Discover → compare → preview | Fictional 30-day profiles share definitions across screens. Rank sorts historical sample values. Real leader discovery, allocation-assisted selection and observed user comprehension remain open. |
| Shadow replay → stop → inspect | An explicit step advances the scenario clock. The same recorded source order cannot consume the budget twice. Exact cash/share arithmetic, delayed book depth, fees, missing observations, partial fills and residual exposure are exercised in [scenario tests](tests/test_shadow.py). Replay time does not advance while the operator is away. |
| Watch → refresh → remove | Public open ordinary positions on the first page with explicit coverage and receipt time. No wallet ownership, spendable balance or signing authority can be inferred. Contract checks and current network limitations are in [provider evidence](docs/provider.md). |
| Runtime settings and recovery | Theme and run revisions survive restart. Stale updates fail. The API and the UI use the same store. [HTTP tests](tests/test_server.py) and [browser journey](tests/browser/journey.py) cover this workflow. |

**Architecture decision.** React, TypeScript and Vite render the client. One loopback Python process serves the built assets and the versioned HTTP API. SQLite serializes each local replay transition and stores operator preferences. A standalone offline installer avoids a container registry, database service and execution worker for this single-user, user-stepped workflow. Revisit PostgreSQL, an isolated worker and an authenticated deployment when concurrent operators or unattended execution become requirements. Live authority must be independently enforced before enabling either a signer or venue writes.

**Next evidence gate.** Capture a public leader observation and a contemporaneous follower-side book on an authorized network. Check identity, timing, coverage, applicable fees and depth before attempting a prospective shadow trial. A transaction may contain several fills. An unavailable or ambiguous observation cannot establish a copy decision. A successful fixture replay cannot establish provider latency, economic viability or an actual user’s comprehension. Use the existing plan for the subsequent gates.

[Master Plan v1.9](docs/MASTER_PLAN.md) is the single intent baseline. [Project instructions](AGENTS.md) cover contributions and acceptance.
