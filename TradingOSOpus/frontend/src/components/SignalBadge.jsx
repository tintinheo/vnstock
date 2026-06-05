export default function SignalBadge({ action, confidence }) {
  const cls = {
    BUY: 'badge-buy', WEAK_BUY: 'badge-buy',
    SELL: 'badge-sell', WEAK_SELL: 'badge-sell',
    HOLD: 'badge-hold',
  }[action] || 'badge-hold';
  return (
    <span className={cls}>
      {action} {confidence ? `${Math.round(confidence * 100)}%` : ''}
    </span>
  );
}