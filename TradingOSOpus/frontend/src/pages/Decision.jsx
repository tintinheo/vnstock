import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { fetchDecision } from '../api/client';
import SignalBadge from '../components/SignalBadge';
import RegimeBadge from '../components/RegimeBadge';
import PriceTargetCard from '../components/PriceTargetCard';
import IndicatorGauge from '../components/IndicatorGauge';
import { Target, RefreshCw } from 'lucide-react';

export default function Decision() {
  const { ticker: paramTicker } = useParams();
  const [ticker, setTicker] = useState(paramTicker || 'FPT');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async (t) => {
    setLoading(true);
    try {
      const res = await fetchDecision(t || ticker);
      setData(res.data);
    } catch (e) { setData(null); }
    setLoading(false);
  };

  useEffect(() => { if (paramTicker) { setTicker(paramTicker); load(paramTicker); } }, [paramTicker]);

  const sig = data?.signal || {};
  const ind = sig.indicators || {};
  const regime = sig.regime || {};
  const pt = data?.price_targets || {};
  const ps = data?.position_sizing || {};
  const fmt = (v) => v ? Number(v).toLocaleString('vi-VN') : '-';

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Target className="w-7 h-7 text-brand-500" />
        <h1 className="text-2xl font-bold">AI Decision</h1>
        <form onSubmit={e => { e.preventDefault(); load(); }} className="flex gap-2 ml-4">
          <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
            className="input-field w-28 text-center font-bold" placeholder="Ticker" />
          <button type="submit" className="btn-primary flex items-center gap-1">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Analyze
          </button>
        </form>
      </div>

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Signal + Indicators */}
          <div className="lg:col-span-2 space-y-4">
            {/* Main Signal */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-3xl font-bold">{data.ticker}</div>
                  <div className="text-3xl font-mono font-bold mt-1">{fmt(ind.price)} <span className="text-sm text-gray-500">VND</span></div>
                </div>
                <div className="text-right space-y-2">
                  <SignalBadge action={sig.action} confidence={sig.confidence} />
                  <div><RegimeBadge regime={regime.regime} /></div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-400 mb-4">
                <div>Buy Score: <span className="text-buy font-bold">{sig.buy_score}</span></div>
                <div>Sell Score: <span className="text-sell font-bold">{sig.sell_score}</span></div>
                <div>ADX: <span className="text-gray-200">{regime.adx}</span></div>
                <div>Volatility: <span className="text-gray-200">{regime.volatility}</span></div>
              </div>
              {/* Reasons */}
              <div className="space-y-1">
                {sig.reasons?.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className={sig.action?.includes('BUY') ? 'text-buy' : sig.action?.includes('SELL') ? 'text-sell' : 'text-hold'}>●</span>
                    <span className="text-gray-300">{r}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Indicator Gauges */}
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-300 mb-4">Technical Indicators</h3>
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                <IndicatorGauge label="RSI (14)" value={ind.rsi} />
                <IndicatorGauge label="Stochastic K" value={ind.stoch_k} />
                <IndicatorGauge label="MFI" value={ind.mfi} />
                <IndicatorGauge label="Williams %R" value={ind.williams_r} min={-100} max={0}
                  zones={[{limit:30,color:'bg-sell'},{limit:70,color:'bg-hold'},{limit:100,color:'bg-buy'}]} />
                <IndicatorGauge label="BB Position" value={ind.bb_position * 100} />
                <IndicatorGauge label="Volume Ratio" value={ind.volume_ratio} min={0} max={3}
                  zones={[{limit:33,color:'bg-gray-500'},{limit:66,color:'bg-hold'},{limit:100,color:'bg-buy'}]} />
              </div>
            </div>

            {/* Position Sizing */}
            {ps.shares > 0 && (
              <div className="card">
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Position Sizing</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div><span className="text-gray-400 text-xs block">Shares</span><span className="text-xl font-bold font-mono">{ps.shares?.toLocaleString()}</span></div>
                  <div><span className="text-gray-400 text-xs block">Cost</span><span className="font-mono">{fmt(ps.cost)} VND</span></div>
                  <div><span className="text-gray-400 text-xs block">Capital %</span><span className="font-mono text-brand-500">{ps.capital_pct}%</span></div>
                  <div><span className="text-gray-400 text-xs block">Risk</span><span className="font-mono text-sell">{fmt(ps.risk_amount)} VND</span></div>
                </div>
                {pt.scaling_plan && (
                  <div className="mt-4 space-y-1.5">
                    <div className="text-xs text-gray-400 font-semibold">Scaling Plan:</div>
                    {Object.entries(pt.scaling_plan).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-2 text-xs">
                        <div className="w-16 text-gray-500">{k}</div>
                        <div className="bg-brand-600/30 text-brand-500 px-2 py-0.5 rounded">{v.pct}%</div>
                        <span className="font-mono">{fmt(v.price)}</span>
                        <span className="text-gray-500">– {v.note}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right: Price Targets */}
          <div className="space-y-4">
            <PriceTargetCard targets={pt} />
            {/* Key Levels */}
            <div className="card space-y-2">
              <h3 className="text-sm font-semibold text-gray-300">Key Levels</h3>
              <div className="text-xs space-y-1">
                <div className="flex justify-between"><span className="text-gray-400">SMA 20</span><span className="font-mono">{fmt(ind.sma20)}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">SMA 50</span><span className="font-mono">{fmt(ind.sma50)}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">BB Lower</span><span className="font-mono">{fmt(ind.bb_lower)}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">BB Upper</span><span className="font-mono">{fmt(ind.bb_upper)}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">VWAP</span><span className="font-mono">{fmt(pt.vwap)}</span></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {!data && !loading && (
        <div className="text-center py-20 text-gray-500">
          Enter a ticker and click Analyze to get AI decision
        </div>
      )}
    </div>
  );
}