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

Open **Notifications** to find past observation warnings and simulated buys or sales across runs, including events recorded while your browser was closed. Repeated events are grouped by run and type. Open the linked run for the latest state and its full decision history.

## Try your first replay

1. In **Discover**, choose **Try a shadow replay**, then **Start shadow**. Keep the default budget for this example.
2. Select **Observe next signal** twice. The first fictional purchase fills. The second fills only partly. Look at the share count after each purchase.
3. Select **Observe next signal** once more. Under **Signal activity**, read why the purchase was skipped. There was no order book for this signal, so the run spent nothing on it.
4. Choose **Stop run**. Reopen **Scenario replays** and select this run. With the default budget you should find $88.26 in simulated cash and 23 open Yes shares.

To try a public wallet, open **Public rankings** and choose a period. Use **Next page** to explore more ranked wallets, or paste a wallet address. Set **Budget per buy** and open a trader. **Check next buy** tests one short window using public data. **Set up public shadow run** carries your wallet and per-buy cap into the simulation. Choose the total starting cash before creating the run. A quiet window leaves the wallet’s suitability unknown. Select two wallets across pages, then choose **Compare wallets → Check both wallets** to test the same budget on each. The checks run one after the other. Read the time, page coverage and result on each wallet card. Your shortlist keeps the latest check for each saved wallet in this browser. Enter the same budget when you return to see those results again.

## Updates and help

In a two-wallet comparison, **Compare holding periods** checks the scheduled market end dates on each returned positions page against the day you may need your cash. The comparison reports missing dates. Settlement time and the ability to sell early depend on the market.

To follow several leaders prospectively with one simulated balance, enable background BUY sampling on runs for at least two different wallets. Open **Saved public runs → Follow leaders with one simulated balance**, choose the runs and starting cash, and start the shared portfolio. Close the browser while the server stays online. Reopen **Shared background portfolios** to inspect cash, entry cost, holdings and missed windows. Pausing or stopping the shared portfolio preserves its positions and each source run's settings. Shared portfolios currently model purchases only.

In **Saved public runs**, choose **Replay buys with one shared budget** once you have two or more runs. Select the runs, enter one simulated starting balance and replay their recorded buys together. Each purchase uses the remaining cash and displayed shares. The replay leaves positions open and shows the modeled cost for each run.

In **Settings → Appearance**, choose a light or dark theme. Under **Workspace accent**, preview Forest or Ocean, open **View discovery** to see it in use, then return to Settings to publish or discard it. To restore the default, preview and publish Forest.

Use **Buy check at this budget** in Public rankings to filter wallets you have browsed or shortlisted in the current period. An observation at another budget cannot establish a match. The run overview shows the last seven days of cash movements, decisions and outstanding exposure.

In **Last seven days**, choose **Export this period** to save the displayed interval, its cash totals, and the decisions behind them as JSON. If the run changed in the meantime, select **Refresh report** before exporting. **Export run** includes the complete journal and retained observation receipts.

In a public run, **Add simulated cash** records a contribution separately from gains and fees. Adding cash preserves a pause. **Decision history → Recheck public activity** lets you revisit a quiet BUY window if the provider indexed trades later. A recheck keeps the original decision and portfolio balances intact.

While a run is active or paused, **Withdraw simulated cash** removes up to the free cash shown. Shares stay open. Future purchases are limited by the cash left and the saved per-entry cap. Withdrawing below 1 pUSD turns off background sampling. The weekly report and its export show withdrawals separately from trading results.

Under **Open simulated positions**, choose **Check final payout** for an outcome. A supported Polygon condition can show a positive payout, a final zero, or an unresolved result. The check shows gross collateral for simulated shares. The journal and cash balance change only through a recorded portfolio action.

Public rankings remembers your two selected wallets for each ranking period in this browser. If the provider is unavailable, you can reopen the saved comparison and check its retrieval dates.

To revise a portfolio budget, open its run and choose **Change future BUY cap**. Enter an amount from 1 pUSD up to the run's starting capital. Each future BUY is also limited by remaining cash. The decision history records the previous and new limits. To return to a previous limit, enter that amount again. Changing the cap keeps a paused run paused.

For hands-off simulation, open a public run and choose **Enable background sampling**. Keep the PolySia server running and close the browser if you wish. Reopen **Public shadow**, select the run and review its decisions, cash, costs and open positions. Each check covers a short BUY window. Gaps can contain missed trades. Pause or stop the run to cancel background sampling. After a pause, resume and explicitly enable it again. A server restart resumes enabled runs and skips the offline interval. SELL observations remain operator initiated.

Enabled runs take turns. Following more wallets can increase the gap before each wallet gets checked again. To see the coverage your host actually achieved, open a run's **Decision history**, expand **Observation details** on consecutive checks and compare their window times. [Measured sampling intervals](docs/provider.md#background-sampling-capacity)

- **Moving an owner-only HTTPS site?** Keep its Cloudflare resources. Follow the [host recovery guide](docs/operations.md#recover-an-https-site).
- **Updating an existing installation?** Stop local foreground use, then rerun the install command. Switching releases saves a verified pre-upgrade workspace copy. The guide includes the backup, restore and rollback commands. [Update and recovery](docs/operations.md#update-and-recover)
- **Download missing or denied?** Check that the server can reach GitHub and open the [release page](https://github.com/PolySia-Systems/PolySia/releases/latest).
- **Checksum failed?** Stop there. Download a fresh copy from the linked release and repeat the check. If it still fails, report it.
- **Local port busy?** Stop the other local instance and rerun the command.
- **Need help?** Include the step, the error, your Linux and Python versions, and the build shown in **System status** if the app opens. Leave out tokens, email addresses and workspace data. [Public issue tracker](https://github.com/PolySia-Systems/PolySia/issues)

## Project and evidence

[Operations and developer commands](docs/operations.md) · [Verified provider behavior](docs/provider.md) · [Master Plan](docs/MASTER_PLAN.md) · [Contribution instructions](AGENTS.md)

**Next evidence gate.** Observe a first-time owner starting from this page without coaching. Can they install, explain a skipped entry, stop a run and find the remaining shares after restart? Record completion and any help needed in the task or PR.
