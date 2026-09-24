import { Search, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function Header() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) navigate(`/decision/${query.trim().toUpperCase()}`);
  };
  return (
    <header className="h-14 bg-surface-800 border-b border-surface-700 flex items-center px-4 gap-4 shrink-0">
      <form onSubmit={handleSearch} className="flex items-center bg-surface-900 rounded-lg border border-surface-700 px-3 py-1.5 w-64">
        <Search className="w-4 h-4 text-gray-500 mr-2" />
        <input value={query} onChange={e => setQuery(e.target.value)}
          className="bg-transparent outline-none text-sm w-full placeholder-gray-500"
          placeholder="Search ticker (e.g. FPT)..." />
      </form>
      <div className="flex-1" />
      <button className="p-2 hover:bg-surface-700 rounded-lg transition-colors">
        <RefreshCw className="w-4 h-4 text-gray-400" />
      </button>
      <div className="text-xs text-gray-500">{new Date().toLocaleDateString('vi-VN')}</div>
    </header>
  );
}