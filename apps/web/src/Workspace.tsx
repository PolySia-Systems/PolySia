import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  ArrowUpRight,
  Check,
  CircleHelp,
  Database,
  Eye,
  Fingerprint,
  Moon,
  RefreshCw,
  Sun,
  Wallet,
} from 'lucide-react'
import { api, type Account, type Workspace } from './api'
import './workspace.css'

type Props = { workspace: Workspace; refresh: () => Promise<void> }
type Health = {
  status: string
  mode: string
  version: string
  liveExecution: boolean
  artifactSha256: string | null
}

function timestamp(value: string | null) {
  if (!value) return 'Unknown'
  return (
    new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'medium',
      timeZone: 'UTC',
    }).format(new Date(value)) + ' UTC'
  )
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed. Please try again.'
}

export function Accounts({
  workspace,
  refresh,
  initialAddress,
}: Props & { initialAddress?: string }) {
  const account = workspace.account
  const [address, setAddress] = useState(initialAddress ?? account?.address ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')

  async function watch(event: FormEvent) {
    event.preventDefault()
    setError('')
    setFeedback('')
    setBusy(true)
    try {
      await api('account', 'POST', { address: address.trim(), revision: workspace.accountRevision })
      await refresh()
      setFeedback('Read attempt complete.')
    } catch (e) {
      setError(errorText(e))
      await refresh().catch(() => {})
    } finally {
      setBusy(false)
    }
  }

  async function disconnect() {
    setBusy(true)
    setError('')
    setFeedback('')
    try {
      await api('account', 'DELETE', { revision: workspace.accountRevision })
      await refresh()
      setAddress('')
      setFeedback('Watch removed. Your wallet and replay history are unaffected.')
    } catch (e) {
      setError(errorText(e))
      await refresh().catch(() => {})
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace-page">
      <section className="panel workspace-panel">
        <header>
          <Eye aria-hidden="true" size={20} />
          <h2>Watch a public account</h2>
        </header>
        <p>
          Inspect published open positions using a Polymarket trading wallet address. No signature
          is required.
        </p>
        <form onSubmit={watch}>
          <label className="field" htmlFor="wallet-address">
            Public wallet address
          </label>
          <div className="watch-input">
            <input
              id="wallet-address"
              type="text"
              placeholder="0x…"
              autoCapitalize="none"
              spellCheck={false}
              autoComplete="off"
              required
              pattern="0x[0-9a-fA-F]{40}"
              maxLength={42}
              title="Enter 0x followed by 40 hexadecimal characters"
              value={address}
              disabled={busy}
              onChange={(e) => setAddress(e.target.value)}
            />
            <button className="btn primary" disabled={busy}>
              {busy
                ? 'Updating…'
                : account?.address === address.trim().toLowerCase()
                  ? 'Refresh positions'
                  : account
                    ? 'Replace watched address'
                    : 'Watch account'}
            </button>
          </div>
          <p className="workspace-note">
            Watching or refreshing sends this address to the Polymarket Data API. A new watch
            replaces the previous address.
          </p>
        </form>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <span role="status" className="muted">
          {feedback}
        </span>
      </section>
      {account && (
        <PositionSnapshot account={account} heading="Position snapshot">
          <a className="btn" href={'#/paper/new?' + new URLSearchParams({wallet: account.address})}>
            Set up public shadow run
          </a>
          <button className="btn subtle" disabled={busy} onClick={disconnect}>
            Remove watch
          </button>
        </PositionSnapshot>
      )}
      {account && <HoldingsValue key={account.address} address={account.address} />}
      {!account && (
        <section className="panel workspace-panel">
          <header>
            <Fingerprint aria-hidden="true" size={20} />
            <h2>Account scope</h2>
          </header>
          <p>
            The public watch is independent of the fictional wallet used for replays. Watching an
            address grants no permission to trade, transfer funds or manage orders.
          </p>
        </section>
      )}
    </div>
  )
}

interface HoldingsValueRead {
  address: string
  status: 'available' | 'unavailable'
  value: string | null
  unit: string | null
  source: string
  checkedAt: string
  observedAt: string | null
  message: string
}

export function HoldingsValue({ address }: { address: string }) {
  const [result, setResult] = useState<HoldingsValueRead | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setBusy(true)
    setResult(null)
    setError('')
    try {
      const read = await api<HoldingsValueRead>('public/traders/' + address + '/value')
      if (read.address !== address) throw new Error('The holdings value identified a different wallet.')
      setResult(read)
    } catch (cause) {
      setError(errorText(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel workspace-panel holdings-value" aria-label="Holdings value">
      <div className="panel-head">
        <h2>Holdings value</h2>
        <button className="btn" disabled={busy} onClick={load}>
          {busy ? 'Reading value…' : result || error ? 'Refresh holdings value' : 'Load holdings value'}
        </button>
      </div>
      <div role="status">
        {result && (
          <>
            <strong className="holdings-amount">
              {result.status === 'available' && result.value !== null
                ? `${result.value} ${result.unit ?? '(unit unavailable)'}`
                : 'Value unavailable'}
            </strong>
            <p>{result.message}</p>
            <p className="workspace-note">{result.source} · Checked {timestamp(result.checkedAt)}
              {result.observedAt && result.observedAt !== result.checkedAt && <> · Retrieved {timestamp(result.observedAt)}</>}
            </p>
          </>
        )}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  )
}

function PositionRows({
  positions,
  caption,
}: {
  positions: Account['positions']
  caption: string
}) {
  return (
    <div className="positions-table">
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th>Market</th>
            <th>Outcome</th>
            <th>Shares</th>
            <th>State</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((position, i) => (
            <tr key={i}>
              <td>{position.market}</td>
              <td>{position.outcome}</td>
              <td>{position.shares}</td>
              <td>
                {({ OPEN: 'Open', REDEEMABLE: 'Redeemable' } as Record<string, string>)[
                  position.status ?? ''
                ] ?? 'Unknown'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PositionSnapshot({
  account,
  heading,
  children,
}: {
  account: Account
  heading: string
  children?: ReactNode
}) {
  return (
    <section className="panel workspace-panel">
      <header>
        <Wallet aria-hidden="true" size={20} />
        <h2>{heading}</h2>
      </header>
      <div className="watch-heading">
        <code>{account.address}</code>
        <span className="badge">Public read only</span>
      </div>
      <p>{account.message}</p>
      <dl className="workspace-facts">
        <div>
          <dt>Last check</dt>
          <dd>{timestamp(account.checkedAt)}</dd>
        </div>
        <div>
          <dt>Snapshot retrieved</dt>
          <dd>{timestamp(account.observedAt)}</dd>
        </div>
        <div>
          <dt>Coverage</dt>
          <dd>
            {account.status === 'unavailable'
              ? 'Current positions unknown'
              : account.complete
                ? 'Complete provider page'
                : 'First page; more positions available'}
          </dd>
        </div>
      </dl>
      {account.positions.length > 0 && (
        <PositionRows positions={account.positions} caption="Positions in this snapshot" />
      )}
      {account.status === 'unavailable' && account.lastSuccessful && (
        <details className="more-details" key={account.address}>
          <summary>Last successful snapshot (historical)</summary>
          <p>
            Retrieved {timestamp(account.lastSuccessful.observedAt)} from{' '}
            {account.lastSuccessful.source}.
          </p>
          <p>
            {account.lastSuccessful.complete
              ? 'Complete provider page at retrieval.'
              : 'First page only at retrieval.'}{' '}
            Current holdings remain unknown.
          </p>
          {account.lastSuccessful.positions.length ? (
            <PositionRows
              positions={account.lastSuccessful.positions}
              caption="Previously reported positions"
            />
          ) : (
            <p>The provider returned no position rows in that snapshot.</p>
          )}
        </details>
      )}
      <p className="workspace-note">
        Source: {account.source}. Cash, equity, open orders, signing authority and trading
        eligibility are unknown.
      </p>
      <div className="watch-actions">
        <a
          className="btn"
          href={'https://polymarket.com/profile/' + account.address}
          target="_blank"
          rel="noreferrer"
        >
          Provider profile <ArrowUpRight aria-hidden="true" size={15} />
        </a>
        {children}
      </div>
    </section>
  )
}

export function Settings({ workspace, refresh }: Props) {
  const { settings } = workspace
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  async function choose(theme: 'light' | 'dark') {
    if (busy || theme === settings.theme) return
    setBusy(true)
    setError('')
    setFeedback('')
    try {
      await api('settings', 'PUT', {
        version: settings.version,
        revision: settings.revision,
        theme,
      })
      await refresh()
      setFeedback('Appearance saved.')
    } catch (e) {
      setError(errorText(e))
      await refresh().catch(() => {})
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="panel workspace-panel">
      <header>
        <Sun size={20} aria-hidden="true" />
        <h2>Appearance</h2>
      </header>
      <p>
        Choose the theme for this workspace. Your selection takes effect immediately and
        persists across restarts.
      </p>
      <div className="theme-choices" role="group" aria-label="Workspace theme">
        {(['light', 'dark'] as const).map((theme) => {
          const Icon = theme === 'light' ? Sun : Moon
          return (
            <button
              key={theme}
              className="theme-choice"
              aria-pressed={theme === settings.theme}
              disabled={busy}
              onClick={() => choose(theme)}
            >
              <span className={'theme-preview theme-preview-' + theme}>
                <i />
                <i />
                <i />
              </span>
              <span>
                <Icon size={16} aria-hidden="true" />
                {theme === 'light' ? 'Light' : 'Dark'}
                {theme === settings.theme && <Check size={16} aria-hidden="true" />}
              </span>
            </button>
          )
        })}
      </div>
      <p className="workspace-note">Workspace preference · Revision {settings.revision}</p>
      <span role="status">{feedback}</span>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  )
}

export function Status({ workspace }: Props) {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setHealth(null)
    setError('')
    api<Health>('health')
      .then((result) => {
        if (active) setHealth(result)
      })
      .catch((e) => {
        if (active) setError(errorText(e))
      })
    return () => {
      active = false
    }
  }, [attempt])
  return (
    <div className="workspace-page">
      <section className="panel workspace-panel">
        <header>
          <Database size={20} aria-hidden="true" />
          <h2>Runtime health</h2>
        </header>
        <dl className="workspace-facts">
          <div>
            <dt>Workspace API</dt>
            <dd>
              {error
                ? 'Unreachable'
                : health
                  ? health.status + ' · v' + health.version
                  : 'Checking…'}
            </dd>
          </div>
          {health && (
            <div>
              <dt>Installed artifact</dt>
              <dd>
                {health.artifactSha256 ? (
                  <code className="artifact-digest" aria-label="Installer SHA-256">
                    {health.artifactSha256}
                  </code>
                ) : (
                  'Source checkout'
                )}
              </dd>
            </div>
          )}
          <div>
            <dt>Last public account check</dt>
            <dd>
              {workspace.account
                ? workspace.account.status + ' · ' + timestamp(workspace.account.checkedAt)
                : 'No watched account'}
            </dd>
          </div>
          <div>
            <dt>Latest replay</dt>
            <dd>{workspace.run?.status ?? 'No run yet'}</dd>
          </div>
        </dl>
        {error && <p role="alert">{error}</p>}
        <button className="btn" onClick={() => setAttempt((value) => value + 1)}>
          <RefreshCw size={15} aria-hidden="true" /> Check API
        </button>
      </section>
      <section className="panel workspace-panel">
        <header>
          <CircleHelp aria-hidden="true" size={20} />
          <h2>Project status</h2>
        </header>
        <p>
          Public rankings and account watches read Polymarket. Public shadow runs use public BUY and SELL
          observations and simulated funds. Scenario replays use fictional leaders, prices and funds.
        </p>
        <p>
          A budgeted observation checks the wallet’s order and market fees before measuring
          displayed depth. The next test is how often a usable quote survives those checks across
          different wallets and market conditions.
        </p>
      </section>
    </div>
  )
}
