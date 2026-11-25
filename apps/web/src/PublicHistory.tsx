import { useState } from 'react'
import { ChartNoAxesCombined } from 'lucide-react'
import { api, errorMessage } from './api'

interface Point {
  time: number
  value: string | null
}
interface History {
  status: 'available' | 'unavailable'
  message: string
  sourceGrid: string | null
  checkedAt: string
  points: Point[]
}

const date = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'UTC',
})

function Series({ points }: { points: Point[] }) {
  const values = points.flatMap((p) => (p.value === null ? [] : [Number(p.value)]))
  const low = Math.min(...values)
  const high = Math.max(...values)
  const start = points[0].time
  const end = points[points.length - 1].time
  const x = (time: number) => (end === start ? 300 : 5 + 590 * ((time - start) / (end - start)))
  const y = (value: string) =>
    high === low ? 45 : 80 - 70 * ((Number(value) - low) / (high - low))
  return (
    <>
      {values.length > 0 && (
        <figure className="public-pnl-plot">
          <figcaption>Cumulative realized P/L (USDC)</figcaption>
          <svg
            viewBox="0 0 600 90"
            role="img"
            aria-label="Cumulative observations. Exact values and timestamps are in the sample table."
          >
            {points.map((point, i) => {
              if (point.value === null) return null
              const prev = points[i - 1]
              const joined = prev && prev.value !== null && point.time - prev.time <= 86400
              return (
                <g key={point.time}>
                  {joined && (
                    <line
                      x1={x(prev.time)}
                      y1={y(prev.value!)}
                      x2={x(point.time)}
                      y2={y(point.value)}
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                  )}
                  <circle cx={x(point.time)} cy={y(point.value)} r="3" fill="currentColor" />
                </g>
              )
            })}
          </svg>
          <small>
            Observed range: {low.toLocaleString('en-US', { maximumFractionDigits: 2 })} to{' '}
            {high.toLocaleString('en-US', { maximumFractionDigits: 2 })} USDC
          </small>
        </figure>
      )}
      <p className="workspace-note">
        Coverage: {date.format(start * 1000)} – {date.format(end * 1000)} UTC
      </p>
      <details className="more-details">
        <summary>View {points.length} daily-grid samples</summary>
        <div className="positions-table">
          <table>
            <caption>Polymarket realized P/L samples</caption>
            <thead>
              <tr>
                <th scope="col">Time (UTC)</th>
                <th scope="col">Cumulative P/L (USDC)</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.time}>
                  <td>{date.format(point.time * 1000)}</td>
                  <td>{point.value ?? 'Unavailable'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

export function PublicHistory({ address }: { address: string }) {
  const [history, setHistory] = useState<History | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function load() {
    setBusy(true)
    setError('')
    setHistory(null)
    try {
      setHistory(await api<History>('public/traders/' + address + '/history'))
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="panel workspace-panel">
      <header>
        <ChartNoAxesCombined size={20} aria-hidden="true" />
        <h2>Realized P/L history</h2>
      </header>
      <p>
        One week of daily observations. Each value is the trader’s cumulative realized P/L across
        markets, liquidity provision and combos. Open-position marks and wallet income are excluded.
      </p>
      <button className="btn" disabled={busy} onClick={load}>
        {busy ? 'Loading history…' : history ? 'Refresh P/L history' : 'Load P/L history'}
      </button>
      {error && <p role="alert">{error}</p>}
      {history &&
        (history.status === 'unavailable' ? (
          <p role="alert">{history.message}</p>
        ) : (
          <>
            {history.points.length ? (
              <Series points={history.points} />
            ) : (
              <p role="status">Polymarket returned no samples for this week.</p>
            )}
            <p className="workspace-note">
              Polymarket Data API v2 · Retrieved {date.format(new Date(history.checkedAt))} UTC
              {history.sourceGrid ? ' · Source interval ' + history.sourceGrid : ''}
            </p>
          </>
        ))}
    </section>
  )
}
