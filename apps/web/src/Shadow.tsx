import {useState, type FormEvent} from 'react'
import {Activity, ArrowRight, CirclePause, CirclePlay, Download, FlaskConical, History, Layers3, Square, StepForward} from 'lucide-react'
import {api, errorMessage, money, signed, type Leader, type Run} from './api'
import {Avatar} from './charts'
import RunHistory from './RunHistory'
type Props = {run:Run|null; refresh:()=>Promise<void>}
export function Preview({leader,run,refresh}:Props & {leader:Leader}){
  const [capital,setCapital]=useState('100.00')
  const [order,setOrder]=useState('10.00')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const active=run?.status==='running'||run?.status==='paused'
  async function start(e:FormEvent){
    e.preventDefault()
    if(busy) return
    setBusy(true);setError('')
    try {
      await api<Run>('runs','POST',{leaderId:leader.id,allocation:capital,orderSize:order})
      await refresh()
      location.hash='/runs'
    }catch(err){setError(errorMessage(err))}
    finally{setBusy(false)}
  }
  return <div className="setup-layout"><form className="panel panel-body stack" onSubmit={start}>
    <div className="section-title"><div className="section-glyph"><FlaskConical size={18}/></div><h2>Shadow configuration</h2></div>
    <div className="preview-identity"><div className="identity"><Avatar leader={leader}/><span><strong>{leader.name}</strong><small>{leader.category} · Scenario leader</small></span></div><span className="badge">Shadow</span></div>
    <p className="muted">Follower account: isolated simulation balance. Starting a run opens the scenario at its first eligible signal.</p>
    <div className="form-grid"><label className="field">Allocation (USD)<input required type="number" inputMode="decimal" min="1" max="10000" step=".01" value={capital} onChange={e=>setCapital(e.target.value)}/><small>Total simulated cash</small></label>
      <label className="field">Per-order cap (USD)<input required type="number" inputMode="decimal" min="1" max={Math.min(Number(capital)||1000,1000)} step=".01" value={order} onChange={e=>setOrder(e.target.value)}/><small>Includes the modeled fee</small></label></div>
    <p className="notice">Stopping ends new decisions. Existing simulated shares stay in the run.</p>
    {active && <p className="notice">A shadow run is active. Finish or stop it before starting another. <a href="#/runs">Open run</a></p>}
    {error && <p role="alert" className="error">{error}</p>}
    <button className="btn primary" disabled={active || busy}>{busy?'Starting…':'Start shadow'}<ArrowRight size={16}/></button>
  </form><section className="panel panel-body"><div className="section-title"><div className="section-glyph"><Layers3 size={18}/></div><h2>Execution policy</h2></div><dl className="facts">
    <div><dt>Market</dt><dd>{leader.market} · Yes</dd></div><div><dt>Decision delay</dt><dd>2 seconds after observation</dd></div><div><dt>Price tolerance</dt><dd>3¢ from the leader’s fill</dd></div>
    <div><dt>Modeled fee</dt><dd>1% of matched notional, rounded up to cents</dd></div><div><dt>Entry & exit</dt><dd>Whole shares. Skip signals older than 10 seconds and missing quotes. Partial fills expire; eligible sales reduce attributed shares proportionally.</dd></div>
  </dl></section></div>
}
export function Shadow({run,refresh}:Props){
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  async function act(action:string){
    if(!run||busy)return
    setBusy(true);setError('')
    try{await api('runs/'+encodeURIComponent(run.id)+'/'+action,'POST',{revision:run.revision});await refresh()}
    catch(err){setError(errorMessage(err));await refresh().catch(()=>undefined)}finally{setBusy(false)}
  }
  const active=run?.status==='running'||run?.status==='paused'
  return <div className="stack">{!run ? <section className="panel empty"><div className="section-glyph"><FlaskConical size={24}/></div><h2>No shadow runs yet</h2><p>Choose a sample leader to replay a copy with simulated cash.</p><a href="#/discover" className="btn primary">Discover leaders <ArrowRight size={16}/></a></section> : <>
    <section className="panel panel-body stack"><div className="panel-head"><div className="section-title"><div className="section-glyph"><FlaskConical size={19}/></div><h2>{run.leader_name}</h2></div><span className="badge">{run.status}</span></div>
      <div><strong>{run.market}</strong><p className="muted">Yes shares · Scenario follower · {money(run.capital)} allocation · {money(run.order_size)} per entry</p></div>
      <div className="stat-grid"><div className="stat"><span>Available cash</span><strong>{money(run.cash)}</strong></div><div className="stat"><span>Open exposure</span><strong>{run.quantity} shares</strong></div><div className="stat"><span>Realized P/L</span><strong>{signed(run.realized_pnl,2)}</strong></div></div>
      <details className="more-details"><summary>Valuation and costs</summary><dl className="facts"><div><dt>Remaining cost basis</dt><dd>{money(run.cost_basis)}</dd></div><div><dt>Midpoint estimate</dt><dd>{run.marked_value===null?'Unavailable':money(run.marked_value)}</dd></div>
        <div><dt>Full-size sale estimate, net of fees</dt><dd>{run.liquidation_value===null?'Unavailable':money(run.liquidation_value)}</dd></div><div><dt>Fees incurred</dt><dd>{money(run.fees)}</dd></div></dl></details>
      <div className="notice">{run.status==='paused'?'New entries paused. Eligible sales can still reduce exposure when you advance.':active?'Waiting for the next scenario signal. Advance the scenario to evaluate it.':'The run has ended. Remaining shares stay open in this simulation.'}</div>
      {active && <><div className="actions"><button disabled={busy} className="btn primary" onClick={()=>act('step')}><StepForward size={16}/>Observe next signal</button>
        <button disabled={busy} className="btn" onClick={()=>act(run.status==='paused'?'resume':'pause')}>{run.status==='paused'?<CirclePlay size={16}/>:<CirclePause size={16}/>} {run.status==='paused'?'Resume entries':'Pause new entries'}</button>
        <button disabled={busy} className="btn" onClick={()=>act('stop')}><Square size={13}/>Stop run</button></div><small className="muted">Stop run ends all future decisions and retains any remaining shares.</small></>}
      {!active && <a href="#/discover" className="btn primary">Choose another leader <ArrowRight size={16}/></a>}
      {error && <p role="alert" className="error">{error}</p>}
    </section>
    <section className="panel panel-body"><div className="panel-head"><div className="section-title"><div className="section-glyph"><Activity size={18}/></div><h2>Signal activity</h2></div><span className="badge">{run.cursor} / {run.total_steps}</span></div>
      {run.events.length===0?<p className="muted">No observations yet. The replay begins with the next eligible source order.</p>:
      <ol className="event-list">{[...run.events].reverse().map(event=><li key={event.id}><span className="event-icon"><History size={16}/></span><div><strong>{event.side} · {event.status}</strong><p>{event.reason}</p><small>{event.quantity} shares · {money(event.filled)} matched · {money(event.fee)} fee · {new Date(event.decided_at).toLocaleTimeString('en-GB',{timeZone:'UTC'})} UTC (scenario)</small></div></li>)}</ol>}
      <a className="text-link" href={'/api/v1/runs/'+encodeURIComponent(run.id)} download={'shadow-'+run.id+'.json'}><Download size={14}/>Export run evidence</a>
    </section>
    </>}
    <RunHistory refreshKey={run ? run.id+'-'+run.revision : ''}/>
  </div>
}
