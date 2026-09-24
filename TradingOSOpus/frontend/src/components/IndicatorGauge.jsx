export default function IndicatorGauge({ label, value, min = 0, max = 100, zones }) {
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  const defaultZones = [
    { limit: 30, color: 'bg-buy' },
    { limit: 70, color: 'bg-hold' },
    { limit: 100, color: 'bg-sell' },
  ];
  const z = zones || defaultZones;
  let barColor = 'bg-gray-500';
  for (const zone of z) { if (pct <= zone.limit) { barColor = zone.color; break; } }
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="font-mono font-medium">{typeof value === 'number' ? value.toFixed(1) : value}</span>
      </div>
      <div className="h-1.5 bg-surface-900 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}