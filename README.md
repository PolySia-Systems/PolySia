# PolySia

Follow a public Polymarket wallet with simulated cash. See which orders your budget could cover, what you would still hold, and why a trade was skipped. You can also practice offline with a fictional trader. PolySia runs on your Linux machine. It never asks for a wallet key or places a real order.

[Install](#install-on-linux) · [Try a replay](#try-your-first-replay) · [Updates and help](#updates-and-help)

## Install on Linux

Open a terminal **on the Linux machine where PolySia should run**. If you use Termius or another SSH client, connect to your server first. On a new or minimal Ubuntu server, open the **Fresh Ubuntu** option below. Otherwise copy this line.

```sh
app=$(curl -qfsSL --proto '=https' https://github.com/PolySia-Systems/PolySia/releases/latest/download/install) && sh -c "$app"
```

<details>
<summary><strong>Fresh Ubuntu · install prerequisites and PolySia in one paste</strong></summary>

Use root or an account with sudo on Ubuntu. Copy this whole block into the server terminal.

```sh
(
  set -e
  if [ "$(id -u)" = 0 ]; then set --; else set -- sudo; fi
  "$@" apt-get -qq update
  "$@" env DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends --no-remove install curl ca-certificates </dev/null
  app=$(curl -qfsSL --proto '=https' https://github.com/PolySia-Systems/PolySia/releases/latest/download/install) && sh -c "$app"
)
```

</details>

- **Local workspace** opens on this machine at the address printed in the terminal. The installer checks Python and SQLite and can install them on supported Ubuntu releases. Ctrl-C stops the app. Reopen it with `"$HOME/.local/share/polysia/current/polysia"`.
- **Private website** sets up or updates an owner-only site on this server. Choose this to open the site from your phone or computer after you close SSH. Use a dedicated Ubuntu 26.04 LTS amd64 host with systemd and administrator access. Have your hostname, owner email and Cloudflare management token ready. Open the printed HTTPS address and sign in.
  If the site already exists, the installer checks whether to update or reconnect it. Have the old host offline for a transfer and have a workspace backup ready to restore saved runs. [Website setup and recovery](docs/operations.md#recover-an-https-site)

## Check your wallet balance

In **Accounts**, paste the public trading wallet address from your Polymarket profile and select **Watch account**. Choose **Read cash balance** to see the pUSD held on Polygon and the time it was checked. Open orders may reserve part of this amount. **Load holdings value** shows the value of your market positions separately.

To follow multiple accounts, enter an optional wallet name and select **Save wallet** for each address. **Saved wallets** switches the active account and reads its positions. Select **Read cash balance** for a fresh reading of that wallet. Wallet names stay in the local workspace.

Open **System status → Shadow portfolio overview** to see how many portfolios use background sampling and which runs need review. Select a run name to inspect its decisions, simulated cash, fees and remaining positions.

## Try your first replay

1. In **Discover**, choose **Try a shadow replay**, then **Start shadow**. Keep the default budget for this example.
2. Select **Observe next signal** twice. The first fictional purchase fills. The second fills only partly. Look at the share count after each purchase.
3. Choose **Stop run**. You can still see the shares you hold. To revisit the result later, open **Scenario replays**.

To try a public wallet, open **Public rankings** and choose a period. Use **Next page** to explore more ranked wallets, or paste a wallet address. Set **Budget per buy** and open a trader. **Check next buy** tests one short window using public data. **Set up public shadow run** carries your wallet and per-buy cap into the simulation. Choose the total starting cash before creating the run. A quiet window leaves the wallet’s suitability unknown. You can also select two wallets across pages to compare their holdings and any buy checks from this visit.

## Updates and help

For hands-off simulation, open a public run and choose **Enable background sampling**. Keep the PolySia server running and close the browser if you wish. Reopen **Public shadow**, select the run and review its decisions, cash, costs and open positions. Each check covers a short BUY window. Gaps can contain missed trades. Pause or stop the run to cancel background sampling. After a pause, resume and explicitly enable it again. A server restart resumes enabled runs and skips the offline interval. SELL observations remain operator initiated.

- **Moving an owner-only HTTPS site?** Keep its Cloudflare resources. Follow the [host recovery guide](docs/operations.md#recover-an-https-site).
- **Updating an existing installation?** Stop local foreground use, then rerun the install command. Switching releases saves a verified pre-upgrade workspace copy. The guide includes the backup, restore and rollback commands. [Update and recovery](docs/operations.md#update-and-recover)
- **Download missing or denied?** Check that the server can reach GitHub and open the [release page](https://github.com/PolySia-Systems/PolySia/releases/latest).
- **Checksum failed?** Stop there. Download a fresh copy from the linked release and repeat the check. If it still fails, report it.
- **Local port busy?** Stop the other local instance and rerun the command.
- **Need help?** Include the step, the error, your Linux and Python versions, and the build shown in **System status** if the app opens. Leave out tokens, email addresses and workspace data. [Public issue tracker](https://github.com/PolySia-Systems/PolySia/issues)

## Project and evidence

[Operations and developer commands](docs/operations.md) · [Verified provider behavior](docs/provider.md) · [Master Plan](docs/MASTER_PLAN.md) · [Contribution instructions](AGENTS.md)

**Next evidence gate.** Observe a first-time owner starting from this page without coaching. Can they install, explain a skipped entry, stop a run and find the remaining shares after restart? Record completion and any help needed in the task or PR.
