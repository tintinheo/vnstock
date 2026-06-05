import { useState, useEffect } from 'react';
import { fetchAudit } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import { Bell, RefreshCw } from 'lucide-react';
export default function Signals() {
  const [logs, setLogs] = useState([]); const [loading, setLoading] = useState(false); const [filters, setFilters] = useState({ticker:'',signal:''});
  const load = async () => { setLoading(true); try { setLogs((await fetchAudit({action_type:'DECISION',limit:200})).data.entries||[]); } catch {} setLoading(false); };
  useEffect(() => { load(); }, []);
  const filtered = logs.filter(l => { if(filters.ticker && !l.ticker?.includes(filters.ticker.toUpperCase())) return false; if(filters.signal && l.signal!==filters.signal) return false; return true; });
  const fmt = v => v ? Number(v).toLocaleString('vi-VN') : '-';
  return (<div className="space-y-6">
    <div className="flex items-center gap-4"><h1 className="text-2xl font-bold flex items-center gap-2"><Bell className="w-7 h-7 text-brand-500"/> Signal History</h1>
      <button onClick={load} className="btn-secondary flex items-center gap-1 text-xs"><RefreshCw className={`w-3 h-3 ${loading?'animate-spin':''}`}/> Refresh</button></div>
    <div className="flex gap-3 text-sm items-center">
      <input value={filters.ticker} onChange={e=>setFilters(p=>({...p,ticker:e.target.value}))} placeholder="Ticker..." className="input-field w-28 py-1 text-xs"/>
      {['','BUY','SELL','HOLD'].map(s=>(<button key={s} onClick={()=>setFilters(p=>({...p,signal:s}))} className={`px-3 py-1 rounded-full text-xs border ${filters.signal===s?'bg-brand-600/20 border-brand-500 text-brand-500':'border-surface-700 text-gray-400'}`}>{s||'All'}</button>))}
      <span className="text-gray-500 ml-auto">{filtered.length} entries</span></div>
    <div className="card overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-xs text-gray-400 border-b border-surface-700">
      <th className="text-left py-2 px-2">Time</th><th className="px-2">Ticker</th><th className="px-2">Signal</th><th className="text-right px-2">Price</th><th className="text-right px-2">RSI</th><th className="text-right px-2">Entry</th><th className="text-right px-2">SL</th><th className="text-right px-2">TP</th><th className="text-right px-2">Shares</th><th className="text-right px-2">Duration</th><th className="px-2">Src</th>
    </tr></thead><tbody>{filtered.map(l => { const s=l.result_summary||{}; return (<tr key={l.id} className="border-b border-surface-700/50 hover:bg-surface-700/30">
      <td className="py-2 px-2 text-xs text-gray-400">{new Date(l.ts).toLocaleString('vi-VN')}</td><td className="px-2 font-bold">{l.ticker}</td>
      <td className="px-2"><SignalBadge action={l.signal} confidence={l.confidence}/></td>
      <td className="text-right px-2 font-mono">{fmt(s.price)}</td><td className="text-right px-2 font-mono">{s.rsi?.toFixed?.(0)}</td>
      <td className="text-right px-2 font-mono text-brand-500">{fmt(s.entry)}</td><td className="text-right px-2 font-mono text-sell">{fmt(s.stop_loss)}</td>
      <td className="text-right px-2 font-mono text-buy">{fmt(s.take_profit)}</td><td className="text-right px-2 font-mono">{s.shares||'-'}</td>
      <td className="text-right px-2 text-xs text-gray-500">{l.duration_ms?.toFixed(0)}ms</td><td className="px-2 text-xs text-gray-500">{l.data_source}</td>
    </tr>);})}</tbody></table></div></div>);
}
