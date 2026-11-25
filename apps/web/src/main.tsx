import { useCallback, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  ChartNoAxesColumnIncreasing,
  Compass,
  FlaskConical,
  LayoutGrid,
  Menu,
  Monitor,
  Settings2,
  Wallet,
  X,
} from 'lucide-react'
import { api, errorMessage, type Directory, type Workspace } from './api'
import { Compare, Discover, LeaderDetail } from './Discover'
import { Preview, SavedReplay, Shadow } from './Shadow'
import { Accounts, Settings, Status } from './Workspace'
import { PublicRankings } from './PublicRankings'
import { PublicRuns } from './PublicRuns'
import './style.css'

const nav = [
  { id: 'discover', name: 'Discover', icon: Compass },
  { id: 'rankings', name: 'Public rankings', icon: ChartNoAxesColumnIncreasing },
  { id: 'paper', name: 'Public shadow', icon: Activity },
  { id: 'runs', name: 'Scenario replays', icon: FlaskConical },
  { id: 'accounts', name: 'Accounts', icon: Wallet },
  { id: 'settings', name: 'Settings', icon: Settings2 },
  { id: 'status', name: 'System status', icon: Activity },
]
function currentRoute() {
  return location.hash.split('?')[0].replace(/^#\/?/, '').split('/').filter(Boolean)
}
const savedKey = 'polysia:shortlist:v1'
function savedIds(): string[] {
  try {
    const ids: unknown = JSON.parse(localStorage.getItem(savedKey) || '[]')
    return Array.isArray(ids)
      ? [...new Set(ids.filter((id): id is string => typeof id === 'string'))]
      : []
  } catch {
    return []
  }
}
function App() {
  const [route, setRoute] = useState(currentRoute)
  const navigationRef = useRef<HTMLElement>(null)
  const menuRef = useRef<HTMLButtonElement>(null)
  const [mobileNav, setMobileNav] = useState(false)
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [directory, setDirectory] = useState<Directory | null>(null)
  const leaders = directory?.leaders ?? []
  const [page = workspace?.run ? 'runs' : 'discover', id] = route
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saved, setSaved] = useState(savedIds)
  const [storageNotice, setStorageNotice] = useState('')
  const refresh = useCallback(async () => {
    const state = await api<Workspace>('workspace')
    setWorkspace(state)
    document.documentElement.dataset.theme = state.settings.theme
  }, [])
  const load = useCallback(async () => {
    setLoadError('')
    setLoading(true)
    try {
      const [directory] = await Promise.all([api<Directory>('leaders'), refresh()])
      setDirectory(directory)
    } catch (error) {
      setLoadError(errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [refresh])
  useEffect(() => {
    void load()
  }, [load])
  useEffect(() => {
    const onHash = () => {
      setRoute(currentRoute())
      setMobileNav(false)
      requestAnimationFrame(() => document.getElementById('main')?.focus({ preventScroll: true }))
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    if (!mobileNav) return
    const nav = navigationRef.current
    const controls = nav?.querySelectorAll<HTMLElement>('a[href],button')
    if (!controls?.length) return
    nav?.querySelector<HTMLElement>('[aria-current="page"]')?.focus()
    const close = () => {
      setMobileNav(false)
      requestAnimationFrame(() => menuRef.current?.focus())
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
      } else if (event.key === 'Tab') {
        const first = controls[0]
        const last = controls[controls.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    const width = matchMedia('(max-width:880px)')
    const onResize = () => {
      if (!width.matches) setMobileNav(false)
    }
    window.addEventListener('keydown', onKey)
    width.addEventListener('change', onResize)
    return () => {
      window.removeEventListener('keydown', onKey)
      width.removeEventListener('change', onResize)
    }
  }, [mobileNav])
  function closeNav() {
    setMobileNav(false)
    requestAnimationFrame(() => menuRef.current?.focus())
  }
  const leader = leaders.find((l) => l.id === id)
  const inDiscover = ['discover', 'leader', 'preview', 'compare'].includes(page)
  const title =
    (
      {
        discover: 'Leader discovery',
        rankings: 'Public rankings',
        paper: id === 'new' ? 'New public run' : id ? 'Public shadow portfolio' : 'Public shadow runs',
        runs: id ? 'Saved replay' : 'Scenario replays',
        accounts: 'Accounts',
        settings: 'Settings',
        status: 'System status',
        compare: 'Compare leaders',
        leader: leader?.name || 'Leader profile',
        preview: 'Shadow preview',
      } as Record<string, string>
    )[page] || 'Page unavailable'
  const subtitle =
    (
      {
        rankings: 'Inspect the traders and positions reported by Polymarket.',
        paper: 'Observe a public leader with simulated cash and keep a record of each decision.',
        discover: 'Explore public trading data or practice a copy with a simulated wallet.',
        runs: 'See how simulated decisions change your cash and open positions.',
        accounts: 'Inspect public wallet positions and read-only connection status.',
        settings: 'Set your preferences for this workspace.',
        status: 'Review this instance and its supported capabilities.',
        compare: 'Compare your shortlist using the same sample period and metric definitions.',
        leader: 'Inspect this sample leader’s history, coverage, and copy context.',
        preview: 'Review the leader, simulated allocation, and execution rules.',
      } as Record<string, string>
    )[page] || ''
  useEffect(() => {
    document.title = title + ' · PolySia'
  }, [title])
  useEffect(() => {
    const key = 'polysia:discover-scroll'
    function saveScroll() {
      try {
        sessionStorage.setItem(key, String(window.scrollY))
      } catch {
        /* Optional scroll restoration. */
      }
    }
    if (page === 'discover' && !loading) {
      try {
        window.scrollTo(0, Number(sessionStorage.getItem(key) || 0))
      } catch {
        /* storage unavailable */
      }
    } else window.scrollTo(0, 0)
    if (page === 'discover') document.addEventListener('click', saveScroll, true)
    return () => document.removeEventListener('click', saveScroll, true)
  }, [page, id, loading])
  function toggle(id: string) {
    const next = saved.includes(id) ? saved.filter((i) => i !== id) : [...saved, id]
    setSaved(next)
    try {
      localStorage.setItem(savedKey, JSON.stringify(next))
    } catch {
      setStorageNotice('Browser storage is unavailable. Your shortlist will last for this visit.')
    }
  }
  const groupName = inDiscover ? 'Discovery' : nav.find((n) => n.id === page)?.name || 'Workspace'
  return (
    <div className="shell">
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault()
          document.getElementById('main')?.focus()
        }}
      >
        Skip to content
      </a>
      <aside
        ref={navigationRef}
        id="workspace-navigation"
        aria-label={mobileNav ? 'Workspace menu' : undefined}
        role={mobileNav ? 'dialog' : undefined}
        aria-modal={mobileNav || undefined}
        onClick={(e) => {
          if (mobileNav && e.target instanceof Element && e.target.closest('a[href]')) {
            setMobileNav(false)
            requestAnimationFrame(() =>
              document.getElementById('main')?.focus({ preventScroll: true }),
            )
          }
        }}
        className={'sidebar' + (mobileNav ? ' open' : '')}
      >
        <div className="brand-row">
          <a href="#/discover" className="brand" aria-label="PolySia home">
            <img src="/polysia.svg" width="36" height="36" alt="" />
            <strong>PolySia</strong>
          </a>
          <button aria-label="Close navigation" className="icon-btn mobile-only" onClick={closeNav}>
            <X size={20} />
          </button>
        </div>
        <nav aria-label="Workspace navigation">
          <div className="nav-label">Workspace</div>
          {nav.slice(0, 5).map(({ id, name, icon: Icon }) => (
            <a
              key={id}
              href={'#/' + id}
              className={
                'nav-link' + ((inDiscover && id === 'discover') || id === page ? ' active' : '')
              }
              aria-current={(inDiscover && id === 'discover') || id === page ? 'page' : undefined}
            >
              <Icon size={19} />
              {name}
            </a>
          ))}
          <div className="nav-label tools">Preferences</div>
          {nav.slice(5).map(({ id, name, icon: Icon }) => (
            <a
              key={id}
              href={'#/' + id}
              className={'nav-link' + (id === page ? ' active' : '')}
              aria-current={id === page ? 'page' : undefined}
            >
              <Icon size={18} />
              {name}
            </a>
          ))}
        </nav>
        <div className="side-footer">
          <div className="instance-icon">
            <Monitor size={18} />
          </div>
          <div>
            <strong>Local workspace</strong>
            <small>Self-hosted instance</small>
          </div>
        </div>
      </aside>
      {mobileNav && (
        <button
          tabIndex={-1}
          className="nav-scrim"
          aria-label="Dismiss navigation"
          onClick={closeNav}
        />
      )}
      <div className="app-column" inert={mobileNav}>
        <header className="topbar">
          <div className="bread">
            <button
              ref={menuRef}
              aria-controls="workspace-navigation"
              className="mobile-only icon-btn"
              aria-label="Open navigation"
              aria-expanded={mobileNav}
              onClick={() => setMobileNav(true)}
            >
              <Menu size={21} />
            </button>
            <LayoutGrid size={15} />
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{groupName}</strong>
          </div>
          <span className="mode-indicator">
            <span className="dot" />
            {['rankings', 'accounts'].includes(page)
              ? 'Read-only data'
              : ['discover', 'settings', 'status'].includes(page)
                ? 'Local workspace'
                : 'Shadow workspace'}
          </span>
        </header>
        <main id="main" tabIndex={-1}>
          {['leader', 'compare', 'preview'].includes(page) && (
            <a className="back" href={page === 'preview' ? '#/leader/' + id : '#/discover'}>
              <ArrowLeft size={14} />
              {page === 'preview' ? 'Leader profile' : 'Back to discovery'}
            </a>
          )}
          <div className="page-head">
            <div>
              <h1>{title}</h1>
              <p>{subtitle}</p>
            </div>
          </div>
          {storageNotice && (
            <p role="status" className="notice">
              {storageNotice}
            </p>
          )}
          {loading ? (
            <div className="panel empty" role="status">
              Loading workspace…
            </div>
          ) : loadError || !workspace || !directory ? (
            <div className="panel empty" role="alert">
              <h2>Workspace unavailable</h2>
              <p>{loadError}</p>
              <button className="btn" onClick={load}>
                Retry connection
              </button>
            </div>
          ) : (
            <>
              <Discover
                limits={directory.limits}
                leaders={leaders}
                saved={saved}
                toggle={toggle}
                visible={page === 'discover'}
              />
              {page === 'leader' && leader && (
                <LeaderDetail leader={leader} saved={saved} toggle={toggle} />
              )}
              {page === 'preview' && leader && (
                <Preview
                  key={location.hash}
                  policy={directory.policy}
                  limits={directory.limits}
                  leader={leader}
                  run={workspace.run}
                  refresh={refresh}
                />
              )}
              {page === 'compare' && <Compare leaders={leaders} saved={saved} toggle={toggle} />}
              {page === 'runs' &&
                (id ? (
                  <SavedReplay key={id} id={id} />
                ) : (
                  <Shadow run={workspace.run} refresh={refresh} />
                ))}
              {page === 'rankings' && <PublicRankings />}
              {page === 'paper' && <PublicRuns key={location.hash} id={id}/>}
              {page === 'accounts' && (
                <Accounts
                  key={id}
                  initialAddress={/^0x[0-9a-f]{40}$/i.test(id ?? '') ? id : undefined}
                  workspace={workspace}
                  refresh={refresh}
                />
              )}
              {page === 'settings' && <Settings workspace={workspace} refresh={refresh} />}
              {page === 'status' && <Status workspace={workspace} refresh={refresh} />}
              {((['leader', 'preview'].includes(page) && !leader) ||
                (!inDiscover && !nav.some((n) => n.id === page))) && (
                <div className="panel empty">
                  <h2>Page unavailable</h2>
                  <a href="#/discover" className="btn">
                    Return to discovery <ArrowRight size={16} />
                  </a>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
createRoot(document.getElementById('root')!).render(<App />)
