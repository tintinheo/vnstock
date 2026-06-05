import SignalBadge from './SignalBadge';
import RegimeBadge from './RegimeBadge';
import { useNavigate } from 'react-router-dom';

export default function StockCard({ result }) {
  const navigate = useNavigate();
  if (!result) return null;
  const { ticker, signal, price_targets: pt, position_sizing: ps } = result;
  const price = signal?.indicators?.price || 0;
  const fmt = (v) => v ? Number(v).toLocaleString('vi-VN') : '-';
  return (
    <div className="card hover:border-brand-500/50 cursor-pointer transition-colors"
         onClick={() => navigate(`/decision/${ticker}`)}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-lg font-bold">{ticker}</span>
        <SignalBadge action={signal?.action} confidence={signal?.confidence} />
      </div>
      <div className="text-2xl font-mono font-bold mb-2">{fmt(price)} <span className="text-xs text-gray-500">VND</span></div>
      <div className="flex items-center gap-2 mb-3">
        <RegimeBadge regime={signal?.regime?.regime} />
        <span className="text-xs text-gray-500">ADX {signal?.regime?.adx}</span>
      </div>
      {pt?.entry_conservative && (
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div><span className="text-gray-500 block">Entry</span><span className="font-mono text-brand-500">{fmt(pt.entry_conservative)}</span></div>
          <div><span className="text-gray-500 block">SL</span><span className="font-mono text-sell">{fmt(pt.stop_loss)}</span></div>
          <div><span className="text-gray-500 block">TP2</span><span className="font-mono text-buy">{fmt(pt.take_profit_2)}</span></div>
        </div>
      )}
      {ps?.shares > 0 && (
        <div className="mt-2 text-xs text-gray-500">{ps.shares.toLocaleString()} shares • {ps.capital_pct}% capital</div>
      )}
    </div>
  );
}