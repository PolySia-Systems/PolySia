import { useState, type FormEvent } from 'react'
import { Download, ScanLine } from 'lucide-react'
import { api, errorMessage } from './api'

interface Receipt {
  schemaVersion: 1 | 2
  wallet: string
  status: 'waiting' | 'incomplete' | 'unavailable' | 'observed'
  windowStartSeconds: number
  windowEndSeconds: number
  reason: string
  researchBudget?: string
  evidenceCheckedMs?: number
  participant?:
    | { status: 'matched'; role: 'maker' | 'taker'; logIndex: number; blockNumber: number }
    | { status: 'unresolved' | 'unavailable'; reason: string }
  capacity?: {
    status: 'estimated' | 'skipped' | 'incomplete'
    reason: string
    budget: string
    shares?: string
    gross?: string
    feeEstimate?: string
    unspent?: string
    maxPriceIncrease: string
    maxLevels: number
  }
  activityCoverage?: { rowsReturned: number; ordinaryBuyRows: number; complete: boolean }
  activityReceivedMs?: number
  bookRequestedMs?: number
  bookReceivedMs?: number
  event?: { eventTimeSeconds: number; price: string; shares: string; fillId: null }
  book?: {
    sourceTimeMs: number
    askLevelCount: number
    sourceAgeAtDetectionMs?: number
    bestAskMinusLeaderPrice?: string | null
    bestBid?: { price: string; shares: string } | null
    bidLevelCount?: number | null
    spreadPerShare?: string | null
    bestAsks: { price: string; shares: string }[]
  }
}

const outcomes: Record<Receipt['status'], string> = {
  waiting: 'No BUY observed in this window',
  incomplete: 'Partial evidence',
  unavailable: 'Observation unavailable',
  observed: 'BUY and displayed book observed',
}

const capacityOutcomes = {
  estimated: 'Displayed capacity estimated',
  skipped: 'Budget check skipped',
  incomplete: 'Budget check incomplete',
}

function clock(ms: number) {
  return new Date(ms).toISOString().slice(11, 23)
}

export function PublicObservation({ address }: { address: string }) {
  const [budget, setBudget] = useState('10')
  const [busy, setBusy] = useState(false)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState('')
  async function observe(event: FormEvent) {
    event.preventDefault()
    setError('')
    setReceipt(null)
    setBusy(true)
    try {
      setReceipt(await api<Receipt>('public/traders/' + address + '/observe', 'POST', { budget }))
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
        Sample the next two seconds for this wallet. For a visible BUY, check the Polygon receipt
        and market fees, then sample the asks after two seconds plus any reported taker delay.
      </p>
      <form className="observation-form" onSubmit={observe}>
        <label className="field">
          Research budget (pUSD)
          <input type="number" inputMode="decimal" required min="1" max="1000" step=".01"
            value={budget} disabled={busy} onChange={e => setBudget(e.target.value)} />
        </label>
        <button className="btn" disabled={busy}>Observe next BUY</button>
      </form>
      <p className="workspace-note" role="status">
        {busy ? 'Sampling this window and checking public evidence…' : 'Research only. No funds are used.'}
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {receipt && (
        <div className="observation-result" aria-live="polite">
          <h3>{receipt.capacity ? capacityOutcomes[receipt.capacity.status] : outcomes[receipt.status]}</h3>
          <p>{receipt.reason}</p>
          {!receipt.capacity && receipt.researchBudget && (
            <p className="workspace-note">Budget for this window · {receipt.researchBudget} pUSD</p>
          )}
          {receipt.capacity && (
            <section className="capacity-result">
              <h4>Research budget · {receipt.capacity.budget} pUSD</h4>
              {receipt.capacity.status === 'estimated' ? (
                <>
                  <strong>{receipt.capacity.shares} whole shares</strong>
                  <p>{receipt.capacity.gross} pUSD in asks + {receipt.capacity.feeEstimate} pUSD
                    estimated taker fee · {receipt.capacity.unspent} pUSD unspent.</p>
                  <p className="workspace-note">Up to {receipt.capacity.maxLevels} ask levels,
                    up to {receipt.capacity.maxPriceIncrease} pUSD per share above the BUY.
                    Assumes no rebates. Venue minimum notional and actual fees remain unverified.</p>
                </>
              ) : <p>{receipt.capacity.reason}</p>}
            </section>
          )}
          {receipt.participant && (
            <p><b>Participant BUY</b>{' · '}
              {receipt.participant.status === 'matched'
                ? `Matched the wallet’s ${receipt.participant.role} order at Polygon block ${receipt.participant.blockNumber}, log ${receipt.participant.logIndex}. Chain finality is unverified.`
                : receipt.participant.reason}
            </p>
          )}
          {receipt.book?.spreadPerShare != null && receipt.book.bestBid && (
            <p>Bid–ask spread <b>{receipt.book.spreadPerShare} pUSD per share</b> · best
              bid {receipt.book.bestBid.price} for {receipt.book.bestBid.shares} shares.</p>
          )}
          {receipt.book?.bidLevelCount === 0 && <p>No bids were displayed for an exit.</p>}
          <details className="observation-evidence">
            <summary>Window, timing and ask levels</summary>
            <dl className="workspace-facts">
              <div>
                <dt>Observation window (UTC)</dt>
                <dd>
                  {new Date(receipt.windowStartSeconds * 1000).toISOString().slice(0, 10)} ·{' '}
                  {clock(receipt.windowStartSeconds * 1000)} –{' '}
                  {clock((receipt.windowEndSeconds + 1) * 1000)}
                </dd>
              </div>
              {receipt.activityCoverage && (
                <div>
                  <dt>Public activity coverage</dt>
                  <dd>
                    {receipt.activityCoverage.ordinaryBuyRows} ordinary BUY rows among{' '}
                    {receipt.activityCoverage.rowsReturned} returned ·{' '}
                    {receipt.activityCoverage.complete
                      ? 'Complete window response'
                      : 'First page only (more rows exist)'}
                  </dd>
                </div>
              )}
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
              {receipt.evidenceCheckedMs != null && (
                <div>
                  <dt>Participant and market checks ended (UTC)</dt>
                  <dd>{clock(receipt.evidenceCheckedMs)}</dd>
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
            {receipt.event && !receipt.participant && (
              <p className="workspace-note">
                The transaction reference can cover several fills. Individual fill identity, follower
                fees and execution price remain unknown.
              </p>
            )}
          </details>
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
