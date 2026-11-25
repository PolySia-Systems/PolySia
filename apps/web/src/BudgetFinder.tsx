import { useState, type FormEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import { api, errorMessage, money, type ScenarioLimits } from './api'

interface Candidate {
  leaderId: string
  name: string
  full: number
  partial: number
  skipped: number
  missingBook: number
}

interface Coverage {
  allocation: string
  orderSize: string
  candidates: Candidate[]
}

export function BudgetFinder({ limits }: { limits: ScenarioLimits }) {
  const [allocation, setAllocation] = useState('100.00')
  const [orderSize, setOrderSize] = useState('10.00')
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<Coverage | null>(null)
  const [error, setError] = useState('')

  async function check(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setReport(null)
    try {
      const result = await api<Coverage>('leaders/coverage', 'POST', { allocation, orderSize })
      setReport(result)
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  const matches = report?.candidates.filter((row) => row.full > 0) ?? []
  const others = report?.candidates.filter((row) => row.full === 0) ?? []
  const query =
    report && new URLSearchParams({ allocation: report.allocation, orderSize: report.orderSize })

  function result(row: Candidate) {
    return (
      <li key={row.leaderId}>
        <strong>{row.name}</strong>
        {row.skipped > 0 && row.missingBook === row.full + row.partial + row.skipped && (
          <small>Insufficient book evidence for this scenario.</small>
        )}
        <span>
          {row.full} full · {row.partial} partial · {row.skipped} skipped buys
        </span>
        {row.missingBook > 0 && (
          <small>
            Book unavailable for {row.missingBook} skipped {row.missingBook === 1 ? 'buy' : 'buys'}.
          </small>
        )}
        <a
          className="text-link"
          href={'#/preview/' + row.leaderId + '?' + query}
          aria-label={'Preview ' + row.name + ' at this budget'}
        >
          Preview replay <ArrowRight size={14} />
        </a>
      </li>
    )
  }

  return (
    <details className="panel panel-body budget-finder">
      <summary>Find leaders for my simulated budget</summary>
      <p className="muted">
        See which fictional scenarios fully filled at least one buy target at your limits. Each
        replay uses its own identical starting balance.
      </p>
      <form className="stack" onSubmit={check}>
        <div className="form-grid">
          <label className="field">
            Simulated budget (USD)
            <input
              type="number"
              inputMode="decimal"
              required
              step=".01"
              disabled={busy}
              min={limits.min_allocation}
              max={limits.max_allocation}
              value={allocation}
              onChange={(e) => {
                setAllocation(e.target.value)
                setReport(null)
                setError('')
              }}
            />
          </label>
          <label className="field">
            Maximum per buy (USD)
            <input
              type="number"
              inputMode="decimal"
              required
              step=".01"
              disabled={busy}
              min={limits.min_order_size}
              max={Math.min(Number(allocation), Number(limits.max_order_size))}
              value={orderSize}
              onChange={(e) => {
                setOrderSize(e.target.value)
                setReport(null)
                setError('')
              }}
            />
          </label>
        </div>
        <button className="btn" disabled={busy}>
          {busy ? 'Comparing…' : 'Check budget'}
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {report && (
        <div className="budget-results" aria-live="polite">
          <h3>
            {matches.length
              ? matches.length + ' scenarios matched'
              : 'No complete buys observed at these limits'}
          </h3>
          <p className="muted">
            {money(report.allocation)} starting cash · {money(report.orderSize)} cap per buy. Books
            and fees are fictional. Future liquidity is unknown.
          </p>
          {matches.length > 0 && <ul>{matches.map(result)}</ul>}
          {others.length > 0 && (
            <details open={!matches.length}>
              <summary>Scenarios without a complete buy ({others.length})</summary>
              <ul>{others.map(result)}</ul>
            </details>
          )}
        </div>
      )}
    </details>
  )
}
