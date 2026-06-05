"""audit/logger.py - Thread-safe JSONL audit logger."""
import json, os, uuid, threading
from datetime import datetime, timedelta

class AuditLogger:
    def __init__(self, log_dir="audit_logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, dt=None):
        d = (dt or datetime.now()).strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{d}.jsonl")

    def log(self, action_type, ticker="", params=None, result=None, status="SUCCESS", duration_ms=0, ip=""):
        entry = {
            "id": str(uuid.uuid4())[:12],
            "ts": datetime.now().isoformat(),
            "action": action_type,
            "ticker": ticker,
            "params": params or {},
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "ip": ip,
            "data_source": (result or {}).get("data_source", ""),
            "signal": (result or {}).get("signal", {}).get("action", ""),
            "confidence": (result or {}).get("signal", {}).get("confidence", 0),
            "result_summary": self._summarize(result),
        }
        with self._lock:
            with open(self._path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return entry["id"]

    def _summarize(self, r):
        if not r or not isinstance(r, dict): return {}
        s = {}
        sig = r.get("signal", {})
        if sig:
            s["action"] = sig.get("action", "")
            s["confidence"] = sig.get("confidence", 0)
            s["regime"] = sig.get("regime", {}).get("regime", "") if isinstance(sig.get("regime"), dict) else ""
            ind = sig.get("indicators", {})
            s["rsi"] = ind.get("rsi", 0)
            s["price"] = ind.get("price", 0)
        pt = r.get("price_targets", {})
        if pt:
            s["entry"] = pt.get("entry_conservative", 0)
            s["stop_loss"] = pt.get("stop_loss", 0)
            s["take_profit"] = pt.get("take_profit_2", 0)
        ps = r.get("position_sizing", {})
        if ps: s["shares"] = ps.get("shares", 0)
        return s

    def get_logs(self, date_from=None, date_to=None, action_type=None, ticker=None, status=None, limit=500):
        entries = []
        if not os.path.exists(self.log_dir): return entries
        files = sorted(os.listdir(self.log_dir), reverse=True)
        for fn in files:
            if not fn.endswith(".jsonl"): continue
            fdate = fn.replace(".jsonl", "")
            if date_from and fdate < date_from: continue
            if date_to and fdate > date_to: continue
            fp = os.path.join(self.log_dir, fn)
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        e = json.loads(line)
                        if action_type and e.get("action") != action_type: continue
                        if ticker and ticker.upper() not in e.get("ticker", "").upper(): continue
                        if status and e.get("status") != status: continue
                        entries.append(e)
                    except: continue
            if len(entries) >= limit: break
        return sorted(entries, key=lambda x: x.get("ts", ""), reverse=True)[:limit]

    def get_stats(self, days=7):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        logs = self.get_logs(date_from=cutoff, limit=10000)
        if not logs: return {"total": 0, "success": 0, "error": 0, "success_rate": 0, "avg_duration_ms": 0, "top_tickers": [], "actions": {}, "signals": {}}
        total = len(logs)
        ok = sum(1 for l in logs if l.get("status") == "SUCCESS")
        dur = [l.get("duration_ms", 0) for l in logs if l.get("duration_ms")]
        tickers, actions, signals = {}, {}, {}
        for l in logs:
            t = l.get("ticker", ""); a = l.get("action", ""); sg = l.get("signal", "")
            if t: tickers[t] = tickers.get(t, 0) + 1
            if a: actions[a] = actions.get(a, 0) + 1
            if sg: signals[sg] = signals.get(sg, 0) + 1
        return {"total": total, "success": ok, "error": total-ok,
                "success_rate": round(ok/total*100, 1) if total else 0,
                "avg_duration_ms": round(sum(dur)/len(dur), 1) if dur else 0,
                "top_tickers": sorted(tickers.items(), key=lambda x: -x[1])[:10],
                "actions": actions, "signals": signals}

    def clear_old(self, days=30):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        removed = 0
        for fn in os.listdir(self.log_dir):
            if fn.endswith(".jsonl") and fn.replace(".jsonl", "") < cutoff:
                os.remove(os.path.join(self.log_dir, fn)); removed += 1
        return removed

audit = AuditLogger()
