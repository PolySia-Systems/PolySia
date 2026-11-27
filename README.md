# PolySia

Follow a public Polymarket wallet with simulated cash. See which orders your budget could cover, what you would still hold, and why a trade was skipped. You can also practice offline with a fictional trader. PolySia runs on your Linux machine. It never asks for a wallet key or places a real order.

[Install](#install-on-linux) · [Try a replay](#try-your-first-replay) · [Updates and help](#updates-and-help)

## Install on Linux

Open a terminal **on the Linux machine where PolySia should run**. If you use Termius or another SSH client, connect to your server first. Copy this command and paste it once.

```sh
(
  set -e
  if [ -f /etc/debian_version ] && { ! command -v curl >/dev/null || [ ! -s /etc/ssl/certs/ca-certificates.crt ]; }; then
    if [ "$(id -u)" = 0 ]; then set --; else set -- sudo; fi
    "$@" apt-get -qq update
    "$@" env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get -qy --no-install-recommends --no-remove install curl ca-certificates </dev/null
  fi
  polysia=$(curl -qfsSL --proto '=https' https://github.com/PolySia-Systems/PolySia/releases/latest/download/install) && sh -c "$polysia"
)
```

On minimal Ubuntu this command installs curl and trusted certificates as needed. Use root or an account with sudo for package installation. The installer verifies the public release and guides you through setup.

- **Local workspace** opens on this machine at the address printed in the terminal. The installer checks Python and SQLite and can install them on supported Ubuntu releases. Ctrl-C stops the app. Reopen it with `"$HOME/.local/share/polysia/current/polysia"`.
- **Private website** sets up or updates an owner-only site on this server. Choose this to open the site from your phone or computer after you close SSH. Use a dedicated Ubuntu 26.04 LTS amd64 host with systemd and administrator access. Have your hostname, owner email and Cloudflare management token ready. Open the printed HTTPS address and sign in.
- **Recover website** reconnects an existing site after replacing its server or restoring a snapshot. Take the previous host offline first. A workspace backup restores saved runs. [Website setup and recovery](docs/operations.md#optional-owner-only-https-access)

## Try your first replay

1. In **Discover**, choose **Try a shadow replay**, then **Start shadow**. Keep the default budget for this example.
2. Select **Observe next signal** twice. The first fictional purchase fills. The second fills only partly. Look at the share count after each purchase.
3. Choose **Stop run**. You can still see the shares you hold. To revisit the result later, open **Scenario replays**.

To try a public wallet, open **Public rankings**, choose a trader, then **Set up public shadow run**. This needs internet access. If a window has no eligible order or a price is missing, inspect the reason in the decision history. Watching an address gives read-only access to public data.

## Updates and help

- **Moving an owner-only HTTPS site?** Keep its Cloudflare resources. Follow the [host recovery guide](docs/operations.md#recover-an-https-site).
- **Updating an existing installation?** Stop local foreground use, then rerun the install command. Switching releases saves a verified pre-upgrade workspace copy. The guide includes the backup, restore and rollback commands. [Update and recovery](docs/operations.md#update-and-recover)
- **Download missing or denied?** Check that the server can reach GitHub and open the [release page](https://github.com/PolySia-Systems/PolySia/releases/latest).
- **Checksum failed?** Stop there. Download a fresh copy from the linked release and repeat the check. If it still fails, report it.
- **Local port busy?** Stop the other local instance and rerun the command.
- **Need help?** Include the step, the error, your Linux and Python versions, and the build shown in **System status** if the app opens. Leave out tokens, email addresses and workspace data. [Public issue tracker](https://github.com/PolySia-Systems/PolySia/issues)

## Project and evidence

[Operations and developer commands](docs/operations.md) · [Verified provider behavior](docs/provider.md) · [Master Plan](docs/MASTER_PLAN.md) · [Contribution instructions](AGENTS.md)

**Next evidence gate.** Observe a first-time owner starting from this page without coaching. Can they install, explain a skipped entry, stop a run and find the remaining shares after restart? Record completion and any help needed in the task or PR.
