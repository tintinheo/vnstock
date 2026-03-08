import { useState, useEffect, useCallback, useRef } from "react";

// ═══════════════════════════════════════════════════════════════
//  CONSTANTS & CONFIG
// ═══════════════════════════════════════════════════════════════
const EXCHANGE_LIMITS = { HOSE: 0.07, HNX: 0.10, UPCoM: 0.15 };

// HOSE tick sizes (VND)
const getTickSize = (price, exchange) => {
  if (exchange === "HNX" || exchange === "UPCoM") return 100;
  if (price < 10000) return 10;
  if (price < 50000) return 50;
  return 100;
};

const roundToTick = (price, exchange) => {
  const tick = getTickSize(price, exchange);
  return Math.round(price / tick) * tick;
};

const calcPriceLevels = (refPrice, exchange) => {
  const limit = EXCHANGE_LIMITS[exchange] || 0.07;
  return {
    tran: roundToTick(refPrice * (1 + limit), exchange),
    san: roundToTick(refPrice * (1 - limit), exchange),
    thamChieu: refPrice,
  };
};

const TV_COLUMNS = [
  "close", "open", "high", "low", "volume",
  "change_abs", "change", "RSI", "SMA20", "SMA50",
  "Recommend.All", "close[1]", "High.3M", "Low.3M",
  "MACD.macd", "MACD.signal"
];

const DEFAULT_WATCHLIST = [
  { ticker: "GAS",  exchange: "HOSE", name: "PV Gas",           sector: "Dầu khí",   flag: "⛽" },
  { ticker: "PVD",  exchange: "HOSE", name: "PV Drilling",      sector: "Dầu khí",   flag: "🛢" },
  { ticker: "BSR",  exchange: "HOSE", name: "Lọc Hóa Dầu BS",  sector: "Dầu khí",   flag: "🏭" },
  { ticker: "PLX",  exchange: "HOSE", name: "Petrolimex",       sector: "Dầu khí",   flag: "⛽" },
  { ticker: "PVS",  exchange: "HNX",  name: "PTSC",             sector: "Dầu khí",   flag: "⚙️" },
  { ticker: "DPM",  exchange: "HOSE", name: "Đạm Phú Mỹ",      sector: "Phân bón",  flag: "🌱" },
  { ticker: "DCM",  exchange: "HOSE", name: "Đạm Cà Mau",      sector: "Phân bón",  flag: "🌿" },
  { ticker: "HAH",  exchange: "HOSE", name: "Hải An",           sector: "Logistics", flag: "🚢" },
  { ticker: "GMD",  exchange: "HOSE", name: "Gemadept",         sector: "Logistics", flag: "⚓" },
  { ticker: "VNM",  exchange: "HOSE", name: "Vinamilk",         sector: "Tiêu dùng", flag: "🥛" },
  { ticker: "VCB",  exchange: "HOSE", name: "Vietcombank",      sector: "Ngân hàng", flag: "🏦" },
  { ticker: "HPG",  exchange: "HOSE", name: "Hòa Phát Group",  sector: "Thép",      flag: "⚒️" },
];

// ═══════════════════════════════════════════════════════════════
//  TRADING SIGNAL LOGIC
// ═══════════════════════════════════════════════════════════════
const getSignal = (rec) => {
  if (rec === null || rec === undefined) return { label: "–", color: "#475569", short: "–" };
  if (rec >= 0.5)  return { label: "Mua mạnh",  color: "#22c55e", short: "MUA↑", bg: "#22c55e18" };
  if (rec >= 0.1)  return { label: "Mua",        color: "#86efac", short: "MUA",  bg: "#86efac15" };
  if (rec > -0.1)  return { label: "Trung lập", color: "#f59e0b", short: "HOLD", bg: "#f59e0b15" };
  if (rec > -0.5)  return { label: "Bán",        color: "#f87171", short: "BÁN",  bg: "#f8717115" };
  return               { label: "Bán mạnh",  color: "#ef4444", short: "BÁN↓", bg: "#ef444418" };
};

const getBuyPrice = (close, ref, san, rsi, sma20, signal) => {
  // Tính giá mua hợp lý dựa trên kỹ thuật
  if (!close || !ref) return null;
  let base = ref; // Mua quanh giá tham chiếu
  if (sma20 && sma20 < close) base = Math.min(ref, sma20 * 1.005); // Hỗ trợ SMA20
  if (rsi && rsi < 35) base = close * 0.995; // RSI oversold → mua ngay gần giá thị trường
  if (rsi && rsi > 70) base = san + (ref - san) * 0.3; // RSI overbought → chờ giảm về sàn
  return Math.max(san, roundToTick(base, "HOSE"));
};

const getSellPrice = (close, ref, tran, rsi, signal) => {
  if (!close || !ref) return null;
  let target = ref + (tran - ref) * 0.55; // Mặc định giữa tham chiếu và trần
  if (rsi && rsi > 65) target = ref + (tran - ref) * 0.3; // Sắp overbought → chốt sớm
  if (rsi && rsi < 40) target = ref + (tran - ref) * 0.7; // Oversold = kỳ vọng hồi mạnh
  return Math.min(tran, roundToTick(target, "HOSE"));
};

// ═══════════════════════════════════════════════════════════════
//  FETCH — TradingView Scanner API
// ═══════════════════════════════════════════════════════════════
const fetchPrices = async (watchlist) => {
  const tickers = watchlist.map(s => `${s.exchange}:${s.ticker}`);
  const res = await fetch("https://scanner.tradingview.com/vietnam/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbols: { tickers, query: { types: [] } },
      columns: TV_COLUMNS,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  return json.data || [];
};

const parseRow = (raw, stockDef) => {
  const [close, open, high, low, volume, changeAbs, changePct,
    rsi, sma20, sma50, recAll, prevClose, high3m, low3m, macdLine, macdSig] = raw.d;

  const ref = prevClose || open || close;
  const { tran, san, thamChieu } = calcPriceLevels(ref, stockDef.exchange);
  const signal = getSignal(recAll);
  const buyPrice  = getBuyPrice(close, ref, san, rsi, sma20, signal);
  const sellPrice = getSellPrice(close, ref, tran, rsi, signal);

  return {
    ...stockDef,
    close, open, high, low, volume,
    changeAbs, changePct,
    rsi, sma20, sma50,
    recAll, prevClose,
    high3m, low3m,
    macdLine, macdSig,
    ref, tran, san, thamChieu,
    signal, buyPrice, sellPrice,
    priceBarPct: tran > san ? Math.min(100, Math.max(0, ((close - san) / (tran - san)) * 100)) : 50,
    updatedAt: Date.now(),
  };
};

// ═══════════════════════════════════════════════════════════════
//  HELPERS / FORMAT
// ═══════════════════════════════════════════════════════════════
const fmtPrice = (v) => v == null ? "–" : Math.round(v).toLocaleString("vi-VN");
const fmtVol   = (v) => v == null ? "–" : v >= 1e6 ? (v/1e6).toFixed(1)+"M" : v >= 1e3 ? (v/1e3).toFixed(0)+"K" : v;
const fmtPct   = (v) => v == null ? "–" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
const fmtRSI   = (v) => v == null ? "–" : v.toFixed(1);
const getChangeColor = (v) => v > 0 ? "#22c55e" : v < 0 ? "#ef4444" : "#f59e0b";
const isMarketOpen = () => {
  const now = new Date();
  const h = now.getHours(), m = now.getMinutes();
  const dayOfWeek = now.getDay();
  if (dayOfWeek === 0 || dayOfWeek === 6) return false;
  const mins = h * 60 + m;
  return (mins >= 9*60+15 && mins <= 11*60+30) || (mins >= 13*60 && mins <= 14*60+45);
};

// ═══════════════════════════════════════════════════════════════
//  SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════
function PriceBar({ pct, tran, san, ref, close, exchange }) {
  const refPct = tran > san ? ((ref - san) / (tran - san)) * 100 : 50;
  const closeColor = close >= ref ? "#22c55e" : "#ef4444";
  return (
    <div style={{ position: "relative", width: "100%", height: 6, background: "#1e293b", borderRadius: 3, overflow: "visible" }}>
      {/* Gradient fill */}
      <div style={{ position: "absolute", left: 0, top: 0, width: `${pct}%`, height: "100%",
        background: `linear-gradient(90deg, #ef444440, ${closeColor}88)`, borderRadius: 3 }} />
      {/* Tham chiếu marker */}
      <div style={{ position: "absolute", left: `${refPct}%`, top: -2, width: 2, height: 10,
        background: "#f59e0b", borderRadius: 1, transform: "translateX(-50%)" }} />
      {/* Current price marker */}
      <div style={{ position: "absolute", left: `${pct}%`, top: -3, width: 3, height: 12,
        background: closeColor, borderRadius: 1, transform: "translateX(-50%)",
        boxShadow: `0 0 6px ${closeColor}` }} />
    </div>
  );
}

function RSIBar({ value }) {
  if (!value) return <span style={{ color: "#475569" }}>–</span>;
  const color = value > 70 ? "#ef4444" : value < 30 ? "#22c55e" : "#94a3b8";
  const label = value > 70 ? "OB" : value < 30 ? "OS" : "";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 36, height: 4, background: "#1e293b", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${value}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontFamily: "IBM Plex Mono", fontSize: 11, color }}>
        {value.toFixed(0)}{label && <span style={{ fontSize: 9, marginLeft: 2 }}>{label}</span>}
      </span>
    </div>
  );
}

function SignalBadge({ signal }) {
  if (!signal || signal.label === "–") return <span style={{ color: "#475569" }}>–</span>;
  return (
    <span style={{ fontFamily: "IBM Plex Mono", fontWeight: 700, fontSize: 11,
      color: signal.color, background: signal.bg,
      border: `1px solid ${signal.color}33`, borderRadius: 5,
      padding: "2px 7px", whiteSpace: "nowrap" }}>
      {signal.short}
    </span>
  );
}

function ExchangeBadge({ exchange }) {
  const colors = { HOSE: "#3b82f6", HNX: "#8b5cf6", UPCoM: "#f59e0b" };
  const color = colors[exchange] || "#64748b";
  return (
    <span style={{ fontFamily: "IBM Plex Mono", fontSize: 9, fontWeight: 700,
      color, background: color + "20", border: `1px solid ${color}40`,
      borderRadius: 3, padding: "1px 5px" }}>
      {exchange}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════
//  DETAIL MODAL
// ═══════════════════════════════════════════════════════════════
function DetailModal({ stock, onClose }) {
  if (!stock) return null;
  const items = [
    { label: "Giá tham chiếu",   value: fmtPrice(stock.thamChieu), color: "#f59e0b",  note: "Giá đóng cửa phiên trước" },
    { label: "Giá trần",         value: fmtPrice(stock.tran),      color: "#ef4444",  note: `+${(EXCHANGE_LIMITS[stock.exchange]*100).toFixed(0)}% từ tham chiếu` },
    { label: "Giá sàn",          value: fmtPrice(stock.san),       color: "#22c55e",  note: `-${(EXCHANGE_LIMITS[stock.exchange]*100).toFixed(0)}% từ tham chiếu` },
    { label: "Giá hiện tại",     value: fmtPrice(stock.close),     color: getChangeColor(stock.changePct), note: fmtPct(stock.changePct) },
    { label: "Mở cửa",           value: fmtPrice(stock.open),      color: "#94a3b8",  note: "Giá ATO" },
    { label: "Cao nhất ngày",    value: fmtPrice(stock.high),      color: "#22c55e",  note: "" },
    { label: "Thấp nhất ngày",   value: fmtPrice(stock.low),       color: "#ef4444",  note: "" },
    { label: "Khối lượng",       value: fmtVol(stock.volume),      color: "#e2e8f0",  note: "CP khớp lệnh" },
    { label: "RSI(14)",          value: fmtRSI(stock.rsi),         color: stock.rsi > 70 ? "#ef4444" : stock.rsi < 30 ? "#22c55e" : "#94a3b8", note: stock.rsi > 70 ? "Quá mua" : stock.rsi < 30 ? "Quá bán" : "Trung lập" },
    { label: "SMA 20",           value: fmtPrice(stock.sma20),     color: "#06b6d4",  note: stock.close > stock.sma20 ? "Giá trên SMA20 ✅" : "Giá dưới SMA20 ⚠️" },
    { label: "SMA 50",           value: fmtPrice(stock.sma50),     color: "#8b5cf6",  note: stock.close > stock.sma50 ? "Uptrend dài hạn" : "Downtrend dài hạn" },
  ];
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}
      onClick={onClose}>
      <div style={{ background: "#0d1526", border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: 16, padding: 28, maxWidth: 560, width: "100%", maxHeight: "85vh",
        overflowY: "auto" }}
        onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
              <span style={{ fontFamily: "IBM Plex Mono", fontWeight: 800, fontSize: 24, color: "#e2e8f0" }}>
                {stock.flag} {stock.ticker}
              </span>
              <ExchangeBadge exchange={stock.exchange} />
            </div>
            <div style={{ color: "#64748b", fontSize: 13 }}>{stock.name} · {stock.sector}</div>
          </div>
          <button onClick={onClose} style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
            color: "#94a3b8", borderRadius: 8, width: 32, height: 32, cursor: "pointer", fontSize: 16 }}>✕</button>
        </div>

        {/* Price bar full */}
        <div style={{ background: "#0f1929", borderRadius: 10, padding: 16, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11,
            color: "#475569", fontFamily: "IBM Plex Mono", marginBottom: 8 }}>
            <span>SÀN {fmtPrice(stock.san)}</span>
            <span style={{ color: "#f59e0b" }}>TC {fmtPrice(stock.thamChieu)}</span>
            <span>TRẦN {fmtPrice(stock.tran)}</span>
          </div>
          <PriceBar pct={stock.priceBarPct} {...stock} />
          <div style={{ textAlign: "center", marginTop: 12 }}>
            <span style={{ fontFamily: "IBM Plex Mono", fontWeight: 800, fontSize: 28,
              color: getChangeColor(stock.changePct) }}>
              {fmtPrice(stock.close)}
            </span>
            <span style={{ color: "#64748b", fontSize: 13, marginLeft: 6 }}>VND</span>
            <span style={{ marginLeft: 12, fontFamily: "IBM Plex Mono", fontSize: 14,
              color: getChangeColor(stock.changePct) }}>
              {fmtPct(stock.changePct)}
            </span>
          </div>
        </div>

        {/* Buy/Sell suggestion */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <div style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)",
            borderRadius: 10, padding: 14 }}>
            <div style={{ color: "#22c55e", fontSize: 11, fontWeight: 700, marginBottom: 6, letterSpacing: 0.5 }}>
              💡 GIÁ NÊN MUA VÀO
            </div>
            <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 800, fontSize: 20, color: "#22c55e" }}>
              {fmtPrice(stock.buyPrice)}
            </div>
            <div style={{ color: "#64748b", fontSize: 11, marginTop: 4 }}>
              {stock.rsi < 35 ? "RSI quá bán → mua ngay" :
               stock.rsi > 70 ? "RSI quá mua → chờ về sàn" :
               "Mua quanh giá tham chiếu"}
            </div>
          </div>
          <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 10, padding: 14 }}>
            <div style={{ color: "#ef4444", fontSize: 11, fontWeight: 700, marginBottom: 6, letterSpacing: 0.5 }}>
              🎯 GIÁ NÊN BÁN RA
            </div>
            <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 800, fontSize: 20, color: "#ef4444" }}>
              {fmtPrice(stock.sellPrice)}
            </div>
            <div style={{ color: "#64748b", fontSize: 11, marginTop: 4 }}>
              {stock.rsi > 65 ? "RSI cao → chốt sớm hơn" :
               "55% khoảng cách đến trần"}
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {items.map(item => (
            <div key={item.label} style={{ background: "#111827", borderRadius: 8, padding: "10px 14px" }}>
              <div style={{ color: "#475569", fontSize: 10, marginBottom: 3 }}>{item.label}</div>
              <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700, color: item.color, fontSize: 14 }}>
                {item.value}
              </div>
              {item.note && <div style={{ color: "#374151", fontSize: 10, marginTop: 2 }}>{item.note}</div>}
            </div>
          ))}
        </div>

        {/* Signal */}
        <div style={{ marginTop: 16, padding: "12px 16px", background: stock.signal?.bg || "#1e293b",
          borderRadius: 10, border: `1px solid ${stock.signal?.color || "#475569"}33`,
          display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ color: "#64748b", fontSize: 12 }}>Tín hiệu kỹ thuật tổng hợp</div>
          <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 800, color: stock.signal?.color, fontSize: 16 }}>
            {stock.signal?.label || "–"}
          </div>
        </div>

        <div style={{ marginTop: 12, color: "#374151", fontSize: 10, textAlign: "center" }}>
          ⚠️ Chỉ mang tính tham khảo kỹ thuật. Không phải tư vấn đầu tư chuyên nghiệp.
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  MAIN APP
// ═══════════════════════════════════════════════════════════════
export default function App() {
  const [watchlist, setWatchlist] = useState(DEFAULT_WATCHLIST);
  const [stockData, setStockData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [countdown, setCountdown] = useState(30);
  const [selectedStock, setSelectedStock] = useState(null);
  const [addInput, setAddInput] = useState("");
  const [addExchange, setAddExchange] = useState("HOSE");
  const [sortBy, setSortBy] = useState("ticker");
  const [filterSector, setFilterSector] = useState("ALL");
  const [filterSignal, setFilterSignal] = useState("ALL");
  const [marketOpen, setMarketOpen] = useState(isMarketOpen());
  const refreshTimer = useRef(null);
  const countdownTimer = useRef(null);

  const loadData = useCallback(async (list = watchlist) => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchPrices(list);
      const map = {};
      rows.forEach((row, i) => {
        if (row && row.d && list[i]) {
          map[list[i].ticker] = parseRow(row, list[i]);
        }
      });
      setStockData(map);
      setLastUpdate(new Date());
      setCountdown(30);
    } catch (e) {
      setError("Không thể kết nối TradingView API. Kiểm tra kết nối mạng.");
    } finally {
      setLoading(false);
    }
  }, [watchlist]);

  useEffect(() => { loadData(); }, []);

  // Auto-refresh
  useEffect(() => {
    refreshTimer.current = setInterval(() => {
      loadData();
      setMarketOpen(isMarketOpen());
    }, 30000);
    countdownTimer.current = setInterval(() => {
      setCountdown(c => c > 0 ? c - 1 : 30);
    }, 1000);
    return () => {
      clearInterval(refreshTimer.current);
      clearInterval(countdownTimer.current);
    };
  }, [loadData]);

  const handleAdd = () => {
    const t = addInput.trim().toUpperCase();
    if (!t || watchlist.find(s => s.ticker === t)) return;
    const newStock = { ticker: t, exchange: addExchange, name: t, sector: "–", flag: "📈" };
    const newList = [...watchlist, newStock];
    setWatchlist(newList);
    loadData(newList);
    setAddInput("");
  };

  const handleRemove = (ticker) => {
    const newList = watchlist.filter(s => s.ticker !== ticker);
    setWatchlist(newList);
    setStockData(prev => { const d = { ...prev }; delete d[ticker]; return d; });
  };

  const sectors = ["ALL", ...new Set(watchlist.map(s => s.sector))];
  const signals = ["ALL", "MUA↑", "MUA", "HOLD", "BÁN", "BÁN↓"];

  const sortedData = Object.values(stockData)
    .filter(s => filterSector === "ALL" || s.sector === filterSector)
    .filter(s => filterSignal === "ALL" || s.signal?.short === filterSignal)
    .sort((a, b) => {
      if (sortBy === "ticker")   return a.ticker.localeCompare(b.ticker);
      if (sortBy === "change")   return (b.changePct || 0) - (a.changePct || 0);
      if (sortBy === "volume")   return (b.volume || 0) - (a.volume || 0);
      if (sortBy === "rsi")      return (b.rsi || 0) - (a.rsi || 0);
      if (sortBy === "upside")   return ((b.sellPrice - b.close) / b.close) - ((a.sellPrice - a.close) / a.close);
      return 0;
    });

  const upCount    = sortedData.filter(s => (s.changePct || 0) > 0).length;
  const downCount  = sortedData.filter(s => (s.changePct || 0) < 0).length;
  const neutralCnt = sortedData.filter(s => (s.changePct || 0) === 0 && s.close).length;

  return (
    <div style={{ minHeight: "100vh", background: "#070d1a", color: "#e2e8f0",
      fontFamily: "'DM Sans', sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: #0d1526; }
        ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 2px; }
        table { border-collapse: collapse; }
        tr:hover td { background: rgba(255,255,255,0.02) !important; }
        button { font-family: 'DM Sans', sans-serif; }
      `}</style>

      {/* ── HEADER ── */}
      <div style={{ background: "#0a1120", borderBottom: "1px solid #0f2040",
        padding: "12px 20px", display: "flex", justifyContent: "space-between",
        alignItems: "center", position: "sticky", top: 0, zIndex: 100 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg,#1d4ed8,#06b6d4)",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>📊</div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 15, letterSpacing: -0.3 }}>VN Stock Terminal</div>
            <div style={{ fontSize: 10, color: "#334155", fontFamily: "IBM Plex Mono" }}>
              Real-time · HOSE · HNX · UPCoM
            </div>
          </div>
        </div>

        {/* Market Status + Ticker */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            {[{ n: upCount, c: "#22c55e", l: "▲" }, { n: neutralCnt, c: "#f59e0b", l: "–" }, { n: downCount, c: "#ef4444", l: "▼" }]
              .map(item => (
                <span key={item.l} style={{ fontFamily: "IBM Plex Mono", fontSize: 12,
                  color: item.c, background: item.c + "18", padding: "2px 8px", borderRadius: 4 }}>
                  {item.l} {item.n}
                </span>
              ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%",
              background: marketOpen ? "#22c55e" : "#ef4444",
              boxShadow: marketOpen ? "0 0 8px #22c55e" : "none",
              animation: marketOpen ? "pulse 1.5s infinite" : "none" }} />
            <span style={{ fontSize: 11, color: marketOpen ? "#22c55e" : "#ef4444",
              fontFamily: "IBM Plex Mono", fontWeight: 600 }}>
              {marketOpen ? "ĐANG GIAO DỊCH" : "ĐÓNG CỬA"}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}
            onClick={() => loadData()}>
            <div style={{ width: 18, height: 18, borderRadius: "50%",
              border: "2px solid #1e3a5f", display: "flex", alignItems: "center",
              justifyContent: "center", position: "relative" }}>
              <svg width="10" height="10" viewBox="0 0 10 10" style={{
                transform: loading ? "rotate(0deg)" : "none",
                animation: loading ? "spin 0.8s linear infinite" : "none"
              }}>
                <path d="M5 1.5 A3.5 3.5 0 1 1 1.5 5" fill="none" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <span style={{ fontSize: 10, color: "#334155", fontFamily: "IBM Plex Mono" }}>
              {loading ? "..." : `${countdown}s`}
            </span>
          </div>
          {lastUpdate && (
            <span style={{ fontSize: 10, color: "#1e3a5f", fontFamily: "IBM Plex Mono" }}>
              {lastUpdate.toLocaleTimeString("vi-VN")}
            </span>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }`}</style>

      <div style={{ padding: "16px 20px" }}>

        {/* ── CONTROLS ── */}
        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
          {/* Add stock */}
          <div style={{ display: "flex", gap: 6, flex: "1 1 300px" }}>
            <input value={addInput} onChange={e => setAddInput(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === "Enter" && handleAdd()}
              placeholder="Thêm mã CP (VD: VCB, TCB…)"
              style={{ flex: 1, background: "#0d1526", border: "1px solid #1e3a5f",
                borderRadius: 8, padding: "8px 12px", color: "#e2e8f0", fontSize: 13,
                fontFamily: "IBM Plex Mono", outline: "none" }} />
            <select value={addExchange} onChange={e => setAddExchange(e.target.value)}
              style={{ background: "#0d1526", border: "1px solid #1e3a5f", borderRadius: 8,
                padding: "8px 10px", color: "#94a3b8", fontSize: 12, cursor: "pointer", outline: "none" }}>
              <option>HOSE</option><option>HNX</option><option>UPCoM</option>
            </select>
            <button onClick={handleAdd}
              style={{ background: "#1d4ed8", border: "none", borderRadius: 8,
                padding: "8px 16px", color: "#fff", fontSize: 12, cursor: "pointer",
                fontWeight: 600 }}>+ Thêm</button>
          </div>

          {/* Filters */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <select value={filterSector} onChange={e => setFilterSector(e.target.value)}
              style={{ background: "#0d1526", border: "1px solid #1e3a5f", borderRadius: 8,
                padding: "8px 10px", color: "#94a3b8", fontSize: 12, cursor: "pointer", outline: "none" }}>
              {sectors.map(s => <option key={s}>{s}</option>)}
            </select>
            <select value={filterSignal} onChange={e => setFilterSignal(e.target.value)}
              style={{ background: "#0d1526", border: "1px solid #1e3a5f", borderRadius: 8,
                padding: "8px 10px", color: "#94a3b8", fontSize: 12, cursor: "pointer", outline: "none" }}>
              {signals.map(s => <option key={s}>{s === "ALL" ? "Tất cả tín hiệu" : s}</option>)}
            </select>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              style={{ background: "#0d1526", border: "1px solid #1e3a5f", borderRadius: 8,
                padding: "8px 10px", color: "#94a3b8", fontSize: 12, cursor: "pointer", outline: "none" }}>
              <option value="ticker">Sắp xếp: A–Z</option>
              <option value="change">Sắp xếp: % Thay đổi</option>
              <option value="volume">Sắp xếp: Khối lượng</option>
              <option value="rsi">Sắp xếp: RSI</option>
              <option value="upside">Sắp xếp: Upside</option>
            </select>
          </div>
        </div>

        {/* ── ERROR ── */}
        {error && (
          <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: 10, padding: "14px 18px", marginBottom: 16, color: "#f87171", fontSize: 13 }}>
            ⚠️ {error}
          </div>
        )}

        {/* ── PRICE TABLE ── */}
        <div style={{ background: "#0a1120", borderRadius: 14, border: "1px solid #0f2040",
          overflow: "hidden" }}>

          {/* Legend */}
          <div style={{ padding: "10px 20px", borderBottom: "1px solid #0f2040",
            display: "flex", gap: 20, fontSize: 11, color: "#1e3a5f", fontFamily: "IBM Plex Mono" }}>
            <span>🟡 Tham chiếu &nbsp; 🔴 Giá trần (+{EXCHANGE_LIMITS.HOSE*100}%/HOSE) &nbsp; 🟢 Giá sàn (-{EXCHANGE_LIMITS.HOSE*100}%/HOSE)</span>
            <span style={{ marginLeft: "auto" }}>Click hàng để xem chi tiết</span>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #0f2040" }}>
                  {[
                    { k: "ticker",  l: "Mã CP",         w: 120 },
                    { k: null,      l: "Sàn ▼",          w: 90, color: "#22c55e" },
                    { k: null,      l: "Tham chiếu",     w: 90, color: "#f59e0b" },
                    { k: null,      l: "Trần ▲",          w: 90, color: "#ef4444" },
                    { k: null,      l: "Giá hiện tại",   w: 100 },
                    { k: "change",  l: "% Thay đổi",     w: 90 },
                    { k: null,      l: "Biên độ ngày",   w: 130 },
                    { k: "volume",  l: "KL khớp",        w: 80 },
                    { k: "rsi",     l: "RSI(14)",         w: 90 },
                    { k: null,      l: "SMA 20",         w: 80 },
                    { k: null,      l: "Giá mua vào 💡", w: 105 },
                    { k: "upside",  l: "Giá bán ra 🎯",  w: 105 },
                    { k: null,      l: "Tín hiệu",       w: 80 },
                    { k: null,      l: "",               w: 36 },
                  ].map((col) => (
                    <th key={col.l || col.k || Math.random()}
                      onClick={() => col.k && setSortBy(col.k)}
                      style={{ padding: "10px 12px", textAlign: col.l === "Mã CP" ? "left" : "right",
                        color: col.color || (col.k ? "#475569" : "#2d3f57"),
                        fontWeight: 600, fontSize: 10, letterSpacing: 0.3,
                        cursor: col.k ? "pointer" : "default", whiteSpace: "nowrap",
                        userSelect: "none", minWidth: col.w,
                        background: sortBy === col.k ? "rgba(59,130,246,0.05)" : "transparent",
                      }}>
                      {col.l}{sortBy === col.k ? " ↓" : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading && Object.keys(stockData).length === 0
                  ? Array(8).fill(0).map((_, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #0a1525" }}>
                      {Array(14).fill(0).map((_, j) => (
                        <td key={j} style={{ padding: "12px", textAlign: "right" }}>
                          <div style={{ height: 12, background: "#0f2040", borderRadius: 3,
                            width: j === 0 ? 60 : Math.random() * 40 + 30, marginLeft: "auto",
                            animation: "pulse 1.2s infinite" }} />
                        </td>
                      ))}
                    </tr>
                  ))
                  : sortedData.length === 0
                  ? (
                    <tr><td colSpan={14} style={{ padding: 40, textAlign: "center", color: "#1e3a5f" }}>
                      Không có dữ liệu
                    </td></tr>
                  )
                  : sortedData.map((s) => {
                    const changeColor = getChangeColor(s.changePct);
                    const isFloor    = s.close <= s.san;
                    const isCeiling  = s.close >= s.tran;
                    const rowBg = isFloor ? "rgba(34,197,94,0.03)" : isCeiling ? "rgba(239,68,68,0.03)" : "transparent";
                    const upside = s.sellPrice && s.close ? ((s.sellPrice - s.close) / s.close * 100) : null;

                    return (
                      <tr key={s.ticker}
                        onClick={() => setSelectedStock(s)}
                        style={{ borderBottom: "1px solid #0a1525", cursor: "pointer",
                          background: rowBg, transition: "background 0.15s" }}>

                        {/* Mã CP */}
                        <td style={{ padding: "11px 12px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                            <span style={{ fontSize: 14 }}>{s.flag}</span>
                            <div>
                              <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700,
                                fontSize: 13, color: "#e2e8f0" }}>{s.ticker}</div>
                              <div style={{ display: "flex", gap: 4, alignItems: "center", marginTop: 2 }}>
                                <ExchangeBadge exchange={s.exchange} />
                                <span style={{ color: "#1e3a5f", fontSize: 9 }}>{s.sector}</span>
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Sàn */}
                        <td style={{ padding: "11px 12px", textAlign: "right",
                          fontFamily: "IBM Plex Mono", fontSize: 12,
                          color: isFloor ? "#22c55e" : "#1a4a2e",
                          fontWeight: isFloor ? 800 : 400 }}>
                          {fmtPrice(s.san)}
                          {isFloor && <span style={{ fontSize: 9, display: "block", color: "#22c55e" }}>GIÁ SÀN</span>}
                        </td>

                        {/* Tham chiếu */}
                        <td style={{ padding: "11px 12px", textAlign: "right",
                          fontFamily: "IBM Plex Mono", fontSize: 12, color: "#b45309", fontWeight: 600 }}>
                          {fmtPrice(s.thamChieu)}
                        </td>

                        {/* Trần */}
                        <td style={{ padding: "11px 12px", textAlign: "right",
                          fontFamily: "IBM Plex Mono", fontSize: 12,
                          color: isCeiling ? "#ef4444" : "#4a1a1a",
                          fontWeight: isCeiling ? 800 : 400 }}>
                          {fmtPrice(s.tran)}
                          {isCeiling && <span style={{ fontSize: 9, display: "block", color: "#ef4444" }}>GIÁ TRẦN</span>}
                        </td>

                        {/* Giá hiện tại */}
                        <td style={{ padding: "11px 12px", textAlign: "right" }}>
                          <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 800,
                            fontSize: 14, color: changeColor }}>
                            {fmtPrice(s.close)}
                          </div>
                          <div style={{ fontSize: 10, color: "#1e3a5f", fontFamily: "IBM Plex Mono" }}>
                            H:{fmtPrice(s.high)} L:{fmtPrice(s.low)}
                          </div>
                        </td>

                        {/* % Thay đổi */}
                        <td style={{ padding: "11px 12px", textAlign: "right" }}>
                          <span style={{ fontFamily: "IBM Plex Mono", fontWeight: 700,
                            fontSize: 13, color: changeColor,
                            background: changeColor + "18", padding: "2px 7px", borderRadius: 4 }}>
                            {fmtPct(s.changePct)}
                          </span>
                        </td>

                        {/* Price Bar */}
                        <td style={{ padding: "11px 16px 11px 12px", minWidth: 130 }}>
                          <PriceBar pct={s.priceBarPct} {...s} />
                        </td>

                        {/* Khối lượng */}
                        <td style={{ padding: "11px 12px", textAlign: "right",
                          fontFamily: "IBM Plex Mono", fontSize: 12, color: "#334155" }}>
                          {fmtVol(s.volume)}
                        </td>

                        {/* RSI */}
                        <td style={{ padding: "11px 12px", textAlign: "right" }}>
                          <RSIBar value={s.rsi} />
                        </td>

                        {/* SMA20 */}
                        <td style={{ padding: "11px 12px", textAlign: "right",
                          fontFamily: "IBM Plex Mono", fontSize: 12,
                          color: s.close > s.sma20 ? "#22c55e" : "#ef4444" }}>
                          {fmtPrice(s.sma20)}
                        </td>

                        {/* Giá mua */}
                        <td style={{ padding: "11px 12px", textAlign: "right" }}>
                          <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700,
                            fontSize: 13, color: "#22c55e" }}>
                            {fmtPrice(s.buyPrice)}
                          </div>
                        </td>

                        {/* Giá bán */}
                        <td style={{ padding: "11px 12px", textAlign: "right" }}>
                          <div style={{ fontFamily: "IBM Plex Mono", fontWeight: 700,
                            fontSize: 13, color: "#ef4444" }}>
                            {fmtPrice(s.sellPrice)}
                          </div>
                          {upside !== null && (
                            <div style={{ fontSize: 10, color: "#16a34a",
                              fontFamily: "IBM Plex Mono" }}>
                              +{upside.toFixed(1)}%
                            </div>
                          )}
                        </td>

                        {/* Tín hiệu */}
                        <td style={{ padding: "11px 12px", textAlign: "right" }}>
                          <SignalBadge signal={s.signal} />
                        </td>

                        {/* Remove */}
                        <td style={{ padding: "11px 8px", textAlign: "center" }}>
                          <button
                            onClick={e => { e.stopPropagation(); handleRemove(s.ticker); }}
                            style={{ background: "none", border: "1px solid #1e3a5f",
                              color: "#1e3a5f", borderRadius: 4, width: 22, height: 22,
                              cursor: "pointer", fontSize: 11, lineHeight: 1 }}>✕</button>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── LEGEND ── */}
        <div style={{ marginTop: 14, display: "flex", gap: 20, flexWrap: "wrap",
          fontSize: 11, color: "#1e3a5f", fontFamily: "IBM Plex Mono" }}>
          <span>📌 HOSE: ±7% &nbsp;|&nbsp; HNX: ±10% &nbsp;|&nbsp; UPCoM: ±15%</span>
          <span>🟡 Đường vàng = giá tham chiếu trên thanh biên độ</span>
          <span>💡 Giá mua/bán dựa trên RSI + SMA20 — chỉ mang tính tham khảo</span>
          <span style={{ marginLeft: "auto" }}>Nguồn: TradingView Scanner API · Tự động làm mới mỗi 30 giây</span>
        </div>
      </div>

      {selectedStock && <DetailModal stock={selectedStock} onClose={() => setSelectedStock(null)} />}
    </div>
  );
}
