import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight, Download, Pause, Play, Plus, ScanLine, Square } from 'lucide-react'
import { api, errorMessage } from './api'
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
  sourceOrder: string | null
  observation?: {windowStartSeconds: number | null; windowEndSeconds: number | null; eventTimeSeconds: number | null; bookReceivedMs: number | null; budget: string}
}
interface Portfolio extends Summary {
  policy: { delaySeconds: number; maxSignalAgeMs: number; maxPriceIncrease: string; maxLevels: number }
  decisions: Decision[]
  nextCursor: number | null
  positions: {conditionId: string; tokenId: string; market: string | null; outcome: string | null; shares: string; cost: string}[]
}
const when = (value: string | number) => new Date(value).toLocaleString('en-GB', { timeZone: 'UTC' }) + ' UTC'
const labels: Record<string, string> = {
  running: 'Running', paused: 'Paused', stopped: 'Stopped', entry: 'Modeled BUY', duplicate: 'Already modeled',
  waiting: 'No BUY observed', incomplete: 'Evidence incomplete', skipped: 'Entry skipped',
  unavailable: 'Observation unavailable', pause: 'Entries paused', resume: 'Entries resumed', stop: 'Run stopped',
}

function Setup() {
  const params = new URLSearchParams(location.hash.split('?')[1])
  const [wallet, setWallet] = useState(params.get('wallet') ?? '')
  const [name, setName] = useState((params.get('name') || 'Public wallet').slice(0, 80))
  const [capital, setCapital] = useState('100')
  const [cap, setCap] = useState('10')
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
      <p>Follow one public wallet with simulated pUSD. You decide when to sample a two-second BUY window.</p>
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
        <p className="workspace-note">Public activity comes from Polymarket and is checked against Polygon. A qualifying BUY uses the displayed asks and an estimated fee. The model assumes available depth
          can fill, uses the book’s share minimum and leaves venue minimum notional unverified. Positions stay open until an exit model is available.</p>
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
      <div><span>{labels[run.status]}</span><small>{run.cash} pUSD cash · {run.entries} modeled {run.entries === 1 ? 'BUY' : 'BUYs'}</small></div>
      <ArrowRight size={16} aria-hidden="true"/></a>)}</div>
    {list?.nextCursor && <button className="btn" disabled={busy} onClick={() => load(list.nextCursor!)}>Older runs</button>}
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

function Detail({id}: {id: string}) {
  const [run, setRun] = useState<Portfolio | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [confirmStop, setConfirmStop] = useState(false)
  const [windows, setWindows] = useState(1)
  const [progress, setProgress] = useState('')
  const latestAction = useRef(0)
  const route = 'public-runs/' + id
  async function load(before?: number) {
    setBusy('load')
    setError('')
    try {
      const page = await api<Portfolio>(route + (before ? '?before=' + before : ''))
      if (before && run && page.revision !== run.revision) setRun(await api<Portfolio>(route))
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
  async function act(action: string) {
    if (!run) return
    const ticket = ++latestAction.current
    setBusy(action)
    setError('')
    setProgress('')
    setConfirmStop(false)
    try {
      let revision = run.revision
      const count = action === 'sample' ? windows : 1
      for (let i = 1; i <= count; i++) {
        if (action === 'sample') setProgress('Observing window ' + i + ' of ' + count + '…')
        const fresh = await api<Portfolio>(route + '/' + action, 'POST', {revision})
        if (ticket !== latestAction.current) return
        setRun(fresh)
        revision = fresh.revision
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
        const fresh = await api<Portfolio>(route)
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
        <small className="muted">Leader wallet</small><code className="paper-wallet">{run.wallet}</code>
        <dl className="paper-metrics">
          <div><dt>Simulated cash</dt><dd>{run.cash} <small>pUSD</small></dd></div>
          <div><dt>Purchases before fees</dt><dd>{run.gross} <small>pUSD</small></dd></div>
          <div><dt>Modeled fees</dt><dd>{run.fees} <small>pUSD</small></dd></div>
        </dl>
        <p className="workspace-note">Started with {run.capital} pUSD · {run.entryCap} pUSD per entry · {when(run.createdAt)}</p>
        <details className="paper-evidence"><summary>Entry assumptions</summary>
          <p>The model uses whole shares from up to {run.policy.maxLevels} displayed ask levels after a {run.policy.delaySeconds}-second delay.
            The price may exceed the leader’s price by up to {run.policy.maxPriceIncrease} pUSD per share. The book must arrive within {run.policy.maxSignalAgeMs / 1000} seconds of the BUY.</p>
          <p>Displayed depth can change. The model reserves estimated fees and checks the minimum share size. The venue’s minimum purchase value is unverified.</p>
        </details>
      </section>
      <section className="panel workspace-panel">
        <h2>{run.status === 'stopped' ? 'Run closed to new entries' : 'Observe a BUY window'}</h2>
        <p>{run.status === 'stopped' ? 'Your decisions and any open simulated shares are preserved.' :
          run.status === 'paused' ? 'Entries are paused. Resume when you want to sample another window.' :
          run.nextBudget ? 'Sample the next two seconds. A verified BUY and a timely book can model an entry of up to ' + run.nextBudget + ' pUSD, including fees.' :
          'Less than 1 pUSD remains. Review your open positions or stop this run.'}</p>
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
          {run.status !== 'stopped' && !confirmStop && <button className="btn" disabled={!!busy && busy !== 'sample'} onClick={() => setConfirmStop(true)}><Square size={14}/> Stop run</button>}
          <a className="btn" href={'/api/v1/' + route + '/export'} download={'polysia-public-shadow-' + id + '.json'}><Download size={15}/> Export run</a>
        </div>
        {confirmStop && <div className="paper-confirm"><p>Stopping is permanent for this run. Your open simulated positions will remain.</p>
          <button className="btn" onClick={() => act('stop')}>Confirm stop</button>{' '}
          <button className="text-link" onClick={() => setConfirmStop(false)}>Keep run</button></div>}
        <div role="status" className="workspace-note">{progress ||
          (busy === 'sample' ? 'Checking public activity, settlement and displayed depth…' :
          run.status === 'stopped' ? 'The full observation receipts are available in the export.' : 'Time between windows is unobserved. An empty window can get one later activity check.')}</div>
      </section>
      <section className="panel workspace-panel"><h2>Open simulated positions</h2>
        {run.positions.length === 0 ? <p>No modeled BUY has opened a position.</p> : <div className="paper-list">
          {run.positions.map(p => <div className="paper-holding" key={p.conditionId + p.tokenId}><div className="paper-position">
            <div><b>{p.market ?? 'Market ' + p.conditionId}</b><small>{p.outcome ?? 'Outcome token ' + p.tokenId}</small></div>
            <div><b>{p.shares} shares</b><small>{p.cost} pUSD cost including fees</small></div>
          </div><PositionMark key={run.revision} route={route} revision={run.revision} token={p.tokenId}/></div>)}</div>}
        <p className="workspace-note">Positions stay open at purchase cost. You can check a recent midpoint estimate for each holding. Selling and realized returns are outside this BUY-only model.</p>
      </section>
      <section className="panel workspace-panel"><h2>Decision history</h2>
        {!run.decisions.length && <p>Your first sample will appear here, including a window with no visible BUY.</p>}
        <ol className="paper-journal">{run.decisions.map(d => <li key={d.revision}>
          <div className="panel-head"><b>{labels[d.kind] ?? d.kind}</b><small className="muted">{when(d.at)}</small></div>
          <p>{d.reason}</p>{d.kind === 'entry' && <p>{d.market && <>{d.market} · </>}{d.shares} shares · {d.gross} pUSD + {d.fee} pUSD fee</p>}
          {d.observation && <details className="paper-evidence"><summary>Observation details</summary>
            <dl><div><dt>Budget</dt><dd>{d.observation.budget} pUSD including fees</dd></div>
              <div><dt>Activity window</dt><dd>{d.observation.windowStartSeconds != null && d.observation.windowEndSeconds != null
                ? when(d.observation.windowStartSeconds * 1000) + ' – ' + when(d.observation.windowEndSeconds * 1000) : 'Unavailable'}</dd></div>
              {d.observation.eventTimeSeconds != null && <div><dt>Reported BUY</dt><dd>{when(d.observation.eventTimeSeconds * 1000)}</dd></div>}
              {d.observation.bookReceivedMs != null && <div><dt>Book received</dt><dd>{when(d.observation.bookReceivedMs)}</dd></div>}
              {d.sourceOrder && <div><dt>Polygon exchange and source order</dt><dd><code>{d.sourceOrder}</code></dd></div>}
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
