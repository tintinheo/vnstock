# NewTradingOS v14.0 — Project Documentation

**Vietnam Multi-Timeframe Trading Platform**  
Documentation follows **PMBOK® Guide 7th Edition** process groups and knowledge areas.

---

## Document Index

| # | Document | PMBOK Knowledge Area | Status |
|---|---|---|---|
| 01 | [Project Charter](01-project-charter.md) | Integration Management | Approved |
| 02 | [Scope Baseline & WBS](02-scope-and-wbs.md) | Scope Management | Baselined |
| 03 | [Requirements Traceability Matrix](03-requirements.md) | Scope Management | Baselined |
| 04 | [Architecture & Technical Design](04-architecture.md) | — (Technical Baseline) | Current |
| 05 | [Risk Register](05-risk-register.md) | Risk Management | Active |
| 06 | [Quality Management Plan](06-quality-management-plan.md) | Quality Management | Active |
| 07 | [Stakeholder Register](07-stakeholder-register.md) | Stakeholder Management | Current |

---

## Project Snapshot

| Field | Value |
|---|---|
| Project Name | NewTradingOS |
| Version | 14.0 |
| Platform | Vietnam Stock Market (HOSE / HNX / UPCoM) |
| Technology | Python 3.13 · Streamlit 1.55 |
| Automated Tests | 407 passed (`pytest tests/ -q --tb=short`, 2026-05-31) |
| Project Start | 2025-Q1 |
| Last Updated | 2026-05-31 |

---

## Folder Structure

```
docs/
├── README.md                      ← This file (document index)
├── 01-project-charter.md          ← Project authorisation & objectives
├── 02-scope-and-wbs.md            ← WBS + scope statement
├── 03-requirements.md             ← RTM: functional & non-functional requirements
├── 04-architecture.md             ← System architecture & component design
├── 05-risk-register.md            ← Identified risks, probability, response
├── 06-quality-management-plan.md  ← Testing strategy, coding standards, KPIs
└── 07-stakeholder-register.md     ← Stakeholders, interests, engagement
```
