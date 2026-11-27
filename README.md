# PolySia

Follow a public Polymarket wallet with simulated cash. Open **Public rankings**, pick a trader or paste a wallet address, and choose **Set up public shadow run**. Choose starting cash and a per-entry cap, then sample one BUY window or a series of five. Once you hold shares, you can also follow a SELL for that outcome. You can also start directly from **Public shadow**. The application runs locally and needs no service accounts.

Each window checks Polymarket activity. A matching Polygon order and a timely public book can produce a simulated trade. To follow a sale, open **Follow a leader SELL** on a position and enter the maximum whole shares to sell before sampling. A partial sale leaves its remaining shares and purchase cost visible. After a full exit, **Closed simulated positions** shows the purchase cost, sale proceeds after fees and realized result for that outcome. Pausing entries keeps SELL windows available. Stopping closes observation and preserves the run for review.

**Check portfolio value** combines simulated cash with fresh midpoint prices. If any holding lacks a current quote, you can inspect the priced portion and see which prices are missing. Use **Modeled trades** in the decision history to find purchases and sales across the full journal. Download the valuation for its prices and timestamps, or **Export run** for the complete decisions and receipts.

**Try the product offline.** In Discover, choose **Try a shadow replay**. Advance two signals to compare a complete fill with a partial one, pause entries, then stop and inspect the remaining shares. All six scenario profiles and their replay events are fictional. Public wallets and their Polymarket holdings can be inspected separately in **Public rankings** or **Accounts**.

## Install the local application

The Linux release is a single offline bundle, `polysia.pyz`. On a supported host with Python 3.12+ and SQLite, obtain the bundle from the project owner and compare its SHA-256 with the owner's trusted release record **before executing it**. From the directory containing the verified bundle, run:

```sh
python3 polysia.pyz --start
```

Open the local address printed after the running application checks its storage and build identity. In Discover choose **Try a shadow replay**. Ctrl-C stops the foreground server. Use `--port 0` to choose a free local port. Install-only and machine-readable paths remain available with `--json`. On a Linux account with a systemd user manager and lingering enabled, `--service` installs a persistent local service. Run `--help` for installation options.

For a transferred bundle, the [verification helper](deploy/verified_install.py) from a trusted checkout checks an independently supplied SHA-256 and runs the verified copy. For a published private release it also accepts `--release TAG` on a workstation with existing repository access. The application server does not need repository credentials. Developers build the same bundle with `make build`; Node and npm are build dependencies only.

The default prefix is `$HOME/.local/share/polysia`. Data lives in `data/workspace.sqlite3` within it. Before an upgrade, back up the running workspace, stop its service or foreground process and install the new bundle into the same prefix. On first start, 0.5.0 marks the database as version 4 so earlier launchers cannot write decisions under outdated rules. Existing public runs retain their recorded policy. To downgrade, restore the matching pre-upgrade backup with the earlier version.

To back up a running installation and verify a restore, choose two new file paths in an existing directory. The launcher checks SQLite storage and reconciles replay balances, public shadow positions and cash with their saved decisions before publishing the copy. Both paths must be unused.

```sh
launcher="$HOME/.local/share/polysia/current/polysia"
"$launcher" backup --to ./workspace-backup.sqlite3
"$launcher" restore --from ./workspace-backup.sqlite3 --to ./workspace-restored.sqlite3
POLYSIA_DB="$PWD/workspace-restored.sqlite3" "$launcher" --port 8766
```

## Optional owner-only HTTPS access

On a fresh designated Ubuntu 26.04 LTS amd64 host booted with systemd, use the verified bundle:

```sh
sudo /usr/bin/python3 -I polysia.pyz --prepare-cloudflare-host
```

This explicit host-preparation mode creates a dedicated service user, installs the Ubuntu JWT libraries when needed, verifies a pinned cloudflared binary, enables the user service manager at boot, and drops root privileges before requesting the Cloudflare token. Keep the Ubuntu package sources and Python installation trusted. On an already-prepared Linux host use `python3 polysia.pyz --cloudflare`. Run it as a dedicated unprivileged OS user with systemd user services and lingering enabled. The remote interpreter needs PyJWT 2.x with cryptography and the host needs an authenticated cloudflared installation supporting `tunnel run --token-file`. Prepare an active Cloudflare zone, an unused hostname, an existing One-time PIN sign-in method and a management token scoped to the required zone/DNS, tunnel, Access application/policy and identity-provider operations. The installer prompts for the hostname, owner email and hidden management token. For unattended operation supply `POLYSIA_HOSTNAME`, `POLYSIA_OWNER_EMAIL` and the token on standard input from a secret manager. Keep it out of shell history.

Use a fresh, private install prefix for the first HTTPS deployment. The prefix stays reserved for HTTPS on later installs. For a separate local installation, use a single-user machine and a different prefix. When upgrading an earlier HTTPS candidate, stop any old foreground loopback launcher and disable any local `polysia.service` for that workspace first. Backup and restore remain available from the HTTPS installation’s launcher.

After setup, open the printed HTTPS address and sign in with the configured owner email. The application and connector use a private Unix socket, and the origin validates the Access signature, issuer, application audience, expiry and owner. Rerun from the same OS user and prefix to recover an interruption. The installer records its own resource IDs and keeps the connector credential under `remote/` in that prefix. To take the site offline, run `systemctl --user disable --now polysia-tunnel.service`. Inspect services with `systemctl --user status polysia-origin.service polysia-tunnel.service`. The owner-login email and test resources must belong to the authorized deployment. The local installation works offline with no Cloudflare configuration. All modes are single-owner and simulated.

## Develop and verify

```sh
make setup         # Install locked web dependencies and compile the UI
make run           # Serve UI + API; development state is under .polysia/
make check         # Python domain, provider-contract and HTTP tests
make verify        # Also run the Chromium journey and offline installation checks
```

Run `make provider-test` for the optional network check. It installs the artifact in a temporary directory, samples a share-limited SELL window, reads the real public rankings, inspects one profile and its realized P/L history, watches that public address, samples one public shadow window and removes the watch. The regular verification suite runs with controlled inputs. With a prior bundle available, run `python3 tests/install_smoke.py --upgrade-from /path/to/previous.pyz` after building to verify state survives an actual upgrade.

The browser checks use system Chromium (`CHROMIUM_PATH` selects another binary) and pinned Python test dependencies. To retain review screenshots, run `make browser-test BROWSER_ARGS="--screenshots /tmp/polysia-review"`. Local mode uses only the Python standard library. The optional HTTPS origin also uses PyJWT and cryptography. `GET /api/v1/health` checks local storage and reports the software version and, for an installation, the artifact SHA-256 recorded by the installer. The System status screen shows runtime health separately from provider coverage.

## Current state and next proof

Build **0.5.0** links public wallet research to simulated entries, exits and portfolio valuation. Each run has its own simulated pUSD and source-order history. Public observations, cash and positions stay separate from scenario funds, watched holdings and provider-reported P/L.

| Journey | Evidence and boundary |
| --- | --- |
| Discover → compare → preview | Fictional 30-day profiles share definitions across screens. Rank sorts historical sample values. The budget finder uses the same engine as the replay and carries the selected allocation and cap into setup. It can return no full matches. No human usability trial has been run. |
| Shadow replay → stop → inspect | An explicit step advances the scenario clock. The same recorded source order cannot consume the budget twice. Exact cash/share arithmetic, delayed book depth, fees, missing observations, partial fills and residual exposure are exercised in [scenario tests](tests/test_shadow.py). Saved runs retain the same marked net result as their reports. A missing midpoint leaves that estimate unavailable. Replay time advances only on request. |
| Public rankings → trader → public watch or observation | Polymarket v2 supplies rank, P/L and share volume for the selected period. Two-wallet comparison reports overlapping open markets and incomplete pages. The optional history chart preserves cumulative realized P/L and gaps. Inspecting positions and preparing a watch do not change which wallet is watched. A budgeted two-second observation checks the order on Polygon, reads market terms, and samples the book after both checks. The receipt reports a capacity estimate, a skip, or missing evidence. It can be downloaded without changing the watch or starting a replay. |
| Public profile → shadow portfolio → partial or full exit | A new run fixes its wallet and entry budget. Before a modeled BUY it checks the available same-outcome sales page for a conflicting SELL. An incomplete or late sales check leaves cash unchanged. A matched SELL uses a predeclared share limit, corroborated leader size and eligible bids. Duplicate orders, superseded windows and failed checks preserve balances. Sales release pooled purchase cost including entry fees. The journal records net proceeds, realized result and residual exposure. [Portfolio tests](tests/test_public_shadow.py) |
| Portfolio → valuation → export | Each check requests up to 12 open-position books. Prices must match the instrument, have a bid below the ask, be at most one minute old and follow the position’s latest change. Full estimates require prices for every holding. Cash-only runs have exact equity. Quotes and timestamps can be downloaded separately from the persistent journal. [Browser journey](tests/browser/journey.py) |
| Watch → refresh → remove | The first provider page distinguishes open and redeemable positions with coverage and receipt time. After a same-wallet refresh fails, an explicitly historical view retains the last successful page. No wallet ownership, spendable balance or signing authority can be inferred. Verified public reads and contract limits are in [provider evidence](docs/provider.md). |
| Runtime settings and recovery | Theme and run revisions survive restart. Stale updates fail. The API and the UI use the same store. [HTTP tests](tests/test_server.py) and [browser journey](tests/browser/journey.py) cover this workflow. |

**Architecture decision.** React, TypeScript and Vite render the client. One Python process serves the built assets and the versioned HTTP API over loopback locally, or over a private Unix socket in the optional owner-only HTTPS deployment. SQLite serializes each local replay transition and stores operator preferences. A standalone offline installer avoids a container registry, database service and execution worker for this single-user, user-stepped workflow. Revisit PostgreSQL and an isolated worker when concurrent operators or unattended execution become requirements. Live authority must be independently enforced before enabling either a signer or venue writes.

**Next product step.** Keep interval polling for the next public shadow trial. In the [paired source study](docs/provider.md#paired-source-decision-26-november-2026), triggering corroboration from Polygon did not improve usable observations. Observe a first-time owner selecting a leader, explaining a skipped entry, stopping and finding the remaining exposure after restart. Record where help was needed.

To run the same checks from an installation, choose a new output file in an existing directory. This example declares three two-second windows at 10 pUSD each. The study writes its plan, attempts, receipts and counts as JSON Lines. Each window has its own unfunded budget. [Sampling policy and provider evidence](docs/provider.md#budgeted-observations)

```sh
"$HOME/.local/share/polysia/current/polysia" study 0xc69bd5567b40ef4d11922eaa57e1f9be1c642076 \
  --budget 10 --seconds 2 --windows 3 --retry-empty --recheck-after 30 --to ./buy-study.jsonl
```

`--retry-empty` schedules one more activity read three seconds after the same window closes, if the first page was complete, showed no ordinary BUY, and the age limit still allows a book check. The summary counts additional reads, BUY detections and capacity estimates. Omit the flag for the original one-read study.

`--recheck-after 30` separately waits until the series finishes, waits 30 seconds, then rereads each interval once. Those pages can reveal later activity. They never produce a capacity estimate. A failed read or a partial page with no BUY leaves that comparison unknown. Time between windows is unobserved.

[Master Plan v1.10](docs/MASTER_PLAN.md) is the single intent baseline. [Project instructions](AGENTS.md) cover contributions and acceptance.
