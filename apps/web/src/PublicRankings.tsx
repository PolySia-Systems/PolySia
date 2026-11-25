import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ArrowUpRight, RefreshCw, Search } from 'lucide-react'
import { api, type Account, errorMessage } from './api'
import { HoldingsValue, PositionSnapshot } from './Workspace'
import { PublicObservation } from './PublicObservation'
import { PublicHistory } from './PublicHistory'
import './rankings.css'

interface PublicTrader {
  address: string
  name: string
  rank: number
  pnl: string
  volumeShares: string
}
interface Leaderboard {
  status: 'available' | 'unavailable'
  source: string
  checkedAt: string
  observedAt: string | null
  period: string
  message: string
  complete: boolean
  leaders: PublicTrader[]
}

const periods = { day: 'Past day', week: 'Past week', month: 'Past month', all: 'All time' }
type Period = keyof typeof periods
const summaryNumber = new Intl.NumberFormat('en', { maximumFractionDigits: 2 })

type ComparisonRead = { account: Account } | { error: string }

function openMarkets(read?: ComparisonRead) {
  if (!read || !('account' in read) || read.account.status !== 'available') return null
  const markets = new Map<string, string>()
  for (const row of read.account.positions) {
    if (row.status === 'REDEEMABLE' || Number(row.shares) === 0) continue
    if (row.status !== 'OPEN' || !row.conditionId?.match(/^0x[0-9a-f]{64}$/)) return null
    markets.set(row.conditionId, row.market)
  }
  return markets
}

function PublicComparison({
  traders,
  board,
  close,
}: {
  traders: PublicTrader[]
  board: Leaderboard
  close: () => void
}) {
  const [reads, setReads] = useState<Record<string, ComparisonRead>>({})
  const heading = useRef<HTMLHeadingElement>(null)
  const [left, right] = traders
  useEffect(() => {
    let current = true
    heading.current?.focus()
    for (const trader of [left, right]) {
      api<Account>('public/traders/' + trader.address)
        .then(
          (account): ComparisonRead =>
            account.address === trader.address ? { account } : { error: 'Wallet mismatch.' },
        )
        .catch((e): ComparisonRead => ({ error: errorMessage(e) }))
        .then((result) => {
          if (current) setReads((old) => ({ ...old, [trader.address]: result }))
        })
    }
    return () => {
      current = false
    }
  }, [left.address, right.address])
  const leftMarkets = openMarkets(reads[left.address])
  const rightMarkets = openMarkets(reads[right.address])
  const shared =
    leftMarkets && rightMarkets
      ? [...leftMarkets.entries()].filter(([id]) => rightMarkets.has(id))
      : null
  const partial = traders.some((trader) => {
    const read = reads[trader.address]
    return read && 'account' in read && !read.account.complete
  })
  const settled = traders.every((trader) => reads[trader.address])
  let overlapSummary = 'Reading position pages…'
  if (settled) {
    if (!shared) {
      overlapSummary =
        'Unknown. Both wallets need available positions with verified market identities.'
    } else if (partial) {
      overlapSummary = shared.length
        ? `At least ${shared.length} shared on the returned pages. Total overlap is unknown.`
        : 'No shared markets found on the returned pages. Total overlap is unknown.'
    } else {
      overlapSummary =
        shared.length === 0
          ? '0 shared open markets on the complete responses.'
          : `${shared.length} shared open market${shared.length === 1 ? '' : 's'}.`
    }
  }
  return (
    <section className="panel panel-body stack" aria-label="Public wallet comparison">
      <div className="panel-head">
        <h2 ref={heading} tabIndex={-1}>
          Wallet comparison
        </h2>
        <button className="btn" onClick={close}>
          Back to rankings
        </button>
      </div>
      <p className="muted">
        {periods[board.period as Period]} ·{' '}
        {board.period === 'all'
          ? 'Lifetime realized P/L'
          : 'Marked equity change net of external flows'}{' '}
        · Volume in shares. Rankings retrieved{' '}
        {new Date(board.observedAt!).toLocaleString('en-GB', { timeZone: 'UTC' })} UTC.
      </p>
      <div className="comparison">
        {traders.map((trader) => {
          const read = reads[trader.address]
          const account = read && 'account' in read ? read.account : null
          return (
            <article key={trader.address} className="compare-card public-compare-card">
              <h3>{trader.name}</h3>
              <code>{trader.address}</code>
              <dl className="facts">
                <div>
                  <dt>Provider rank</dt>
                  <dd>{trader.rank}</dd>
                </div>
                <div>
                  <dt>P/L (USDC)</dt>
                  <dd>{summaryNumber.format(Number(trader.pnl))}</dd>
                </div>
                <div>
                  <dt>Volume (shares)</dt>
                  <dd>{summaryNumber.format(Number(trader.volumeShares))}</dd>
                </div>
                <div>
                  <dt>Positions</dt>
                  <dd>
                    {!read
                      ? 'Reading…'
                      : account?.status === 'available'
                        ? account.complete
                          ? 'Complete response'
                          : 'First page only'
                        : 'Unavailable'}
                  </dd>
                </div>
              </dl>
              <p className="workspace-note muted">
                {account?.observedAt
                  ? 'Retrieved ' +
                    new Date(account.observedAt).toLocaleString('en-GB', { timeZone: 'UTC' }) +
                    ' UTC'
                  : (account?.message ?? (read && 'error' in read ? read.error : ''))}
              </p>
            </article>
          )
        })}
      </div>
      <div className="stack public-overlap">
        <h3>Open-market overlap</h3>
        <p role="status">{overlapSummary}</p>
        {shared && shared.length > 0 && (
          <ul>
            {shared.map(([id, title]) => (
              <li key={id}>{title}</li>
            ))}
          </ul>
        )}
        <small className="muted">
          Counts distinct condition IDs with positive open ordinary positions in both snapshots.
          Each wallet is read separately. Different outcomes in the same market count as one shared
          market. Redeemable positions and combos are excluded.
        </small>
      </div>
    </section>
  )
}

function Profile({
  address,
  trader,
  period,
  close,
}: {
  address: string
  trader?: PublicTrader
  period: Period
  close: () => void
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    heading.current?.focus()
  }, [address])
  const [snapshot, setSnapshot] = useState<Account | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let current = true
    setSnapshot(null)
    setError('')
    api<Account>('public/traders/' + address)
      .then((data) => {
        if (data.address !== address)
          throw new Error('The position response identified a different wallet.')
        if (current) setSnapshot(data)
      })
      .catch((e) => {
        if (current) setError(errorMessage(e))
      })
    return () => {
      current = false
    }
  }, [address, revision])
  return (
    <div className="stack profile-snapshot">
      <div>
        <button className="text-link" onClick={close}>
          Back to rankings
        </button>
      </div>
      <div className="profile-label">
        <h2 ref={heading} tabIndex={-1}>
          {trader?.name ?? 'Public wallet'}
        </h2>
        {trader ? (
          <span className="badge">
            Provider rank {trader.rank} · {periods[period]}
          </span>
        ) : (
          <code>{address}</code>
        )}
      </div>
      {trader && (
        <p className="muted">
          Reported volume: {summaryNumber.format(Number(trader.volumeShares))} shares · P/L:{' '}
          {summaryNumber.format(Number(trader.pnl))} USDC
        </p>
      )}
      <div><a className="btn primary" href={'#/paper/new?' + new URLSearchParams({wallet: address, name: trader?.name ?? 'Public wallet'})}>
        Set up public shadow run <ArrowRight size={16} aria-hidden="true" />
      </a></div>
      <PublicHistory address={address} />
      {snapshot && (
        <PositionSnapshot account={snapshot} heading="Open positions">
          <a className="btn primary" href={'#/accounts/' + address}>
            Watch this address <ArrowRight size={15} />
          </a>
        </PositionSnapshot>
      )}
      {!snapshot && !error && (
        <p className="muted" role="status">
          Reading published positions…
        </p>
      )}
      {(error || snapshot?.status === 'unavailable') && (
        <div>
          {error && <p role="alert">{error}</p>}
          <button className="btn" onClick={() => setRevision((r) => r + 1)}>
            Retry position lookup
          </button>
        </div>
      )}
      <HoldingsValue key={address} address={address} />
      <PublicObservation address={address} />
    </div>
  )
}

export function PublicRankings() {
  const [period, setPeriod] = useState<Period>('month')
  const [query, setQuery] = useState('')
  const [selected, select] = useState<string | null>(null)
  const [picks, setPicks] = useState<string[]>([])
  const [comparing, setComparing] = useState(false)
  const profileTrigger = useRef<HTMLElement | null>(null)
  const searchInput = useRef<HTMLInputElement>(null)
  const compareButton = useRef<HTMLButtonElement>(null)
  const [board, setBoard] = useState<Leaderboard | null>(null)
  const [error, setError] = useState('')
  const [revision, refresh] = useState(0)
  useEffect(() => {
    let current = true
    setBoard(null)
    setError('')
    select(null)
    setPicks([])
    setComparing(false)
    api<Leaderboard>('public/leaders?period=' + period)
      .then((data) => {
        if (current && data.period === period) setBoard(data)
        else if (current) setError('The provider returned a different ranking period.')
      })
      .catch((e) => {
        if (current) setError(errorMessage(e))
      })
    return () => {
      current = false
    }
  }, [period, revision])
  const matching = (board?.leaders ?? []).filter((trader) =>
    (trader.name + ' ' + trader.address).toLowerCase().includes(query.trim().toLowerCase()),
  )
  const pastedAddress = /^0x[0-9a-f]{40}$/i.test(query.trim()) ? query.trim().toLowerCase() : null
  const trader = board?.leaders.find((item) => item.address === selected)
  function openProfile(address: string, trigger: HTMLElement | null) {
    setComparing(false)
    profileTrigger.current = trigger
    select(address)
  }
  const chosen = (board?.leaders ?? []).filter((row) => picks.includes(row.address))
  return (
    <div className="stack">
      <section className="panel panel-body public-board">
        <header className="panel-head">
          <h2>Polymarket leaderboard</h2>
          <span className="badge">Public data</span>
        </header>
        <p className="muted">
          Official P/L ranking ·{' '}
          {period === 'all'
            ? 'Lifetime realized result'
            : 'Change in marked equity net of external flows'}
          . Includes combo activity. Follower costs and returns are unknown.
        </p>
        <form
          className="directory-tools"
          onSubmit={(event) => {
            event.preventDefault()
            if (pastedAddress) openProfile(pastedAddress, searchInput.current)
          }}
        >
          <label className="search">
            <Search size={16} aria-hidden="true" />
            <input
              ref={searchInput}
              aria-label="Search public traders"
              value={query}
              onChange={(e) => {
                select(null)
                setQuery(e.target.value)
              }}
              type="search"
              placeholder="Search name or paste wallet…"
            />
          </label>
          {pastedAddress && (
            <button className="btn primary" type="submit">
              Inspect wallet
            </button>
          )}
          <label className="select-field">
            <select
              aria-label="Ranking period"
              value={period}
              onChange={(e) => {
                setBoard(null)
                setPeriod(e.target.value as Period)
              }}
            >
              {Object.entries(periods).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            className="btn"
            type="button"
            onClick={() => {
              setBoard(null)
              refresh((v) => v + 1)
            }}
          >
            <RefreshCw size={14} />
            Refresh rankings
          </button>
        </form>
        {!board && !error && (
          <p role="status" className="muted">
            Reading Polymarket rankings…
          </p>
        )}
        {(error || board?.status === 'unavailable') && (
          <p role="alert" className="notice">
            {error || board?.message} Use Refresh rankings to try again.
          </p>
        )}
        {board?.status === 'available' && (
          <>
            <div className="public-compare-tools">
              <span>{picks.length} of 2 wallets selected</span>
              <button
                className="btn"
                ref={compareButton}
                disabled={chosen.length !== 2 || comparing}
                onClick={() => {
                  select(null)
                  setComparing(true)
                }}
              >
                Compare wallets
              </button>
            </div>
            {matching.length ? (
              <div className="public-list">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">
                        <span className="sr-only">Compare</span>
                      </th>
                      <th scope="col">Rank</th>
                      <th scope="col">Trader</th>
                      <th scope="col">
                        P/L <small>(USDC)</small>
                      </th>
                      <th scope="col" className="volume">
                        Volume <small>(shares)</small>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {matching.map((row) => (
                      <tr
                        key={row.address}
                        className={selected === row.address ? 'inspected' : undefined}
                      >
                        <td>
                          <input
                            type="checkbox"
                            aria-label={'Select ' + row.name + ' for comparison'}
                            checked={picks.includes(row.address)}
                            disabled={!picks.includes(row.address) && picks.length === 2}
                            onChange={(e) => {
                              setComparing(false)
                              setPicks(
                                e.target.checked
                                  ? [...picks, row.address]
                                  : picks.filter((id) => id !== row.address),
                              )
                            }}
                          />
                        </td>
                        <td>{row.rank}</td>
                        <td>
                          <button
                            className="trader-button"
                            aria-label={'Inspect ' + row.name}
                            aria-expanded={selected === row.address}
                            onClick={(event) => {
                              if (selected === row.address) select(null)
                              else openProfile(row.address, event.currentTarget)
                            }}
                          >
                            <strong>
                              {row.name} <ArrowUpRight size={14} />
                            </strong>
                            <small>
                              {row.address.slice(0, 8)}…{row.address.slice(-5)}
                            </small>
                          </button>
                        </td>
                        <td className={Number(row.pnl) < 0 ? 'negative' : 'positive'}>
                          {summaryNumber.format(Number(row.pnl))}
                        </td>
                        <td className="volume">{summaryNumber.format(Number(row.volumeShares))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="notice">
                {pastedAddress
                  ? 'This address is outside the rankings shown.'
                  : board.leaders.length
                    ? 'No matching traders on this page. Paste a full wallet address to inspect its positions.'
                    : 'Polymarket returned an empty page.'}
              </p>
            )}
            <p className="workspace-note muted">
              {board.leaders.length} traders returned ·{' '}
              {board.complete ? 'Complete response' : 'First page only'} · Retrieved{' '}
              {new Date(board.observedAt!).toLocaleString('en-GB', { timeZone: 'UTC' })} UTC
            </p>
          </>
        )}
      </section>
      {comparing && chosen.length === 2 && board?.period === period && (
        <PublicComparison
          traders={chosen}
          board={board}
          close={() => {
            setComparing(false)
            requestAnimationFrame(() => compareButton.current?.focus())
          }}
        />
      )}
      {selected && (
        <Profile
          key={selected}
          address={selected}
          period={period}
          trader={trader}
          close={() => {
            select(null)
            profileTrigger.current?.focus()
          }}
        />
      )}
    </div>
  )
}
