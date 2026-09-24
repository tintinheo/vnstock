import { useState } from 'react';
import { fetchBacktest } from '../api/client';
import { BarChart3 } from 'lucide-react';

export default function Backtest() {
  const [ticker, setTicker] = useState('FPT');
  const [strategy, setStrategy] = useState('1W');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try { const r = await fetchBacktest(ticker, strategy); setResult(r.data); } catch {}
    setLoading(false);
  };
  const fmt = (v) => v ? Number(v).toLocaleString('vi-VN') : '-';

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><BarChart3 className="w-7 h-7 text-brand-500" /> Backtest</h1>
      <div className="card flex flex-wrap items-end gap-3">
        <div><label className="text-xs text-gray-400">Ticker</label><input value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())} className="input-field w-28" /></div>
        <div><label className="text-xs text-gray-400">Strategy</label>
          <select value={strategy} onChange={e=>setStrategy(e.target.value)} className="input-field w-32">
            {['1W','2W','1M','3M','5M'].map(s=><option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <button onClick={run} disabled={loading} className="btn-primary">{loading ? 'Running...' : 'Run Backtest'}</button>
      </div>
      {result && !result.error && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card"><div className="text-xs text-gray-400">Return</div><div className={`text-xl font-bold ${result.total_return_pct >= 0 ? 'text-buy' : 'text-sell'}`}>{result.total_return_pct}%</div></div>
          <div className="card"><div className="text-xs text-gray-400">Trades</div><div className="text-xl font-bold">{result.total_trades}</div></div>
          <div className="card"><div className="text-xs text-gray-400">Sharpe</div><div className="text-xl font-bold">{result.metrics?.sharpe_ratio?.toFixed(2)}</div></div>
          <div className="card"><div className="text-xs text-gray-400">Max DD</div><div className="text-xl font-bold text-sell">{result.metrics?.max_drawdown_pct?.toFixed(1)}%</div></div>
        </div>
      )}
    </div>
  );
}