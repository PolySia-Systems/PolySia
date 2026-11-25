import { useMemo, useState } from 'react'
import {
  ArrowDownWideNarrow,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Check,
  ChevronDown,
  ChevronRight,
  Compass,
  Layers3,
  Search,
  Sparkles,
  TrendingUp,
  UsersRound,
  X,
} from 'lucide-react'
import { money, signed, type Leader, type ScenarioLimits } from './api'
import { BudgetFinder } from './BudgetFinder'
import { Avatar, HistoryChart } from './charts'

export interface Picks {
  saved: string[]
  toggle: (id: string) => void
}
interface DiscoveryProps extends Picks {
  leaders: Leader[]
  visible: boolean
  limits: ScenarioLimits
}
function ShortlistButton({ leader, saved, toggle }: { leader: Leader } & Picks) {
  const on = saved.includes(leader.id)
  return (
    <button
      className={'icon-btn save' + (on ? ' on' : '')}
      aria-pressed={on}
      aria-label={
        (on ? 'Remove ' : 'Save ') + leader.name + (on ? ' from shortlist' : ' to shortlist')
      }
      onClick={() => toggle(leader.id)}
      title={on ? 'Remove from shortlist' : 'Save to shortlist'}
    >
      <Bookmark size={17} fill={on ? 'currentColor' : 'none'} />
    </button>
  )
}
export function LeaderSpotlight({ leader, detail = false }: { leader: Leader; detail?: boolean }) {
  return (
    <section className="spotlight" aria-label="Example leader history">
      <div className="spot-copy">
        <div className="spot-label">
          <Sparkles size={14} />
          {detail ? 'Performance history' : 'Example profile'}
        </div>
        {!detail && <h2>{leader.name}</h2>}
        <span className="spot-profit">{signed(leader.pnl)}</span>
        <span className="spot-definition">
          Leader P/L <span>·</span> Fictional 30-day history
        </span>
        {!detail && (
          <a href={'#/leader/' + leader.id} className="spot-link">
            View profile <ArrowUpRight size={15} />
          </a>
        )}
      </div>
      <div className="spot-graph">
        <div className="chart-key">
          <i />
          Cumulative leader P/L
        </div>
        <HistoryChart leader={leader} />
      </div>
    </section>
  )
}

export function Discover({ leaders, saved, toggle, visible, limits }: DiscoveryProps) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<'pnl' | 'volume' | 'win_rate'>('pnl')
  const [tab, setTab] = useState<'all' | 'saved'>('all')
  const ranked = useMemo(
    () =>
      [...leaders].sort(
        (a, b) => Number(b[sort]) - Number(a[sort]) || a.name.localeCompare(b.name),
      ),
    [leaders, sort],
  )
  const rows = ranked.filter(
    (leader) =>
      (tab === 'all' || saved.includes(leader.id)) &&
      (!category || leader.category === category) &&
      [leader.name, leader.handle, leader.category]
        .join(' ')
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  )
  const spotlight = leaders.find((leader) => leader.id === 'atlas') || leaders[0]
  return (
    <div hidden={!visible} className="discover stack">
      {spotlight && <LeaderSpotlight leader={spotlight} />}
      <BudgetFinder limits={limits} />
      <section className="directory panel">
        <div className="directory-head">
          <div className="section-title">
            <div className="section-glyph">
              <UsersRound size={18} />
            </div>
            <h2>Leader directory</h2>
          </div>
          <span className="period">
            <span className="dot" />
            30-day sample
          </span>
        </div>
        <div className="tabs-row">
          <div className="tabs">
            <button
              className={tab === 'all' ? 'selected' : ''}
              aria-pressed={tab === 'all'}
              onClick={() => setTab('all')}
            >
              All leaders <b>{leaders.length}</b>
            </button>
            <button
              className={tab === 'saved' ? 'selected' : ''}
              aria-pressed={tab === 'saved'}
              onClick={() => setTab('saved')}
            >
              <Bookmark size={14} />
              Shortlist <b>{saved.length}</b>
            </button>
          </div>
          {saved.length >= 2 && (
            <a href="#/compare" className="text-link">
              Compare <ArrowRight size={14} />
            </a>
          )}
        </div>
        <div className="directory-tools">
          <label className="search">
            <Search size={16} />
            <input
              type="search"
              placeholder="Search leaders…"
              aria-label="Search leaders"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className="select-field">
            <Layers3 size={15} />
            <select
              aria-label="Filter category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All categories</option>
              {[...new Set(leaders.map((l) => l.category))].sort().map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <ChevronDown size={13} />
          </div>
          <div className="select-field">
            <ArrowDownWideNarrow size={15} />
            <select
              aria-label="Sort leaders"
              value={sort}
              onChange={(e) => setSort(e.target.value as typeof sort)}
            >
              <option value="pnl">P/L: highest first</option>
              <option value="volume">Volume: highest first</option>
              <option value="win_rate">Win rate: highest first</option>
            </select>
            <ChevronDown size={13} />
          </div>
        </div>
        {rows.length > 0 ? (
          <div className="directory-scroll">
            <table className="leader-table">
              <thead>
                <tr>
                  <th scope="col" className="rank-col">
                    #
                  </th>
                  <th scope="col">Leader</th>
                  <th scope="col" className="pnl-col">
                    Leader P/L
                  </th>
                  <th scope="col" className="history-col">
                    P/L trend
                  </th>
                  <th scope="col" className="win-col">
                    Win rate
                  </th>
                  <th scope="col" className="volume-col">
                    Volume
                  </th>
                  <th scope="col">
                    <span className="sr-only">Shortlist</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((leader) => (
                  <tr key={leader.id}>
                    <td className="rank-col mono">
                      {String(ranked.indexOf(leader) + 1).padStart(2, '0')}
                    </td>
                    <td>
                      <a className="identity" href={'#/leader/' + leader.id}>
                        <Avatar leader={leader} />
                        <span>
                          <strong>{leader.name}</strong>
                          <small>{leader.category}</small>
                        </span>
                      </a>
                    </td>
                    <td className="pnl-col">
                      <strong className={Number(leader.pnl) >= 0 ? 'positive' : 'negative'}>
                        {signed(leader.pnl)}
                      </strong>
                    </td>
                    <td className="history-col">
                      <HistoryChart leader={leader} compact />
                    </td>
                    <td className="win-col">{leader.win_rate}%</td>
                    <td className="volume-col">{money(leader.volume, 0)}</td>
                    <td className="save-cell">
                      <ShortlistButton leader={leader} saved={saved} toggle={toggle} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">
            <div className="section-glyph">
              <Search size={24} />
            </div>
            <h3>
              {tab === 'saved' && !saved.length ? 'Your shortlist is empty' : 'No matching leaders'}
            </h3>
            <p>
              {tab === 'saved' && !saved.length
                ? 'Save a leader using the bookmark in the directory.'
                : 'Try a different name or category.'}
            </p>
            <button
              className="btn"
              onClick={() => {
                setQuery('')
                setCategory('')
                setTab('all')
              }}
            >
              Show all leaders
            </button>
          </div>
        )}
        <footer className="directory-footer">
          <span>
            {rows.length} of {leaders.length} sample leaders
          </span>
          <span>Rank reflects the selected sample metric</span>
        </footer>
      </section>
    </div>
  )
}

export function LeaderDetail({ leader, saved, toggle }: { leader: Leader } & Picks) {
  return (
    <div className="stack">
      <section className="profile-head panel">
        <div className="identity">
          <Avatar leader={leader} large />
          <div>
            <span className="badge">{leader.category}</span>
            <p>{leader.description}</p>
          </div>
        </div>
        <div className="actions">
          <ShortlistButton leader={leader} saved={saved} toggle={toggle} />
          <a className="btn primary" href={'#/preview/' + leader.id}>
            Preview shadow <ArrowRight size={16} />
          </a>
        </div>
      </section>
      <LeaderSpotlight leader={leader} detail />
      <div className="stat-grid">
        <div className="stat">
          <span>Matched volume</span>
          <strong>{money(leader.volume, 0)}</strong>
        </div>
        <div className="stat">
          <span>Resolved win rate</span>
          <strong>{leader.win_rate}%</strong>
        </div>
        <div className="stat">
          <span>Markets</span>
          <strong>{leader.markets}</strong>
        </div>
      </div>
      <section className="panel panel-body">
        <div className="section-title">
          <div className="section-glyph">
            <Compass size={18} />
          </div>
          <h2>Copy context</h2>
        </div>
        <dl className="facts">
          <div>
            <dt>Scenario market</dt>
            <dd>{leader.market}</dd>
          </div>
          <div>
            <dt>Evidence</dt>
            <dd>
              Synthetic 30-day leader history. Win rate counts resolved markets. Volume sums matched
              notional.
            </dd>
          </div>
          <div>
            <dt>Follower outcome</dt>
            <dd>
              Your shadow run uses a separate simulated balance and a delayed book. The leader’s
              history does not estimate your return.
            </dd>
          </div>
        </dl>
      </section>
    </div>
  )
}

export function Compare({ leaders, saved, toggle }: { leaders: Leader[] } & Picks) {
  const selected = leaders.filter((l) => saved.includes(l.id))
  return (
    <div className="stack">
      <section className="panel panel-body">
        <div className="section-title">
          <div className="section-glyph">
            <TrendingUp size={18} />
          </div>
          <h2>Shortlisted leaders</h2>
        </div>
        <p className="muted">
          Illustrative leader results over the same 30 days. Position overlap is unavailable in this
          sample.
        </p>
        <div className="comparison">
          {selected.map((l) => (
            <article className="compare-card" key={l.id}>
              <div className="identity">
                <Avatar leader={l} />
                <strong>{l.name}</strong>
                <button
                  className="icon-btn"
                  aria-label={'Remove ' + l.name + ' from shortlist'}
                  onClick={() => toggle(l.id)}
                >
                  <X size={15} />
                </button>
              </div>
              <dl className="facts">
                <div>
                  <dt>Category</dt>
                  <dd>{l.category}</dd>
                </div>
                <div>
                  <dt>Leader P/L</dt>
                  <dd>{signed(l.pnl)}</dd>
                </div>
                <div>
                  <dt>Volume</dt>
                  <dd>{money(l.volume, 0)}</dd>
                </div>
                <div>
                  <dt>Resolved win rate</dt>
                  <dd>{l.win_rate}%</dd>
                </div>
                <div>
                  <dt>Markets</dt>
                  <dd>{l.markets}</dd>
                </div>
              </dl>
              <a className="text-link" href={'#/leader/' + l.id}>
                View profile <ChevronRight size={14} />
              </a>
            </article>
          ))}
        </div>
        {!selected.length && (
          <p className="notice">
            <Check size={16} />
            Your shortlist is empty. <a href="#/discover">Browse leaders</a>
          </p>
        )}
      </section>
    </div>
  )
}
