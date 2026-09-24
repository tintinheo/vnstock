import { useState, useEffect } from 'react';
import { fetchPortfolio } from '../api/client';
import { Briefcase } from 'lucide-react';

export default function Portfolio() {
  const [data, setData] = useState(null);
  useEffect(() => { fetchPortfolio().then(r => setData(r.data)).catch(() => {}); }, []);
  const fmt = (v) => v ? Number(v).toLocaleString('vi-VN') : '0';
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Briefcase className="w-7 h-7 text-brand-500" /> Portfolio</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card"><div className="text-xs text-gray-400">Cash</div><div className="text-2xl font-mono font-bold">{fmt(data?.cash)} VND</div></div>
        <div className="card"><div className="text-xs text-gray-400">Positions Value</div><div className="text-2xl font-mono font-bold">{fmt(data?.positions_value)} VND</div></div>
        <div className="card"><div className="text-xs text-gray-400">Total Equity</div><div className="text-2xl font-mono font-bold text-brand-500">{fmt(data?.total_equity)} VND</div></div>
      </div>
      {data?.positions?.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-gray-400 border-b border-surface-700">
              <th className="text-left py-2">Ticker</th><th className="text-right">Shares</th><th className="text-right">Avg Price</th><th className="text-right">Current</th><th className="text-right">P&L</th>
            </tr></thead>
            <tbody>{data.positions.map(p => (
              <tr key={p.ticker} className="border-b border-surface-700/50">
                <td className="py-2 font-bold">{p.ticker}</td>
                <td className="text-right font-mono">{p.shares?.toLocaleString()}</td>
                <td className="text-right font-mono">{fmt(p.avg_price)}</td>
                <td className="text-right font-mono">{fmt(p.current_price)}</td>
                <td className={`text-right font-mono ${p.unrealized_pnl >= 0 ? 'text-buy' : 'text-sell'}`}>{fmt(p.unrealized_pnl)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}