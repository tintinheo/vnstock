import { useState, useRef } from 'react';
import { fetchDecision } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import RegimeBadge from '../components/RegimeBadge';
import TableFilter, { SortHeader } from '../components/TableFilter';
import { useNavigate } from 'react-router-dom';
import { ScanSearch, Square } from 'lucide-react';
import API from '../api/client';

const COLS = [
  { key: 'ticker', label: 'Ticker', filterType: 'text', accessor: r => r.ticker },
  { key: 'signal', label: 'Signal', filterType: 'select', options: ['BUY','SELL','HOLD','WEAK_BUY','WEAK_SELL'], accessor: r => r.signal?.action },
  { key: 'regime', label: 'Regime', filterType: 'select', options: ['UPTREND','DOWNTREND','SIDEWAY','WEAK_UPTREND'], accessor: r => r.signal?.regime?.regime },
  { key: 'price', label: 'Price', filterType: 'number', accessor: r => r.signal?.indicators?.price },
  { key: 'rsi', label: 'RSI', filterType: 'number', accessor: r => r.signal?.indicators?.rsi },
  { key: 'macd', label: 'MACD', filterType: 'number', accessor: r => r.signal?.indicators?.macd_hist },
  { key: 'vol', label: 'Vol Ratio', filterType: 'number', accessor: r => r.signal?.indicators?.volume_ratio },
  { key: 'conf', label: 'Confidence', filterType: 'number', accessor: r => r.signal?.confidence },
];

export default function Scanner() {
  const [watchlist, setWatchlist] = useState('');
  const [exchanges, setExchanges] = useState({ HOSE: false, HNX: false, UPCOM: false });
  const [results, setResults] = useState([]);
  const [filteredResults, setFilteredResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0, ticker: '' });
  const [capital, setCapital] = useState(500000000);
  const [tickerCounts, setTickerCounts] = useState({});
  const stopRef = useRef(false);
  const navigate = useNavigate();

const toggleExchange = async (ex) => {
    const nv = !exchanges[ex]; setExchanges(p => ({ ...p, [ex]: nv }));
    if (nv && !tickerCounts[ex]) {
      try {
        const res = await API.get(`/tickers/${ex}`);
        setTickerCounts(p => ({ ...p, [ex]: res.data.count }));
      } catch {}
    }
};

  const scan = async () => {
    setLoading(true); stopRef.current = false; setResults([]);
    let tickers = watchlist.split(/[,;\s]+/).map(t => t.trim().toUpperCase()).filter(Boolean);
    for (const ex of ['HOSE','HNX','UPCOM']) if (exchanges[ex]) try { tickers = [...new Set([...tickers, ...(await API.get(`/tickers/${ex}`)).data.tickers])]; } catch {} // eslint-disable-line
    if (!tickers.length) { setLoading(false); return; }
    setProgress({ current: 0, total: tickers.length, ticker: '' });
    const all = [];
    for (let i = 0; i < tickers.length; i += 5) {
      if (stopRef.current) break;
      setProgress({ current: i, total: tickers.length, ticker: tickers.slice(i, i+5).join(', ') });
      const data = (await Promise.all(tickers.slice(i,i+5).map(t => fetchDecision(t, capital).then(r=>r.data).catch(()=>null)))).filter(Boolean);
      all.push(...data); setResults([...all]);
      if (i+5 < tickers.length && !stopRef.current) await new Promise(r => setTimeout(r, 1200));
    }
    setProgress(p => ({...p, current: tickers.length, ticker: 'Done!'})); setLoading(false);
  };
  const fmt = v => v ? Number(v).toLocaleString('vi-VN') : '-';

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><ScanSearch className="w-7 h-7 text-brand-500" /> Stock Scanner</h1>
      <div className="card space-y-4">
        <div><label className="text-xs text-gray-400 mb-1 block">Custom Watchlist</label>
          <textarea value={watchlist} onChange={e => setWatchlist(e.target.value)} className="input-field h-12 resize-none font-mono text-sm" placeholder="FPT, VCB, HPG..." /></div>
        <div className="flex gap-3 flex-wrap">
          {[['HOSE','~400'],['HNX','~200'],['UPCOM','~45']].map(([ex,d]) => (
            <label key={ex} className={`flex items-center gap-2 px-4 py-2 rounded-lg cursor-pointer border ${exchanges[ex]?'bg-brand-600/20 border-brand-500 text-brand-500':'bg-surface-900 border-surface-700 text-gray-400'}`}>
              <input type="checkbox" checked={exchanges[ex]} onChange={() => toggleExchange(ex)} className="hidden" />
              <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${exchanges[ex]?'bg-brand-500 border-brand-500':'border-gray-600'}`}>{exchanges[ex] && <span className="text-white text-xs">✓</span>}</div>
              <div><div className="font-medium">{ex}</div><div className="text-xs opacity-60">{tickerCounts[ex]||d} stocks</div></div>
            </label>))}
          <div className="ml-auto flex items-end gap-2">
            <div><label className="text-xs text-gray-400">Capital</label><input type="number" value={capital} onChange={e=>setCapital(+e.target.value)} className="input-field text-sm w-40" /></div>
            {!loading ? <button onClick={scan} className="btn-primary flex items-center gap-2"><ScanSearch className="w-4 h-4" /> Scan</button>
              : <button onClick={()=>stopRef.current=true} className="bg-sell text-white py-2 px-4 rounded-lg flex items-center gap-2"><Square className="w-4 h-4" /> Stop</button>}
          </div>
        </div>
      </div>
      {loading && progress.total>0 && <div className="card"><div className="flex justify-between text-xs text-gray-400 mb-1"><span>{progress.ticker}</span><span>{progress.current}/{progress.total}</span></div><div className="h-2 bg-surface-900 rounded-full overflow-hidden"><div className="h-full bg-brand-500 rounded-full transition-all" style={{width:`${(progress.current/progress.total)*100}%`}} /></div></div>}
      {results.length > 0 && (
        <div className="card overflow-x-auto">
          <TableFilter columns={COLS} data={results} onFiltered={setFilteredResults}>
            {({ filtered, toggleSort, sortCol, sortDir }) => (
              <table className="w-full text-sm mt-2"><thead><tr className="text-xs text-gray-400 border-b border-surface-700">
                <th className="text-left py-2 px-2">#</th>
                <SortHeader label="Ticker" colKey="ticker" sortCol={sortCol} sortDir={sortDir} onSort={toggleSort} />
                <SortHeader label="Price" colKey="price" sortCol={sortCol} sortDir={sortDir} onSort={toggleSort} />
                <SortHeader label="Signal" colKey="signal" sortCol={sortCol} sortDir={sortDir} onSort={toggleSort} />
                <th className="text-center px-2">Regime</th>
                <SortHeader label="RSI" colKey="rsi" sortCol={sortCol} sortDir={sortDir} onSort={toggleSort} />
                <SortHeader label="MACD" colKey="macd" sortCol={sortCol} sortDir={sortDir} onSort={toggleSort} />
                <SortHeader label="VolR" colKey="vol" sortCol={sortCol} sortDir={sortDir} onSort={toggleSort} />
                <th className="text-right px-2">Entry</th><th className="text-right px-2">SL</th><th className="text-right px-2">TP</th>
                <th className="text-right px-2">Shares</th><th className="text-center px-2">Src</th>
              </tr></thead><tbody>{filteredResults.map((r,i) => {
                const s=r.signal||{}, ind=s.indicators||{}, pt=r.price_targets||{}, ps=r.position_sizing||{};
                return (<tr key={r.ticker} className="border-b border-surface-700/50 hover:bg-surface-700/30 cursor-pointer" onClick={()=>navigate(`/decision/${r.ticker}`)}>
                  <td className="py-2 px-2 text-gray-500 text-xs">{i+1}</td><td className="px-2 font-bold">{r.ticker}</td>
                  <td className="text-right px-2 font-mono">{fmt(ind.price)}</td>
                  <td className="text-center px-2"><SignalBadge action={s.action} confidence={s.confidence} /></td>
                  <td className="text-center px-2"><RegimeBadge regime={s.regime?.regime} /></td>
                  <td className={`text-right px-2 font-mono ${ind.rsi<30?'text-buy':ind.rsi>70?'text-sell':''}`}>{ind.rsi?.toFixed(0)}</td>
                  <td className={`text-right px-2 font-mono ${ind.macd_hist>0?'text-buy':'text-sell'}`}>{ind.macd_hist?.toFixed(0)}</td>
                  <td className="text-right px-2 font-mono">{ind.volume_ratio?.toFixed(1)}x</td>
                  <td className="text-right px-2 font-mono text-brand-500">{fmt(pt.entry_conservative)}</td>
                  <td className="text-right px-2 font-mono text-sell">{fmt(pt.stop_loss)}</td>
                  <td className="text-right px-2 font-mono text-buy">{fmt(pt.take_profit_2)}</td>
                  <td className="text-right px-2 font-mono">{ps.shares?ps.shares.toLocaleString():'-'}</td>
                  <td className="text-center px-2 text-xs text-gray-500">{r.data_source}</td>
                </tr>);})}</tbody></table>)}
          </TableFilter>
        </div>)}
    </div>);
}
