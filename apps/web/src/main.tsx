import {useCallback, useEffect, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Activity, ArrowLeft, ArrowRight, Bookmark, ChartNoAxesCombined, Check, ChevronRight, CircleHelp, Compass, FlaskConical, LayoutGrid, Menu, Monitor, PanelLeftClose, Settings2, ShieldCheck, Wallet, X} from 'lucide-react'
import {api,errorMessage,type Leader,type Workspace} from './api'
import {Compare,Discover,LeaderDetail} from './Discover'
import {Preview,Shadow} from './Shadow'
import {Accounts,Settings,Status} from './Workspace'
import './style.css'

const nav = [
  {id:'discover',name:'Discover',icon:Compass},
  {id:'runs',name:'Shadow runs',icon:FlaskConical},
  {id:'accounts',name:'Accounts',icon:Wallet},
  {id:'settings',name:'Settings',icon:Settings2},
  {id:'status',name:'System status',icon:Activity},
]
function currentRoute() {return location.hash.replace(/^#\/?/,'').split('/').filter(Boolean)}
const savedKey='polysia:shortlist:v1'
function savedIds():string[]{
  try{const ids:unknown=JSON.parse(localStorage.getItem(savedKey)||'[]');return Array.isArray(ids)?[...new Set(ids.filter((id):id is string=>typeof id==='string'))]:[]}catch{return []}
}
function App(){
  const [[page='discover',id],setRoute]=useState(currentRoute)
  const [mobileNav,setMobileNav]=useState(false)
  const [workspace,setWorkspace]=useState<Workspace|null>(null)
  const [leaders,setLeaders]=useState<Leader[]>([])
  const [loading,setLoading]=useState(true)
  const [loadError,setLoadError]=useState('')
  const [saved,setSaved]=useState(savedIds)
  const [storageNotice,setStorageNotice]=useState('')
  const refresh=useCallback(async()=>{const state=await api<Workspace>('workspace');setWorkspace(state);document.documentElement.dataset.theme=state.settings.theme},[])
  const load=useCallback(async()=>{
    setLoadError('');setLoading(true)
    try{const [directory]=await Promise.all([api<{leaders:Leader[]}>('leaders'),refresh()]);setLeaders(directory.leaders)}
    catch(error){setLoadError(errorMessage(error))}finally{setLoading(false)}
  },[refresh])
  useEffect(()=>{void load()},[load])
  useEffect(()=>{
    const onHash=()=>{setRoute(currentRoute());setMobileNav(false)}
    window.addEventListener('hashchange',onHash)
    return ()=>window.removeEventListener('hashchange',onHash)
  },[])
  useEffect(()=>{
    const onEscape=(event:KeyboardEvent)=>{if(event.key==='Escape')setMobileNav(false)}
    window.addEventListener('keydown',onEscape);return ()=>window.removeEventListener('keydown',onEscape)
  },[])
  const leader=leaders.find(l=>l.id===id)
  const inDiscover=['discover','leader','preview','compare'].includes(page)
  const title=({discover:'Leader discovery',runs:'Shadow runs',accounts:'Accounts',settings:'Settings',status:'System status',compare:'Compare leaders',leader:leader?.name||'Leader profile',preview:'Shadow preview'} as Record<string,string>)[page]||'Page unavailable'
  const subtitle=({discover:'Explore trading profiles and test a leader with simulated capital.',runs:'Follow each simulated decision from signal to settlement of the fill.',accounts:'Inspect public wallet positions and read-only connection status.',settings:'Set your preferences for this workspace.',status:'Review this instance and its supported capabilities.',compare:'Compare your shortlist using the same sample period and metric definitions.',leader:'Inspect this sample leader’s history, coverage, and copy context.',preview:'Review the leader, simulated allocation, and execution rules.'} as Record<string,string>)[page]||''
  useEffect(()=>{document.title=title+' · PolySia'},[title])
  useEffect(()=>{
    const key='polysia:discover-scroll'
    function saveScroll(){if(page==='discover')sessionStorage.setItem(key,String(window.scrollY))}
    if(page==='discover'&&!loading){try{window.scrollTo(0,Number(sessionStorage.getItem(key)||0))}catch{/* storage unavailable */}}
    else window.scrollTo(0,0)
    if(page==='discover') document.addEventListener('click',saveScroll,true)
    return ()=>document.removeEventListener('click',saveScroll,true)
  },[page,loading])
  function toggle(id:string){
    const next=saved.includes(id)?saved.filter(i=>i!==id):[...saved,id]
    setSaved(next);try{localStorage.setItem(savedKey,JSON.stringify(next))}catch{setStorageNotice('Browser storage is unavailable. Your shortlist will last for this visit.')}
  }
  const groupName=inDiscover?'Discovery':nav.find(n=>n.id===page)?.name||'Workspace'
  return <div className="shell">
    <a className="skip-link" href="#main" onClick={e=>{e.preventDefault();document.getElementById('main')?.focus()}}>Skip to content</a>
    <aside className={'sidebar'+(mobileNav?' open':'')}>
      <div className="brand-row"><a href="#/discover" className="brand" aria-label="PolySia home"><img src="/polysia.svg" width="36" height="36" alt=""/><strong>PolySia</strong></a><button aria-label="Close navigation" className="icon-btn mobile-only" onClick={()=>setMobileNav(false)}><X size={20}/></button></div>
      <nav aria-label="Workspace navigation">
        <div className="nav-label">Workspace</div>
        {nav.slice(0,3).map(({id,name,icon:Icon})=><a key={id} href={'#/'+id} className={'nav-link'+((inDiscover&&id==='discover')||id===page?' active':'')} aria-current={((inDiscover&&id==='discover')||id===page)?'page':undefined}><Icon size={19}/>{name}</a>)}
        <div className="nav-label tools">Preferences</div>
        {nav.slice(3).map(({id,name,icon:Icon})=><a key={id} href={'#/'+id} className={'nav-link'+(id===page?' active':'')} aria-current={id===page?'page':undefined}><Icon size={18}/>{name}</a>)}
      </nav>
      <div className="side-footer"><div className="instance-icon"><Monitor size={18}/></div><div><strong>Local workspace</strong><small>Self-hosted instance</small></div></div>
    </aside>
    {mobileNav && <button className="nav-scrim" aria-label="Dismiss navigation" onClick={()=>setMobileNav(false)}/>}
    <div className="app-column">
      <header className="topbar"><div className="bread"><button className="mobile-only icon-btn" aria-label="Open navigation" aria-expanded={mobileNav} onClick={()=>setMobileNav(true)}><Menu size={21}/></button><LayoutGrid size={15}/><span>Workspace</span><ChevronRight size={13}/><strong>{groupName}</strong></div>
        <span className="mode-indicator"><span className="dot"/>Shadow workspace</span>
      </header>
      <main id="main" tabIndex={-1}>
        {['leader','compare','preview'].includes(page)&&<a className="back" href={page==='preview'?'#/leader/'+id:'#/discover'}><ArrowLeft size={14}/>{page==='preview'?'Leader profile':'Back to discovery'}</a>}
        <div className="page-head"><div><h1>{title}</h1><p>{subtitle}</p></div>{page==='discover'&&<div className="sample-tag"><FlaskConical size={14}/>Scenario data</div>}</div>
        {storageNotice&&<p role="status" className="notice">{storageNotice}</p>}
        {loading ? <div className="panel empty" role="status">Loading workspace…</div> : loadError || !workspace ? <div className="panel empty" role="alert"><h2>Workspace unavailable</h2><p>{loadError}</p><button className="btn" onClick={load}>Retry connection</button></div> : <>
          <Discover leaders={leaders} saved={saved} toggle={toggle} visible={page==='discover'}/>
          {page==='leader' && leader && <LeaderDetail leader={leader} saved={saved} toggle={toggle}/>}
          {page==='preview' && leader && <Preview key={leader.id} leader={leader} run={workspace.run} refresh={refresh}/>}
          {page==='compare' && <Compare leaders={leaders} saved={saved} toggle={toggle}/>}
          {page==='runs' && <Shadow run={workspace.run} refresh={refresh}/>}
          {page==='accounts' && <Accounts workspace={workspace} refresh={refresh}/>}
          {page==='settings' && <Settings workspace={workspace} refresh={refresh}/>}
          {page==='status' && <Status workspace={workspace} refresh={refresh}/>}
          {((['leader','preview'].includes(page)&&!leader)||(!inDiscover&&!nav.some(n=>n.id===page)))&&<div className="panel empty"><h2>Page unavailable</h2><a href="#/discover" className="btn">Return to discovery <ArrowRight size={16}/></a></div>}
        </>}
      </main>
    </div>
  </div>
}
createRoot(document.getElementById('root')!).render(<App/>)
