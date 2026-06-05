export default function PriceTargetCard({ targets }) {
  if (!targets || targets.action === 'HOLD') return null;
  const fmt = (v) => v ? Number(v).toLocaleString('vi-VN') : '-';
  const isBuy = targets.action === 'BUY' || targets.action === 'WEAK_BUY';
  return (
    <div className="card space-y-3">
      <h3 className="text-sm font-semibold text-gray-300">Price Targets</h3>
      {isBuy ? (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-gray-400">Entry (conservative)</span><span className="text-brand-500 font-mono">{fmt(targets.entry_conservative)}</span></div>
          <div className="flex justify-between"><span className="text-gray-400">Entry (aggressive)</span><span className="text-brand-500/70 font-mono">{fmt(targets.entry_aggressive)}</span></div>
          <hr className="border-surface-700" />
          <div className="flex justify-between"><span className="text-sell">Stop-Loss</span><span className="text-sell font-mono font-bold">{fmt(targets.stop_loss)} <span className="text-xs">({targets.stop_loss_pct}%)</span></span></div>
          <hr className="border-surface-700" />
          <div className="flex justify-between"><span className="text-gray-400">TP1 (1.5R)</span><span className="text-buy font-mono">{fmt(targets.take_profit_1)}</span></div>
          <div className="flex justify-between"><span className="text-gray-400">TP2 (2.5R)</span><span className="text-buy font-mono font-bold">{fmt(targets.take_profit_2)}</span></div>
          <div className="flex justify-between"><span className="text-gray-400">TP3 (3.5R)</span><span className="text-buy font-mono">{fmt(targets.take_profit_3)}</span></div>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-gray-400">Exit (market)</span><span className="text-sell font-mono">{fmt(targets.exit_market)}</span></div>
          <div className="flex justify-between"><span className="text-gray-400">Exit (limit)</span><span className="text-sell font-mono">{fmt(targets.exit_limit)}</span></div>
        </div>
      )}
    </div>
  );
}