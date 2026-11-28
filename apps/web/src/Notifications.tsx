import { useEffect, useState } from 'react'
import { api, errorMessage } from './api'

const labels = { incomplete: 'Incomplete observation', unavailable: 'Provider unavailable',
  entry: 'Simulated buy', exit: 'Simulated sale' }
type Category = 'warnings' | 'trades'
interface Notices {
  checkedAt: string
  more: boolean
  items: { id: string; wallet: string; name: string; status: string; kind: keyof typeof labels
    recorded: string; reason: string; revision: number; occurrences: number }[]
}

export function Notifications() {
  const [category, setCategory] = useState<Category>('warnings')
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<Notices | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setError('')
    setResult(null)
    api<Notices>('workspace/notifications?category=' + category).then(data => {
      if (active) setResult(data)
    }).catch(cause => { if (active) setError(errorMessage(cause)) })
    return () => { active = false }
  }, [attempt, category])
  return <section className="panel workspace-panel">
    <div className="paper-actions">
      <label className="field">Show notifications
        <select value={category} onChange={e => setCategory(e.target.value as Category)}>
          <option value="warnings">Observation warnings</option>
          <option value="trades">Simulated fills</option>
        </select>
      </label>
      <button className="btn" onClick={() => setAttempt(x => x + 1)}>Refresh notifications</button>
    </div>
    {error ? <p role="alert">{error}</p> : !result ? <p role="status">Reading saved decisions…</p> : <>
      <p className="workspace-note">Checked {new Date(result.checkedAt).toLocaleString()}. Repeated events are grouped by run and type. Open a run to see its current state.</p>
      {result.items.length ? <ul className="paper-journal">{result.items.map(item =>
        <li key={item.id + item.kind}>
          <strong>{labels[item.kind]}</strong> · <time dateTime={item.recorded}>{new Date(item.recorded).toLocaleString()}</time>
          <p>{item.reason}</p>
          <a href={'#/paper/' + item.id}>{item.name}</a> · {item.status} · {item.occurrences} recorded
          <div className="workspace-note">Leader {item.wallet.slice(0, 8)}…{item.wallet.slice(-6)} · decision {item.revision}</div>
        </li>)}</ul> : <p>{category === 'warnings' ? 'No observation warnings have been recorded.' : 'No simulated buys or sales have been recorded.'}</p>}
      {result.more && <p>Showing the 20 most recently updated groups. <a href="#/paper">Open saved runs</a> for their full journals.</p>}
    </>}
  </section>
}
