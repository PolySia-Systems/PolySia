import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage } from './api'

type Source = {id: string; wallet: string; name: string; backgroundEnabled: boolean}
type Item = {id: string; name: string; status: 'running' | 'paused' | 'stopped'}
type Pool = Item & {
  generation: number; windows: number; startingCash: string; cost: string; fees: string; cash: string
  limitedBuys: number; missingSaleChecks: number; duplicateOrders: number; otherRecordedDecisions: Record<string, number>
  latestSourceWindow: {recorded: string; reason: string; run_id: string} | null
  runs: {id: string; name: string; sourceBackgroundEnabled: boolean; recordedBuys: number; modeledBuys: number
    sharesByToken: Record<string, number>; cost: string}[]
}

export function CapitalPoolSetup({runs}: {runs: Source[]}) {
  const [pools, setPools] = useState<Item[]>([])
  const [name, setName] = useState('')
  const [capital, setCapital] = useState('100')
  const [members, setMembers] = useState<string[]>([])
  const [id] = useState(() => crypto.randomUUID().replaceAll('-', ''))
  const [issue, setIssue] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    api<{pools: Item[]}>('capital-pools').then(result => {
      if (active) { setPools(result.pools); setIssue('') }
    }).catch(error => { if (active) setIssue(errorMessage(error)) })
    return () => { active = false }
  }, [attempt])
  async function start(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setIssue('')
    try {
      const result = await api<Pool>('capital-pools/' + id, 'PUT', {name, capital, runIds: members})
      location.hash = '/paper/pool-' + result.id
    } catch (error) { setIssue(errorMessage(error)) }
    finally { setBusy(false) }
  }
  const enabled = runs.filter(run => run.backgroundEnabled)
  return <section aria-label="Shared background portfolios">
    <h3>Shared background portfolios</h3>
    {pools.map(pool => <p key={pool.id}><a href={'#/paper/pool-' + pool.id}>{pool.name}</a> · {pool.status}</p>)}
    {issue && <p role="alert">{issue} <button className="text-link" onClick={() => setAttempt(n => n + 1)}>Refresh list</button></p>}
    <details className="paper-sale"><summary>Follow leaders with one simulated balance</summary>
      <p>Choose runs for different wallets with background BUY sampling enabled. Only future windows count. The server keeps sampling when the browser closes. Original runs keep their own balances.</p>
      {new Set(enabled.map(run => run.wallet)).size < 2
        ? <p>Enable background sampling in two runs for different wallets, then return here. Use Older runs to load more saved choices.</p>
        : <form onSubmit={start}>
          <label>Portfolio name<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label>
          <label>Shared cash (pUSD)<input type="number" required min="1" max="1000" step=".01" value={capital} onChange={e => setCapital(e.target.value)} /></label>
          <fieldset className="shared-options" disabled={busy}><legend>Background runs</legend>
            {enabled.map(run => <label key={run.id}><input type="checkbox" checked={members.includes(run.id)}
              onChange={e => setMembers(e.target.checked ? [...members, run.id] : members.filter(id => id !== run.id))}/>
              {run.name} · {run.wallet.slice(0, 8)}…{run.wallet.slice(-6)} · {run.id.slice(0, 8)}</label>)}
          </fieldset>
          <button className="btn" disabled={busy || members.length < 2}>Start shared portfolio</button>
        </form>}
    </details>
  </section>
}

export function CapitalPool({id}: {id: string}) {
  const [pool, setPool] = useState<Pool | null>(null)
  const [issue, setIssue] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const route = 'capital-pools/' + id
  async function update(status?: Item['status']) {
    setBusy(true)
    setIssue('')
    try {
      const result = status && pool
        ? await api<Pool>(route + '/control', 'POST', {generation: pool.generation, status})
        : await api<Pool>(route)
      setPool(result)
      setConfirm(false)
    } catch (cause) { setIssue(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  useEffect(() => { void update() }, [id])
  const others = pool?.otherRecordedDecisions ?? {}
  return <section className="panel workspace-panel paper-page">
    <a className="text-link" href="#/paper">All public runs</a>
    <div className="panel-head"><h2>{pool?.name ?? 'Shared background portfolio'}</h2>
      <button className="btn" onClick={() => update()} disabled={busy}>Refresh portfolio</button></div>
    {issue && <p role="alert">{issue}</p>}
    {pool && <>
      <p><strong>{pool.status}</strong> · {pool.windows} recorded background windows</p>
      {pool.latestSourceWindow && <p>Latest <a href={'#/paper/' + pool.latestSourceWindow.run_id}>source window</a> · {new Date(pool.latestSourceWindow.recorded).toLocaleString()} · {pool.latestSourceWindow.reason}</p>}
      <dl className="paper-metrics"><div><dt>Simulated cash left</dt><dd>{pool.cash} <small>pUSD</small></dd></div>
        <div><dt>Open purchase cost</dt><dd>{pool.cost} <small>pUSD</small></dd></div>
        <div><dt>Included fees</dt><dd>{pool.fees} <small>pUSD</small></dd></div></dl>
      <p>Starting cash was {pool.startingCash} pUSD. Sales and market valuations are unavailable for shared portfolios. The shares below remain open.</p>
      {pool.runs.map(run => <div key={run.id} className="paper-closed"><a href={'#/paper/' + run.id}>{run.name}</a>
        <p>Source sampling {run.sourceBackgroundEnabled ? 'enabled' : 'off'} · {run.modeledBuys} of {run.recordedBuys} recorded buys modeled · {run.cost} pUSD used</p>
        {Object.entries(run.sharesByToken).map(([token, shares]) => <p key={token}>{shares} shares · Outcome token {token}</p>)}
      </div>)}
      <p>{others.waiting ?? 0} quiet windows · {(others.incomplete ?? 0) + (others.unavailable ?? 0) + pool.missingSaleChecks} with missing evidence · {(others.skipped ?? 0) + pool.limitedBuys} skipped by limits or policy · {(others.duplicate ?? 0) + pool.duplicateOrders} repeated orders.</p>
      <details className="paper-evidence"><summary>How shared buys work</summary>
        <p>Each source first tests its own balance and per-buy cap. Eligible buys then use the remaining shared cash and asks in the order their decisions were saved. Previously consumed shares at each price stay used. A source that stops sampling contributes no new windows.</p></details>
      {pool.status !== 'stopped' && <div className="paper-actions">
        <button className="btn" disabled={busy} onClick={() => update(pool.status === 'running' ? 'paused' : 'running')}>
          {pool.status === 'running' ? 'Pause shared buys' : 'Resume shared buys'}</button>
        <button className="btn" disabled={busy} onClick={() => setConfirm(true)}>Stop shared portfolio</button></div>}
      {confirm && <div className="paper-confirm" role="group" aria-label="Confirm shared portfolio stop">
        <p>Stop this portfolio permanently? Open shares and cash stay visible. The source runs keep their own sampling settings.</p>
        <button className="btn" disabled={busy} onClick={() => update('stopped')}>Confirm stop</button>
        <button className="btn" disabled={busy} onClick={() => setConfirm(false)}>Keep portfolio</button></div>}
    </>}
  </section>
}
