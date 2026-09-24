import { useState, useEffect, useMemo } from 'react';
import { Filter, X, ArrowUpDown, ArrowUp, ArrowDown, Download } from 'lucide-react';

export default function TableFilter({ columns, data, onFiltered, children }) {
  const [filters, setFilters] = useState({});
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [showFilters, setShowFilters] = useState(false);
  const setFilter = (key, val) => setFilters(p => ({ ...p, [key]: val }));
  const clearAll = () => { setFilters({}); setSortCol(null); };

  const filtered = useMemo(() => {
    let d = [...(data || [])];
    for (const col of columns) {
      const f = filters[col.key];
      if (f === undefined || f === '' || f === null) continue;
      if (col.filterType === 'text') d = d.filter(r => String(col.accessor(r) || '').toLowerCase().includes(String(f).toLowerCase()));
      else if (col.filterType === 'select') d = d.filter(r => String(col.accessor(r)) === String(f));
      else if (col.filterType === 'number') {
        const [min, max] = f;
        if (min !== '' && min != null) d = d.filter(r => (col.accessor(r) || 0) >= Number(min));
        if (max !== '' && max != null) d = d.filter(r => (col.accessor(r) || 0) <= Number(max));
      }
    }
    if (sortCol) {
      const col = columns.find(c => c.key === sortCol);
      if (col) d.sort((a, b) => { const va = col.accessor(a) ?? 0, vb = col.accessor(b) ?? 0; const cmp = typeof va === 'string' ? va.localeCompare(vb) : va - vb; return sortDir === 'asc' ? cmp : -cmp; });
    }
    return d;
  }, [data, filters, sortCol, sortDir, columns]);

  useEffect(() => { onFiltered?.(filtered); }, [filtered]);
  const toggleSort = (key) => { if (sortCol === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortCol(key); setSortDir('asc'); } };
  const exportCSV = () => {
    const hdr = columns.map(c => c.label).join(',');
    const rows = filtered.map(r => columns.map(c => { const v = c.accessor(r); return typeof v === 'string' && v.includes(',') ? `"${v}"` : v ?? ''; }).join(','));
    const blob = new Blob([[hdr, ...rows].join('\n')], { type: 'text/csv' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `export_${Date.now()}.csv`; a.click();
  };
  const activeCount = Object.values(filters).filter(v => v !== '' && v != null && !(Array.isArray(v) && v.every(x => x === '' || x == null))).length;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs">
        <button onClick={() => setShowFilters(!showFilters)} className={`flex items-center gap-1 px-2 py-1 rounded border ${showFilters ? 'bg-brand-600/20 border-brand-500 text-brand-500' : 'border-surface-700 text-gray-400'}`}>
          <Filter className="w-3 h-3" /> Filters {activeCount > 0 && <span className="bg-brand-500 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px]">{activeCount}</span>}
        </button>
        {activeCount > 0 && <button onClick={clearAll} className="text-gray-500 hover:text-gray-300 flex items-center gap-1"><X className="w-3 h-3" /> Clear</button>}
        <span className="text-gray-500 ml-auto">Showing {filtered.length} of {data?.length || 0}</span>
        <button onClick={exportCSV} className="flex items-center gap-1 px-2 py-1 rounded border border-surface-700 text-gray-400 hover:text-gray-200"><Download className="w-3 h-3" /> CSV</button>
      </div>
      {showFilters && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2 p-3 bg-surface-900 rounded-lg border border-surface-700">
          {columns.filter(c => c.filterType).map(col => (
            <div key={col.key}>
              <label className="text-[10px] text-gray-500 block mb-0.5">{col.label}</label>
              {col.filterType === 'text' && <input value={filters[col.key] || ''} onChange={e => setFilter(col.key, e.target.value)} className="input-field text-xs py-1" placeholder={`Search...`} />}
              {col.filterType === 'select' && <select value={filters[col.key] || ''} onChange={e => setFilter(col.key, e.target.value)} className="input-field text-xs py-1"><option value="">All</option>{(col.options || []).map(o => <option key={o} value={o}>{o}</option>)}</select>}
              {col.filterType === 'number' && <div className="flex gap-1"><input type="number" placeholder="Min" value={(filters[col.key]||['',''])[0]} onChange={e => setFilter(col.key, [e.target.value, (filters[col.key]||['',''])[1]])} className="input-field text-xs py-1 w-1/2" /><input type="number" placeholder="Max" value={(filters[col.key]||['',''])[1]} onChange={e => setFilter(col.key, [(filters[col.key]||['',''])[0], e.target.value])} className="input-field text-xs py-1 w-1/2" /></div>}
            </div>
          ))}
        </div>
      )}
      {typeof children === 'function' ? children({ filtered, toggleSort, sortCol, sortDir }) : children}
    </div>
  );
}

export function SortHeader({ label, colKey, sortCol, sortDir, onSort, className = '' }) {
  const active = sortCol === colKey;
  return (<th className={`px-2 py-2 cursor-pointer hover:text-gray-200 select-none ${className}`} onClick={() => onSort(colKey)}>
    <span className="flex items-center gap-1">{label} {active ? (sortDir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3 opacity-30" />}</span>
  </th>);
}
