import { Bell } from 'lucide-react';

export default function Signals() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Bell className="w-7 h-7 text-brand-500" /> Signal History</h1>
      <div className="card text-center py-20 text-gray-500">
        <Bell className="w-12 h-12 mx-auto mb-4 opacity-30" />
        <p>Signal history will appear here after scanning.</p>
        <p className="text-xs mt-2">Go to Scanner → Scan → signals are logged automatically.</p>
      </div>
    </div>
  );
}