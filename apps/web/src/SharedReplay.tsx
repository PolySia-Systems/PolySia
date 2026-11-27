import { useState, type FormEvent } from 'react'
import { api, errorMessage } from './api'

type RunOption = {id: string; name: string; wallet: string}
type Replay = {
  startingCash: string; cash: string; cost: string; fees: string
  duplicateOrders: number; missingSaleChecks: number; limitedBuys: number
  firstBookMs: number | null; lastBookMs: number | null
  otherRecordedDecisions: Record<string, number>
  runs: (RunOption & {revision: number; recordedBuys: number; modeledBuys: number; cost: string})[]
}

export function SharedReplay({runs}: {runs: RunOption[]}) {
  const [selected, setSelected] = useState<string[]>([])
  const [capital, setCapital] = useState('100')
  const [report, setReport] = useState<Replay | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function change(ids: string[], funds: string) {
    setSelected(ids)
    setCapital(funds)
    setError('')
    setReport(null)
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setReport(null)
    try { setReport(await api<Replay>('public-runs/shared-replay', 'POST', {runIds: selected, capital})) }
    catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <details className="paper-sale">
    <summary>Replay buys with one shared budget</summary>
    <p>Choose saved runs to see which of their recorded buys fit in one simulated cash balance. Each buy keeps its original cap.</p>
    <form onSubmit={submit}>
      <fieldset className="shared-options" disabled={busy}>
        <legend>Choose at least two runs</legend>
        {runs.map(run => <label key={run.id}>
          <input type="checkbox" checked={selected.includes(run.id)} onChange={e =>
            change(e.target.checked ? [...selected, run.id] : selected.filter(id => id !== run.id), capital)}/>
          {run.name} · {run.wallet.slice(0, 8)}…{run.wallet.slice(-6)} · run {run.id.slice(0, 8)}
        </label>)}
      </fieldset>
      <label>Shared starting cash (pUSD)<input type="number" required min="1" max="1000" step=".01" value={capital}
        disabled={busy} onChange={e => change(selected, e.target.value)} /></label>
      <button className="btn" disabled={busy || selected.length < 2}>{busy ? 'Replaying buys…' : 'Replay selected buys'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {report && <section aria-label="Shared budget result" aria-live="polite">
      <h3>Shared budget result</h3>
      <p><strong>{report.cash} pUSD cash left</strong> from {report.startingCash} pUSD. Modeled purchase cost was {report.cost} pUSD, including {report.fees} pUSD in fees.</p>
      {report.firstBookMs !== null && report.lastBookMs !== null
        ? <p>Retained books from {new Date(report.firstBookMs).toISOString()} through {new Date(report.lastBookMs).toISOString()}.</p>
        : <p>The selected runs have no recorded buys to replay.</p>}
      <ul>{report.runs.map(run => <li key={run.id}><a href={'#/paper/' + run.id}>{run.name}</a> · revision {run.revision} · {run.modeledBuys} of {run.recordedBuys} recorded buys modeled · {run.cost} pUSD used</li>)}</ul>
      <p>{report.duplicateOrders} repeated orders across runs. {report.missingSaleChecks} missing sale checks. {report.limitedBuys} buys limited by remaining budget or depth.</p>
      <p>Books are processed in receipt order, with ties settled by run ID. Earlier purchases consume the displayed shares at each price for the rest of the replay.</p>
      <p>Only original modeled buys are eligible. The selected journals also contain {report.otherRecordedDecisions.exit ?? 0} modeled {report.otherRecordedDecisions.exit === 1 ? 'sale' : 'sales'} and {report.otherRecordedDecisions.waiting ?? 0} quiet {report.otherRecordedDecisions.waiting === 1 ? 'window' : 'windows'}. This entry-only replay leaves shares open and reports no investment return. Your saved runs keep their original balances.</p>
    </section>}
  </details>
}
