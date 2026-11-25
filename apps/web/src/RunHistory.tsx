import { useEffect, useState } from 'react'
import { Download, History } from 'lucide-react'
import { api, errorMessage, money, signed, type Run } from './api'
import './history.css'

type Summary = Pick<
  Run,
  | 'id'
  | 'status'
  | 'leader_name'
  | 'capital'
  | 'order_size'
  | 'cash'
  | 'quantity'
  | 'marked_net_result'
  | 'fees'
> & { createdAt: string }
type Page = { runs: Summary[]; nextCursor: string | null }

export default function RunHistory({ refreshKey }: { refreshKey: string }) {
  const [cursor, setCursor] = useState<string | null>(null)
  const [page, setPage] = useState<Page | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let current = true
    setPage(null)
    setError('')
    const query = cursor ? '?before=' + encodeURIComponent(cursor) : ''
    api<Page>('runs' + query)
      .then((value) => {
        if (current) setPage(value)
      })
      .catch((reason) => {
        if (current) setError(errorMessage(reason))
      })
    return () => {
      current = false
    }
  }, [cursor, refreshKey, attempt])
  const rows = page?.runs.filter((run) => run.status === 'completed' || run.status === 'stopped')
  return (
    <section className="panel replay-history" aria-labelledby="run-history-title">
      <div className="panel-head">
        <h2 className="section-title" id="run-history-title">
          <History size={18} aria-hidden="true" /> Run history
        </h2>
      </div>
      <div className="panel-body">
        {error && (
          <div role="alert" className="error">
            {error}{' '}
            <button className="btn" onClick={() => setAttempt((x) => x + 1)}>
              Retry
            </button>
          </div>
        )}
        {!page && !error && (
          <p role="status" className="muted">
            Loading saved runs…
          </p>
        )}
        {page && !rows?.length && (
          <p className="muted">Completed and stopped replays appear here.</p>
        )}
        {rows && rows.length > 0 && (
          <>
            <p className="muted history-note">
              Estimated net P/L includes fees and the value of open shares at the final step’s
              midpoint. Open shares without a midpoint leave the estimate unavailable.
            </p>
            <div className="history-rows">
              {rows.map((run) => (
                <article className="history-row" key={run.id}>
                  <div className="history-identity">
                    <a
                      href={'#/runs/' + run.id}
                      aria-label={'Review ' + run.leader_name + ' run ' + run.id.slice(0, 8)}
                    >
                      <strong>{run.leader_name}</strong>
                    </a>
                    <span className="muted">
                      {run.status === 'stopped' ? 'Stopped' : 'Completed'} ·{' '}
                      <time dateTime={run.createdAt}>
                        {new Date(run.createdAt).toLocaleString(undefined, {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </time>
                    </span>
                  </div>
                  <dl className="history-facts">
                    <div>
                      <dt>Allocation / cap</dt>
                      <dd>
                        {money(run.capital)} / {money(run.order_size)}
                      </dd>
                    </div>
                    <div>
                      <dt>Cash / open shares</dt>
                      <dd>
                        {money(run.cash)} / {run.quantity}
                      </dd>
                    </div>
                    <div>
                      <dt>Estimated net P/L</dt>
                      <dd>
                        {run.marked_net_result === null
                          ? 'Unavailable'
                          : signed(run.marked_net_result, 2)}
                      </dd>
                    </div>
                    <div>
                      <dt>Fees</dt>
                      <dd>{money(run.fees)}</dd>
                    </div>
                  </dl>
                  <a
                    className="btn history-export"
                    href={'/api/v1/runs/' + encodeURIComponent(run.id)}
                    download={'polysia-replay-' + run.id + '.json'}
                    aria-label={
                      'Export ' + run.leader_name + ' run ' + run.id.slice(0, 8) + ' as JSON'
                    }
                  >
                    <Download aria-hidden="true" size={15} /> Export JSON
                  </a>
                </article>
              ))}
            </div>
          </>
        )}
        {(cursor || page?.nextCursor) && (
          <div className="history-paging">
            {cursor && (
              <button className="btn" onClick={() => setCursor(null)}>
                Newest runs
              </button>
            )}
            {page?.nextCursor && (
              <button className="btn" onClick={() => setCursor(page.nextCursor)}>
                Older runs
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
