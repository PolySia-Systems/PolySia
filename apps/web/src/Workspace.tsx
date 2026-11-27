import { useEffect, useState, type ReactNode } from 'react'
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
import { api, type Accent, type Account, type Workspace } from './api'
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
  const [invalidAddress, setInvalidAddress] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')

  const saved = workspace.savedWallets.find((wallet) => wallet.address === account?.address)

  async function watch(nextAddress: string) {
    setError('')
    setFeedback('')
    setBusy(true)
    try {
      await api('account', 'POST', { address: nextAddress.trim(), revision: workspace.accountRevision })
      await refresh()
      setAddress(nextAddress.trim().toLowerCase())
      setInvalidAddress(false)
      setFeedback('Read attempt complete.')
    } catch (e) {
      setError(errorText(e))
      await refresh().catch(() => {})
    } finally {
      setBusy(false)
    }
  }

  async function updateSaved(label: string | null) {
    if (!account) return
    setBusy(true)
    setError('')
    setFeedback('')
    const wallet = { address: account.address, revision: workspace.accountRevision }
    try {
      if (label === null) await api('account/saved', 'DELETE', wallet)
      else await api('account/saved', 'PUT', { ...wallet, label })
      await refresh()
      setFeedback(label === null ? 'Removed from saved wallets.' : 'Wallet saved.')
    } catch (cause) {
      setError(errorText(cause))
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
      setInvalidAddress(false)
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
          Enter the public trading wallet address from your Polymarket profile to check cash and open positions.
        </p>
        {workspace.savedWallets.length > 0 && (
          <label className="field saved-wallet-picker">
            Saved wallets
            <select value={saved?.address ?? ''} disabled={busy}
              onChange={(event) => void watch(event.target.value)}>
              <option disabled value="">Select a wallet</option>
              {workspace.savedWallets.map((wallet) => (
                <option key={wallet.address} value={wallet.address}>
                  {wallet.label ? wallet.label + ' · ' : ''}{wallet.address}
                </option>
              ))}
            </select>
          </label>
        )}
        <form onSubmit={(event) => { event.preventDefault(); void watch(address) }}>
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
              aria-invalid={invalidAddress || undefined}
              aria-describedby={invalidAddress ? 'wallet-address-error' : undefined}
              onInvalid={() => setInvalidAddress(true)}
              title="Enter 0x followed by 40 hexadecimal characters"
              value={address}
              disabled={busy}
              onChange={(e) => {
                setAddress(e.target.value)
                if (e.target.validity.valid) setInvalidAddress(false)
              }}
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
          {invalidAddress && <p className="error" id="wallet-address-error" role="alert">
            Use 0x followed by exactly 40 hexadecimal characters.
          </p>}
          <p className="workspace-note">
            Watching or switching reads this address from Polymarket. Each wallet has its own cash and positions.
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
      {account && <WalletValue key={'cash-' + account.address} address={account.address} kind="cash" walletName={saved?.label} />}
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
      {account && (
        <section className="panel workspace-panel" aria-label="Save this wallet">
          <h2>Save this wallet</h2>
          <p className="workspace-note">Keep this public address for quick switching. Saved wallets have read-only access.</p>
          <form key={account.address + '/' + (saved?.label ?? '')}
            onSubmit={(event) => {
              event.preventDefault()
              void updateSaved(String(new FormData(event.currentTarget).get('label') ?? ''))
            }}>
            <label className="field" htmlFor="saved-wallet-name">Wallet name (optional)</label>
            <div className="watch-input">
              <input id="saved-wallet-name" name="label" defaultValue={saved?.label ?? ''} maxLength={64} disabled={busy} />
              <button className="btn" disabled={busy}>{saved ? 'Update name' : 'Save wallet'}</button>
              {saved && <button type="button" className="btn subtle" disabled={busy}
                onClick={() => void updateSaved(null)}>Remove from saved wallets</button>}
            </div>
          </form>
        </section>
      )}
      {account && <WalletValue key={account.address} address={account.address} kind="holdings" />}
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

interface WalletValueRead {
  address: string
  status: 'available' | 'unavailable'
  value: string | null
  unit: string | null
  source: string
  checkedAt: string
  observedAt: string | null
  message: string
}

export function WalletValue({ address, kind, walletName }: { address: string; kind: 'cash' | 'holdings'; walletName?: string }) {
  const cash = kind === 'cash'
  const title = cash ? 'Cash balance' : 'Holdings value'
  const [result, setResult] = useState<WalletValueRead | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const loadLabel = cash ? 'Read cash balance' : 'Load holdings value'
  const buttonLabel = result || error ? `Refresh ${title.toLowerCase()}` : loadLabel
  const unavailable = cash ? 'Balance unavailable' : 'Value unavailable'

  async function load() {
    setBusy(true)
    setResult(null)
    setError('')
    try {
      const endpoint = cash ? 'cash' : 'value'
      const read = await api<WalletValueRead>(`public/traders/${address}/${endpoint}`)
      if (read.address !== address) throw new Error('The result identified a different wallet.')
      setResult(read)
    } catch (cause) {
      setError(errorText(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel workspace-panel holdings-value" aria-label={title}>
      <div className="panel-head">
        <h2>{title}</h2>
        <button className="btn" disabled={busy} onClick={load}>
          {busy ? 'Reading…' : buttonLabel}
        </button>
      </div>
      {cash && <p className="workspace-note">Polygon pUSD · {walletName && walletName + ' · '}
        <code title={address}>{address.slice(0, 8)}…{address.slice(-6)}</code></p>}
      <div role="status">
        {result && (
          <>
            <strong className="holdings-amount">
              {result.status === 'available' && result.value !== null
                ? `${result.value} ${result.unit ?? '(unit unavailable)'}`
                : unavailable}
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

export function Settings({ workspace, refresh, preview, previewAccent }: Props & {
  preview: Accent | null; previewAccent: (draft: Accent | null) => void
}) {
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
  const published = workspace.accent
  async function publish() {
    if (busy || !preview) return
    setBusy(true)
    setError('')
    setFeedback('')
    try {
      await api('settings/accent', 'PUT', preview)
      await refresh()
      previewAccent(null)
      setFeedback('Workspace accent published.')
    } catch (e) {
      setError(errorText(e))
      await refresh().catch(() => {})
    } finally { setBusy(false) }
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
      <h3>Workspace accent</h3>
      <p>Preview the color of links and actions across this tab. Publish to use it throughout the workspace in both light and dark themes.</p>
      <div className="paper-actions" role="group" aria-label="Accent presets">
        {(['forest', 'ocean'] as const).map(preset => <button key={preset} type="button" className="btn"
          disabled={busy} aria-pressed={preset === (preview?.preset ?? published.preset)}
          onClick={() => {
            previewAccent(preset === published.preset ? null : {preset, revision: published.revision})
            setError('')
            setFeedback('')
          }}>{preset === (preview?.preset ?? published.preset) && <Check size={16} aria-hidden="true" />}
          {preset === 'forest' ? 'Forest (default)' : 'Ocean'}</button>)}
      </div>
      <p className="workspace-note">Published accent · {published.preset} · Revision {published.revision}</p>
      {preview && <>
        <p role="status">Previewing {preview.preset}. <a href="#/discover">View discovery</a></p>
        <div className="paper-actions">
          <button className="btn primary" disabled={busy} onClick={publish}>Publish accent</button>
          <button className="btn" disabled={busy} onClick={() => previewAccent(null)}>Discard preview</button>
        </div>
      </>}
      <span role="status">{feedback}</span>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  )
}

interface OwnerOverview {
  running: number
  paused: number
  stopped: number
  background: number
  checkedAt: string
  more: boolean
  issues: { id: string; name: string; updated: string; reason: string }[]
}

function PortfolioStatus() {
  const [overview, setOverview] = useState<OwnerOverview | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setOverview(null)
    setError('')
    api<OwnerOverview>('workspace/overview').then(result => {
      if (active) setOverview(result)
    }).catch(cause => {
      if (active) setError(errorText(cause))
    })
    return () => { active = false }
  }, [attempt])
  return (
    <section className="panel workspace-panel" aria-label="Shadow portfolio overview">
      <header><Eye size={20} aria-hidden="true" /><h2>Shadow portfolio overview</h2></header>
      {overview ? <>
        <p>{overview.running} running · {overview.paused} paused · {overview.stopped} stopped</p>
        <p>Background sampling enabled for {overview.background} {overview.background === 1 ? 'run' : 'runs'}.</p>
        <h3>Needs review</h3>
        {overview.issues.length ? <ul>{overview.issues.map(issue => (
          <li key={issue.id}>
            <a href={'#/paper/' + issue.id}>{issue.name}</a> · {issue.reason}
            <span className="workspace-note"> · {timestamp(issue.updated)}</span>
          </li>
        ))}</ul> : <p>No current observation warnings or stopped runs with open shares.</p>}
        {overview.more && <p>Showing the five most recent items.</p>}
        <p className="workspace-note">Checked {timestamp(overview.checkedAt)}</p>
      </> : error ? <p role="alert">{error}</p> : <p role="status">Reading saved runs…</p>}
      <div className="watch-actions">
        <a className="btn" href="#/paper">View all shadow runs</a>
        <button className="btn subtle" onClick={() => setAttempt(value => value + 1)}>Refresh overview</button>
      </div>
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
      <PortfolioStatus />
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
              <dt>Workspace access</dt>
              <dd>{health.mode === 'owner-access' ? 'Owner-only HTTPS' : health.mode === 'local' ? 'Local loopback' : 'Unknown'}</dd>
            </div>
          )}
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
          The next trial follows a first-time owner selecting a leader, explaining a skipped entry
          and finding the remaining shares after stopping and restarting.
        </p>
      </section>
    </div>
  )
}
