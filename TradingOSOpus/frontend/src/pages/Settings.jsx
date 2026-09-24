import { useState } from 'react';
import { Settings as SettingsIcon, Save } from 'lucide-react';

export default function Settings() {
  const [config, setConfig] = useState({
    apiUrl: 'http://localhost:8000',
    capital: 500000000,
    riskPct: 2,
    atrMultiplier: 2.0,
    rrRatio: 2.5,
  });
  const update = (key, val) => setConfig(p => ({ ...p, [key]: val }));
  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold flex items-center gap-2"><SettingsIcon className="w-7 h-7 text-brand-500" /> Settings</h1>
      <div className="card space-y-4">
        <div><label className="text-xs text-gray-400">API URL</label><input value={config.apiUrl} onChange={e=>update('apiUrl',e.target.value)} className="input-field" /></div>
        <div><label className="text-xs text-gray-400">Capital (VND)</label><input type="number" value={config.capital} onChange={e=>update('capital',+e.target.value)} className="input-field" /></div>
        <div className="grid grid-cols-3 gap-3">
          <div><label className="text-xs text-gray-400">Risk %</label><input type="number" step="0.5" value={config.riskPct} onChange={e=>update('riskPct',+e.target.value)} className="input-field" /></div>
          <div><label className="text-xs text-gray-400">ATR Mult</label><input type="number" step="0.1" value={config.atrMultiplier} onChange={e=>update('atrMultiplier',+e.target.value)} className="input-field" /></div>
          <div><label className="text-xs text-gray-400">R:R Ratio</label><input type="number" step="0.1" value={config.rrRatio} onChange={e=>update('rrRatio',+e.target.value)} className="input-field" /></div>
        </div>
        <button className="btn-primary flex items-center gap-2"><Save className="w-4 h-4" /> Save Settings</button>
      </div>
    </div>
  );
}