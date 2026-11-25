import { useState } from 'react'
import { Download, ScanLine } from 'lucide-react'
import { api, errorMessage } from './api'

interface Receipt {
  schemaVersion: 1
  wallet: string
  status: 'waiting' | 'incomplete' | 'unavailable' | 'observed'
  windowStartSeconds: number
  windowEndSeconds: number
  reason: string
  activityReceivedMs?: number
  bookRequestedMs?: number
  bookReceivedMs?: number
  event?: { eventTimeSeconds: number; price: string; shares: string; fillId: null }
  book?: {
    sourceTimeMs: number
    askLevelCount: number
    sourceAgeAtDetectionMs?: number
    bestAskMinusLeaderPrice?: string | null
    bestAsks: { price: string; shares: string }[]
  }
}

const outcomes: Record<Receipt['status'], string> = {
  waiting: 'No BUY observed in this window',
  incomplete: 'Partial evidence',
  unavailable: 'Observation unavailable',
  observed: 'BUY and displayed book observed',
}

function clock(ms: number) {
  return new Date(ms).toISOString().slice(11, 23)
}

export function PublicObservation({ address }: { address: string }) {
  const [busy, setBusy] = useState(false)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState('')
  async function observe() {
    setError('')
    setReceipt(null)
    setBusy(true)
    try {
      setReceipt(await api<Receipt>('public/traders/' + address + '/observe', 'POST', {}))
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel workspace-panel">
      <header>
        <ScanLine aria-hidden="true" size={20} />
        <h2>Public BUY observation</h2>
      </header>
      <p>
        Sample the next five seconds for this wallet. An ordinary buy visible in that window
        triggers one read of the same outcome’s displayed asks.
      </p>
      <button className="btn" disabled={busy} onClick={observe}>
        Observe next BUY
      </button>
      <span role="status">{busy ? ' Sampling one window…' : ''}</span>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {receipt && (
        <div className="observation-result" aria-live="polite">
          <h3>{outcomes[receipt.status]}</h3>
          <p>{receipt.reason}</p>
          <dl className="workspace-facts">
            <div>
              <dt>Observation window (UTC)</dt>
              <dd>
                {new Date(receipt.windowStartSeconds * 1000).toISOString().slice(0, 10)} ·{' '}
                {clock(receipt.windowStartSeconds * 1000)} –{' '}
                {clock((receipt.windowEndSeconds + 1) * 1000)}
              </dd>
            </div>
            {receipt.event && (
              <div>
                <dt>Provider BUY time (UTC)</dt>
                <dd>
                  {clock(receipt.event.eventTimeSeconds * 1000)} · {receipt.event.shares} shares at{' '}
                  {receipt.event.price}
                </dd>
              </div>
            )}
            {receipt.activityReceivedMs != null && (
              <div>
                <dt>Activity received (UTC)</dt>
                <dd>{clock(receipt.activityReceivedMs)}</dd>
              </div>
            )}
            {receipt.book && (
              <div>
                <dt>Book source time (UTC)</dt>
                <dd>{clock(receipt.book.sourceTimeMs)}</dd>
              </div>
            )}
            {receipt.book?.sourceAgeAtDetectionMs != null && (
              <div>
                <dt>Book update relative to detection</dt>
                <dd>
                  {Math.abs(receipt.book.sourceAgeAtDetectionMs)} ms{' '}
                  {receipt.book.sourceAgeAtDetectionMs >= 0 ? 'before' : 'after'} detection
                </dd>
              </div>
            )}
            {receipt.book?.bestAskMinusLeaderPrice != null && (
              <div>
                <dt>Best ask minus reported BUY price</dt>
                <dd>{receipt.book.bestAskMinusLeaderPrice} per share</dd>
              </div>
            )}
            {receipt.bookReceivedMs != null && (
              <div>
                <dt>Book received (UTC)</dt>
                <dd>{clock(receipt.bookReceivedMs)}</dd>
              </div>
            )}
          </dl>
          {receipt.book && receipt.book.bestAsks.length > 0 && (
            <div className="positions-table">
              <table>
                <caption>
                  Lowest {receipt.book.bestAsks.length} of {receipt.book.askLevelCount} displayed
                  ask levels
                  {receipt.status === 'incomplete' ? ' · timing or coverage unverified' : ''}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Ask price</th>
                    <th scope="col">Shares available</th>
                  </tr>
                </thead>
                <tbody>
                  {receipt.book.bestAsks.map((level, i) => (
                    <tr key={i}>
                      <td>{level.price}</td>
                      <td>{level.shares}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {receipt.event && (
            <p className="workspace-note">
              The transaction reference can cover several fills. Individual fill identity, follower
              fees and execution price remain unknown.
            </p>
          )}
          <a
            className="btn"
            href={
              'data:application/json;charset=utf-8,' +
              encodeURIComponent(JSON.stringify(receipt, null, 2))
            }
            download={'polysia-observation-' + receipt.windowStartSeconds + '.json'}
          >
            <Download size={15} aria-hidden="true" />
            Download observation
          </a>
        </div>
      )}
    </section>
  )
}
