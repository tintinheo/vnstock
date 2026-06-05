import { useState, useEffect } from 'react';
import { fetchDecision } from '../api/client';
import StockCard from '../components/StockCard';
import { TrendingUp, TrendingDown, Activity, BarChart3 } from 'lucide-react';
import API from '../api/client';

export default function Dashboard() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  useEffect(() => {
    async function load() {
      setLoading(true);
      let tickers = [];
      try {
        const r = await API.get('/tickers/HOSE');
        tickers = r.data.tickers.slice(0, 30);
      } catch {
        tickers = ['FPT','VCB','HPG','MBB','TCB','VNM','VHM','SSI','ACB','STB',
                    'MWG','PNJ','REE','GVR','VRE','TPB','CTG','BID','SAB','PLX',
                    'GAS','POW','VJC','HDB','SHB','EIB','KDH','DGC','MSN','VIC'];
      }

      setProgress({ current: 0, total: tickers.length });
      const allResults = [];
      const BATCH = 5;

      for (let i = 0; i < tickers.length; i += BATCH) {
        const batch = tickers.slice(i, i + BATCH);
        const promises = batch.map(t =>
          fetchDecision(t).then(r => r.data).catch(() => null)
        );
        const data = (await Promise.all(promises)).filter(Boolean);
        allResults.push(...data);
        setResults([...allResults]);
        setProgress({ current: Math.min(i + BATCH, tickers.length), total: tickers.length });
        if (i + BATCH < tickers.length) await new Promise(r => setTimeout(r, 1200));
      }
      setLoading(false);
    }
    load();
  }, []);

  const buys = results.filter(r => r.signal?.action?.includes('BUY'));
  const sells = results.filter(r => r.signal?.action?.includes('SELL'));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card flex items-center gap-3">
          <div className="p-2 bg-brand-600/20 rounded-lg"><Activity className="w-5 h-5 text-brand-500" /></div>
          <div><div className="text-xs text-gray-400">Scanned</div><div className="text-xl font-bold">{results.length}</div></div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="p-2 bg-buy/20 rounded-lg"><TrendingUp className="w-5 h-5 text-buy" /></div>
          <div><div className="text-xs text-gray-400">BUY</div><div className="text-xl font-bold text-buy">{buys.length}</div></div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="p-2 bg-sell/20 rounded-lg"><TrendingDown className="w-5 h-5 text-sell" /></div>
          <div><div className="text-xs text-gray-400">SELL</div><div className="text-xl font-bold text-sell">{sells.length}</div></div>
        </div>
        <div className="card flex items-center gap-3">
          <div className="p-2 bg-hold/20 rounded-lg"><BarChart3 className="w-5 h-5 text-hold" /></div>
          <div><div className="text-xs text-gray-400">HOLD</div><div className="text-xl font-bold text-hold">{results.length - buys.length - sells.length}</div></div>
        </div>
      </div>

      {loading && (
        <div className="card">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Loading market data...</span>
            <span>{progress.current}/{progress.total}</span>
          </div>
          <div className="h-2 bg-surface-900 rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 rounded-full transition-all duration-300"
              style={{ width: `${progress.total > 0 ? (progress.current/progress.total)*100 : 0}%` }} />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {results.map(r => <StockCard key={r.ticker} result={r} />)}
      </div>
    </div>
  );
}
