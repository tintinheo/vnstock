"""risk/portfolio.py – Portfolio allocation, rebalancing, drawdown monitoring."""
import pandas as pd
from typing import Dict, List
from config.settings import TRADING

class Portfolio:
    def __init__(self, initial_capital=None):
        self.initial_capital = initial_capital or TRADING["initial_capital"]
        self.cash = self.initial_capital; self.positions = {}; self.history = []; self.peak_value = self.initial_capital

    @property
    def total_value(self):
        return self.cash + sum(p["shares"]*p.get("current_price",p["entry_price"]) for p in self.positions.values())

    @property
    def drawdown(self):
        return (self.peak_value - self.total_value) / self.peak_value if self.peak_value else 0

    def update_peak(self):
        if self.total_value > self.peak_value: self.peak_value = self.total_value

    def buy(self, ticker, price, shares, date=""):
        commission = price*shares*TRADING["commission_rate"]; total_cost = price*shares+commission
        if total_cost > self.cash:
            shares = int(self.cash / (price*(1+TRADING["commission_rate"])))
            if shares <= 0: return {"status":"rejected","reason":"insufficient_cash"}
            commission = price*shares*TRADING["commission_rate"]; total_cost = price*shares+commission
        self.cash -= total_cost
        if ticker in self.positions:
            old=self.positions[ticker]; ts=old["shares"]+shares; avg=(old["entry_price"]*old["shares"]+price*shares)/ts
            self.positions[ticker] = {**old,"shares":ts,"entry_price":avg,"current_price":price}
        else:
            self.positions[ticker] = {"shares":shares,"entry_price":price,"current_price":price,"entry_date":date,"highest_price":price,"days_held":0}
        trade = {"action":"BUY","ticker":ticker,"shares":shares,"price":price,"commission":commission,"date":date,"portfolio_value":self.total_value}
        self.history.append(trade); self.update_peak(); return {"status":"filled",**trade}

    def sell(self, ticker, price, shares=None, date=""):
        if ticker not in self.positions: return {"status":"rejected","reason":"no_position"}
        pos = self.positions[ticker]
        if shares is None: shares = pos["shares"]
        shares = min(shares, pos["shares"])
        commission = price*shares*TRADING["commission_rate"]; tax = price*shares*TRADING["tax_rate"]
        pnl = (price-pos["entry_price"])*shares - commission - tax
        self.cash += price*shares - commission - tax
        if shares >= pos["shares"]: del self.positions[ticker]
        else: self.positions[ticker]["shares"] -= shares
        trade = {"action":"SELL","ticker":ticker,"shares":shares,"price":price,"commission":commission,"tax":tax,"pnl":pnl,"date":date,"portfolio_value":self.total_value}
        self.history.append(trade); self.update_peak(); return {"status":"filled",**trade}

    def update_prices(self, prices):
        for t, p in prices.items():
            if t in self.positions:
                self.positions[t]["current_price"]=p
                if p > self.positions[t].get("highest_price",0): self.positions[t]["highest_price"]=p
                self.positions[t]["days_held"] = self.positions[t].get("days_held",0)+1
        self.update_peak()

    def get_allocation(self):
        if not self.positions: return pd.DataFrame(columns=["ticker","shares","value","weight"])
        rows = []; tv = self.total_value
        for t,p in self.positions.items():
            val=p["shares"]*p.get("current_price",p["entry_price"])
            rows.append({"ticker":t,"shares":p["shares"],"entry_price":p["entry_price"],"current_price":p.get("current_price",p["entry_price"]),"value":val,"weight":val/tv if tv>0 else 0})
        return pd.DataFrame(rows)

    def summary(self):
        return {"total_value":round(self.total_value,0),"cash":round(self.cash,0),"positions_count":len(self.positions),
                "total_return_pct":round((self.total_value/self.initial_capital-1)*100,2),"max_drawdown_pct":round(self.drawdown*100,2),"total_trades":len(self.history)}
