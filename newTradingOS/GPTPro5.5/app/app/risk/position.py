def position_size(nav, risk_pct, entry, stop):
    risk_budget=nav*risk_pct; per_share=max(entry-stop, entry*.005); qty=int(risk_budget//per_share); return {"risk_budget":risk_budget,"risk_per_share":per_share,"quantity":qty,"position_value":qty*entry,"position_pct_nav":qty*entry/nav if nav else 0}
