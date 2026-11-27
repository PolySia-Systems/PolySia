import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight, Download, Pause, Play, Plus, ScanLine, Square } from 'lucide-react'
import { api, apiResponse, errorMessage, validBuyBudget } from './api'
import { SharedReplay } from './SharedReplay'
import './public-runs.css'

interface Summary {
  id: string
  name: string
  wallet: string
  capital: string
  cash: string
  entryCap: string
  gross: string
  fees: string
  exits: number
  sales: string
  realized: string
  openCost: string
  entries: number
  revision: number
  status: 'running' | 'paused' | 'stopped'
  createdAt: string
  updatedAt: string
  nextBudget: string | null
}
interface Decision {
  revision: number
  at: string
  kind: string
  reason: string
  gross: string
  fee: string
  shares: string
  market: string | null
  outcome: string | null
  sourceOrder: string | null
  sourceFill?: string
  proceeds?: string
  targetShares?: string
  releasedCost?: string
  realized?: string
  observation?: {windowStartSeconds: number | null; windowEndSeconds: number | null; eventTimeSeconds: number | null; bookReceivedMs: number | null; budget: string | null; side: 'BUY' | 'SELL'; maxShares: string | null; outcomeToken: string | null}
}
interface Holding {
  conditionId: string
  tokenId: string
  market: string | null
  outcome: string | null
  shares: string
  cost: string
  soldShares: string
  saleProceeds: string
  releasedCost: string
  realized: string
}
interface Portfolio extends Summary {
  fundedCapital: string
  deposits: string
  withdrawals: string
  netContributions: string
  backgroundEnabled: boolean
  exitsEnabled: boolean
  activeExitPolicy: {maxPriceDecrease: string; costMethod: string} | null
  policy: { checkSalesBeforeEntry?: boolean; saleSizing?: string; delaySeconds: number; maxSignalAgeMs: number; maxPriceIncrease: string; maxLevels: number }
  decisions: Decision[]
  nextCursor: number | null
  positions: Holding[]
  closedPositions: (Holding & {closedAt: string})[]
}
const when = (value: string | number) => new Date(value).toLocaleString('en-GB', { timeZone: 'UTC' }) + ' UTC'
const labels: Record<string, string> = {
  'change-cap': 'BUY cap changed',
  deposit: 'Simulated cash added',
  withdraw: 'Simulated cash withdrawn',
  running: 'Running', paused: 'Paused', stopped: 'Stopped', entry: 'Modeled BUY', duplicate: 'Already modeled',
  'background-on': 'Background sampling enabled', 'background-off': 'Background sampling disabled',
  waiting: 'No BUY observed', incomplete: 'Evidence incomplete', skipped: 'Entry skipped',
  unavailable: 'Observation unavailable', pause: 'Entries paused', resume: 'Entries resumed', stop: 'Run stopped', exit: 'Modeled SELL', 'enable-exits': 'SELL windows enabled',
}

function Setup() {
  const params = new URLSearchParams(location.hash.split('?')[1])
  const carriedCap = params.get('cap')
  const initialCap = validBuyBudget(carriedCap) ? carriedCap : '10'
  const [wallet, setWallet] = useState(params.get('wallet') ?? '')
  const [name, setName] = useState((params.get('name') || 'Public wallet').slice(0, 80))
  const [capital, setCapital] = useState(Number(initialCap) > 100 ? '' : '100')
  const [cap, setCap] = useState(initialCap)
  const capitalCents = validBuyBudget(capital) ? Math.round(Number(capital) * 100) : 0
  const capCents = validBuyBudget(cap) ? Math.round(Number(cap) * 100) : 0
  const [id] = useState(() => crypto.randomUUID().replaceAll('-', ''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function start(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const run = await api<Portfolio>('public-runs/' + id, 'PUT', {wallet, name, capital, cap})
      location.hash = '/paper/' + run.id
    } catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <div className="stack paper-page">
    <a className="text-link" href="#/paper"><ArrowLeft size={15} /> All public runs</a>
    <section className="panel workspace-panel">
      <h2>Set up a public shadow run</h2>
      <p>Follow one public wallet with simulated pUSD. Choose when to observe a BUY. Once a position opens, you can watch for the leader to sell that same outcome.</p>
      {validBuyBudget(carriedCap) && <p className="workspace-note">Your wallet preview used a cap of {carriedCap} pUSD per buy. Choose your total simulated cash below.</p>}
      <form className="stack paper-form" onSubmit={start}>
        <label className="field">Run name<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label>
        <label className="field">Leader wallet<input required pattern="0x[0-9a-fA-F]{40}" placeholder="0x…"
          spellCheck={false} autoComplete="off" value={wallet} onChange={e => setWallet(e.target.value.trim())} /></label>
        <div className="paper-pair">
          <label className="field">Starting cash (pUSD)<input required type="number" min="1" max="1000" step=".01" value={capital}
            onChange={e => setCapital(e.target.value)} /></label>
          <label className="field">Per-entry cap (pUSD)<input required type="number" min="1" max={Math.min(Number(capital) || 1000, 1000)} step=".01"
            value={cap} onChange={e => setCap(e.target.value)} /></label>
        </div>
        {capCents > 0 && capCents <= capitalCents && <p role="status">
          If the first buy uses its full cap, at least {((capitalCents - capCents) / 100).toFixed(2)} pUSD
          of your starting cash remains. Later buys can use more of that cash.
        </p>}
        <details className="paper-evidence"><summary>Compare per-buy limits</summary>
          <p>Choose how much of your starting cash one purchase can use, including modeled fees.
            A larger purchase can lose more on a single outcome. A smaller one may fall below the market minimum.</p>
          <div className="actions">{[10, 25].map(percent => {
            const cents = Math.floor(capitalCents * percent / 100)
            return <button key={percent} type="button" className="btn" disabled={busy || cents < 100}
              onClick={() => setCap((cents / 100).toFixed(2))}>
              Use {percent}%{capitalCents > 0 && ' · ' + (cents / 100).toFixed(2) + ' pUSD'}
            </button>
          })}</div>
          <p>These examples round down to cents. The minimum supported cap is 1 pUSD.
            You can enter another cap above. A position can stay open after you stop, and the time needed to sell is unknown.</p>
        </details>
        <details className="paper-evidence"><summary>How simulated trades are priced</summary>
          <p>Public activity comes from Polymarket and is checked against Polygon. A qualifying BUY uses displayed asks and estimated fees.
            The model checks the minimum share size. The venue’s minimum purchase value is unverified. Each SELL window requires a share limit and a matching leader sale.</p>
        </details>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn primary" disabled={busy}>{busy ? 'Creating run…' : 'Create shadow run'} <ArrowRight size={16} /></button>
      </form>
    </section>
  </div>
}

interface RunList {runs: Summary[]; nextCursor: string | null}
function Library() {
  const [list, setList] = useState<RunList | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function load(before?: string) {
    setBusy(true)
    setError('')
    try {
      const page = await api<RunList>('public-runs' + (before ? '?before=' + before : ''))
      setList(old => ({...page, runs: before && old ? [...old.runs, ...page.runs] : page.runs}))
    } catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  useEffect(() => { void load() }, [])
  return <section className="panel workspace-panel paper-page">
    <div className="panel-head"><h2>Saved public runs</h2><a className="btn primary" href="#/paper/new"><Plus size={16}/> New run</a></div>
    {error && <p className="error" role="alert">{error} <button className="text-link" onClick={() => load(list?.nextCursor ?? undefined)}>Retry</button></p>}
    {!list && busy && <p role="status">Loading runs…</p>}
    {list && !list.runs.length && <div className="paper-empty"><ScanLine size={26} aria-hidden="true"/><h3>Follow your first public wallet</h3>
      <p>Choose a trader from the rankings or start a run with a wallet address. Your simulated cash, positions and decisions are saved here.</p>
      <a className="text-link" href="#/rankings">Browse public rankings <ArrowRight size={15}/></a></div>}
    <div className="paper-list">{list?.runs.map(run => <a key={run.id} href={'#/paper/' + run.id} className="paper-list-row">
      <div><b>{run.name}</b><small>{run.wallet.slice(0, 8)}…{run.wallet.slice(-6)} · {when(run.updatedAt)}</small></div>
      <div><span>{labels[run.status]}</span><small>{run.cash} pUSD cash · {run.openCost} pUSD open cost</small><small>{run.entries} {run.entries === 1 ? 'BUY' : 'BUYs'} · {run.exits} {run.exits === 1 ? 'SELL' : 'SELLs'}</small></div>
      <ArrowRight size={16} aria-hidden="true"/></a>)}</div>
    {list?.nextCursor && <button className="btn" disabled={busy} onClick={() => load(list.nextCursor!)}>Older runs</button>}
    {list && list.runs.length > 1 && <SharedReplay runs={list.runs} />}
  </section>
}

interface Mark {
  midpoint: string | null
  value: string | null
  changeFromCost: string | null
  bid: string | null
  ask: string | null
  bookTimeMs: number | null
  checkedMs: number
  reason: string
}

function PositionMark({route, revision, token}: {route: string; revision: number; token: string}) {
  const [mark, setMark] = useState<Mark | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function check() {
    setBusy(true)
    setMark(null)
    setError('')
    try { setMark(await api<Mark>(route + '/positions/' + token + '/mark', 'POST', {revision})) }
    catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <div className="paper-mark">
    <button className="text-link" disabled={busy} onClick={check}>
      {busy ? 'Checking book…' : mark ? 'Refresh price estimate' : 'Check price estimate'}
    </button>
    <div role="status">{error || (mark && <>
      <p><b>{mark.value == null ? 'Price estimate unavailable' : mark.value + ' pUSD estimated value'}</b>
        {mark.changeFromCost != null && <> · {mark.changeFromCost} pUSD versus purchase cost including fees</>}</p>
      <p>{mark.reason}</p>
      {mark.midpoint != null && <small>Bid {mark.bid} · Ask {mark.ask} · Midpoint {mark.midpoint} pUSD per share</small>}
      <small>Polymarket order book{mark.bookTimeMs != null && <> · Source {when(mark.bookTimeMs)}</>} · Checked {when(mark.checkedMs)}</small>
    </>)}</div>
  </div>
}

function PositionSale({shares, policy, cumulative, busy, observe}: {shares: string; policy: NonNullable<Portfolio['activeExitPolicy']>; cumulative: boolean; busy: boolean; observe: (limit: string) => void}) {
  const [limit, setLimit] = useState('')
  return <details className="paper-sale">
    <summary>Follow a leader SELL</summary>
    <p>Observe this outcome for two seconds. A matched sale can reduce your simulated position
      by up to your limit and the whole shares the leader sold. The minimum bid is {policy.maxPriceDecrease} pUSD per share
      below the leader’s price. Limited depth can leave shares open.</p>
    <small>Cost allocation · {policy.costMethod}</small>
    <form onSubmit={e => { e.preventDefault(); observe(limit) }}>
      <label className="field">Maximum shares to sell
        <input type="number" required min="1" max={shares} step="1" value={limit} placeholder={'1–' + shares}
          disabled={busy} onChange={e => setLimit(e.target.value)}/></label>
      <button className="btn" disabled={busy}><ScanLine size={15}/> Observe leader SELL</button>
    </form>
    <small>The leader’s total inventory is unknown. {cumulative
      ? 'The first share limit for a matched SELL order caps all its fills together. Smaller fills can add up to the minimum sale.'
      : 'This run uses its original rules. Only the first modeled fill of each SELL order counts.'}</small>
  </details>
}

interface Valuation {
  runId: string
  revision: number
  checkedMs: number
  total: number
  checked: number
  priced: number
  pricedValue: string | null
  equity: string | null
  unrealized: string | null
  netResult: string | null
  cash: string
  capital: string
  grossPurchases: string
  grossSales: string
  modeledFees: string
  withdrawals: string
  cashBenchmark: { from: string; endValue: string | null; additionalFlows: string; netReturnPct: string | null; unpricedValueNeededToMatchCash: string | null }
  marks: (Mark & {tokenId: string; market: string | null; outcome: string | null})[]
}
function PortfolioValue({run}: {run: Portfolio}) {
  const [value, setValue] = useState<Valuation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function price() {
    setBusy(true)
    setValue(null)
    setError('')
    try { setValue(await api<Valuation>('public-runs/' + run.id + '/valuation', 'POST', {revision: run.revision})) }
    catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <div className="paper-valuation">
    <div className="panel-head"><h3>Portfolio value</h3>
      <button className="btn" disabled={busy} onClick={price}>{busy ? 'Checking prices…' : value ? 'Refresh portfolio value' : 'Check portfolio value'}</button></div>
    <div role="status">
      {error && <p>{error}</p>}
      {!value && !error && <p>Combine simulated cash with recent midpoint prices for your open shares.</p>}
      {value && <>
        <dl className="paper-metrics"><div><dt>Estimated equity</dt><dd>{value.equity ?? 'Unknown'} {value.equity != null && <small>pUSD</small>}</dd></div>
          <div><dt>Unrealized result</dt><dd>{value.unrealized ?? 'Unknown'} {value.unrealized != null && <small>pUSD</small>}</dd></div>
          <div><dt>Net result</dt><dd>{value.netResult ?? 'Unknown'} {value.netResult != null && <small>pUSD</small>}</dd></div></dl>
        <p>{value.total ? value.priced + ' of ' + value.total + (value.total === 1 ? ' open position priced.' : ' open positions priced.') + (value.priced > 0 ? ' Midpoint value is ' + value.pricedValue + ' pUSD before exit fees.' : '') :
          'All value is held in simulated cash.'} Checked {when(value.checkedMs)}.</p>
        {value.total > value.checked && <p>This check covered {value.checked} holdings. Other holdings have no price in this snapshot.</p>}
        <p><strong>Compared with holding cash</strong> · {value.cashBenchmark.endValue === null
          ? 'A cash-only account could not have covered every withdrawal at the time it was made.'
          : value.withdrawals !== '0'
            ? 'Holding cash with the same deposits and withdrawals would leave ' + value.cashBenchmark.endValue + ' pUSD at zero yield.'
            : <>Keeping {value.cashBenchmark.additionalFlows === '0' ? 'the starting cash' : 'all contributed cash'} since {when(value.cashBenchmark.from)} would leave {value.cashBenchmark.endValue} pUSD at zero yield.</>}
          {value.cashBenchmark.netReturnPct !== null && <> The simulated return on {value.cashBenchmark.additionalFlows === '0' ? 'starting cash' : 'total contributions'} is {value.cashBenchmark.netReturnPct}%.</>}
          {value.cashBenchmark.unpricedValueNeededToMatchCash === '0' && <> Cash and priced shares already cover the cash benchmark. Total return is unknown.</>}
          {value.cashBenchmark.unpricedValueNeededToMatchCash != null && value.cashBenchmark.unpricedValueNeededToMatchCash !== '0' && <>
            {' '}The unpriced holdings would need a combined value of {value.cashBenchmark.unpricedValueNeededToMatchCash} pUSD to match it. Total return is unknown.</>}
        </p>
      </>}
    </div>
    {value && <details className="paper-evidence"><summary>Valuation evidence</summary>
      <p>Cash reconciliation in pUSD · {value.capital} starting cash + {value.cashBenchmark.additionalFlows} added cash − {value.withdrawals} withdrawn − {value.grossPurchases} purchases
        {' '}+ {value.grossSales} sales − {value.modeledFees} modeled fees = {value.cash} remaining cash.</p>
      {value.marks.map(m => <div key={m.tokenId}><b>{m.market ?? 'Outcome token ' + m.tokenId} · {m.outcome}</b>
        <p>{m.value == null ? m.reason : m.value + ' pUSD at a midpoint of ' + m.midpoint + ' pUSD per share.'}
          {m.bookTimeMs != null && <> Polymarket book updated {when(m.bookTimeMs)}.</>}</p></div>)}
      <a className="text-link" href={'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(value, null, 2))}
        download={'polysia-valuation-' + run.id + '.json'}>Download valuation</a>
    </details>}
  </div>
}

function exposureSummary(run: Portfolio) {
  if (!run.positions.length) return 'No simulated positions remain open.'
  const first = run.positions[0]
  if (run.positions.length === 1) {
    const outcome = [first.market ?? 'Market ' + first.conditionId, first.outcome ?? 'Token ' + first.tokenId].join(' · ')
    return first.shares + ' simulated ' + (first.shares === '1' ? 'share remains' : 'shares remain') + ' in ' + outcome + '.'
  }
  return run.positions.length + ' simulated positions remain open with a total purchase cost of ' + run.openCost + ' pUSD.'
}

interface WeekSummary {
  runId: string
  revision: number
  from: string
  through: string
  openingCash: string
  funding: string
  withdrawals: string
  purchases: string
  sales: string
  fees: string
  closingCash: string
  realizedOnSales: string
  netResult: string | null
  observations: number
  counts: Record<string, number>
  latestObservation: {kind: string; reason: string; recorded: string} | null
}

function ExportWeek({report}: {report: WeekSummary}) {
  const [busy, setBusy] = useState(false)
  const [issue, setIssue] = useState('')
  async function download() {
    setBusy(true)
    setIssue('')
    try {
      const response = await apiResponse('public-runs/' + report.runId + '/week/export', 'POST', {
        through: report.through, revision: report.revision,
      })
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = 'polysia-week-' + report.runId + '-' + report.through.slice(0, 10) + '-r' + report.revision + '.json'
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 0)
    } catch (cause) { setIssue(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <div>
    <button className="btn" disabled={busy} onClick={download}><Download size={15}/>{busy ? 'Preparing export…' : 'Export this period'}</button>
    {issue && <p role="alert">{issue} Select Refresh report and try again.</p>}
  </div>
}

function WeekOverview({run, refreshRun}: {run: Portfolio; refreshRun: () => void}) {
  const [report, setReport] = useState<WeekSummary | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setError('')
    setReport(null)
    api<WeekSummary>('public-runs/' + run.id + '/week').then(result => {
      if (result.runId !== run.id) throw new Error('The report identified a different run.')
      if (active) setReport(result)
    }).catch(cause => { if (active) setError(errorMessage(cause)) })
    return () => { active = false }
  }, [run.id, run.revision, attempt])
  const stale = report && report.revision !== run.revision
  return <section className="panel workspace-panel" aria-label="Last seven days">
    <div className="panel-head"><h2>Last seven days</h2>
      <button className="btn" onClick={() => { refreshRun(); setAttempt(a => a + 1) }}>Refresh report</button>
    </div>
    {error ? <p role="alert">{error}</p> : stale ? <p role="status">This run changed. Refresh the report to see its latest decisions.</p> :
      report ? <>
        <p className="workspace-note">{when(report.from)} through {when(report.through)} · Simulated pUSD</p>
        <dl className="paper-metrics">
          <div><dt>Net result in period</dt><dd>{report.netResult ?? 'Unknown'}</dd></div>
          <div><dt>Realized on sales in period</dt><dd>{report.realizedOnSales}</dd></div>
          <div><dt>Fees in period</dt><dd>{report.fees}</dd></div>
        </dl>
        {report.netResult === null && <p className="workspace-note">An open position needs a price at the start or end of this period. The journal has no price for that boundary.</p>}
        <p>Opening cash {report.openingCash} · Funding added {report.funding} · Withdrawn {report.withdrawals} · Purchases {report.purchases} · Gross sales {report.sales} · Closing cash {report.closingCash}</p>
        <p>{report.observations} recorded windows · {report.counts.entry ?? 0} buys · {report.counts.exit ?? 0} sales · {report.counts.skipped ?? 0} skipped · {report.counts.waiting ?? 0} quiet · {(report.counts.incomplete ?? 0) + (report.counts.unavailable ?? 0)} with missing evidence · {report.counts.duplicate ?? 0} repeats.</p>
        <p>{run.status === 'stopped' ? 'Sampling has stopped.' : run.status === 'paused' ? 'New entries are paused. Resume to check new purchases.' :
          !run.nextBudget ? 'The remaining cash is below the minimum for a BUY window.' : run.backgroundEnabled ? 'Background BUY sampling is enabled.' : 'Manual sampling is active. Choose a window to check for a purchase.'}
          {' '}{run.positions.length} open {run.positions.length === 1 ? 'position' : 'positions'} currently, with a recorded cost of {run.openCost} pUSD.</p>
        {run.positions.length > 0 && <details className="paper-evidence"><summary>Remaining positions</summary>
          <ul>{run.positions.map(p => <li key={p.conditionId + '/' + p.tokenId}>
            {p.market ?? p.conditionId} · {p.outcome ?? p.tokenId} · {p.shares} shares
          </li>)}</ul></details>}
        {report.latestObservation && <p className="workspace-note">Latest window at {when(report.latestObservation.recorded)} · {report.latestObservation.reason}</p>}
        <ExportWeek key={report.through} report={report}/>
      </> : <p role="status">Reading the last seven days…</p>}
  </section>
}

function WindowRecheck({route, revision}: {route: string; revision: number}) {
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  async function check() {
    setBusy(true)
    try {
      const result = await api<{visibleBuys: number | null; complete: boolean; checkedMs: number}>(
        route + '/decisions/' + revision + '/recheck', 'POST', {})
      let message = 'The activity recheck was unavailable.'
      if (result.visibleBuys !== null) {
        message = result.visibleBuys
          ? 'The provider now shows ' + (result.complete ? '' : 'at least ') + result.visibleBuys + ' BUY row(s) in this earlier window. The original decision and cash are preserved.'
          : result.complete ? 'The provider still shows no ordinary BUY in this window.' : 'The returned page is incomplete. Activity in this window remains unknown.'
      }
      setStatus(message + ' Checked ' + when(result.checkedMs))
    } catch (cause) { setStatus(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <div><button className="text-link" onClick={check} disabled={busy}>{busy ? 'Checking…' : 'Recheck public activity'}</button>
    <p role="status">{status}</p></div>
}

function Detail({id}: {id: string}) {
  const [run, setRun] = useState<Portfolio | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [confirmStop, setConfirmStop] = useState(false)
  const [windows, setWindows] = useState(1)
  const [newCap, setNewCap] = useState('')
  const [depositAmount, setDepositAmount] = useState('')
  const [withdrawAmount, setWithdrawAmount] = useState('')
  const [progress, setProgress] = useState('')
  const [saleFeedback, setSaleFeedback] = useState('')
  const [tradesOnly, setTradesOnly] = useState(false)
  const latestAction = useRef(0)
  const route = 'public-runs/' + id
  function historyRoute(trades: boolean, before?: number) {
    const query = new URLSearchParams()
    if (trades) query.set('view', 'trades')
    if (before) query.set('before', String(before))
    return query.size ? route + '?' + query : route
  }
  async function load(before?: number, trades = tradesOnly) {
    setBusy('load')
    setError('')
    try {
      const page = await api<Portfolio>(historyRoute(trades, before))
      setTradesOnly(trades)
      if (before && run && page.revision !== run.revision) setRun(await api<Portfolio>(historyRoute(trades)))
      else setRun(old => before && old ? {...page, decisions: [...old.decisions, ...page.decisions]} : page)
    } catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy('') }
  }
  useEffect(() => {
    void load()
    const leave = () => { latestAction.current++ }
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) { setProgress(''); void load() }
    }
    window.addEventListener('pagehide', leave)
    window.addEventListener('pageshow', restore)
    return () => {
      leave()
      window.removeEventListener('pagehide', leave)
      window.removeEventListener('pageshow', restore)
    }
  }, [id])
  async function act(action: string, sale?: {token: string; limit: string}) {
    if (!run) return
    const ticket = ++latestAction.current
    setBusy(action)
    setError('')
    setProgress('')
    setConfirmStop(false)
    setSaleFeedback('')
    try {
      let revision = run.revision
      const count = action === 'sample' ? windows : 1
      for (let i = 1; i <= count; i++) {
        if (action === 'sample') setProgress('Observing window ' + i + ' of ' + count + '…')
        const endpoint = sale ? route + '/positions/' + sale.token + '/observe-sell' : route + '/' + action
        let body: {revision: number; maxShares?: string; cap?: string; amount?: string} = {revision}
        if (sale) body.maxShares = sale.limit
        if (action === 'change-cap') body.cap = newCap
        if (action === 'deposit') body.amount = depositAmount
        if (action === 'withdraw') body.amount = withdrawAmount
        const fresh = await api<Portfolio>(endpoint, 'POST', body)
        if (ticket !== latestAction.current) return
        const displayed = tradesOnly ? await api<Portfolio>(historyRoute(true)) : fresh
        if (ticket !== latestAction.current) return
        setRun(displayed)
        if (action === 'deposit') {
          setDepositAmount('')
          setProgress('Simulated deposit recorded. Available cash is ' + fresh.cash + ' pUSD.')
        }
        if (action === 'withdraw') {
          setWithdrawAmount('')
          setProgress('Simulated withdrawal recorded. Available cash is ' + fresh.cash + ' pUSD.')
        }
        if (action === 'change-cap') {
          setNewCap('')
          setProgress('Future BUY cap saved at ' + fresh.entryCap + ' pUSD.')
        }
        revision = fresh.revision
        if (sale) {
          const decision = fresh.decisions[0]
          const position = run.positions.find(p => p.tokenId === sale.token)
          const subject = [position?.market ?? 'Outcome token ' + sale.token, position?.outcome].filter(Boolean).join(' · ')
          setSaleFeedback(subject + ' · ' + (decision.kind === 'exit' ? 'Sold ' + decision.shares + ' simulated shares for ' + decision.proceeds + ' pUSD after fees.' : decision.reason))
        }
        if (action === 'sample') {
          const decision = fresh.decisions[0]
          const outcome = decision.kind === 'entry' ? 'Modeled BUY of ' + decision.shares + ' shares.' : decision.reason
          setProgress(i + ' of ' + count + (count === 1 ? ' window recorded. ' : ' windows recorded. ') + outcome)
          if (!fresh.nextBudget || decision.kind === 'unavailable') break
        }
      }
    }
    catch (cause) {
      if (ticket !== latestAction.current) return
      setError(errorMessage(cause))
      setProgress('')
      try {
        const fresh = await api<Portfolio>(historyRoute(tradesOnly))
        if (ticket === latestAction.current) setRun(fresh)
      } catch { /* Keep the last observed state available. */ }
    } finally { if (ticket === latestAction.current) setBusy('') }
  }
  return <div className="stack paper-page">
    <a className="text-link" href="#/paper"><ArrowLeft size={15}/> All public runs</a>
    {error && <div className="error" role="alert">{error} <button className="text-link" onClick={() => load()}>Refresh run</button></div>}
    {!run && busy && <p role="status">Loading run…</p>}
    {run && <>
      <section className="panel workspace-panel paper-overview">
        <div className="panel-head"><h2>{run.name}</h2><span className="badge">{labels[run.status]}</span></div>
        {run.status === 'stopped' && <p className="paper-stop-summary" role="status">{exposureSummary(run)}</p>}
        <small className="muted">Leader wallet</small><code className="paper-wallet">{run.wallet}</code>
        <dl className="paper-metrics">
          <div><dt>Simulated cash</dt><dd>{run.cash} <small>pUSD</small></dd></div>
          <div><dt>Open position cost</dt><dd>{run.openCost} <small>pUSD</small></dd></div>
          <div><dt>Realized result</dt><dd>{run.realized} <small>pUSD</small></dd></div>
        </dl>
        <p className="workspace-note">Started with {run.capital} pUSD · {run.entryCap} pUSD per entry · {when(run.createdAt)}</p>
        {run.status !== 'stopped' && Number(run.netContributions) <= 999 && <details className="paper-evidence"><summary>Add simulated cash</summary>
          <form className="stack paper-form" onSubmit={e => { e.preventDefault(); void act('deposit') }}>
            <label className="field">Simulated deposit (pUSD)<input required type="number" min="1" step=".01"
              max={Math.min(1000, 1000 - Number(run.netContributions))} value={depositAmount} onChange={e => setDepositAmount(e.target.value)}/></label>
            <p>This adds to the funds this strategy can spend on future simulated purchases. Its per-entry cap and pause setting stay the same. Deposits appear separately from trading results.</p>
            <button className="btn" disabled={!!busy || !depositAmount}>Record simulated deposit</button>
          </form>
        </details>}
        {run.status !== 'stopped' && run.cash !== '0' && <details className="paper-evidence"><summary>Withdraw simulated cash</summary>
          <form className="stack paper-form" onSubmit={e => { e.preventDefault(); void act('withdraw') }}>
            <label className="field">Simulated withdrawal (pUSD)<input required type="number" min="0.000001" step="0.000001" max={run.cash}
              value={withdrawAmount} onChange={e => setWithdrawAmount(e.target.value)}/></label>
            <p>Up to {run.cash} pUSD is free. Your shares stay open. Future purchases use the remaining cash within your cap.
              {run.backgroundEnabled && ' Background sampling turns off if less than 1 pUSD remains.'}</p>
            <button className="btn" disabled={!!busy || !withdrawAmount}>Record simulated withdrawal</button>
          </form>
        </details>}
        {run.status !== 'stopped' && <details className="paper-evidence"><summary>Change future BUY cap</summary>
          <form className="stack paper-form" onSubmit={e => { e.preventDefault(); void act('change-cap') }}>
            <label className="field">New per-entry cap (pUSD)
              <input required type="number" min="1" max={Number(run.capital)} step=".01" value={newCap}
                placeholder={run.entryCap} onChange={e => setNewCap(e.target.value)}/>
            </label>
            <p>Each future purchase can use up to this amount, including modeled fees, from the remaining simulated cash. Existing positions keep their original costs.</p>
            <button className="btn" disabled={!!busy || !newCap}>Save future cap</button>
          </form>
        </details>}
        <p className="workspace-note">Purchases {run.gross} pUSD · Sales {run.sales} pUSD before fees · Total modeled fees {run.fees} pUSD</p>
        <details className="paper-evidence"><summary>Entry assumptions</summary>
          <p>The model uses whole shares from up to {run.policy.maxLevels} displayed ask levels after a {run.policy.delaySeconds}-second delay.
            The price may exceed the leader’s price by up to {run.policy.maxPriceIncrease} pUSD per share. The book must arrive within {run.policy.maxSignalAgeMs / 1000} seconds of the BUY.</p>
          <p>{run.policy.checkSalesBeforeEntry
            ? 'Before pricing a BUY, the model checks for a sale of the same outcome since the BUY’s reported second. A visible sale blocks the entry. Public indexing can lag.'
            : 'This run checks purchases only during BUY windows. A leader sale may go unseen.'} Each source order can use the entry budget once, even across multiple fills.</p>
          <p>Displayed depth can change. The model reserves estimated fees and checks the minimum share size. The venue’s minimum purchase value is unverified.</p>
        </details>
        <PortfolioValue key={run.revision} run={run}/>
      </section>
      {run.status === 'running' && run.nextBudget && <section className="panel workspace-panel" aria-label="Background sampling">
        <div className="panel-head"><h2>{run.backgroundEnabled ? 'Background sampling enabled' : 'Background sampling'}</h2>
          <button className="btn" disabled={!!busy} onClick={() => act(run.backgroundEnabled ? 'background-off' : 'background-on')}>
            {run.backgroundEnabled ? 'Disable background sampling' : 'Enable background sampling'}
          </button>
        </div>
        <p>While PolySia is running, it checks short BUY windows with your simulated budget, even after you close the browser. Checks are spaced at least 15 seconds apart. Activity between windows can be missed.</p>
        {run.backgroundEnabled && <button className="text-link" disabled={!!busy} onClick={() => load()}>Refresh decisions</button>}
      </section>}
      <WeekOverview run={run} refreshRun={() => void load()}/>
      <div className="paper-workbench">
      <section className="panel workspace-panel">
        <h2>{run.status === 'stopped' ? 'Run closed to observations' : run.status === 'paused' ? 'New entries paused' : 'Observe a BUY window'}</h2>
        <p>{run.status === 'stopped' ? 'You can review the saved decisions, check current prices and export this run.' :
          run.status === 'paused' ? (run.exitsEnabled ? 'You can still observe a SELL for an open position.' : 'New entries are paused. Resume when you want to observe another BUY.') :
          run.nextBudget ? 'Sample the next two seconds. A verified BUY and a timely book can model an entry of up to ' + run.nextBudget + ' pUSD, including fees.' :
          'Less than 1 pUSD remains for a BUY. You can still manage open positions.'}</p>
        {run.status === 'running' && run.nextBudget && <label className="paper-window-count">Windows to sample
          <select value={windows} disabled={!!busy} onChange={e => { setWindows(Number(e.target.value)); setProgress('') }}>
            <option value={1}>One window</option><option value={5}>Up to five windows</option>
          </select></label>}
        {run.status === 'running' && windows > 1 && <p className="workspace-note">Keep this run open for the series. Leaving lets the current window finish and ends further sampling.</p>}
        <div className="paper-actions">
          {run.status === 'running' && <><button className="btn primary" disabled={!!busy || !run.nextBudget} onClick={() => act('sample')}>
            <ScanLine size={16}/>{busy === 'sample' ? 'Observing…' : windows === 1 ? 'Sample next window' : 'Start sampling'}</button>
            <button className="btn" disabled={!!busy && busy !== 'sample'} onClick={() => act('pause')}><Pause size={15}/> Pause entries</button></>}
          {run.status === 'paused' && <button className="btn primary" disabled={!!busy} onClick={() => act('resume')}><Play size={15}/> Resume entries</button>}
          {run.status !== 'stopped' && !confirmStop && <button className="btn" disabled={!!busy && busy !== 'sample' && busy !== 'sell'} onClick={() => setConfirmStop(true)}><Square size={14}/> Stop run</button>}
          <a className="btn" href={'/api/v1/' + route + '/export'} download={'polysia-public-shadow-' + id + '.json'}><Download size={15}/> Export run</a>
        </div>
        {confirmStop && <div className="paper-confirm" role="group" aria-label="Stop this run permanently">
          <strong>Stop observing this wallet?</strong>
          <p>{exposureSummary(run)} Stopping ends future BUY and SELL windows for this run.</p>
          <button className="btn" onClick={() => act('stop')}>Confirm stop</button>{' '}
          <button className="text-link" onClick={() => setConfirmStop(false)}>Keep run</button></div>}
        <div role="status" className="workspace-note">{progress ||
          (busy === 'sample' ? 'Checking public activity, settlement and displayed depth…' :
          run.status === 'stopped' ? 'The full observation receipts are available in the export.' : 'Time between windows is unobserved. An empty window can get one later activity check.')}</div>
      </section>
      <section className="panel workspace-panel" aria-label="Open simulated positions"><h2>Open simulated positions</h2>
        {(busy === 'sell' || saleFeedback) && <p role="status" className="paper-sale-result">{busy === 'sell' ? 'Checking the leader’s sale and delayed bids…' : saleFeedback}</p>}
        {!run.exitsEnabled && run.status !== 'stopped' && <div className="paper-legacy">
          <p>This run started with BUY-only rules. You can enable share-limited SELL windows and preserve its history.</p>
          <button className="btn" disabled={!!busy} onClick={() => act('enable-exits')}>Enable SELL windows</button>
        </div>}
        {run.positions.length === 0 ? <p>{run.entries ? 'All simulated positions are closed.' : 'No modeled BUY has opened a position.'}</p> : <div className="paper-list">
          {run.positions.map(p => <div className="paper-holding" key={p.conditionId + p.tokenId}><div className="paper-position">
            <div><b>{p.market ?? 'Market ' + p.conditionId}</b><small>{p.outcome ?? 'Outcome token ' + p.tokenId}</small></div>
            <div><b>{p.shares} shares</b><small>{p.cost} pUSD cost including fees</small></div>
          </div>{p.soldShares !== '0' && <small>{p.soldShares} shares sold to date · {p.realized} pUSD realized</small>}
            <PositionMark key={run.revision} route={route} revision={run.revision} token={p.tokenId}/>
            {run.activeExitPolicy && run.status !== 'stopped' && <PositionSale shares={p.shares} policy={run.activeExitPolicy} cumulative={!!run.policy.saleSizing} busy={!!busy}
              observe={limit => act('sell', {token: p.tokenId, limit})}/>}
          </div>)}</div>}
        <p className="workspace-note">Open cost includes purchase fees. A midpoint check estimates the value of the remaining shares. Realized result includes sale fees and the purchase cost of shares sold.</p>
      </section>
      </div>
      {run.closedPositions.length > 0 && <section className="panel workspace-panel" aria-label="Closed simulated positions">
        <h2>Closed simulated positions</h2>
        {run.closedPositions.map(p => <div className="paper-closed" key={p.conditionId + p.tokenId}>
          <div className="panel-head"><h3>{p.market ?? 'Market ' + p.conditionId} · {p.outcome ?? 'Outcome token ' + p.tokenId}</h3>
            <b>{p.realized} pUSD realized</b></div>
          <p>{p.soldShares} shares sold · {p.releasedCost} pUSD purchase cost including fees · {p.saleProceeds} pUSD received after sale fees</p>
          <small>Last sale {when(p.closedAt)}</small>
        </div>)}
      </section>}
      <section className="panel workspace-panel"><div className="panel-head"><h2>Decision history</h2>
        <label className="paper-window-count">Show <select aria-label="Decision history filter" disabled={!!busy}
          value={tradesOnly ? 'trades' : 'all'} onChange={e => load(undefined, e.target.value === 'trades')}>
          <option value="all">All decisions</option><option value="trades">Modeled trades</option></select></label></div>
        {!run.decisions.length && <p>{tradesOnly ? 'No modeled purchases or sales in this run.' : 'Your first window will appear here, even if no trade is visible.'}</p>}
        <ol className="paper-journal">{run.decisions.map(d => <li key={d.revision}>
          <div className="panel-head"><b>{d.observation?.side === 'SELL' && d.kind === 'duplicate' ? 'Sale already recorded' :
              d.observation?.side === 'SELL' && d.kind === 'waiting' ? 'No matching SELL observed' :
              d.observation?.side === 'SELL' && d.kind === 'skipped' ? 'Sale skipped' : labels[d.kind] ?? d.kind}</b><small className="muted">{when(d.at)}</small></div>
          <p>{d.reason}</p>{d.kind === 'entry' && <p>{d.market && <>{d.market} · </>}{d.outcome && <>{d.outcome} · </>}{d.shares} shares · {d.gross} pUSD + {d.fee} pUSD fee</p>}
          {d.kind === 'waiting' && d.observation?.side === 'BUY' && d.observation.windowStartSeconds != null &&
            <WindowRecheck route={route} revision={d.revision}/>}
          {d.kind === 'exit' && <p>{d.market && <>{d.market} · </>}{d.outcome && <>{d.outcome} · </>}{d.shares} of {d.targetShares} targeted shares sold · {d.proceeds} pUSD after fees · {d.realized} pUSD realized</p>}
          {d.observation && <details className="paper-evidence"><summary>Observation details</summary>
            <dl>{d.observation.side === 'SELL' ? <div><dt>Share limit</dt><dd>{d.observation.maxShares} shares</dd></div> :
              <div><dt>Budget</dt><dd>{d.observation.budget} pUSD including fees</dd></div>}
              {d.kind === 'exit' && <div><dt>Sale accounting</dt><dd>{d.gross} pUSD gross · {d.fee} pUSD fee · {d.releasedCost} pUSD purchase cost released</dd></div>}
              <div><dt>Activity window</dt><dd>{d.observation.windowStartSeconds != null && d.observation.windowEndSeconds != null
                ? when(d.observation.windowStartSeconds * 1000) + ' – ' + when(d.observation.windowEndSeconds * 1000) : 'Unavailable'}</dd></div>
              {d.observation.outcomeToken && <div><dt>Selected outcome token</dt><dd><code>{d.observation.outcomeToken}</code></dd></div>}
              {d.observation.eventTimeSeconds != null && <div><dt>Reported {d.observation.side}</dt><dd>{when(d.observation.eventTimeSeconds * 1000)}</dd></div>}
              {d.observation.bookReceivedMs != null && <div><dt>Book received</dt><dd>{when(d.observation.bookReceivedMs)}</dd></div>}
              {d.sourceOrder && <div><dt>Polygon exchange and source order</dt><dd><code>{d.sourceOrder}</code></dd></div>}
              {d.sourceFill && <div><dt>Verified Polygon fill</dt><dd><code>{d.sourceFill}</code></dd></div>}
            </dl>
          </details>}
        </li>)}</ol>
        {run.nextCursor && <button className="btn" disabled={!!busy} onClick={() => load(run.nextCursor!)}>Earlier decisions</button>}
      </section>
    </>}
  </div>
}

export function PublicRuns({id}: {id?: string}) {
  if (id === 'new') return <Setup/>
  return id ? <Detail key={id} id={id}/> : <Library/>
}
