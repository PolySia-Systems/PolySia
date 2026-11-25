# Provider evidence

Checked 2026-11-25 for the public watch-only wallet workflow. The integration uses a single HTTPS GET, needs no SDK dependency or credentials, and sends only the entered address and position filters to Polymarket.

| Capability | Evidence and limits |
| --- | --- |
| Watch a wallet | The official Python client lists public positions by trading wallet. A valid address permits a lookup. It establishes neither wallet ownership nor signing authority. |
| Open ordinary positions | The adapter requests `GET https://data-api.polymarket.com/v2/positions` with `user`, `status=OPEN` and `limit=20`. It checks the returned wallet, open status, token identity, exact decimal share quantity and cursor envelope. A further page is reported as partial. The result excludes closed, redeemable and combo positions, orders, cash and other account activity. |
| Freshness | `observedAt` is the local UTC receipt time for a successful response. The provider's indexing delay is unknown. `checkedAt` records the latest attempt, including failures. A successful empty page means zero matching rows within this query. Failed or incompatible responses leave holdings unknown. |
| Compatibility check | Both rows of the official version 0.20.1 test sample decoded locally with their distinct tokens and 400000.0 shares each, inside a v2 pagination envelope. Repository tests additionally cover exact decimals, partial coverage, mixed wallets, duplicate rows, schema drift and network errors. |
| Live verification gate | A GET using the public SDK sample address received HTTP 403 from this environment's CONNECT proxy before reaching the Data API. Confirm a successful lookup, partial pagination and observation time from a host already authorized to access the endpoint before claiming production compatibility. An SDK sample supplies contract evidence only. |
| Rankings and shadow execution | The discovery and replay fixtures are separate from this account reader. No leaderboard equivalence, historical book coverage, profitability, owner authentication, delegated execution, or live eligibility has been established. |

Inspected the official `polymarket-client` 0.20.1 source at commit `81e8abfb2a131ef3874f8fe405c9d95b2123fcdf`. The positions API still exposes legacy-named cost fields. This adapter displays shares only. Extending it to show portfolio equity requires independent evidence about current collateral, valuation and coverage. [Request builder](https://github.com/Polymarket/py-sdk/blob/81e8abfb2a131ef3874f8fe405c9d95b2123fcdf/src/polymarket/_internal/actions/data.py) · [Response envelope](https://github.com/Polymarket/py-sdk/blob/81e8abfb2a131ef3874f8fe405c9d95b2123fcdf/src/polymarket/_internal/data_envelope.py) · [Position sample](https://github.com/Polymarket/py-sdk/blob/81e8abfb2a131ef3874f8fe405c9d95b2123fcdf/tests/fixtures/data_v2/positions.json)

**Managed-source decision.** The current slice needs one public lookup and a bounded replay. A Goldsky feed adds a managed service without resolving the missing follower-side book observations. Keep direct reads and defer indexing. Before selecting an event feed, compare a bounded set of identifiable source fills on coverage, first arrival, redelivery, corrections, coverage of current market versions and total cost as described in section 8.8 of the plan. No managed pipeline or paid experiment was provisioned.

## Prospective observation

Run this from the repository root on a Linux host with authorized access to the public Data API and CLOB. The example uses the wallet in the upstream SDK fixture. Replace it with the public trading wallet to observe.

```sh
python3 -m apps.server.observe 0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b --seconds 10
```

The CLI starts its UTC window at the next whole second, waits 1–30 seconds, then reads one page of new BUY activity. If the page is complete and contains an ordinary wallet-relative BUY, the CLI selects the earliest reported event and immediately requests that token's book. A window containing more than 20 rows is incomplete. An empty response can reflect indexing lag. Maximum two GETs, 256 KiB per response, four-second socket timeout, and a command deadline 12 seconds beyond the selected window.

JSON output records event time, local retrieval times, transaction, condition and token IDs, exact reported price and shares, provider book timestamp and the best three displayed asks. The source-to-receipt difference includes the chosen sampling window and possible clock skew. `observed` means a matching book was retrieved after detection. Old or future book timestamps, empty asks, unsupported responses and endpoint failures produce partial or unavailable evidence. Exit code 0 covers observed and waiting states, and 2 covers incomplete or unavailable evidence.

**Execution identity remains unresolved.** The ordinary public activity model exposes a transaction hash. A transaction can contain multiple fills and overlapping representations. The probe leaves `fillId` null and emits no copy signal, order, fee estimate or modeled return. Connecting these observations to a prospective shadow decision requires a reliable participant-relative fill identity, instrument version, and follower costs. The checked SDK distinguishes normal trades from combos and reports ask levels in descending price order. [Activity model](https://github.com/Polymarket/py-sdk/blob/81e8abfb2a131ef3874f8fe405c9d95b2123fcdf/src/polymarket/models/data/activity.py) · [Book model](https://github.com/Polymarket/py-sdk/blob/81e8abfb2a131ef3874f8fe405c9d95b2123fcdf/src/polymarket/models/clob/order_book.py) · [Book request](https://github.com/Polymarket/py-sdk/blob/81e8abfb2a131ef3874f8fe405c9d95b2123fcdf/src/polymarket/_internal/actions/clob.py)

On 2026-11-25 the one-second command returned `unavailable` on the first GET, with exit code 2. It produced no activity or book sample. Contract tests cover the paired read and the partial, empty and inaccessible paths.
