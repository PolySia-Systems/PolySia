# PolySia

Explore a leader’s history, compare a shortlist, and follow a simulated copy from a signal to its effect on cash and open positions. In **Public rankings**, open a trader, enter a research budget and select **Observe next BUY** to check a recent wallet-owned order against the displayed liquidity and fees. A separate account watch remembers one public address. The local application requires no private keys or service accounts.

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

Local build **0.2.2** can check a two-second observation window twice to catch a BUY that becomes visible while there is still time to check the book. The trader screen shows when each request was made, when a page arrived, and which read first showed the BUY. The installer records its artifact SHA-256. Source and review history are in [PolySia-Systems/PolySia](https://github.com/PolySia-Systems/PolySia).

| Journey | Evidence and boundary |
| --- | --- |
| Discover → compare → preview | Fictional 30-day profiles share definitions across screens. Rank sorts historical sample values. The budget finder uses the same engine as the replay and carries the selected allocation and cap into setup. It can return no full matches. No human usability trial has been run. |
| Shadow replay → stop → inspect | An explicit step advances the scenario clock. The same recorded source order cannot consume the budget twice. Exact cash/share arithmetic, delayed book depth, fees, missing observations, partial fills and residual exposure are exercised in [scenario tests](tests/test_shadow.py). Saved runs retain the same marked net result as their reports. A missing midpoint leaves that estimate unavailable. Replay time advances only on request. |
| Public rankings → trader → public watch or observation | Polymarket v2 supplies rank, P/L and share volume for the selected period. Two-wallet comparison reports overlapping open markets and incomplete pages. The optional history chart preserves cumulative realized P/L and gaps. Inspecting positions and preparing a watch do not change which wallet is watched. A budgeted two-second observation checks the order on Polygon, reads market terms, and samples the book after both checks. The receipt reports a capacity estimate, a skip, or missing evidence. It can be downloaded without changing the watch or starting a replay. |
| Watch → refresh → remove | The first provider page distinguishes open and redeemable positions with coverage and receipt time. After a same-wallet refresh fails, an explicitly historical view retains the last successful page. No wallet ownership, spendable balance or signing authority can be inferred. Verified public reads and contract limits are in [provider evidence](docs/provider.md). |
| Runtime settings and recovery | Theme and run revisions survive restart. Stale updates fail. The API and the UI use the same store. [HTTP tests](tests/test_server.py) and [browser journey](tests/browser/journey.py) cover this workflow. |

**Architecture decision.** React, TypeScript and Vite render the client. One loopback Python process serves the built assets and the versioned HTTP API. SQLite serializes each local replay transition and stores operator preferences. A standalone offline installer avoids a container registry, database service and execution worker for this single-user, user-stepped workflow. Revisit PostgreSQL, an isolated worker and an authenticated deployment when concurrent operators or unattended execution become requirements. Live authority must be independently enforced before enabling either a signer or venue writes.

**Next evidence gate.** Measure which wallet BUYs are visible in time for a delayed book check across different wallets and markets. One of four initially empty windows later showed two BUYs. Keep late discoveries separate from prospective capacity. Reconcile follower fee rounding and order minimums before recording prospective shadow fills.

To run the same checks from an installation, choose a new output file in an existing directory. This example declares three two-second windows at 10 pUSD each. The study writes its plan, attempts, receipts and counts as JSON Lines. Each window has its own unfunded budget. [Sampling policy and provider evidence](docs/provider.md#budgeted-observations)

```sh
"$HOME/.local/share/polysia/current/polysia" study 0xc69bd5567b40ef4d11922eaa57e1f9be1c642076 \
  --budget 10 --seconds 2 --windows 3 --retry-empty --recheck-after 30 --to ./buy-study.jsonl
```

`--retry-empty` schedules one more activity read three seconds after the same window closes, if the first page was complete, showed no ordinary BUY, and the age limit still allows a book check. The summary counts additional reads, BUY detections and capacity estimates. Omit the flag for the original one-read study.

`--recheck-after 30` separately waits until the series finishes, waits 30 seconds, then rereads each interval once. Those pages can reveal later activity. They never produce a capacity estimate. A failed read or a partial page with no BUY leaves that comparison unknown. Time between windows is unobserved.

[Master Plan v1.9](docs/MASTER_PLAN.md) is the single intent baseline. [Project instructions](AGENTS.md) cover contributions and acceptance.
