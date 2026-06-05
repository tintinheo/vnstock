import { useState, useEffect } from 'react';
import { fetchDecision } from '../api/client';
import StockCard from '../components/StockCard';
import { TrendingUp, TrendingDown, Activity, BarChart3, Filter } from 'lucide-react';
import API from '../api/client';
export default function Dashboard() {
  const [results, setResults] = useState([]); const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({current:0,total:0}); const [filter, setFilter] = useState({signal:'',search:''});
  useEffect(() => { (async () => { setLoading(true);
    let tickers = []; try { tickers = (await API.get('/tickers/HOSE')).data.tickers.slice(0,30); } catch { tickers = ['FPT','VCB','HPG','MBB','TCB','VNM','VHM','SSI','ACB','STB','MWG','PNJ','REE','GVR','VRE','TPB','CTG','BID','SAB','PLX','GAS','POW','VJC','HDB','SHB','EIB','KDH','DGC','MSN','VIC']; }
    setProgress({current:0,total:tickers.length}); const all = [];
    for (let i=0;i<tickers.length;i+=5) { const data=(await Promise.all(tickers.slice(i,i+5).map(t=>fetchDecision(t).then(r=>r.data).catch(()=>null)))).filter(Boolean); all.push(...data); setResults([...all]); setProgress({current:Math.min(i+5,tickers.length),total:tickers.length}); if(i+5<tickers.length) await new Promise(r=>setTimeout(r,1200)); }
    setLoading(false);})(); }, []);
  const filtered = results.filter(r => { if(filter.signal && !r.signal?.action?.includes(filter.signal)) return false; if(filter.search && !r.ticker?.includes(filter.search.toUpperCase())) return false; return true; });
  const buys=filtered.filter(r=>r.signal?.action?.includes('BUY')), sells=filtered.filter(r=>r.signal?.action?.includes('SELL'));
  return (<div className="space-y-6"><h1 className="text-2xl font-bold">Dashboard</h1>
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="card flex items-center gap-3"><div className="p-2 bg-brand-600/20 rounded-lg"><Activity className="w-5 h-5 text-brand-500"/></div><div><div className="text-xs text-gray-400">Scanned</div><div className="text-xl font-bold">{filtered.length}</div></div></div>
      <div className="card flex items-center gap-3"><div className="p-2 bg-buy/20 rounded-lg"><TrendingUp className="w-5 h-5 text-buy"/></div><div><div className="text-xs text-gray-400">BUY</div><div className="text-xl font-bold text-buy">{buys.length}</div></div></div>
      <div className="card flex items-center gap-3"><div className="p-2 bg-sell/20 rounded-lg"><TrendingDown className="w-5 h-5 text-sell"/></div><div><div className="text-xs text-gray-400">SELL</div><div className="text-xl font-bold text-sell">{sells.length}</div></div></div>
      <div className="card flex items-center gap-3"><div className="p-2 bg-hold/20 rounded-lg"><BarChart3 className="w-5 h-5 text-hold"/></div><div><div className="text-xs text-gray-400">HOLD</div><div className="text-xl font-bold text-hold">{filtered.length-buys.length-sells.length}</div></div></div>
    </div>
    <div className="flex items-center gap-3 text-sm"><Filter className="w-4 h-4 text-gray-500"/>
      <input value={filter.search} onChange={e=>setFilter(p=>({...p,search:e.target.value}))} placeholder="Search ticker..." className="input-field w-32 py-1 text-xs"/>
      {['','BUY','SELL','HOLD'].map(s=>(<button key={s} onClick={()=>setFilter(p=>({...p,signal:s}))} className={`px-3 py-1 rounded-full text-xs border ${filter.signal===s?'bg-brand-600/20 border-brand-500 text-brand-500':'border-surface-700 text-gray-400'}`}>{s||'All'}</button>))}
    </div>
    {loading && <div className="card"><div className="flex justify-between text-xs text-gray-400 mb-1"><span>Loading...</span><span>{progress.current}/{progress.total}</span></div><div className="h-2 bg-surface-900 rounded-full overflow-hidden"><div className="h-full bg-brand-500 rounded-full transition-all" style={{width:`${progress.total>0?(progress.current/progress.total)*100:0}%`}}/></div></div>}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">{filtered.map(r=><StockCard key={r.ticker} result={r}/>)}</div>
  </div>);
}
