# Stakeholder Register
## NewTradingOS v14.0

**PMBOK Knowledge Area:** Stakeholder Management  
**Process Group:** Initiating → Monitoring & Controlling  
**Document Version:** 2.0  
**Date:** 2026-05-30

---

## 1. Stakeholder Identification

| ID | Stakeholder | Role | Organisation | Location |
|---|---|---|---|---|
| SH-001 | Captain Seventh | Project Owner, Developer, Primary User | Individual | Vietnam |
| SH-002 | Claude Sonnet 4.6 (Copilot) | AI Development Partner | Anthropic / GitHub | Remote |
| SH-003 | Vietnamese Retail Investors (archetype) | Indirect Beneficiary / Target User | — | Vietnam |
| SH-004 | Vietnam Securities Commission (SSC) | Regulatory Authority | Government | Hanoi, Vietnam |
| SH-005 | HoSE (Ho Chi Minh Stock Exchange) | Market Operator | Exchange | HCM City, Vietnam |
| SH-006 | HNX (Hanoi Stock Exchange) | Market Operator | Exchange | Hanoi, Vietnam |
| SH-007 | DNSE Securities | Primary Data Provider | FinTech | Vietnam |
| SH-008 | SSI Securities | Secondary Data Provider (API fallback) | Brokerage | Vietnam |
| SH-009 | CafeF | Tertiary Data Provider (HTML fallback) | Media / FinTech | Vietnam |
| SH-010 | Yahoo Finance | World Market Data Provider | Yahoo Inc. | USA |

---

## 2. Stakeholder Analysis Matrix

| ID | Stakeholder | Power | Interest | Quadrant | Engagement Level |
|---|---|---|---|---|---|
| SH-001 | Captain Seventh | High | High | **Manage Closely** | Lead — all decisions |
| SH-002 | Claude Sonnet 4.6 | High | High | **Manage Closely** | Collaborative implementation partner |
| SH-003 | VN Retail Investors | Low | High | **Keep Informed** | Inform via UI clarity, Guide, disclaimers |
| SH-004 | SSC | High | Low | **Keep Satisfied** | Comply — no automated execution; show risk disclaimers |
| SH-005 | HoSE | High | Low | **Keep Satisfied** | Comply — price limit rules encoded; no scraping abuse |
| SH-006 | HNX | Medium | Low | **Monitor** | Comply — HNX limit (±10%) correctly applied |
| SH-007 | DNSE | Medium | Low | **Monitor** | Respect API rate limits; handle HTTP errors gracefully |
| SH-008 | SSI | Medium | Low | **Monitor** | Use as fallback only; respect TOS |
| SH-009 | CafeF | Low | Low | **Monitor** | Minimal scraping; tertiary fallback only |
| SH-010 | Yahoo Finance | Low | Low | **Monitor** | 8 symbols only; comply with free-tier limits |

**Quadrant Definitions (Power/Interest Grid):**
- **Manage Closely** (High Power / High Interest) — Full engagement; involve in all decisions
- **Keep Satisfied** (High Power / Low Interest) — Compliance focus; no conflict
- **Keep Informed** (Low Power / High Interest) — Regular information; transparency
- **Monitor** (Low Power / Low Interest) — Watch for changes; minimal engagement

---

## 3. Stakeholder Engagement Plan

### SH-001 — Captain Seventh (Owner / Developer / User)

| Attribute | Detail |
|---|---|
| Interests | Accurate trading signals for VN market; fast development cycles; reliable ML forecasting |
| Influence | Complete decision authority over scope, architecture, and release |
| Concerns | Model accuracy, API reliability, performance, regulatory compliance |
| Engagement Strategy | Primary decision-maker. All design decisions validated against user experience. GUIDE.md maintained as end-user reference. |
| Communication | Direct — VS Code Copilot chat session |

---

### SH-002 — Claude Sonnet 4.6 (AI Development Partner)

| Attribute | Detail |
|---|---|
| Interests | Accurate implementation; clean, maintainable code; comprehensive test coverage |
| Influence | High — proposes and implements all code changes |
| Concerns | Correctness of VN-specific financial logic; OWASP compliance; test integrity |
| Engagement Strategy | Collaborative — all changes reviewed against requirements and tests before finalisation. Session memory maintained for continuity. |
| Communication | GitHub Copilot Chat (VS Code) |

---

### SH-003 — Vietnamese Retail Investor (Target User Archetype)

| Attribute | Detail |
|---|---|
| Profile | Self-directed investor trading HoSE/HNX equities; limited access to institutional tools |
| Interests | Clear BUY/HOLD/SELL signals; understandable score breakdown; capital protection guidance |
| Influence | Low (indirect; represents the application's purpose) |
| Concerns | Misinterpreting signals as guaranteed advice; over-reliance on ML forecasts |
| Engagement Strategy | Clear risk disclaimers in Guide tab; score breakdown shown for every signal; "DECISION SUPPORT ONLY — NOT FINANCIAL ADVICE" banner recommended |

---

### SH-004 — Vietnam Securities Commission (SSC)

| Attribute | Detail |
|---|---|
| Interests | Market integrity; investor protection; regulatory compliance |
| Influence | High — rule changes (T+1, price limits) require code updates |
| Concerns | Automated trading tools circumventing rules; market manipulation facilitation |
| Engagement Strategy | No automated order execution; strict price-limit encoding; track SSC announcements for T+1 migration date |
| Monitored Announcements | T+1 settlement implementation timeline; changes to ±7% HoSE limit |

---

### SH-007 – SH-010 — Data Providers

| Provider | API Type | Rate Limit Risk | Mitigation |
|---|---|---|---|
| DNSE | REST JSON | Moderate | 6s timeout; fallback chain; retry once |
| SSI | REST JSON | Low | Fallback only; no high-frequency calls |
| CafeF | HTML scrape | High (fragile) | Tertiary fallback; minimal calls; snapshot test fixtures |
| Yahoo Finance | yfinance / REST | Low | 8 symbols; once per session; cache result |

---

## 4. Key Stakeholder Dates

| Date | Event | Affected Stakeholders |
|---|---|---|
| Q3 2026 (est.) | SSC T+1 settlement implementation | SH-001, SH-004, SH-005 |
| Ongoing | DNSE/SSI API monitoring | SH-001, SH-007, SH-008 |
| Quarterly | Backtesting / model accuracy review | SH-001, SH-002 |
| Semi-annually | Indicator relevance review vs VN market evolution | SH-001, SH-002 |

---

## 5. Communication Matrix

| From | To | Channel | Frequency | Content |
|---|---|---|---|---|
| SH-001 | SH-002 | Copilot Chat | As needed | Feature requests, bug reports, design decisions |
| SH-002 | SH-001 | Copilot Chat | Synchronous | Implementation updates, risk flags, test results |
| SH-004/SH-005 | SH-001 | SSC/HoSE website | Monitor monthly | Regulatory updates (T+1, price limits, disclosure rules) |
| SH-007/SH-008 | SH-001 | API error responses | Automated | HTTP 4xx/5xx signals API changes |
