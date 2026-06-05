import { AlertTriangle, Database, Wifi, HardDrive } from 'lucide-react';

export default function DataSourceBadge({ source, showWarning = true }) {
  const config = {
    TCBS: { color: 'text-buy bg-buy/10 border-buy/30', icon: Wifi, label: 'TCBS Live' },
    VCI: { color: 'text-buy bg-buy/10 border-buy/30', icon: Wifi, label: 'VCI Live' },
    CACHE: { color: 'text-blue-400 bg-blue-400/10 border-blue-400/30', icon: HardDrive, label: 'Cache' },
    SYNTHETIC: { color: 'text-sell bg-sell/10 border-sell/30', icon: AlertTriangle, label: '⚠️ FAKE DATA' },
  }[source] || { color: 'text-gray-400 bg-gray-800 border-gray-700', icon: Database, label: source || 'Unknown' };

  const Icon = config.icon;
  const isSynthetic = source === 'SYNTHETIC';

  return (
    <div>
      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${config.color}`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </span>
      {isSynthetic && showWarning && (
        <div className="mt-2 p-3 bg-sell/10 border border-sell/30 rounded-lg text-xs text-sell">
          <div className="flex items-center gap-2 font-bold mb-1">
            <AlertTriangle className="w-4 h-4" /> WARNING: Synthetic Data
          </div>
          <p>Prices shown are <strong>randomly generated</strong> and do NOT reflect real market prices.
          Decisions based on this data are meaningless. Check your internet connection or API status.</p>
        </div>
      )}
    </div>
  );
}
