import { useState, useEffect } from 'react';
import { fetchAudit, fetchAuditStats } from '../api/client';
import { FileText, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
export default function AuditLog() {
  const [logs, setLogs] = useState([]); const [stats, setStats] = useState(null); const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({action_type:'',ticker:'',status:''}); const [expanded, setExpanded] = useState({});
  const load = async () => { setLoading(true); try { const [lr,sr] = await Promise.all([fetchAudit({...filters,limit:300}),fetchAuditStats(7)]); setLogs(lr.data.entries||[]); setStats(sr.data); } catch {} setLoading(false); };
  useEffect(() => { load(); }, []);
  return (<div className="space-y-6">
    <div className="flex items-center gap-4"><h1 className="text-2xl font-bold flex items-center gap-2"><FileText className="w-7 h-7 text-brand-500"/> Audit Log</h1>
      <button onClick={load} className="btn-secondary flex items-center gap-1 text-xs"><RefreshCw className={`w-3 h-3 ${loading?'animate-spin':''}`}/> Refresh</button></div>
    {stats && <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      <div className="card"><div className="text-xs text-gray-400">Total (7d)</div><div className="text-xl font-bold">{stats.total}</div></div>
      <div className="card"><div className="text-xs text-gray-400">Success Rate</div><div className="text-xl font-bold text-buy">{stats.success_rate}%</div></div>
      <div className="card"><div className="text-xs text-gray-400">Avg Duration</div><div className="text-xl font-bold">{stats.avg_duration_ms?.toFixed(0)}ms</div></div>
      <div className="card"><div className="text-xs text-gray-400">Success</div><div className="text-xl font-bold text-buy">{stats.success}</div></div>
      <div className="card"><div className="text-xs text-gray-400">Errors</div><div className="text-xl font-bold text-sell">{stats.error}</div></div>
    </div>}
    <div className="flex gap-3 text-sm">
      <input value={filters.ticker} onChange={e=>setFilters(p=>({...p,ticker:e.target.value}))} placeholder="Ticker..." className="input-field w-28 py-1 text-xs"/>
      <select value={filters.action_type} onChange={e=>setFilters(p=>({...p,action_type:e.target.value}))} className="input-field w-32 py-1 text-xs"><option value="">All Actions</option>{['DECISION','SIGNAL','BACKTEST','DATA'].map(a=><option key={a} value={a}>{a}</option>)}</select>
      <select value={filters.status} onChange={e=>setFilters(p=>({...p,status:e.target.value}))} className="input-field w-28 py-1 text-xs"><option value="">All</option><option value="SUCCESS">SUCCESS</option><option value="ERROR">ERROR</option></select>
      <button onClick={load} className="btn-primary text-xs py-1">Apply</button>
      <span className="text-gray-500 ml-auto">{logs.length} entries</span></div>
    <div className="card overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-xs text-gray-400 border-b border-surface-700">
      <th className="w-6"></th><th className="text-left py-2 px-2">Time</th><th className="px-2">Action</th><th className="px-2">Ticker</th><th className="px-2">Signal</th><th className="text-right px-2">Duration</th><th className="px-2">Status</th><th className="px-2">Source</th>
    </tr></thead><tbody>{logs.map(l=>(<>
      <tr key={l.id} className="border-b border-surface-700/50 hover:bg-surface-700/30 cursor-pointer" onClick={()=>setExpanded(p=>({...p,[l.id]:!p[l.id]}))}>
        <td className="px-1">{expanded[l.id]?<ChevronDown className="w-3 h-3 text-gray-500"/>:<ChevronRight className="w-3 h-3 text-gray-500"/>}</td>
        <td className="py-2 px-2 text-xs text-gray-400">{new Date(l.ts).toLocaleString('vi-VN')}</td>
        <td className="px-2"><span className="px-2 py-0.5 rounded text-xs bg-surface-700">{l.action}</span></td>
        <td className="px-2 font-bold">{l.ticker}</td>
        <td className="px-2 text-xs">{l.signal && <span className={l.signal.includes('BUY')?'text-buy':l.signal.includes('SELL')?'text-sell':'text-hold'}>{l.signal}</span>}</td>
        <td className="text-right px-2 font-mono text-xs">{l.duration_ms?.toFixed(0)}ms</td>
        <td className="px-2"><span className={`text-xs ${l.status==='SUCCESS'?'text-buy':'text-sell'}`}>{l.status}</span></td>
        <td className="px-2 text-xs text-gray-500">{l.data_source}</td></tr>
      {expanded[l.id] && <tr key={l.id+'d'}><td colSpan={8} className="px-4 py-3 bg-surface-900"><pre className="text-xs text-gray-400 overflow-auto max-h-60">{JSON.stringify(l,null,2)}</pre></td></tr>}
    </>))}</tbody></table></div></div>);
}
