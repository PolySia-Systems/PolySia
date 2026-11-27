# Operating PolySia

Run the [README install command](../README.md#install-on-linux) in the destination Linux terminal. The shell keeps terminal input available for prompts and runs the installer only after curl completes successfully. The installer downloads the named public release, checks its pinned SHA-256 and runs the existing bundled setup. Website setup stages and runs the verified bundle with administrator privileges. The app runs under its dedicated service user.

Local mode works with Python 3.12 or later and SQLite. On Ubuntu 24.04 and 26.04 the installer can obtain a missing runtime from the distribution. Private HTTPS hosting is supported on Ubuntu 26.04 amd64 with systemd.

For offline use, transfer the bundle privately and verify it against the matching tagged installer's SHA-256 before running `python3 -I polysia.pyz --start` on Linux.

## Update and recover

The default prefix is `$HOME/.local/share/polysia`. Data lives in `data/workspace.sqlite3` within it. Before a local upgrade, back up the running workspace, stop its service or foreground process and install the new bundle into the same prefix. Startup migrates the workspace and preserves the recorded policy for existing public runs. To downgrade, restore the matching pre-upgrade backup with the earlier version.

For a pinned or offline installation from a trusted checkout, [verified_install.py](../deploy/verified_install.py) verifies a bundle against an independently obtained release digest before running it. Use `--release TAG` to download with GitHub CLI or `--file` with a transferred bundle. The verified bundle supports offline local use and can install a persistent systemd user service with `--service` when lingering is enabled.

To back up a running installation and verify a restore, choose two new file paths in an existing directory. The launcher checks SQLite storage and reconciles replay balances, public shadow positions and cash with their saved decisions before publishing the copy. Both paths must be unused.

```sh
launcher="$HOME/.local/share/polysia/current/polysia"
"$launcher" backup --to ./workspace-backup.sqlite3
"$launcher" restore --from ./workspace-backup.sqlite3 --to ./workspace-restored.sqlite3
POLYSIA_DB="$PWD/workspace-restored.sqlite3" "$launcher" --port 8766
```

### Return to a previous release

Pause use during an upgrade. A version change with an existing database saves a checked copy under `backups/` before switching the launcher. The backup filename starts with the previous release digest. Keep an off-host copy. A snapshot contains only changes committed by the time it was taken.

For a local rollback, stop the application, obtain the verified previous bundle, and install it into a **new** prefix with `python3 -I polysia.pyz --prefix "$HOME/polysia-rollback"`. Use its launcher to restore the matching snapshot to that prefix's unused database path, then start it:

```sh
mkdir -p "$HOME/polysia-rollback/data"
"$HOME/polysia-rollback/current/polysia" restore --from /path/to/snapshot.sqlite3 --to "$HOME/polysia-rollback/data/workspace.sqlite3"
"$HOME/polysia-rollback/current/polysia"
```

For HTTPS, stop both units on the current server. Follow **Recover an HTTPS site** on a clean supported destination with the previous verified recovery-capable bundle and matching snapshot. Keep the failed installation offline until the owner verifies the restored history. To uninstall local foreground mode, stop it, keep a verified backup outside the install prefix, and remove only the dedicated prefix when ready to discard its history. For a local user service, first run `systemctl --user disable --now polysia.service`, remove its PolySia user unit and run `systemctl --user daemon-reload`.

## Optional owner-only HTTPS access

For first setup, use an active zone in your Cloudflare account and enable the [One-time PIN login method](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/). Create a [custom API token](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/) limited to that account and zone. The installer reads the zone and identity providers, manages DNS records in that zone, and manages tunnels and Access applications and policies in that account. Use Zone Read, DNS Edit, Cloudflare Tunnel Edit, Access Apps and Policies Edit, and Access Organizations, Identity Providers, and Groups Read. Store the token in your password manager. Enter it at the hidden terminal prompt. On a repeat installation, the deployment journal supplies the expected hostname and owner.

For a first installation or update, run the [README command](../README.md#install-on-linux) on the dedicated server and choose **Private website**. The installer prepares the service user, Ubuntu JWT libraries, a verified cloudflared binary and services that start at boot. It prompts for the management token after dropping root privileges. Keep the Ubuntu package sources and system Python trusted.

For automation with the verified bundle, run `sudo /usr/bin/python3 -I polysia.pyz --prepare-cloudflare-host` on the supported server. On an already prepared host, run `python3 -I polysia.pyz --cloudflare` as the dedicated service user with a lingering systemd user manager, PyJWT 2.x with cryptography and a trusted cloudflared supporting `tunnel run --token-file`. Supply `POLYSIA_HOSTNAME`, `POLYSIA_OWNER_EMAIL` and a token on standard input from a secret manager for noninteractive use.

Use a fresh, private install prefix for the first HTTPS deployment. The prefix stays reserved for HTTPS on later installs. For a separate local installation, use a single-user machine and a different prefix. When upgrading an earlier HTTPS candidate, stop any old foreground loopback launcher and disable any local `polysia.service` for that workspace first. Backup and restore remain available from the HTTPS installation’s launcher.

After setup, open the printed HTTPS address and sign in with the configured owner email. The application and connector use a private Unix socket, and the origin validates the Access signature, issuer, application audience, expiry and owner. Rerun from the same OS user and prefix to recover an interruption. The installer records its own resource IDs and keeps the connector credential under `remote/` in that prefix. From a root SSH session, take the site offline with `systemctl --user --machine=polysia-service@.host disable --now polysia-tunnel.service`. From the same root shell, inspect services with `systemctl --user --machine=polysia-service@.host status polysia-origin.service polysia-tunnel.service`. The owner-login email and test resources must belong to the authorized deployment. The local installation works offline with no Cloudflare configuration. All modes are single-owner and simulated.

### Recover an HTTPS site

Use the original hostname and owner email. Use a tunnel dedicated to this site. To update on the original machine, back up the database and rerun the HTTPS installer. A matching running release can pass its checks without restarting. If you replace your **management API token**, enter the new token at the next installer prompt. The connector uses a separate credential.

For a replacement host or a restored snapshot, schedule one transfer at a time. Choose **Private website**. The installer checks the saved deployment and the hostname before offering a transfer. Clones can share a machine ID. Keep the old host offline, or disable its tunnel and stop its origin before the final database backup. Run service commands in the dedicated user's systemd session:

```sh
systemctl --user disable --now polysia-tunnel.service polysia-origin.service
"$HOME/.local/share/polysia/current/polysia" backup --to ./final-backup.sqlite3
```

Copy the backup privately to the new host. The dedicated service user needs read access to the file and its parent directories. On the new host run the [README command](../README.md#install-on-linux) and choose **Private website**. The installer verifies an existing workspace. If the workspace is missing, choose the backup option and enter the absolute path. Choose a new workspace only if you accept starting without saved history. Cloudflare retains routing and identity settings.

For noninteractive recovery, add `--recover` to the verified bundle's HTTPS setup command. With no workspace on the destination, also pass `--workspace-backup /absolute/path/to/backup.sqlite3` or explicitly choose `--empty-workspace`.

The installer discovers the tunnel from the hostname's proxied DNS record. It checks the tunnel, its protected socket route, the proxied DNS target and the single-owner Access application and policy. During explicit recovery, it can move the original polysia-test socket to the standard polysia-service socket after it verifies the workspace choice and the entire owner-only route. An already correct route needs no change. It requires the previous connectors to be disconnected, rotates the tunnel credential and starts the replacement. A stopped host with the old credential cannot reconnect. The guided installer asks before transferring the site and accepts a replacement token at the hidden prompt if Cloudflare rejects the first one. If setup stops after rotation, rerun recovery on the intended destination. Recovery reuses an already restored workspace. To return to the former host, stop the replacement, transfer the latest verified database and use the same recovery procedure there.

If inventory is missing, the hostname has another policy, or an unrecognized socket route differs, inspect the named resource in Cloudflare. Preserve existing resources while resolving the conflict. Changing hostname, account, owner or any other install path requires a separately planned move. After success, sign in as the owner, check a saved run and confirm its status and remaining shares. A private browser window without an owner session should show the Access login challenge.

To retire the site, stop and disable both services. Keep the workspace backup and Cloudflare resources for later recovery. For permanent removal, verify the account, hostname and IDs in the deployment journal before removing its DNS record, Access app with its policy, and disconnected tunnel in the dashboard. Keep shared identity providers and unrelated resources.

## Develop and verify

```sh
make setup         # Install locked web dependencies and compile the UI
make run           # Serve UI + API; development state is under .polysia/
make check         # Python domain, provider-contract and HTTP tests
make verify        # Also run the Chromium journey and offline installation checks
```

For a release, build the bundle, set its version and SHA-256 in the top-level [install script](../install), and run `make verify` followed by `make release-check` on isolated Linux with port 8765 free. That check exercises the README command in a terminal with controlled download responses. Upload the tested `polysia.pyz` and `install` as a prerelease. On a machine with Docker, run `make fresh-install-check FRESH_INSTALL_ARGS=--candidate` to exercise the real downloads and package installation on minimal Ubuntu before promotion. Mark the passing release as latest. Rerun `make fresh-install-check` with the published instructions and `make release-check RELEASE_BUNDLE=/path/to/polysia.pyz RELEASE_GUIDE=/path/to/install` with both anonymously downloaded assets. Exercise the live owner-only route when it changes. If distribution becomes private, retain a reachable installation entry and design the download authorization before changing visibility.

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
