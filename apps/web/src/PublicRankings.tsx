import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, RefreshCw, Search, X } from 'lucide-react'
import { api, type Account, errorMessage, validBuyBudget } from './api'
import { PositionSnapshot, WalletValue } from './Workspace'
import { PublicObservation, type BudgetTest, type WalletCheck } from './PublicObservation'
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
  nextCursor: string | null
  leaders: PublicTrader[]
}

const periods = { day: 'Past day', week: 'Past week', month: 'Past month', all: 'All time' }
type Period = keyof typeof periods
const summaryNumber = new Intl.NumberFormat('en', { maximumFractionDigits: 2 })
const smallNumber = new Intl.NumberFormat('en', { maximumSignificantDigits: 2 })
function profitLabel(raw: string) {
  const value = Number(raw)
  const format = value && Math.abs(value) < 0.01 ? smallNumber : summaryNumber
  return (value > 0 ? '+' : '') + format.format(value)
}
const utc = (stamp: string) => new Date(stamp).toLocaleString('en-GB', { timeZone: 'UTC' }) + ' UTC'
type PickedTrader = PublicTrader & { rankedAt: string }
const evidenceLabels = {
  all: 'All wallets on this page',
  estimated: 'Modeled buy observed',
  skipped: 'Buy skipped by the model',
  inconclusive: 'Inconclusive check',
  unchecked: 'No check at this budget',
}
type EvidenceFilter = keyof typeof evidenceLabels

const shortlistKey = (period: Period) => 'polysia:public-shortlist:v1:' + period
const periodKey = 'polysia:rankings-period:v1'
function visitPeriod(): Period {
  try {
    const value = sessionStorage.getItem(periodKey)
    if (value && Object.hasOwn(periods, value)) return value as Period
  } catch { /* The default period works without browser storage. */ }
  return 'month'
}
function readShortlist(period: Period): PickedTrader[] {
  try {
    const raw = localStorage.getItem(shortlistKey(period))
    if (!raw || raw.length > 16384) return []
    const rows = JSON.parse(raw)
    if (!Array.isArray(rows) || rows.length > 2) return []
    const valid = rows.every(row =>
      row && typeof row.address === 'string' && /^0x[0-9a-f]{40}$/.test(row.address) &&
      typeof row.name === 'string' && row.name.length > 0 && row.name.length <= 1000 &&
      Number.isSafeInteger(row.rank) && row.rank > 0 &&
      typeof row.pnl === 'string' && /^-?\d+(?:\.\d+)?$/.test(row.pnl) && Number.isFinite(Number(row.pnl)) &&
      typeof row.volumeShares === 'string' && /^\d+(?:\.\d+)?$/.test(row.volumeShares) && Number.isFinite(Number(row.volumeShares)) &&
      typeof row.rankedAt === 'string' && Number.isFinite(Date.parse(row.rankedAt)))
    return valid && new Set(rows.map(row => row.address)).size === rows.length ? rows : []
  } catch {
    return []
  }
}

type ComparisonRead = { account: Account } | { error: string }

function openMarkets(read?: ComparisonRead) {
  if (!read || !('account' in read) || read.account.status !== 'available') return null
  const markets = new Map<string, {title: string; outcomes: Set<string>}>()
  for (const row of read.account.positions) {
    if (row.status === 'REDEEMABLE' || Number(row.shares) === 0) continue
    if (row.status !== 'OPEN' || !row.conditionId?.match(/^0x[0-9a-f]{64}$/)) return null
    const market = markets.get(row.conditionId) ?? {title: row.market, outcomes: new Set<string>()}
    market.outcomes.add(row.outcome)
    markets.set(row.conditionId, market)
  }
  return markets
}

function PublicComparison({
  traders,
  period,
  close,
  inspect,
  checks,
}: {
  traders: PickedTrader[]
  period: Period
  close: () => void
  inspect: (trader: PickedTrader) => void
  checks: Record<string, WalletCheck>
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
        {periods[period]} ·{' '}
        {period === 'all'
          ? 'Lifetime realized P/L'
          : 'Marked equity change net of external flows'}{' '}
        · Volume in shares. The rank, P/L and volume below are snapshots from the time each wallet was selected.
      </p>
      <div className="comparison">
        {traders.map((trader) => {
          const read = reads[trader.address]
          const account = read && 'account' in read ? read.account : null
          const check = checks[trader.address]
          const markets = trader.address === left.address ? leftMarkets : rightMarkets
          return (
            <article key={trader.address} className="compare-card public-compare-card">
              <h3>{trader.name}</h3>
              <code>{trader.address}</code>
              <small className="muted">Rank read {utc(trader.rankedAt)}</small>
              <dl className="facts">
                <div>
                  <dt>Provider rank</dt>
                  <dd>{trader.rank}</dd>
                </div>
                <div>
                  <dt>P/L (USDC)</dt>
                  <dd title={trader.pnl}>{profitLabel(trader.pnl)}</dd>
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
                {shared && markets && markets.size > 0 && <div>
                  <dt>Shared open markets</dt><dd>{shared.length} of {markets.size} shown</dd>
                </div>}
              </dl>
              <div className="wallet-check-summary">
                <strong>{check ? 'Buy check · ' + check.budget + ' pUSD' : 'Buy check'}</strong>
                <p>{check ? check.result : 'Open this wallet to test a simulated buy.'}</p>
                {check?.windowEnd != null && <small>Window ended {utc(new Date(check.windowEnd * 1000).toISOString())}</small>}
              </div>
              <p className="workspace-note muted">
                {account?.observedAt
                  ? 'Retrieved ' +
                    new Date(account.observedAt).toLocaleString('en-GB', { timeZone: 'UTC' }) +
                    ' UTC'
                  : (account?.message ?? (read && 'error' in read ? read.error : ''))}
              </p>
              <button className="btn" onClick={() => inspect(trader)} aria-label={'Open profile for ' + trader.name}>
                View wallet <ArrowRight size={14} aria-hidden="true" />
              </button>
            </article>
          )
        })}
      </div>
      <div className="stack public-overlap">
        <h3>Open-market overlap</h3>
        <p role="status">{overlapSummary}</p>
        {shared && shared.length > 0 && (
          <ul>
            {shared.map(([id, market]) => (
              <li key={id}><strong>{market.title}</strong>
                <div>{left.name} · {[...market.outcomes].join(', ')}</div>
                <div>{right.name} · {[...rightMarkets!.get(id)!.outcomes].join(', ')}</div>
              </li>
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
  rankedAt,
  period,
  close,
  budgetTest,
  backLabel,
}: {
  address: string
  trader?: PublicTrader
  rankedAt?: string
  period: Period
  close: () => void
  budgetTest: BudgetTest
  backLabel: string
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
          <ArrowLeft size={15} aria-hidden="true" /> {backLabel}
        </button>
      </div>
      <section className="panel panel-body wallet-summary">
        <div className="profile-label">
          <h2 ref={heading} tabIndex={-1}>{trader?.name ?? 'Public wallet'}</h2>
          {trader && <span className="badge">Provider rank {trader.rank} · {periods[period]}</span>}
        </div>
        <code className="wallet-address">{address}</code>
        {trader && (
          <p className="muted">Reported volume: {summaryNumber.format(Number(trader.volumeShares))} shares · P/L: {profitLabel(trader.pnl)} USDC{rankedAt && <> · Rank read {utc(rankedAt)}</>}</p>
        )}
      </section>
      <PublicObservation address={address} name={trader?.name ?? 'Public wallet'} {...budgetTest} />
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
      <WalletValue key={address} address={address} kind="holdings" />
    </div>
  )
}

export function PublicRankings() {
  const [period, setPeriod] = useState<Period>(visitPeriod)
  const [budget, setBudget] = useState('10')
  const [checksByBudget, setChecksByBudget] = useState<Record<string, Record<string, WalletCheck>>>({})
  const [filter, setFilter] = useState<EvidenceFilter>('all')
  const checks = validBuyBudget(budget) ? checksByBudget[Number(budget).toFixed(2)] ?? {} : {}
  const [query, setQuery] = useState('')
  const [selected, select] = useState<string | null>(null)
  const [picks, setPicks] = useState<PickedTrader[]>(() => readShortlist(period))
  const [storageIssue, setStorageIssue] = useState(false)
  const unsaved = useRef<Partial<Record<Period, PickedTrader[]>>>({})
  const [comparing, setComparing] = useState(false)
  const profileTrigger = useRef<HTMLElement | null>(null)
  const searchInput = useRef<HTMLInputElement>(null)
  const returnToComparison = useRef(false)
  const compareButton = useRef<HTMLButtonElement>(null)
  const [pages, setPages] = useState<Leaderboard[]>([])
  const [index, setIndex] = useState(0)
  const [paging, setPaging] = useState(false)
  const [pageError, setPageError] = useState('')
  const generation = useRef(0)
  const list = useRef<HTMLDivElement>(null)
  const board = pages[index]?.period === period ? pages[index] : null
  const [error, setError] = useState('')
  const [revision, refresh] = useState(0)
  useEffect(() => {
    let current = true
    setPages([])
    setIndex(0)
    setPaging(false)
    setPageError('')
    setError('')
    select(null)
    setComparing(false)
    api<Leaderboard>('public/leaders?period=' + period)
      .then((data) => {
        if (current && data.period === period) setPages([data])
        else if (current) setError('The provider returned a different ranking period.')
      })
      .catch((e) => {
        if (current) setError(errorMessage(e))
      })
    return () => {
      current = false
      generation.current++
    }
  }, [period, revision])
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key === null || event.key === shortlistKey(period)) {
        if (unsaved.current[period]) return
        setPicks(readShortlist(period))
        setComparing(false)
        returnToComparison.current = false
      }
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [period])
  function updatePicks(next: PickedTrader[]) {
    setPicks(next)
    try {
      if (next.length) localStorage.setItem(shortlistKey(period), JSON.stringify(next))
      else localStorage.removeItem(shortlistKey(period))
      delete unsaved.current[period]
      setStorageIssue(false)
    } catch {
      unsaved.current[period] = next
      setStorageIssue(true)
    }
  }
  // Snapshots only. Filtering never requests a new page, profile or observation.
  const filtering = filter !== 'all'
  const candidates = useMemo(() => {
    if (!filtering) return (board?.leaders ?? []).map(row => ({...row, rankedAt: board!.observedAt!}))
    const visited = new Map(picks.map(pick => [pick.address, pick]))
    for (const page of pages) {
      if (page.period !== period || page.status !== 'available' || !page.observedAt) continue
      for (const row of page.leaders) {
        const saved = visited.get(row.address)
        if (!saved || Date.parse(saved.rankedAt) <= Date.parse(page.observedAt)) {
          visited.set(row.address, {...row, rankedAt: page.observedAt})
        }
      }
    }
    return [...visited.values()].sort((a, b) => a.rank - b.rank)
  }, [filtering, period, pages, picks, board])
  const matching = candidates.filter(row =>
    (row.name + ' ' + row.address).toLowerCase().includes(query.trim().toLowerCase()) &&
    (!filtering || (validBuyBudget(budget) && (checks[row.address]?.outcome ?? 'unchecked') === filter)),
  )
  const pastedAddress = /^0x[0-9a-f]{40}$/i.test(query.trim()) ? query.trim().toLowerCase() : null
  const ranked = candidates.find(item => item.address === selected)
  const picked = picks.find((item) => item.address === selected)
  const trader = ranked ?? picked
  function openProfile(address: string, trigger: HTMLElement | null, fromComparison = false) {
    returnToComparison.current = fromComparison
    setComparing(false)
    profileTrigger.current = trigger
    select(address)
  }
  function showPage(to: number) {
    setIndex(to)
    setPageError('')
    setQuery('')
    list.current?.scrollTo(0, 0)
  }
  async function nextPage() {
    if (pages[index + 1]) return showPage(index + 1)
    if (!board?.nextCursor || paging) return
    const version = generation.current
    setPaging(true)
    setPageError('')
    try {
      const query = new URLSearchParams({period, cursor: board.nextCursor})
      const next = await api<Leaderboard>('public/leaders?' + query)
      if (version !== generation.current) return
      if (next.status !== 'available') throw new Error(next.message)
      if (next.period !== period || (next.nextCursor && pages.some(page => page.nextCursor === next.nextCursor))) {
        throw new Error('The ranking pages have changed. Refresh the rankings to start again.')
      }
      setPages([...pages, next])
      showPage(index + 1)
    } catch (cause) {
      if (version === generation.current) setPageError(errorMessage(cause))
    } finally {
      if (version === generation.current) setPaging(false)
    }
  }
  return (
    <div className="stack">
      <section className="panel panel-body public-board" hidden={!!selected || comparing}>
        <header className="board-heading">
          <h2>Polymarket leaderboard</h2>
          <p>Ranked by each trader’s past profit or loss. Open a wallet to check a simulated buy at your budget.</p>
        </header>
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
              placeholder={filtering ? 'Search filtered wallets or paste an address' : 'Search this page or paste a wallet'}
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
                const next = e.target.value as Period
                setPeriod(next)
                try { sessionStorage.setItem(periodKey, next) } catch { /* Keep this visit usable. */ }
                setPicks(unsaved.current[next] ?? readShortlist(next))
                setStorageIssue(unsaved.current[next] !== undefined)
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
              refresh((v) => v + 1)
            }}
          >
            <RefreshCw size={14} aria-hidden="true" />
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
        {(board?.status === 'available' || picks.length > 0) && (
          <>
            <div className="public-compare-tools">
              <label className="board-budget">Budget per buy
                <span>
                  <input aria-label="Simulated budget per buy" type="number" min="1" max="1000" step=".01"
                    inputMode="decimal" value={budget} onChange={event => setBudget(event.target.value)} />
                  pUSD
                </span>
              </label>
              <div className="compare-choices">
                <span>{picks.length ? picks.length + ' of 2 selected' : 'Select two wallets'}</span>
                <button className="btn" ref={compareButton} disabled={picks.length !== 2}
                  onClick={() => { select(null); setComparing(true) }}>
                  Compare wallets
                </button>
              </div>
            </div>
            <label className="evidence-filter">Buy check at this budget
              <select value={filter} onChange={event => setFilter(event.target.value as EvidenceFilter)}>
                {Object.entries(evidenceLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </label>
            {picks.length > 0 && <section className="public-shortlist" aria-label="Saved comparison shortlist">
              <h3>{periods[period]} shortlist</h3>
              <ul>{picks.map(pick => <li key={pick.address}>
                <button className="text-link" onClick={event => openProfile(pick.address, event.currentTarget)}
                  aria-label={'Inspect shortlisted wallet ' + pick.name}>{pick.name}</button>
                <button className="shortlist-remove" aria-label={'Remove ' + pick.name + ' from shortlist'}
                  onClick={() => updatePicks(picks.filter(row => row.address !== pick.address))}>
                  <X size={15} aria-hidden="true"/>
                </button>
              </li>)}</ul>
              {!storageIssue && <small>Saved in this browser for this ranking period.</small>}
            </section>}
            {storageIssue && <p role="status" className="notice">Browser storage is unavailable. Reloading may lose these changes.</p>}
          </>
        )}
        {(board?.status === 'available' || (filtering && picks.length > 0)) && (
          <>
            {filtering && <p className="workspace-note" role="status">{validBuyBudget(budget)
              ? `${matching.length} of ${candidates.length} browsed or shortlisted wallets match. Results use each wallet’s latest check at ${budget} pUSD in this visit.`
              : 'Enter a budget from 1 to 1,000 pUSD in whole cents to filter checks.'}</p>}
            {matching.length ? (
              <div className="public-list" ref={list}>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">
                        <span className="sr-only">Compare</span>
                      </th>
                      <th scope="col">Rank</th>
                      <th scope="col">Trader</th>
                      <th scope="col">
                        Profit / loss <small>(USDC)</small>
                      </th>
                      <th scope="col" className="volume">
                        Volume <small>(shares)</small>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {matching.map((row) => (
                      <tr key={row.address}>
                        <td>
                          <label className="pick-wallet"><input
                            type="checkbox"
                            aria-label={'Select ' + row.name + ' for comparison'}
                            checked={picks.some(pick => pick.address === row.address)}
                            disabled={picks.length === 2 && !picks.some(pick => pick.address === row.address)}
                            onChange={(e) => {
                              setComparing(false)
                              updatePicks(
                                e.target.checked
                                  ? [...picks, row]
                                  : picks.filter((pick) => pick.address !== row.address),
                              )
                            }}
                          /></label>
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
                              {row.name}
                            </strong>
                            <small>
                              {row.address.slice(0, 8)}…{row.address.slice(-5)}
                            </small>
                            {filtering && checks[row.address]?.windowEnd != null && <small>Checked {utc(new Date(checks[row.address].windowEnd! * 1000).toISOString())}</small>}
                          </button>
                        </td>
                        <td title={row.pnl} className={Number(row.pnl) < 0 ? 'negative' : 'positive'}>
                          {profitLabel(row.pnl)}
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
                  : filtering
                    ? 'Choose another check result or open a wallet to test one window.'
                    : board?.leaders.length
                    ? 'No matching traders on this page. Paste a full wallet address to inspect its positions.'
                    : 'Polymarket returned an empty page.'}
              </p>
            )}
            {board?.status === 'available' && !filtering && <div className="board-pages">
              <span role="status">Page {index + 1} · {board.leaders.length} wallets</span>
              <div>
                <button className="btn" disabled={!index || paging} onClick={() => showPage(index - 1)}>
                  <ChevronLeft size={15} aria-hidden="true" /> Previous
                </button>
                <button className="btn" disabled={!board.nextCursor || paging} onClick={nextPage}>
                  {paging ? 'Loading…' : 'Next page'} <ChevronRight size={15} aria-hidden="true" />
                </button>
              </div>
            </div>}
            {pageError && <p className="error" role="alert">{pageError} You can retry Next page.</p>}
            <details className="rank-basis"><summary>How rankings are calculated</summary>
              <p>{period === 'all' ? 'All time uses realized profit and loss.' : 'Polymarket measures the change in portfolio value after deposits and withdrawals.'}
                {' '}Includes combo trades. Copying has its own prices and fees. Coverage is limited to this Polymarket board.
                {board?.observedAt && <> Page read {utc(board.observedAt)}.</>} Ranks can change between reads.</p>
            </details>
          </>
        )}
      </section>
      {comparing && picks.length === 2 && (
        <PublicComparison
          traders={picks}
          period={period}
          checks={checks}
          inspect={pick => openProfile(pick.address, compareButton.current, true)}
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
          rankedAt={ranked?.rankedAt ?? picked?.rankedAt}
          budgetTest={{budget, setBudget, saveCheck: (wallet, result) => {
            const key = Number(result.budget).toFixed(2)
            setChecksByBudget(old => ({...old, [key]: {...old[key], [wallet]: result}}))
          }}}
          close={() => {
            select(null)
            if (returnToComparison.current) setComparing(true)
            else requestAnimationFrame(() => profileTrigger.current?.focus())
          }}
          backLabel={returnToComparison.current ? 'Back to comparison' : 'Back to rankings'}
        />
      )}
    </div>
  )
}
