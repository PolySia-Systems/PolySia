import {useId} from 'react'
import {money, type Leader} from './api'

export function Avatar({leader, large = false}: {leader: Leader; large?: boolean}) {
  return <span aria-hidden="true" className={'avatar avatar-' + leader.id + (large ? ' avatar-lg' : '')}>
    <i/><b/><em/>
  </span>
}

/** Plot the supplied observations; the segments between samples are linear. */
export function HistoryChart({leader, compact = false}: {leader: Leader; compact?: boolean}) {
  const id = useId()
  const data = leader.history
  if (data.length < 2) return <span className="muted">History unavailable</span>
  const min = Math.min(...data, 0)
  const max = Math.max(...data, 1)
  const width = compact ? 86 : 480
  const height = compact ? 28 : 130
  const top = compact ? 2 : 8
  const bottom = height - top
  const path = data.map((n, i) => {
    const x = 2 + (width - 4) * i / (data.length - 1)
    const y = bottom - (n - min) / (max - min) * (bottom - top)
    return (i === 0 ? 'M' : 'L') + x.toFixed(2) + ',' + y.toFixed(2)
  }).join(' ')
  if (compact) return <svg className="sparkline" width={width} height={height} viewBox={'0 0 ' + width + ' ' + height} aria-hidden="true">
    <path d={path} stroke="currentColor" fill="none" strokeWidth="1.7" strokeLinejoin="round"/>
  </svg>
  return <div className="large-chart" role="img" aria-label={leader.name + ' illustrative cumulative P/L over 30 days, from ' + money(data[0]) + ' to ' + money(data[data.length - 1])}>
    <div className="chart-plot">
      <div className="axis-values">{[max, (min + max)/2, min].map((n,i) => <span key={i}>{money(n,0)}</span>)}</div>
      <svg preserveAspectRatio="none" viewBox={'0 0 ' + width + ' ' + height} aria-hidden="true">
        <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c2eb8e" stopOpacity=".24"/><stop offset="100%" stopColor="#c2eb8e" stopOpacity=".01"/></linearGradient></defs>
        {[top,(top+bottom)/2,bottom].map(y=><line key={y} x1="0" x2={width} y1={y} y2={y} stroke="currentColor" strokeDasharray="3 5" opacity=".22"/>)}
        <path d={path + ' L' + (width-2) + ',' + bottom + ' L2,' + bottom + ' Z'} fill={'url(#' + id + ')'}/>
        <path d={path} stroke="#c5ee93" fill="none" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke"/>
      </svg>
    </div>
    <div className="axis-days"><span>Day 1</span><span>Day 10</span><span>Day 20</span><span>Day 30</span></div>
  </div>
}
