import { useEffect, useState, type FormEvent } from 'react'
import { ArrowUpRight, Check, CircleHelp, Database, Eye, Fingerprint, Moon, RefreshCw, Sun, Wallet } from 'lucide-react'
import { api, type Workspace } from './api'
import './workspace.css'

type Props = { workspace: Workspace; refresh: () => Promise<void> }
type Health = { status: string; mode: string; version: string; liveExecution: boolean }

function timestamp(value: string | null) {
  if (!value) return 'Unknown'
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' })
    .format(new Date(value)) + ' UTC'
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed. Please try again.'
}

export function Accounts({ workspace, refresh }: Props) {
  const account = workspace.account
  const [address, setAddress] = useState(account?.address ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')

  async function watch(event: FormEvent) {
    event.preventDefault()
    setError('')
    setFeedback('')
    setBusy(true)
    try {
      await api('account', 'POST', {address: address.trim()})
      await refresh()
      setFeedback('Read attempt complete.')
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  async function disconnect() {
    setBusy(true)
    setError('')
    setFeedback('')
    try {
      await api('account', 'DELETE')
      await refresh()
      setAddress('')
      setFeedback('Watch removed. Your wallet and replay history are unaffected.')
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return <div className="workspace-page">
    <section className="panel workspace-panel">
      <header><Eye aria-hidden="true" size={20}/><h2>Watch a public account</h2></header>
      <p>Inspect published open positions using a Polymarket trading wallet address. No signature is required.</p>
      <form onSubmit={watch}>
        <label className="field" htmlFor="wallet-address">Public wallet address</label>
        <div className="watch-input"><input id="wallet-address" type="text" placeholder="0x…" autoCapitalize="none"
          spellCheck={false} autoComplete="off" required pattern="0x[0-9a-fA-F]{40}" maxLength={42}
          title="Enter 0x followed by 40 hexadecimal characters" value={address} disabled={busy}
          onChange={e => setAddress(e.target.value)}/>
          <button className="btn primary" disabled={busy}>{busy ? 'Updating…' : account?.address === address.trim().toLowerCase() ? 'Refresh positions' : 'Watch account'}</button>
        </div>
        <p className="workspace-note">Checking sends this address to the Polymarket Data API. Only one address is watched at a time.</p>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      <span role="status" className="muted">{feedback}</span>
    </section>
    {account && <section className="panel workspace-panel">
      <header><Wallet aria-hidden="true" size={20}/><h2>Position snapshot</h2></header>
      <div className="watch-heading"><code>{account.address}</code><span className="badge">Public read only</span></div>
      <p>{account.message}</p>
      <dl className="workspace-facts"><div><dt>Last check</dt><dd>{timestamp(account.checkedAt)}</dd></div>
        <div><dt>Snapshot retrieved</dt><dd>{timestamp(account.observedAt)}</dd></div>
        <div><dt>Coverage</dt><dd>{account.status === 'unavailable' ? 'Current positions unknown' : account.complete ? 'All returned open positions' : 'Partial page of open positions'}</dd></div>
      </dl>
      {account.positions.length > 0 && <div className="positions-table"><table><caption>Positions in the retained snapshot</caption><thead><tr><th>Market</th><th>Outcome</th><th>Shares</th></tr></thead>
        <tbody>{account.positions.map((position, i) => <tr key={i}><td>{position.market}</td><td>{position.outcome}</td><td>{position.shares}</td></tr>)}</tbody></table></div>}
      <p className="workspace-note">Source: {account.source}. Cash, equity, open orders, signing authority and trading eligibility are unknown.</p>
      <div className="watch-actions"><a className="btn" href={'https://polymarket.com/profile/' + account.address} target="_blank" rel="noreferrer">Provider profile <ArrowUpRight aria-hidden="true" size={15}/></a>
        <button className="btn subtle" disabled={busy} onClick={disconnect}>Remove watch</button></div>
    </section>}
    {!account && <section className="panel workspace-panel"><header><Fingerprint aria-hidden="true" size={20}/><h2>Account scope</h2></header>
      <p>The public watch is independent of the fictional wallet used for replays. Watching an address grants no permission to trade, transfer funds or manage orders.</p></section>}
  </div>
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
      await api('settings', 'PUT', {version: settings.version, revision: settings.revision, theme})
      await refresh()
      setFeedback('Appearance saved.')
    } catch (e) {
      setError(errorText(e))
      await refresh().catch(() => {})
    } finally {
      setBusy(false)
    }
  }
  return <section className="panel workspace-panel">
    <header><Sun size={20} aria-hidden="true"/><h2>Appearance</h2></header>
    <p>Choose the theme for this local workspace. Your selection takes effect immediately and persists across restarts.</p>
    <div className="theme-choices" role="group" aria-label="Workspace theme">{(['light', 'dark'] as const).map(theme => {
      const Icon = theme === 'light' ? Sun : Moon
      return <button key={theme} className="theme-choice" aria-pressed={theme === settings.theme} disabled={busy} onClick={() => choose(theme)}>
        <span className={'theme-preview theme-preview-' + theme}><i/><i/><i/></span>
        <span><Icon size={16} aria-hidden="true"/>{theme === 'light' ? 'Light' : 'Dark'}{theme === settings.theme && <Check size={16} aria-hidden="true"/>}</span>
      </button>
    })}</div>
    <p className="workspace-note">Workspace preference · Revision {settings.revision}</p>
    <span role="status">{feedback}</span>{error && <p role="alert" className="error">{error}</p>}
  </section>
}

export function Status({ workspace }: Props) {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setHealth(null)
    setError('')
    api<Health>('health').then(result => { if (active) setHealth(result) })
      .catch(e => { if (active) setError(errorText(e)) })
    return () => { active = false }
  }, [attempt])
  return <div className="workspace-page">
    <section className="panel workspace-panel">
      <header><Database size={20} aria-hidden="true"/><h2>Runtime health</h2></header>
      <dl className="workspace-facts">
        <div><dt>Local API</dt><dd>{error ? 'Unreachable' : health ? health.status + ' · v' + health.version : 'Checking…'}</dd></div>
        <div><dt>Last public account check</dt><dd>{workspace.account ? workspace.account.status + ' · ' + timestamp(workspace.account.checkedAt) : 'No watched account'}</dd></div>
        <div><dt>Latest replay</dt><dd>{workspace.run?.status ?? 'No run yet'}</dd></div>
      </dl>
      {error && <p role="alert">{error}</p>}
      <button className="btn" onClick={() => setAttempt(value => value + 1)}><RefreshCw size={15} aria-hidden="true"/> Check API</button>
    </section>
    <section className="panel workspace-panel"><header><CircleHelp aria-hidden="true" size={20}/><h2>Project status</h2></header>
      <p>Discovery and shadow runs use fictional scenarios. Replays demonstrate how limits, cost and liquidity affect a simulated wallet. The account watch reads a separate public data source.</p>
      <p>Next proof: observe a real leader fill and the follower’s available book after detection. Live execution and economic performance remain unverified.</p>
    </section>
  </div>
}
