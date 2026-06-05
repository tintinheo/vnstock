import { useState, useRef } from 'react';
import { fetchDecision } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import RegimeBadge from '../components/RegimeBadge';
import { useNavigate } from 'react-router-dom';
import { ScanSearch, Square } from 'lucide-react';
import API from '../api/client';

export default function Scanner() {
  const [watchlist, setWatchlist] = useState('');
  const [exchanges, setExchanges] = useState({ HOSE: false, HNX: false, UPCOM: false });
  const [filters, setFilters] = useState({ rsiMin: 0, rsiMax: 100, volMin: 0 });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0, ticker: '' });
  const [capital, setCapital] = useState(500000000);
  const [tickerCounts, setTickerCounts] = useState({});
  const stopRef = useRef(false);
  const navigate = useNavigate();

  const toggleExchange = async (ex) => {
    const newVal = !exchanges[ex];
    setExchanges(p => ({ ...p, [ex]: newVal }));
    if (newVal && !tickerCounts[ex]) {
      try {
        const r = await API.get(`/tickers/${ex}`);
        setTickerCounts(p => ({ ...p, [ex]: r.data.count }));
      } catch (e) { console.warn('Failed to fetch', ex, e); }
    }
  };

  const scan = async () => {
    setLoading(true);
    stopRef.current = false;
    setResults([]);

    let tickers = watchlist.split(/[,;\s]+/).map(t => t.trim().toUpperCase()).filter(Boolean);

    for (const ex of ['HOSE', 'HNX', 'UPCOM']) {
      if (exchanges[ex]) {
        try {
          const r = await API.get(`/tickers/${ex}`);
          tickers = [...new Set([...tickers, ...r.data.tickers])];
        } catch (e) { console.warn('Failed to fetch', ex, 'tickers', e); }
      }
    }

    if (tickers.length === 0) { setLoading(false); return; }
    setProgress({ current: 0, total: tickers.length, ticker: '' });

    const BATCH = 5;
    const allResults = [];

    for (let i = 0; i < tickers.length; i += BATCH) {
      if (stopRef.current) break;
      const batch = tickers.slice(i, i + BATCH);
      setProgress({ current: i, total: tickers.length, ticker: batch.join(', ') });

      const promises = batch.map(t =>
        fetchDecision(t, capital).then(r => r.data).catch(() => null)
      );
      const data = (await Promise.all(promises)).filter(Boolean);

      const filtered = data.filter(r => {
        const rsi = r.signal?.indicators?.rsi ?? 50;
        const vol = r.signal?.indicators?.volume_ratio ?? 1;
        return rsi >= filters.rsiMin && rsi <= filters.rsiMax && vol >= filters.volMin;
      });

      allResults.push(...filtered);
      const sorted = [...allResults].sort((a, b) => {
        const order = { BUY: 0, WEAK_BUY: 1, HOLD: 2, WEAK_SELL: 3, SELL: 4 };
        return (order[a.signal?.action] ?? 2) - (order[b.signal?.action] ?? 2)
          || (b.signal?.confidence || 0) - (a.signal?.confidence || 0);
      });
      setResults(sorted);

      if (i + BATCH < tickers.length && !stopRef.current)
        await new Promise(r => setTimeout(r, 1200));
    }

    setProgress(p => ({ ...p, current: tickers.length, ticker: 'Done!' }));
    setLoading(false);
  };

  const stopScan = () => { stopRef.current = true; };
  const fmt = (v) => v ? Number(v).toLocaleString('vi-VN') : '-';
  const totalSelected = Object.entries(exchanges)
    .reduce((s, [ex, on]) => s + (on ? (tickerCounts[ex] || 0) : 0), 0)
    + watchlist.split(/[,;\s]+/).filter(Boolean).length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <ScanSearch className="w-7 h-7 text-brand-500" /> Stock Scanner
      </h1>

      {/* Controls */}
      <div className="card space-y-4">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Custom Watchlist</label>
          <textarea value={watchlist} onChange={e => setWatchlist(e.target.value)}
            className="input-field h-16 resize-none font-mono text-sm"
            placeholder="FPT, VCB, HPG, MBB, TCB..." />
        </div>

        <div>
          <label className="text-xs text-gray-400 mb-2 block">Exchanges (fetch ALL tickers)</label>
          <div className="flex gap-3 flex-wrap">
            {[['HOSE', '~400 stocks'], ['HNX', '~200 stocks'], ['UPCOM', '~45 stocks']].map(([ex, desc]) => (
              <label key={ex} className={`flex items-center gap-2 px-4 py-2 rounded-lg cursor-pointer border transition-colors
                ${exchanges[ex] ? 'bg-brand-600/20 border-brand-500 text-brand-500' : 'bg-surface-900 border-surface-700 text-gray-400 hover:border-gray-600'}`}>
                <input type="checkbox" checked={exchanges[ex]} onChange={() => toggleExchange(ex)} className="hidden" />
                <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${exchanges[ex] ? 'bg-brand-500 border-brand-500' : 'border-gray-600'}`}>
                  {exchanges[ex] && <span className="text-white text-xs">✓</span>}
                </div>
                <div>
                  <div className="font-medium">{ex}</div>
                  <div className="text-xs opacity-60">{tickerCounts[ex] ? `${tickerCounts[ex]} stocks` : desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div><label className="text-xs text-gray-400">RSI Min</label>
            <input type="number" value={filters.rsiMin} onChange={e => setFilters(p => ({...p, rsiMin: +e.target.value}))} className="input-field text-sm" /></div>
          <div><label className="text-xs text-gray-400">RSI Max</label>
            <input type="number" value={filters.rsiMax} onChange={e => setFilters(p => ({...p, rsiMax: +e.target.value}))} className="input-field text-sm" /></div>
          <div><label className="text-xs text-gray-400">Min Vol Ratio</label>
            <input type="number" step="0.1" value={filters.volMin} onChange={e => setFilters(p => ({...p, volMin: +e.target.value}))} className="input-field text-sm" /></div>
          <div><label className="text-xs text-gray-400">Capital (VND)</label>
            <input type="number" value={capital} onChange={e => setCapital(+e.target.value)} className="input-field text-sm" /></div>
          <div className="flex items-end gap-2">
            {!loading
              ? <button onClick={scan} className="btn-primary w-full flex items-center justify-center gap-2">
                  <ScanSearch className="w-4 h-4" /> Scan {totalSelected > 0 ? `(${totalSelected})` : ''}
                </button>
              : <button onClick={stopScan} className="bg-sell hover:bg-sell/80 text-white font-medium py-2 px-4 rounded-lg w-full flex items-center justify-center gap-2">
                  <Square className="w-4 h-4" /> Stop
                </button>
            }
          </div>
        </div>
      </div>

      {/* Progress */}
      {loading && progress.total > 0 && (
        <div className="card">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Scanning: {progress.ticker}</span>
            <span>{progress.current}/{progress.total} ({Math.round(progress.current/progress.total*100)}%)</span>
          </div>
          <div className="h-2 bg-surface-900 rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 rounded-full transition-all duration-300" style={{ width: `${(progress.current/progress.total)*100}%` }} />
          </div>
          <div className="text-xs text-gray-500 mt-1">Found {results.length} matching</div>
        </div>
      )}

      {/* Summary badges */}
      {results.length > 0 && (
        <div className="flex gap-3 text-sm">
          <span className="badge-buy">{results.filter(r => r.signal?.action?.includes('BUY')).length} BUY</span>
          <span className="badge-sell">{results.filter(r => r.signal?.action?.includes('SELL')).length} SELL</span>
          <span className="badge-hold">{results.filter(r => !r.signal?.action?.includes('BUY') && !r.signal?.action?.includes('SELL')).length} HOLD</span>
          <span className="text-gray-500">Total: {results.length}</span>
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-400 border-b border-surface-700">
                <th className="text-left py-2 px-2">#</th>
                <th className="text-left px-2">Ticker</th>
                <th className="text-right px-2">Price</th>
                <th className="text-center px-2">Signal</th>
                <th className="text-center px-2">Regime</th>
                <th className="text-right px-2">RSI</th>
                <th className="text-right px-2">MACD</th>
                <th className="text-right px-2">VolR</th>
                <th className="text-right px-2">Entry</th>
                <th className="text-right px-2">SL</th>
                <th className="text-right px-2">TP</th>
                <th className="text-right px-2">Shares</th>
                <th className="text-center px-2">Src</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => {
                const sig = r.signal || {};
                const ind = sig.indicators || {};
                const pt = r.price_targets || {};
                const ps = r.position_sizing || {};
                return (
                  <tr key={r.ticker}
                    className="border-b border-surface-700/50 hover:bg-surface-700/30 cursor-pointer transition-colors"
                    onClick={() => navigate(`/decision/${r.ticker}`)}>
                    <td className="py-2 px-2 text-gray-500 text-xs">{i+1}</td>
                    <td className="px-2 font-bold">{r.ticker}</td>
                    <td className="text-right px-2 font-mono">{fmt(ind.price)}</td>
                    <td className="text-center px-2"><SignalBadge action={sig.action} confidence={sig.confidence} /></td>
                    <td className="text-center px-2"><RegimeBadge regime={sig.regime?.regime} /></td>
                    <td className={`text-right px-2 font-mono ${ind.rsi < 30 ? 'text-buy' : ind.rsi > 70 ? 'text-sell' : ''}`}>{ind.rsi?.toFixed(0)}</td>
                    <td className={`text-right px-2 font-mono ${ind.macd_hist > 0 ? 'text-buy' : 'text-sell'}`}>{ind.macd_hist?.toFixed(0)}</td>
                    <td className={`text-right px-2 font-mono ${ind.volume_ratio > 1.5 ? 'text-buy' : ''}`}>{ind.volume_ratio?.toFixed(1)}x</td>
                    <td className="text-right px-2 font-mono text-brand-500">{fmt(pt.entry_conservative)}</td>
                    <td className="text-right px-2 font-mono text-sell">{fmt(pt.stop_loss)}</td>
                    <td className="text-right px-2 font-mono text-buy">{fmt(pt.take_profit_2)}</td>
                    <td className="text-right px-2 font-mono">{ps.shares ? ps.shares.toLocaleString() : '-'}</td>
                    <td className="text-center px-2 text-xs text-gray-500">{r.data_source}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
