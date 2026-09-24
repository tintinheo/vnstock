"""backtest/report.py – Generate HTML backtest report."""
import os
from config.settings import REPORT_DIR

def generate_html_report(result, output_path=None):
    if output_path is None:
        os.makedirs(REPORT_DIR, exist_ok=True)
        output_path = os.path.join(REPORT_DIR, f"backtest_{result.get('ticker','X')}_{result.get('strategy','ALL')}.html")
    m = result.get("metrics",{}); trades = result.get("trades",[]); eq = result.get("equity_curve",[])
    if eq:
        mn,mx=min(eq),max(eq); rng=mx-mn if mx>mn else 1; w,h=600,150
        pts=[f"{i/max(len(eq)-1,1)*w:.1f},{h-(v-mn)/rng*h:.1f}" for i,v in enumerate(eq)]
        svg=f'<svg width="{w}" height="{h}" style="background:#f9f9f9"><polyline points="{" ".join(pts)}" fill="none" stroke="#2196F3" stroke-width="2"/></svg>'
    else: svg="<p>No data</p>"
    trade_rows="".join(f'<tr><td>{t.get("date","")}</td><td>{t.get("action","")}</td><td>{t.get("ticker","")}</td><td>{t.get("shares","")}</td><td>{t.get("price",0):,.0f}</td><td style="color:{"green" if t.get("pnl",0)>0 else "red"}">{t.get("pnl",""):,.0f}</td></tr>' for t in trades[-50:] if isinstance(t.get("pnl",0),(int,float)))
    html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Backtest Report</title>
<style>body{{font-family:Arial;margin:20px}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}}.metric{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:15px;text-align:center}}.metric .value{{font-size:24px;font-weight:bold;color:#1a237e}}.metric .label{{font-size:12px;color:#666}}table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border:1px solid #ddd;text-align:center}}th{{background:#3f51b5;color:#fff}}</style></head>
<body><h1>Backtest Report – {result.get('ticker','')} {result.get('strategy','')}</h1>
<div class="metrics">
<div class="metric"><div class="value">{m.get('total_return_pct',0):.1f}%</div><div class="label">Total Return</div></div>
<div class="metric"><div class="value">{m.get('sharpe_ratio',0):.2f}</div><div class="label">Sharpe</div></div>
<div class="metric"><div class="value">{m.get('max_drawdown_pct',0):.1f}%</div><div class="label">Max DD</div></div>
<div class="metric"><div class="value">{m.get('win_rate_pct',0):.0f}%</div><div class="label">Win Rate</div></div>
<div class="metric"><div class="value">{m.get('profit_factor',0):.2f}</div><div class="label">Profit Factor</div></div>
<div class="metric"><div class="value">{m.get('total_trades',0)}</div><div class="label">Trades</div></div>
<div class="metric"><div class="value">{m.get('cagr_pct',0):.1f}%</div><div class="label">CAGR</div></div>
<div class="metric"><div class="value">{m.get('sortino_ratio',0):.2f}</div><div class="label">Sortino</div></div>
</div><h2>Equity Curve</h2>{svg}
<h2>Trades</h2><table><tr><th>Date</th><th>Action</th><th>Ticker</th><th>Shares</th><th>Price</th><th>P&L</th></tr>{trade_rows}</table>
<p style="color:#999;font-size:11px">Vietnam AI Trading System v3 | Simulation only</p></body></html>"""
    with open(output_path,"w",encoding="utf-8") as f: f.write(html)
    return output_path
