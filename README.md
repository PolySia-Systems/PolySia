# PolySia

Explore a leader’s history, compare a shortlist, and follow a simulated copy from a signal to its effect on cash and open positions. Open **Public rankings** to read Polymarket’s leaderboard, inspect a real trader’s positions and observe a short window for a new BUY. A separate account watch remembers one public address. The local application requires no private keys or service accounts.

**Start with Discover.** Choose **Research public wallets** to see the provider's rankings or paste a full trading wallet address. An address lookup leaves the saved watch in place. Choose **Try a shadow replay** to preview Atlas Meridian with simulated funds. Advance two signals to compare a complete fill with a partial one. Pause entries, advance once more, then stop and inspect the remaining shares. Open a saved run by name to review its decisions or download its JSON. All six scenario profiles and their replay events are fictional.

## Install the local application

The supported installation entry point is the bundled `polysia.pyz`. The Linux runtime needs Python 3.12 with SQLite. A source checkout additionally needs Node and npm to build the artifact. The development pins are in [the Python version file](.python-version), [the Node version file](.node-version) and [the web lockfile](apps/web/package-lock.json). From the repository root:

```sh
make build
python3 dist/polysia.pyz --prefix "$HOME/.local/share/polysia"
"$HOME/.local/share/polysia/current/polysia"
```

Open the local address printed by the launcher (default port 8765). The artifact includes the compiled interface, fonts and server. Installation works offline once the artifact is available. To upgrade, stop the server, install the new bundle into the same prefix and restart the launcher. State lives in `data/workspace.sqlite3` under the prefix. Stop the foreground server with Ctrl-C. Use `--port PORT` on the launcher if the port is occupied.

To back up a running installation and verify a restore, choose two new file paths in an existing directory. The launcher checks SQLite storage and reconciles every recorded replay’s cash, shares and fees before publishing the copy. Both paths must be unused.

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

Run `make provider-test` for the optional network check. It installs the artifact in a temporary directory, reads the real public rankings, inspects one profile and its realized P/L history, watches that public address and removes the watch. The regular verification suite runs with controlled inputs. With a prior bundle available, run `python3 tests/install_smoke.py --upgrade-from /path/to/previous.pyz` after building to verify state survives an actual upgrade.

The browser checks use system Chromium (`CHROMIUM_PATH` selects another binary) and pinned Python test dependencies. To retain review screenshots, run `make browser-test BROWSER_ARGS="--screenshots /tmp/polysia-review"`. The shipped application has no Python package dependencies. `GET /api/v1/health` checks local storage and reports the software version and, for an installation, the artifact SHA-256 recorded by the installer. The System status screen shows runtime health separately from provider coverage.

## Current state and next proof

Local build **0.1.1** was exercised on Debian 13 x86_64. Source and review history are in [PolySia-Systems/PolySia](https://github.com/PolySia-Systems/PolySia). Use `git rev-parse HEAD` to identify a checkout and the installer's SHA-256 identifier to identify a built artifact. No hosted release is certified.

| Journey | Evidence and boundary |
| --- | --- |
| Discover → compare → preview | Fictional 30-day profiles share definitions across screens. Rank sorts historical sample values. The budget finder uses the same engine as the replay and carries the selected allocation and cap into setup. It can return no full matches. No human usability trial has been run. |
| Shadow replay → stop → inspect | An explicit step advances the scenario clock. The same recorded source order cannot consume the budget twice. Exact cash/share arithmetic, delayed book depth, fees, missing observations, partial fills and residual exposure are exercised in [scenario tests](tests/test_shadow.py). Saved runs retain the same marked net result as their reports. A missing midpoint leaves that estimate unavailable. Replay time advances only on request. |
| Public rankings → trader → public watch or observation | Polymarket v2 supplies rank, P/L and share volume for the selected period. Two-wallet comparison reports overlapping open markets and incomplete pages. The optional history chart preserves cumulative realized P/L and gaps. Inspecting positions and preparing a watch do not change which wallet is watched. A five-second observation reports missing activity, incomplete evidence or displayed book depth; it never starts a replay or signs an order. |
| Watch → refresh → remove | The first provider page distinguishes open and redeemable positions with coverage and receipt time. After a same-wallet refresh fails, an explicitly historical view retains the last successful page. No wallet ownership, spendable balance or signing authority can be inferred. Verified public reads and contract limits are in [provider evidence](docs/provider.md). |
| Runtime settings and recovery | Theme and run revisions survive restart. Stale updates fail. The API and the UI use the same store. [HTTP tests](tests/test_server.py) and [browser journey](tests/browser/journey.py) cover this workflow. |

**Architecture decision.** React, TypeScript and Vite render the client. One loopback Python process serves the built assets and the versioned HTTP API. SQLite serializes each local replay transition and stores operator preferences. A standalone offline installer avoids a container registry, database service and execution worker for this single-user, user-stepped workflow. Revisit PostgreSQL, an isolated worker and an authenticated deployment when concurrent operators or unattended execution become requirements. Live authority must be independently enforced before enabling either a signer or venue writes.

**Next evidence gate.** Pair the public observation receipt with a source that identifies the participant’s economic fill within a transaction. Measure point-in-time book coverage after detection at a stated follower budget. The public activity endpoint alone exposes insufficient identity for unattended copying. Record incomplete samples alongside successful reads. Verify applicable fees and instrument constraints before trialing prospective shadow fills. A transaction may contain several fills. An unavailable or ambiguous observation cannot establish a copy decision. A successful fixture replay cannot establish provider latency, economic viability or an actual user’s comprehension. Use the existing plan for the subsequent gates.

[Master Plan v1.9](docs/MASTER_PLAN.md) is the single intent baseline. [Project instructions](AGENTS.md) cover contributions and acceptance.
