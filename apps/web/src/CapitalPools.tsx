import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage } from './api'

type Source = {id: string; wallet: string; name: string; backgroundEnabled: boolean}
type Item = {id: string; name: string; status: 'running' | 'paused' | 'stopped'}
type Week = {from: string; through: string} & ({available: false; reason: string} | {
  available: true; openingCash: string; funding: string; purchaseCost: string; includedFees: string
  closingCash: string; buys: number; counts: Record<string, number>; netResult: string | null
  coverage: Record<string, {receipts: number; completePageSeconds: number; periodSeconds: number
    longestGap: {from: string; through: string} | null}>
})
type Pool = Item & {
  week: Week
  generation: number; windows: number; startingCash: string; cost: string; fees: string; cash: string
  limitedBuys: number; missingSaleChecks: number; duplicateOrders: number; otherRecordedDecisions: Record<string, number>
  latestSourceWindow: {recorded: string; reason: string; run_id: string} | null
  runs: {id: string; name: string; wallet: string; sourceBackgroundEnabled: boolean; recordedBuys: number; modeledBuys: number
    sharesByToken: Record<string, number>; cost: string}[]
}

const utc = (value: string) => new Date(value).toLocaleString(undefined, {timeZone: 'UTC', hour12: false})

function PoolWeek({pool}: {pool: Pool}) {
  const week = pool.week
  return <section className="paper-valuation" aria-label="Shared portfolio week">
    <h3>Last seven days</h3>
    <small>{utc(week.from)} – {utc(week.through)} UTC</small>
    {week.available ? <>
      <p>{week.buys} shared {week.buys === 1 ? 'buy' : 'buys'} used {week.purchaseCost} pUSD, including {week.includedFees} in fees.
        {' '}{week.counts.waiting ?? 0} quiet windows · {(week.counts.incomplete ?? 0) + (week.counts.unavailable ?? 0)} windows with missing evidence.</p>
      <p>{week.netResult === null ? 'Net result is unknown because shares remain open without a valuation.' : 'Net result was 0 pUSD. The portfolio held only cash.'}</p>
      <details className="paper-evidence"><summary>Cash and sampling by wallet</summary>
        <p>Opening cash {week.openingCash} pUSD · Funding {week.funding} pUSD · Closing cash {week.closingCash} pUSD.</p>
        <p>Coverage counts the time in windows with a complete public activity page. Indexing may lag. Gaps include pauses and time between checks, starting when the portfolio existed.</p>
        {pool.runs.map(run => {
          const sample = week.coverage[run.id]
          return <div className="paper-closed" key={run.id}><a href={'#/paper/' + run.id}>{run.name} · {run.wallet.slice(0, 6)}…{run.wallet.slice(-4)}</a>
            <p>{sample.receipts} saved {sample.receipts === 1 ? 'window' : 'windows'} · {sample.completePageSeconds.toLocaleString(undefined, {maximumFractionDigits: 3})} seconds covered
              {' '}of {sample.periodSeconds.toLocaleString(undefined, {maximumFractionDigits: 3})} seconds.</p>
            {sample.longestGap && <p>Longest gap · {utc(sample.longestGap.from)} – {utc(sample.longestGap.through)} UTC</p>}
          </div>
        })}
      </details>
    </> : <p>{week.reason}</p>}
  </section>
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
      <p>Choose runs for different leaders with background sampling enabled. This portfolio starts with its own simulated cash and follows future BUY windows. Each source account keeps its funds and history.</p>
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
      {pool.status === 'running' && pool.runs.every(run => !run.sourceBackgroundEnabled) &&
        <p>No source is sampling. Open a source run below to review its status and enable background sampling if available.</p>}
      {pool.latestSourceWindow && <p>Latest <a href={'#/paper/' + pool.latestSourceWindow.run_id}>source window</a> · {new Date(pool.latestSourceWindow.recorded).toLocaleString()} · {pool.latestSourceWindow.reason}</p>}
      <dl className="paper-metrics"><div><dt>Simulated cash left</dt><dd>{pool.cash} <small>pUSD</small></dd></div>
        <div><dt>Open purchase cost</dt><dd>{pool.cost} <small>pUSD</small></dd></div>
        <div><dt>Included fees</dt><dd>{pool.fees} <small>pUSD</small></dd></div></dl>
      <p>Starting cash was {pool.startingCash} pUSD. {pool.runs.some(run => run.modeledBuys > 0)
        ? 'The shares below remain open. Shared portfolios do not model sales or market valuations.'
        : 'The shared portfolio has no open shares.'}</p>
      <PoolWeek pool={pool} />
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
