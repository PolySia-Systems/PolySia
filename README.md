# PolySia

Follow a public Polymarket wallet with simulated cash. Open **Public rankings**, pick a trader or paste a wallet address, and choose **Set up public shadow run**. Choose starting cash and a per-entry cap, then sample one BUY window or a series of five. Once you hold shares, you can also follow a SELL for that outcome. You can also start directly from **Public shadow**. The application runs locally and needs no service accounts.

Each window checks Polymarket activity. A matching Polygon order and a timely public book can produce a simulated trade. To follow a sale, open **Follow a leader SELL** on a position and enter the maximum whole shares to sell before sampling. A partial sale leaves its remaining shares and purchase cost visible. After a full exit, **Closed simulated positions** shows the purchase cost, sale proceeds after fees and realized result for that outcome. Pausing entries keeps SELL windows available. Stopping closes observation and preserves the run for review.

**Check portfolio value** combines simulated cash with fresh midpoint prices. If any holding lacks a current quote, you can inspect the priced portion and see which prices are missing. Use **Modeled trades** in the decision history to find purchases and sales across the full journal. Download the valuation for its prices and timestamps, or **Export run** for the complete decisions and receipts.

**Try the product offline.** In Discover, choose **Try a shadow replay**. Advance two signals to compare a complete fill with a partial one, pause entries, then stop and inspect the remaining shares. All six scenario profiles and their replay events are fictional. Public wallets and their Polymarket holdings can be inspected separately in **Public rankings** or **Accounts**.

## Install the local application

The supported installation entry point is the bundled `polysia.pyz`. The Linux runtime needs Python 3.12 with SQLite. A source checkout additionally needs Node and npm to build the artifact. The development pins are in [the Python version file](.python-version), [the Node version file](.node-version) and [the web lockfile](apps/web/package-lock.json). From the repository root:

```sh
make build
python3 dist/polysia.pyz --prefix "$HOME/.local/share/polysia"
"$HOME/.local/share/polysia/current/polysia"
```

Open the local address printed by the launcher (default port 8765). The artifact includes the compiled interface, fonts and server. Installation works offline once the artifact is available. Before upgrading from 0.2.x or 0.3.0, make a backup with the existing launcher. Stop the server, install the new bundle into the same prefix and restart. The first launch migrates the database to schema 3. Existing public runs keep their original BUY-only policy. On an open run, **Enable SELL windows** records your policy change. To downgrade, restore the pre-upgrade backup with the earlier version. Later decisions are only available in the newer database. State lives in `data/workspace.sqlite3` under the prefix. Stop the foreground server with Ctrl-C. Use `--port PORT` on the launcher if the port is occupied.

To back up a running installation and verify a restore, choose two new file paths in an existing directory. The launcher checks SQLite storage and reconciles replay balances, public shadow positions and cash with their saved decisions before publishing the copy. Both paths must be unused.

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

Run `make provider-test` for the optional network check. It installs the artifact in a temporary directory, samples a share-limited SELL window, reads the real public rankings, inspects one profile and its realized P/L history, watches that public address, samples one public shadow window and removes the watch. The regular verification suite runs with controlled inputs. With a prior bundle available, run `python3 tests/install_smoke.py --upgrade-from /path/to/previous.pyz` after building to verify state survives an actual upgrade.

The browser checks use system Chromium (`CHROMIUM_PATH` selects another binary) and pinned Python test dependencies. To retain review screenshots, run `make browser-test BROWSER_ARGS="--screenshots /tmp/polysia-review"`. The shipped application has no Python package dependencies. `GET /api/v1/health` checks local storage and reports the software version and, for an installation, the artifact SHA-256 recorded by the installer. The System status screen shows runtime health separately from provider coverage.

## Current state and next proof

Local build **0.4.0** links public wallet research to simulated entries, exits and portfolio valuation. Each run has its own simulated pUSD and source-order history. Public observations, cash and positions stay separate from scenario funds, watched holdings and provider-reported P/L.

| Journey | Evidence and boundary |
| --- | --- |
| Discover → compare → preview | Fictional 30-day profiles share definitions across screens. Rank sorts historical sample values. The budget finder uses the same engine as the replay and carries the selected allocation and cap into setup. It can return no full matches. No human usability trial has been run. |
| Shadow replay → stop → inspect | An explicit step advances the scenario clock. The same recorded source order cannot consume the budget twice. Exact cash/share arithmetic, delayed book depth, fees, missing observations, partial fills and residual exposure are exercised in [scenario tests](tests/test_shadow.py). Saved runs retain the same marked net result as their reports. A missing midpoint leaves that estimate unavailable. Replay time advances only on request. |
| Public rankings → trader → public watch or observation | Polymarket v2 supplies rank, P/L and share volume for the selected period. Two-wallet comparison reports overlapping open markets and incomplete pages. The optional history chart preserves cumulative realized P/L and gaps. Inspecting positions and preparing a watch do not change which wallet is watched. A budgeted two-second observation checks the order on Polygon, reads market terms, and samples the book after both checks. The receipt reports a capacity estimate, a skip, or missing evidence. It can be downloaded without changing the watch or starting a replay. |
| Public profile → shadow portfolio → partial or full exit | A new run fixes its wallet and entry budget. A matched SELL uses a predeclared share limit, corroborated leader size and eligible bids. Duplicate orders, superseded windows and failed checks preserve balances. Sales release pooled purchase cost including entry fees. The journal records net proceeds, realized result and residual exposure. [Portfolio tests](tests/test_public_shadow.py) |
| Portfolio → valuation → export | Each check requests up to 12 open-position books. Prices must match the instrument, have a bid below the ask, be at most one minute old and follow the position’s latest change. Full estimates require prices for every holding. Cash-only runs have exact equity. Quotes and timestamps can be downloaded separately from the persistent journal. [Browser journey](tests/browser/journey.py) |
| Watch → refresh → remove | The first provider page distinguishes open and redeemable positions with coverage and receipt time. After a same-wallet refresh fails, an explicitly historical view retains the last successful page. No wallet ownership, spendable balance or signing authority can be inferred. Verified public reads and contract limits are in [provider evidence](docs/provider.md). |
| Runtime settings and recovery | Theme and run revisions survive restart. Stale updates fail. The API and the UI use the same store. [HTTP tests](tests/test_server.py) and [browser journey](tests/browser/journey.py) cover this workflow. |

**Architecture decision.** React, TypeScript and Vite render the client. One loopback Python process serves the built assets and the versioned HTTP API. SQLite serializes each local replay transition and stores operator preferences. A standalone offline installer avoids a container registry, database service and execution worker for this single-user, user-stepped workflow. Revisit PostgreSQL, an isolated worker and an authenticated deployment when concurrent operators or unattended execution become requirements. Live authority must be independently enforced before enabling either a signer or venue writes.

**Next product step.** Use the installed sampling study to compare timely, late, missed and usable observations against later public reads. Declare wallets, budget, delay, duration and a decision threshold before sampling. Use that evidence to choose the observation method. In parallel, verified payouts can support simulated settlement for positions held through resolution. [Provider evidence](docs/provider.md#public-shadow-sales)

To run the same checks from an installation, choose a new output file in an existing directory. This example declares three two-second windows at 10 pUSD each. The study writes its plan, attempts, receipts and counts as JSON Lines. Each window has its own unfunded budget. [Sampling policy and provider evidence](docs/provider.md#budgeted-observations)

```sh
"$HOME/.local/share/polysia/current/polysia" study 0xc69bd5567b40ef4d11922eaa57e1f9be1c642076 \
  --budget 10 --seconds 2 --windows 3 --retry-empty --recheck-after 30 --to ./buy-study.jsonl
```

`--retry-empty` schedules one more activity read three seconds after the same window closes, if the first page was complete, showed no ordinary BUY, and the age limit still allows a book check. The summary counts additional reads, BUY detections and capacity estimates. Omit the flag for the original one-read study.

`--recheck-after 30` separately waits until the series finishes, waits 30 seconds, then rereads each interval once. Those pages can reveal later activity. They never produce a capacity estimate. A failed read or a partial page with no BUY leaves that comparison unknown. Time between windows is unobserved.

[Master Plan v1.10](docs/MASTER_PLAN.md) is the single intent baseline. [Project instructions](AGENTS.md) cover contributions and acceptance.
