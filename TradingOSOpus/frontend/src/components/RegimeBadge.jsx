export default function RegimeBadge({ regime }) {
  const colors = {
    UPTREND: 'text-buy bg-buy/10 border-buy/30',
    WEAK_UPTREND: 'text-buy/70 bg-buy/5 border-buy/20',
    DOWNTREND: 'text-sell bg-sell/10 border-sell/30',
    WEAK_DOWNTREND: 'text-sell/70 bg-sell/5 border-sell/20',
    SIDEWAY: 'text-hold bg-hold/10 border-hold/30',
  }[regime] || 'text-gray-400 bg-gray-800 border-gray-700';
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors}`}>
      {regime}
    </span>
  );
}