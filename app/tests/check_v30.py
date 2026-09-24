import os
"""v29/v30 assertion checker — run: python check_v30.py"""
import ast, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'quant_app.py'), 'r', encoding='utf-8') as f:
    src = f.read()

# AST check
try:
    ast.parse(src)
    lines = src.count('\n')
    print(f'AST OK — {lines} lines')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
    sys.exit(1)

chk_pass = 0
chk_fail = 0
def chk(desc, cond):
    global chk_pass, chk_fail
    if cond:
        chk_pass += 1
    else:
        chk_fail += 1
        print(f'  FAIL: {desc}')

# Navigation
chk('nav_section in session_state', 'nav_section' in src)
chk('sidebar nav_section_radio', 'nav_section_radio' in src)
chk('render_start_tab called', 'render_start_tab()' in src)
chk('render_scanner_tab called', 'render_scanner_tab()' in src)
chk('render_stock_profiler_tab called', 'render_stock_profiler_tab()' in src)
chk('render_portfolio_tab called', 'render_portfolio_tab()' in src)
chk('render_backtest_tab called', 'render_backtest_tab()' in src)
chk('render_changelog_tab called', 'render_changelog_tab()' in src)

# F0
chk('f0_mode = True default', 'f0_mode = True' in src or "f0_mode', True" in src)
chk('f0_mode_toggle key', 'f0_mode_toggle' in src)
chk('f0_visited_tabs initialized', 'f0_visited_tabs' in src)
chk('def f0_tab_banner', 'def f0_tab_banner' in src)
chk('def render_start_tab', 'def render_start_tab' in src)

# CSS
chk('GLOBAL_CSS defined', 'GLOBAL_CSS = ' in src or "GLOBAL_CSS=" in src)
chk('GLOBAL_CSS injected', 'st.markdown(GLOBAL_CSS' in src)
chk('badge-buy in CSS', 'badge-buy' in src)
chk('badge-sell in CSS', 'badge-sell' in src)
chk('f0-card in CSS', 'f0-card' in src)
chk('def signal_badge', 'def signal_badge' in src)
chk('def f0_explain', 'def f0_explain' in src)

# Tooltips (15 keys)
for key in ['EPS','BVPS','PB','DCF','Graham','Stop_Loss','RR','CGT',
            'T2','NPL','NIM','Golden_Cross','Death_Cross','Swing_Trade','Tech_Score']:
    chk(f'TOOLTIPS has {key}', f'"{key}"' in src)

# v30 parser
chk('def parse_ssi_portfolio_xlsx', 'def parse_ssi_portfolio_xlsx' in src)
chk('def _clean_num', 'def _clean_num' in src)
chk('PORTFOLIO_COLUMNS', 'PORTFOLIO_COLUMNS' in src)

# Metrics & tax
chk('def compute_portfolio_metrics', 'def compute_portfolio_metrics' in src)
chk('def compute_portfolio_tax', 'def compute_portfolio_tax' in src)
chk('total_tax used', 'total_tax' in src)

# Scenarios
chk('def project_portfolio_scenario', 'def project_portfolio_scenario' in src)
chk('SECTOR_BETA defined', 'SECTOR_BETA = {' in src)
chk('SCENARIO_DEFINITIONS defined', 'SCENARIO_DEFINITIONS = [' in src)
chk('S1 vni_pct 10.0', '"vni_pct": 10.0' in src)
chk('S2 vni_pct 0.5', '"vni_pct": 0.5' in src)
chk('S3 vni_pct -18.0', '"vni_pct": -18.0' in src)

# TP/CL
chk('def generate_tp_plan', 'def generate_tp_plan' in src)
chk('TP_ALLOCATION_RULES', 'TP_ALLOCATION_RULES = {' in src)
chk('def generate_cl_plan', 'def generate_cl_plan' in src)
chk('def recovery_pct_needed', 'def recovery_pct_needed' in src)
chk('break-even guard abs<0.5', 'abs(pnl_pct) < 0.5' in src)

# Audit
chk('def save_portfolio_audit', 'def save_portfolio_audit' in src)
chk('def load_portfolio_audit', 'def load_portfolio_audit' in src)
chk('def compute_portfolio_delta', 'def compute_portfolio_delta' in src)
chk('PORTFOLIO_AUDIT_PATH', 'PORTFOLIO_AUDIT_PATH' in src)

# C-01: IV source
chk('C-01 iv_source field', 'iv_source' in src)

# C-02: T+2 terminology
chk('C-02 LOCKED_STATUS', 'LOCKED_STATUS_VI' in src)
chk('C-02 T+2 settlement', 'T+2 settlement' in src or 'thanh toan T+2' in src)

# C-03: empirical beta
chk('C-03 pessimistic Chung khoan 2.20', '2.20' in src)
chk('C-03 SECTOR_BETA_DISCLAIMER', 'SECTOR_BETA_DISCLAIMER' in src)

# C-04: circuit breakers
chk('C-04 exchange param in CL', 'exchange: str' in src)
chk('C-04 EXCHANGE_BANDS', 'EXCHANGE_BANDS = {' in src)
chk('C-04 def round_price_exchange', 'def round_price_exchange' in src)

# C-05: Graham
chk('C-05 VN_GRAHAM_MULTIPLIER', 'VN_GRAHAM_MULTIPLIER' in src)

# C-06: forecast disclosure
chk('C-06 FORECAST_CONFIDENCE', 'FORECAST_CONFIDENCE = {' in src)
chk('C-06 RECOVERY_TIME_ESTIMATE', 'RECOVERY_TIME_ESTIMATE = {' in src)

# C-07: legal
chk('C-07 LEGAL_DISCLAIMER_VI', 'LEGAL_DISCLAIMER_VI' in src)
chk('C-07 consent checkbox', 'portfolio_data_consent' in src)
chk('C-07 Article 211', 'Article 211' in src or '211' in src)

# H-04: FOL
chk('H-04 get_fol_status', 'def get_fol_status' in src)
chk('H-04 KNOWN_FOL_RESTRICTIONS', 'KNOWN_FOL_RESTRICTIONS' in src)
chk('H-04 HVN 0.0', '"HVN": 0.0' in src or "'HVN': 0.0" in src)

# H-08: sector override
chk('H-08 SECTOR_OVERRIDE', 'SECTOR_OVERRIDE = {' in src)
chk('H-08 TCH PGC VGC in override', '"TCH"' in src and '"PGC"' in src and '"VGC"' in src)

# H-11: session recovery
chk('H-11 _persist_portfolio_session', 'def _persist_portfolio_session' in src)
chk('H-11 _restore_portfolio_session', 'def _restore_portfolio_session' in src)

# Other
chk('M-03 n_winning in audit', 'n_winning' in src)
chk('ENH-56 import_portfolio_to_watchlist', 'def import_portfolio_to_watchlist' in src)
chk('v30 version string in docstring', 'v30.0' in src)
chk('v30 in app_title VI', 'TERMINAL v30.0' in src)

print(f'\nTotal: {chk_pass} PASS, {chk_fail} FAIL')
