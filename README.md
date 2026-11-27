# PolySia

Follow a public Polymarket wallet with simulated cash. See which orders your budget could cover, what you would still hold, and why a trade was skipped. You can also practice offline with a fictional trader. PolySia runs on your Linux machine. It never asks for a wallet key or places a real order.

[Install](#install-on-linux) · [Try a replay](#try-your-first-replay) · [Updates and help](#updates-and-help)

## Install on Linux

Open a terminal on your own computer. Use a Linux shell, or Git Bash on Windows for a remote installation. Install [GitHub CLI](https://cli.github.com/) and sign in with a GitHub account that can read this repository (`gh auth login`). Keep that login on your computer. Copy this whole command into the terminal:

```sh
(
  set -e
  stage=$(mktemp -d)
  cd "$stage"
  trap 'rm -f guide.sh polysia.pyz; cd /; rmdir "$stage"' EXIT
  gh release download v0.5.3 -R github.com/PolySia-Systems/PolySia -p guide.sh -p polysia.pyz
  printf '%s  %s\n' 3b17a9fb7bed2a6eeaf2c1839b657d9f4ce0306eb84384d6e8b97f1498104b53 guide.sh 45ea9d466f6da5c5f72d69bc5de3b989f0768e80e16cc09e3667b2550d13820a polysia.pyz | sha256sum -c -
  sh ./guide.sh
)
```

Choose **1** for this single-user Linux computer (Python 3.12+ with SQLite). Open the local address printed in the terminal. Ctrl-C stops the app. Reopen it with `"$HOME/.local/share/polysia/current/polysia"`.

Choose **2** for a new private HTTPS site or an update on its current server. Choose **3** after replacing the server or restoring a snapshot. Both use your existing SSH access to a dedicated Ubuntu 26.04 LTS amd64 host. Have the hostname, owner's email and scoped Cloudflare token ready. For recovery, take the previous host offline first and copy any workspace backup to the new server. Open the printed HTTPS address and sign in as the owner. [Cloudflare setup and recovery](docs/operations.md#optional-owner-only-https-access)

## Try your first replay

1. In **Discover**, choose **Try a shadow replay**, then **Start shadow**. Keep the default budget for this example.
2. Select **Observe next signal** twice. The first fictional purchase fills. The second fills only partly. Look at the share count after each purchase.
3. Choose **Stop run**. You can still see the shares you hold. To revisit the result later, open **Scenario replays**.

To try a public wallet, open **Public rankings**, choose a trader, then **Set up public shadow run**. This needs internet access. If a window has no eligible order or a price is missing, inspect the reason in the decision history. Watching an address gives read-only access to public data.

## Updates and help

- **Moving an owner-only HTTPS site?** Keep its Cloudflare resources. Follow the [host recovery guide](docs/operations.md#recover-an-https-site).
- **Updating an existing installation?** Stop local foreground use, then rerun the install command. Switching releases saves a verified pre-upgrade workspace copy. The guide includes the backup, restore and rollback commands. [Update and recovery](docs/operations.md#update-and-recover)
- **Download missing or denied?** Sign in to GitHub with the account that can read this private repository and open the [release page](https://github.com/PolySia-Systems/PolySia/releases/latest).
- **Checksum failed?** Stop there. Download a fresh copy from the linked release and repeat the check. If it still fails, report it.
- **Local port busy?** Stop the other local instance and rerun the command.
- **Need help?** Include the step, the exact error, your Linux and Python versions, and the build shown in **System status** if the app opens. Leave out tokens, email addresses and workspace data. [Private issue tracker](https://github.com/PolySia-Systems/PolySia/issues)

## Project and evidence

[Operations and developer commands](docs/operations.md) · [Verified provider behavior](docs/provider.md) · [Master Plan](docs/MASTER_PLAN.md) · [Contribution instructions](AGENTS.md)

**Next evidence gate.** Observe a first-time owner starting from this page without coaching. Can they install, explain a skipped entry, stop a run and find the remaining shares after restart? Record completion and any help needed in the task or PR.
