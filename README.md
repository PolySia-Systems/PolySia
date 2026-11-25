# PolySia

Explore a leader’s history, compare a shortlist, and follow a simulated copy from a signal to its effect on cash and open positions. Open **Public rankings** to read Polymarket’s leaderboard, inspect a real trader’s positions and observe a short window for a new BUY. A separate account watch remembers one public address. The local application requires no private keys or service accounts.

**Start with Discover.** Open Atlas Meridian, select **Preview shadow**, and inspect the allocation, fee and price limits. Start the run and choose **Observe next signal** twice. Compare the complete fill with the partial fill. Pause new entries, advance the scenario, then stop and inspect the shares you still hold. Run history includes downloadable evidence. All six discovery profiles and all replay events are fictional.

## Install the local application

The supported installation entry point is the bundled `polysia.pyz`. The Linux runtime needs Python 3.12 with SQLite. A source checkout additionally needs Node and npm to build the artifact. The development pins are in [the Python version file](.python-version), [the Node version file](.node-version) and [the web lockfile](apps/web/package-lock.json). From the repository root:

```sh
make build
python3 dist/polysia.pyz --prefix "$HOME/.local/share/polysia"
"$HOME/.local/share/polysia/current/polysia"
```

Open the local address printed by the launcher (default port 8765). The artifact includes the compiled interface, fonts and server. Installation works offline once the artifact is available. Rerun the same installer to refresh code in the same prefix. State lives in `data/workspace.sqlite3` under the prefix. Stop the foreground server with Ctrl-C. Use `--port PORT` on the launcher if the port is occupied.

To back up a running installation and verify a restore, choose two new file paths in an existing directory. The launcher refuses to overwrite either file.

```sh
launcher="$HOME/.local/share/polysia/current/polysia"
"$launcher" backup --to ./workspace-backup.sqlite3
"$launcher" restore --from ./workspace-backup.sqlite3 --to ./workspace-restored.sqlite3
POLYSIA_DB="$PWD/workspace-restored.sqlite3" "$launcher" --port 8766
```

This is an English-language, single-operator application for a trusted local machine. It binds to loopback. Anyone with access to that OS user can use the workspace. Remote hosting, authentication, signing and real trading require separate milestones.

## Develop and verify

```sh
make setup         # Install locked web dependencies and compile the UI
make run           # Serve UI + API; development state is under .polysia/
make check         # Python domain, provider-contract and HTTP tests
make verify        # Also run the Chromium journey and offline installation checks
```

Run `make provider-test` for the optional network check. It installs the artifact in a temporary directory, reads the real public rankings, inspects one profile, watches that public address and removes the watch. The regular verification suite runs with controlled inputs.

The browser checks use system Chromium (`CHROMIUM_PATH` selects another binary) and pinned Python test dependencies. To retain review screenshots, run `make browser-test BROWSER_ARGS="--screenshots /tmp/polysia-review"`. The shipped application has no Python package dependencies. `GET /api/v1/health` checks local storage and reports the software version. The System status screen shows runtime health separately from provider coverage.

## Current state and next proof

Development baseline **0.1.0**, [PolySia-Systems/PolySia](https://github.com/PolySia-Systems/PolySia). Use `git rev-parse HEAD` to identify a checkout and the installer's SHA-256 identifier to identify a built artifact. No hosted release is certified.

| Journey | Evidence and boundary |
| --- | --- |
| Discover → compare → preview | Fictional 30-day profiles share definitions across screens. Rank sorts historical sample values. The budget finder uses the same engine as the replay and carries the selected allocation and cap into setup. It can return no full matches. No human usability trial has been run. |
| Shadow replay → stop → inspect | An explicit step advances the scenario clock. The same recorded source order cannot consume the budget twice. Exact cash/share arithmetic, delayed book depth, fees, missing observations, partial fills and residual exposure are exercised in [scenario tests](tests/test_shadow.py). Replay time does not advance while the operator is away. |
| Public rankings → trader → public watch or observation | Polymarket v2 supplies rank, P/L and share volume for the selected period. Inspecting positions and preparing a watch do not change which wallet is watched. A five-second observation reports missing activity, incomplete evidence or displayed book depth; it never starts a replay or signs an order. |
| Watch → refresh → remove | The first provider page distinguishes open and redeemable positions with coverage and receipt time. No wallet ownership, spendable balance or signing authority can be inferred. Verified public reads and contract limits are in [provider evidence](docs/provider.md). |
| Runtime settings and recovery | Theme and run revisions survive restart. Stale updates fail. The API and the UI use the same store. [HTTP tests](tests/test_server.py) and [browser journey](tests/browser/journey.py) cover this workflow. |

**Architecture decision.** React, TypeScript and Vite render the client. One loopback Python process serves the built assets and the versioned HTTP API. SQLite serializes each local replay transition and stores operator preferences. A standalone offline installer avoids a container registry, database service and execution worker for this single-user, user-stepped workflow. Revisit PostgreSQL, an isolated worker and an authenticated deployment when concurrent operators or unattended execution become requirements. Live authority must be independently enforced before enabling either a signer or venue writes.

**Next evidence gate.** Use the bounded public observation probe to establish reliable participant-relative fill identity and measure whether fresh executable depth remains after detection at a specified follower budget. Record incomplete samples alongside successful reads. Verify applicable fees and instrument constraints before trialing prospective shadow fills. A transaction may contain several fills. An unavailable or ambiguous observation cannot establish a copy decision. A successful fixture replay cannot establish provider latency, economic viability or an actual user’s comprehension. Use the existing plan for the subsequent gates.

[Master Plan v1.9](docs/MASTER_PLAN.md) is the single intent baseline. [Project instructions](AGENTS.md) cover contributions and acceptance.
