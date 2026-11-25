import { useState, type FormEvent } from 'react'
import { Download, ScanLine } from 'lucide-react'
import { api, errorMessage } from './api'

interface ActivityCoverage {
  rowsReturned: number
  ordinaryBuyRows: number
  complete: boolean
}

interface ActivityRead {
  requestedMs: number
  receivedMs?: number
  activityCoverage?: ActivityCoverage
  reason?: string
}

interface Receipt {
  schemaVersion: 1 | 2 | 3
  wallet: string
  status: 'waiting' | 'incomplete' | 'unavailable' | 'observed'
  windowStartSeconds: number
  windowEndSeconds: number
  reason: string
  researchBudget?: string
  evidenceCheckedMs?: number
  participant?:
    | { status: 'matched'; role: 'maker' | 'taker'; logIndex: number; blockNumber: number;
        grossCollateral?: string; chargedFee?: string; totalCollateral?: string }
    | { status: 'unresolved' | 'unavailable'; reason: string }
  capacity?: {
    status: 'estimated' | 'skipped' | 'incomplete'
    reason: string
    budget: string
    shares?: string
    gross?: string
    feeEstimate?: string
    spreadPercentOfAsk?: string | null
    unspent?: string
    maxPriceIncrease: string
    maxLevels: number
  }
  activityCoverage?: ActivityCoverage
  activityReads?: ActivityRead[]
  detectionRead?: 1 | 2
  activityReceivedMs?: number
  bookRequestedMs?: number
  bookReceivedMs?: number
  event?: {
    eventTimeSeconds: number
    price: string
    shares: string
    fillId: null
    marketTitle?: string
    outcomeLabel?: string
    tokenId?: string
  }
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
  const [retryEmpty, setRetryEmpty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState('')
  const showReason = receipt && (!receipt.capacity || (
    receipt.status !== 'observed' && receipt.capacity.reason !== receipt.reason
  )) && !receipt.activityReads?.some(read => read.reason === receipt.reason)
  async function observe(event: FormEvent) {
    event.preventDefault()
    setError('')
    setReceipt(null)
    setBusy(true)
    try {
      const options = retryEmpty ? { budget, retryEmpty: true } : { budget }
      const result = await api<Receipt>('public/traders/' + address + '/observe', 'POST', options)
      if (result.wallet !== address) throw new Error('The observation identified a different wallet.')
      setReceipt(result)
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
        Look for BUYs this wallet makes in the next two seconds. If a BUY arrives in time, PolySia
        checks its Polygon receipt and market fees, then samples the asks after two seconds plus
        any reported taker delay.
      </p>
      <form className="observation-form" onSubmit={observe}>
        <label className="field">
          Research budget (pUSD)
          <input type="number" inputMode="decimal" required min="1" max="1000" step=".01"
            value={budget} disabled={busy} onChange={e => setBudget(e.target.value)} />
        </label>
        <div className="observation-retry">
          <label>
            <input type="checkbox" checked={retryEmpty} disabled={busy}
              onChange={e => setRetryEmpty(e.target.checked)} aria-describedby="retry-window-timing" />
            Check again if the first read is empty
          </label>
          <small id="retry-window-timing" className="muted">
            If the complete first page has no ordinary BUY, try the same window three seconds
            after it closes while a timely book check is still possible.
          </small>
        </div>
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
          {showReason && <p>{receipt.reason}</p>}
          {receipt.activityReads && receipt.activityReads.length > 0 && (
            <section className="activity-reads" aria-label="Activity reads">
              <h4>{receipt.detectionRead
                ? `BUY first visible on the ${receipt.detectionRead === 1 ? 'first' : 'second'} read`
                : 'Activity reads'}</h4>
              <ol>
                {receipt.activityReads.map((read, i) => (
                  <li key={i}>
                    <b>{i === 0 ? 'First read' : 'Second read'}</b>
                    {read.activityCoverage && (
                      <span>
                        {read.activityCoverage.ordinaryBuyRows} ordinary BUY{' '}
                        {read.activityCoverage.ordinaryBuyRows === 1 ? 'row' : 'rows'} among{' '}
                        {read.activityCoverage.rowsReturned} returned ·{' '}
                        {read.activityCoverage.complete ? 'Complete page' : 'First page only'}
                      </span>
                    )}
                    {read.reason && <span>{read.reason}</span>}
                    <small className="read-times muted">
                      <span>Requested {clock(read.requestedMs)} UTC</span>
                      {read.receivedMs != null && <span>Received {clock(read.receivedMs)} UTC</span>}
                    </small>
                  </li>
                ))}
              </ol>
            </section>
          )}
          {receipt.event && (
            <div>
              {receipt.event.marketTitle && <p><b>{receipt.event.marketTitle}</b></p>}
              <p><b>Wallet BUY</b> · {receipt.event.shares} shares
                {receipt.event.outcomeLabel && <> on <b>{receipt.event.outcomeLabel}</b></>} at {receipt.event.price} pUSD per share.</p>
            </div>
          )}
          {receipt.participant?.status === 'matched' && receipt.participant.grossCollateral != null &&
            receipt.participant.chargedFee != null && receipt.participant.totalCollateral != null && (
            <p><b>Wallet spend</b> · {receipt.participant.grossCollateral} pUSD in shares +{' '}
              {receipt.participant.chargedFee} pUSD charged fee = {receipt.participant.totalCollateral} pUSD total.</p>
          )}
          {!receipt.capacity && receipt.researchBudget && (
            <p className="workspace-note">Budget for this window · {receipt.researchBudget} pUSD</p>
          )}
          {receipt.capacity && (
            <section className="capacity-result">
              <h4>Research budget · {receipt.capacity.budget} pUSD</h4>
              {receipt.capacity.status === 'estimated' ? (
                <>
                  <strong>{receipt.capacity.shares} whole shares</strong> of displayed buy capacity
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
          {receipt.capacity?.status === 'estimated' && receipt.book?.spreadPerShare != null && receipt.book.bestBid && (
            <p>Bid–ask spread <b>{receipt.book.spreadPerShare} pUSD per share</b> · best
              bid {receipt.book.bestBid.price} for {receipt.book.bestBid.shares} shares.
              {receipt.capacity.spreadPercentOfAsk != null && ` The spread is ${receipt.capacity.spreadPercentOfAsk}% of the best ask.`}</p>
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
              {!receipt.activityReads && receipt.activityCoverage && (
                <div>
                  <dt>Public activity coverage</dt>
                  <dd>
                    {receipt.activityCoverage.ordinaryBuyRows} ordinary BUY rows among{' '}
                    {receipt.activityCoverage.rowsReturned} returned ·{' '}
                    {receipt.activityCoverage.complete
                      ? 'Complete page'
                      : 'First page only (more rows exist)'}
                  </dd>
                </div>
              )}
              {receipt.event && (
                <div>
                  <dt>Provider BUY time (UTC)</dt>
                  <dd>
                    {clock(receipt.event.eventTimeSeconds * 1000)}
                  </dd>
                </div>
              )}
              {receipt.event?.tokenId && (
                <div><dt>Outcome token</dt><dd>{receipt.event.tokenId}</dd></div>
              )}
              {!receipt.activityReads && receipt.activityReceivedMs != null && (
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
