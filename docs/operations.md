# Operating PolySia

Use the [Linux installation instructions](../README.md#install-on-linux) for a first local installation.

## Update and recover

The default prefix is `$HOME/.local/share/polysia`. Data lives in `data/workspace.sqlite3` within it. Before an upgrade, back up the running workspace, stop its service or foreground process and install the new bundle into the same prefix. On first start, 0.5.0 marks the database as version 4 so earlier launchers cannot write decisions under outdated rules. Existing public runs retain their recorded policy. To downgrade, restore the matching pre-upgrade backup with the earlier version.

With a trusted checkout and an independent release digest, operators can use [verified_install.py](../deploy/verified_install.py) with `--release TAG` on an authorized workstation or `--file` after a transfer. Both verify the bytes before invoking the bundled installer. Use `--service` after verification for a persistent local systemd user service with lingering enabled. The default foreground installation works offline.

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

### Recover an HTTPS site

Use the same hostname, owner email and absolute install prefix. To update on the original machine, back up the database and rerun the HTTPS installer. A matching running release can pass its checks without restarting. If you replace your **management API token**, enter the new token at the next installer prompt. The connector uses a separate credential.

For a replacement host or a restored snapshot, schedule one transfer at a time. Use the transfer command even if the snapshot contains the journal. Clones can share a machine ID. Keep the old host offline, or disable its tunnel and stop its origin before the final database backup. Run service commands in the dedicated user's systemd session:

```sh
systemctl --user disable --now polysia-tunnel.service polysia-origin.service
"$HOME/.local/share/polysia/current/polysia" backup --to ./final-backup.sqlite3
```

Copy the backup privately to the new host. The dedicated service user needs read access to the file and its parent directories. In the Cloudflare dashboard, open the intended account and copy the tunnel UUID for this hostname. On the new host run the verified recovery-capable bundle:

```sh
read -r -p "Cloudflare tunnel UUID: " tunnel_id
sudo /usr/bin/python3 -I polysia.pyz --prepare-cloudflare-host \
  --recover-tunnel "$tunnel_id" --workspace-backup /absolute/path/to/final-backup.sqlite3
```

If the destination already has the saved workspace, omit the backup option. The installer verifies that database before reconnecting. If the original workspace was lost and you accept losing its history, replace the backup option with `--empty-workspace`. Cloudflare retains routing and identity settings. It cannot restore saved runs. On a prepared host the same options work with `--cloudflare`.

The installer checks the selected tunnel, its protected socket route, the proxied DNS target and the single-owner Access application and policy. It requires the previous connectors to be disconnected, rotates the tunnel credential and starts the replacement. A stopped host with the old credential cannot reconnect. Keep the management token with the operator. If setup stops after rotation, rerun recovery on the intended destination. If the workspace was already restored, omit the backup option. To return to the former host, stop the replacement, transfer the latest verified database and use the same recovery procedure there.

If inventory is missing, the hostname has another policy, or the socket route differs, inspect the named resource in Cloudflare. Preserve existing resources while resolving the conflict. Changing hostname, account, owner or install path requires a separately planned move. After success, sign in as the owner, check a saved run and confirm its status and remaining shares. A private browser window without an owner session should show the Access login challenge.

To retire the site, stop and disable both services. Keep the workspace backup and Cloudflare resources for later recovery. For permanent removal, verify the account, hostname and IDs in the deployment journal before removing its DNS record, Access app with its policy, and disconnected tunnel in the dashboard. Keep shared identity providers and unrelated resources.

## Develop and verify

```sh
make setup         # Install locked web dependencies and compile the UI
make run           # Serve UI + API; development state is under .polysia/
make check         # Python domain, provider-contract and HTTP tests
make verify        # Also run the Chromium journey and offline installation checks
```

For a private release, run `make release-check` after `make verify` on an isolated Linux machine with local port 8765 available. It runs the README install command against the existing bundle without rebuilding it. Promote those exact bytes. After publication, download the asset as a repository reader and repeat with `make release-check RELEASE_BUNDLE=/path/to/polysia.pyz`.

Run `make provider-test` for the optional network check. It installs the artifact in a temporary directory, samples a share-limited SELL window, reads the real public rankings, inspects one profile and its realized P/L history, watches that public address, samples one public shadow window and removes the watch. The regular verification suite runs with controlled inputs. With a prior bundle available, run `python3 tests/install_smoke.py --upgrade-from /path/to/previous.pyz` after building to verify state survives an actual upgrade.

The browser checks use system Chromium (`CHROMIUM_PATH` selects another binary) and pinned Python test dependencies. To retain review screenshots, run `make browser-test BROWSER_ARGS="--screenshots /tmp/polysia-review"`. Local mode uses only the Python standard library. The optional HTTPS origin also uses PyJWT and cryptography. `GET /api/v1/health` checks local storage and reports the software version and, for an installation, the artifact SHA-256 recorded by the installer. The System status screen shows runtime health separately from provider coverage.

**Architecture decision.** React, TypeScript and Vite render the client. One Python process serves the built assets and the versioned HTTP API over loopback locally, or over a private Unix socket in the optional owner-only HTTPS deployment. SQLite serializes each local replay transition and stores operator preferences. A standalone offline installer avoids a container registry, database service and execution worker for this single-user, user-stepped workflow. Revisit PostgreSQL and an isolated worker when concurrent operators or unattended execution become requirements. Live authority must be independently enforced before enabling either a signer or venue writes.

## Public observations

Public shadow trials use interval polling. The [paired source study](provider.md#paired-source-decision-26-november-2026) found no improvement in usable observations from Polygon-triggered corroboration.

To sample public BUY windows from an installation, choose a new output file in an existing directory. This example declares three two-second windows at 10 pUSD each. The study writes its plan, attempts, receipts and counts as JSON Lines. Each window has its own unfunded budget. [Sampling policy and provider evidence](provider.md#budgeted-observations)

```sh
"$HOME/.local/share/polysia/current/polysia" study 0xc69bd5567b40ef4d11922eaa57e1f9be1c642076 \
  --budget 10 --seconds 2 --windows 3 --retry-empty --recheck-after 30 --to ./buy-study.jsonl
```

`--retry-empty` schedules one more activity read three seconds after the same window closes, if the first page was complete, showed no ordinary BUY, and the age limit still allows a book check. The summary counts additional reads, BUY detections and capacity estimates. Omit the flag for the original one-read study.

`--recheck-after 30` separately waits until the series finishes, waits 30 seconds, then rereads each interval once. Those pages can reveal later activity. They never produce a capacity estimate. A failed read or a partial page with no BUY leaves that comparison unknown. Time between windows is unobserved.
