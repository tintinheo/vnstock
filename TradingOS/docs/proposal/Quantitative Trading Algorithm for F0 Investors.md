## **Quantitative Trading Algorithm for F0 Investors**

# **Quantitative Investment Strategy and Automated Trading System Development for the Vietnam Stock Market: A Comprehensive Report from the Academic Board and Technology Experts**

## **Strategic Vision and Macroeconomic Context of Vietnam 2025-2026**

The Vietnamese stock market is entering a historic transformation phase, driven by the convergence of regulatory reforms, technological infrastructure upgrades, and a surge in credit flows. As an Academic Board comprising Professors of Computational Finance, Senior Quantitative Traders, and Technology Directors, this report establishes a comprehensive roadmap for developing an automated trading system optimized for the T+2.5 settlement mechanism and strictly adhering to international management standards.

The macroeconomic backdrop in 2025 recorded impressive growth, with Q3 GDP reaching 8.23%, the second-highest rate in the 2011-2025 period.1 This stability is reinforced by committed FDI inflows of $28.54 billion in the first nine months, reflecting strong international investor confidence in the domestic business environment.1 Notably, the credit boom, with approximately VND 2.6 quadrillion injected into the economy in 2025, has created unprecedented liquidity momentum, with average daily trading values on the stock market hitting VND 29.5 trillion.2

| Macro Indicators | Recorded Values (2025) | Significance for the Stock Market |
| :---- | :---- | :---- |
| GDP Growth | 8.23% (Q3/2025) | Solid foundation for corporate profit growth 1 |
| Credit Growth | 16.56% (as of November) | Ample money supply driving asset valuations 2 |
| Market Capitalization | \>VND 9.68 quadrillion (\~$387B) | Market size equivalent to 84.1% of 2024 GDP 3 |
| Number of Accounts | \>11 million accounts | Massive surge in retail (F0) investors 3 |

The roadmap for a market upgrade from "Frontier" to "Secondary Emerging" status by FTSE Russell in September 2026 is the most critical catalyst.1 This requires trading systems to achieve absolute precision and the capability to process data at scale to accommodate the anticipated influx of foreign capital into the large-cap stocks of the VN30 index.4

## **Analysis of the T+2.5 Settlement Mechanism and High-Frequency Dynamics**

The shortening of the settlement cycle from T+3 to T+2.5 (officially applied since August 2022\) has completely transformed the behavioral structure of the market.6 Under the new regulations, securities and cash are transferred to investor accounts between 11:30 AM and 12:30 PM on the T+2 day, allowing them to execute trades during the afternoon session of the same day.6

This mechanism creates a "liquidity singularity" at 1:00 PM (13:00) daily. Research on high-frequency data in Vietnam reveals that the intraday volatility pattern follows a modified U-shape, with a sharp peak appearing immediately at the afternoon opening.8 This phenomenon is the result of the simultaneous release of buy positions from T+0, combined with information accumulation and psychological expectations during the midday break.8 For F0 investors, this is a prime time for behavioral biases due to short-term profit-taking or stop-loss pressures, creating inefficiencies that quantitative algorithms can exploit.8

| Time Milestone | T+2.5 Process (Current) | Strategic Impact |
| :---- | :---- | :---- |
| T+0 | Execution of buy/sell trade | Establishing the base position |
| T+2 (11:30-12:30) | VSDC completes clearing & asset transfer | Shares available to sell in the afternoon 6 |
| T+2 (13:00) | Afternoon session opening | Liquidity explosion, sharp price volatility 8 |
| T+3 | Start of a new trading cycle | Completion of the financial circuit |

This inefficiency is further amplified by the fact that over 80% of trading volume comes from retail investors, who frequently overreact to noisy signals.8 The proposed algorithm focuses on identifying reversal or trend-continuation signals at the 13:00 threshold based on information and liquidity asymmetry.8

## **Proposed Quantitative Trading Algorithm for F0 Investors**

Under the guidance of our Computational Finance Professors and Quantitative Trading Experts, we propose a Hybrid Algorithm combining Particle Swarm Optimization (PSO) with market-specific factor models for Vietnam (the VN-4 Model).

### **The VN-4 Multi-Factor Model and Stock Selection Strategy**

In-depth research into factors affecting returns in Vietnam shows that the traditional Fama-French 3-factor model is insufficient to explain abnormal fluctuations.12 Instead, the VN-4 model has proven to have superior explanatory power by integrating a Turnover factor.12

1. **Market Factor**: Reflects the general fluctuations of the VN-Index.  
2. **Size Factor**: Exploits the small-cap effect, where smaller companies often provide higher returns in emerging markets over the long term.12  
3. **Value Factor (EP)**: Uses the Earnings-to-Price (EP) ratio instead of Book-to-Market (BM), as EP is proven to be more sensitive to accounting and valuation specifics in Vietnam.12  
4. **Turnover Factor**: This acts as a proxy for investor attention and speculation. High-turnover stocks tend to yield lower future returns due to overreaction by the crowd, helping the algorithm filter out "overheated" stocks.12

### **Optimizing Technical Indicators with PSO (Particle Swarm Optimization)**

Rather than using fixed parameters for RSI or MACD, the system automatically adjusts parameter sets via the PSO algorithm to adapt to T+2.5 afternoon session volatility.14 The PSO algorithm simulates the behavior of bird flocks to search for optimal points in a multi-dimensional space, simultaneously optimizing three objectives:

* Maximizing Total Return.  
* Maximizing Win Rate.  
* Minimizing Number of Trades (to optimize taxes and fees).14

![][image1]  
![][image2]  
The position vector ![][image3] includes RSI parameters (period ![][image4], thresholds ![][image5]) and MACD parameters (periods ![][image6]).14 This optimization allows the algorithm to recognize whether the 13:00 volatility is a short-term Mean Reversion or a confirmation of a strong Momentum trend.14

## **Software Development Life Cycle (SDLC) according to PMBOK and BABOK Standards**

Constructing a quantitative trading application with absolute precision requires a tight integration of Project Management (PMBOK) and Business Analysis (BABOK). Under the direction of the Software Director and Delivery Manager, every feature must undergo rigorous control steps before release.

### **Project Management according to PMBOK (6th/7th Edition)**

We adopt a Hybrid SDLC model—Waterfall for core components and Agile for trading strategies.16

1. **Initiating Process Group**: Establishing a Project Charter that defines the goal as a "Zero-error automated trading system".18 Identifying constraints regarding the KRX infrastructure and SSC/VSDC regulations.3  
2. **Planning Process Group**: Building a Work Breakdown Structure (WBS) focusing on modules: Data Collection, Algorithm Calculation Engine, Risk Management, and Order Execution.20  
3. **Monitoring and Controlling Process Group**: Using milestones such as the completion of SSI API integration and the finalized backtesting of 5 years of historical data.18

### **Business Analysis according to BABOK (Version 3\)**

The Business Analyst (BA) team executes requirements elicitation through the Core Concept Model (BACCM), focusing on creating "Value" for F0 investors within the volatile Vietnamese market "Context".21

* **Elicitation & Collaboration**: BAs perform Document Analysis on SSI Fast Connect API technical specs and T+2.5 settlement rules to ensure business logic does not violate market rules.22  
* **Requirements Life Cycle Management**: Every requirement from the investment strategy (e.g., automated stop-loss when price hits the Kelly threshold) must be traceable from the design phase to User Acceptance Testing (UAT).22

### **Specific SDLC Phases for the Quant Trading App**

| Phase | Core Focus | Key Deliverables |
| :---- | :---- | :---- |
| Preliminary Analysis | Assessing technology and SSI data feasibility | Feasibility Report 17 |
| Systems Analysis | Defining T+2.5 and VN-4 algorithm logic | Business Requirements Document (BRD) 20 |
| Systems Design | Microservices architecture and SQL/NoSQL design | System Architecture Design 17 |
| Development | Python/Node.js programming with SSI SDK integration | Source Code & Unit Test Results 27 |
| Integration & Testing | Regression and stress testing for afternoon pressure | QA Report & Backtest Analysis 17 |
| Deployment | Parallel run with manual trading | Production System 17 |

## **Deep Integration of SSI Fast Connect API and Market Data**

To ensure "standardized, accurate, and up-to-date" performance, the system connects directly to the SSI Fast Connect API via two main product lines: FC Data and FC Trading.29

### **Connectivity Architecture and Security**

The integration process begins with setting up identity keys: ConsumerID, ConsumerSecret, and PrivateKey.29 The system uses the RSA algorithm with SHA256 signatures to ensure every outgoing order is authenticated and immutable.31

1. **FC Data (Market Data)**:  
   * Uses REST API to fetch security lists (/securities), financial report details (/securities\_details), and historical OHLCV data (/securities\_chart).32  
   * Uses WebSocket (Streaming) for low-latency real-time price updates. Subscribed channels include X (Best prices), B (Real-time OHLC candles), and MI (VN30 index).28  
2. **FC Trading (Automated Trading)**:  
   * Supports order placement (/NewOrder), modification (/ModifyOrder), and cancellation (/CancelOrder).27  
   * Manages portfolios (/portfolio) and assets (/asset) in real-time to update purchasing power and margin ratios.29

### **Typical JSON Data Structure from SSI**

The system must handle JSON response structures from SSI with high precision. For example, querying historical data for ticker "SSI" on HOSE:

JSON

{  
  "data":,  
  "status": 200,  
  "message": "Success"  
}

32

This data is fed into the PSO algorithm's calculation pipeline to make instantaneous trading decisions when market conditions satisfy the optimized parameters.28

## **Risk Management Strategy and Investor Psychology**

A perfect Quant Trading system lies not just in the entry-point algorithm but in its ability to protect capital through mathematical models and psychological bias control.

### **Position Optimization using the Kelly Criterion**

We apply the Kelly Criterion formula to determine the optimal capital size for each position, based on the win probability (![][image7]) and the reward-to-risk ratio (![][image8]) calculated from actual backtesting on SSI data.35

![][image9]  
Where ![][image10] is the probability of loss. To accommodate F0 investors who are often sensitive to volatility, the system applies a "Fractional Kelly" (e.g., Half-Kelly), which reduces volatility risk by 50% while retaining approximately 71% of the potential returns of the full Kelly level.35

### **Addressing Psychological Biases and Herding Behavior**

F0 investors in Vietnam are often influenced by:

* **Overconfidence**: Leading to over-trading and ignoring stop-loss rules.9  
* **Herding Behavior**: Following the crowd during liquidity surges at 13:00, often leading to buying at high prices.9  
* **Anchoring Bias**: Clinging to old peak prices without recognizing changes in macro factors.38

The fully automated system removes these psychological barriers. Orders are executed based on defined quantitative thresholds without emotional interference, ensuring absolute discipline—the key factor for success in the Vietnamese stock market.39

## **Transformation Roadmap and 2026 Vision: KRX System and FTSE Upgrade**

The Vietnamese stock market in 2026 will witness landmark changes with the official operation of the KRX technology system.3 This will not only accelerate order processing to millions of orders per second but also pave the way for new financial products such as day-trading (T+0) and short-selling.5

We advise that the Quant Trading system be built on an open architecture to integrate these features as soon as the legal framework allows. Holding the advantage of standardized SSI data and an algorithm proven through the T+2.5 cycle will be the solid foundation for F0 investors to become professional traders, ready for an "Emerging Market" with a capitalization expected to exceed $500 billion by the end of the decade.1

The Academic Board affirms that the combination of financial mathematics, standard software engineering, and deep local context understanding is the only path to achieving sustainable profits and absolute risk management in the era of digital trading in Vietnam.

#### **Works cited**

1. Vietnam's stock market's impressive momentum \- VnEconomy, accessed March 18, 2026, [https://en.vneconomy.vn/vietnams-stock-markets-impressive-momentum.htm](https://en.vneconomy.vn/vietnams-stock-markets-impressive-momentum.htm)  
2. Vietnam's credit boom may fuel explosive stock market rally in 2026 \- VietNamNet, accessed March 18, 2026, [https://vietnamnet.vn/en/vietnam-s-credit-boom-may-fuel-explosive-stock-market-rally-in-2026-2470649.html](https://vietnamnet.vn/en/vietnam-s-credit-boom-may-fuel-explosive-stock-market-rally-in-2026-2470649.html)  
3. Vietnam stock market ends 2025 at historic peak, enters new growth phase \- VietNamNet, accessed March 18, 2026, [https://vietnamnet.vn/en/vietnam-stock-market-ends-2025-at-historic-peak-enters-new-growth-phase-2474824.html](https://vietnamnet.vn/en/vietnam-stock-market-ends-2025-at-historic-peak-enters-new-growth-phase-2474824.html)  
4. 2026 Vietnam Stock Exchange (VN30, HOSE) API Integration Guide \- Medium, accessed March 18, 2026, [https://medium.com/@wutainfofu/2026-vietnam-stock-exchange-vn30-hose-api-integration-guide-072186b4ce0b](https://medium.com/@wutainfofu/2026-vietnam-stock-exchange-vn30-hose-api-integration-guide-072186b4ce0b)  
5. Vietnam's stock market enters its strongest transformation in a decade \- VietNamNet, accessed March 18, 2026, [https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html](https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html)  
6. Notice of Shortening the Settlement Time for Securities with T \+ 2 Settlement Cycle \- HSC, accessed March 18, 2026, [https://www.hsc.com.vn/en/notice-of-shortening-the-settlement-time-for-securities-with-t-2-settlement-cycle](https://www.hsc.com.vn/en/notice-of-shortening-the-settlement-time-for-securities-with-t-2-settlement-cycle)  
7. Investors to be able to trade stocks on T+2 settlement cycle \- Vietnam News, accessed March 18, 2026, [https://vietnamnews.vn/economy/1254864/investors-to-be-able-to-trade-stocks-on-t-2-settlement-cycle.html](https://vietnamnews.vn/economy/1254864/investors-to-be-able-to-trade-stocks-on-t-2-settlement-cycle.html)  
8. High-frequency dynamics of the Vietnam stock market \- ResearchGate, accessed March 18, 2026, [https://www.researchgate.net/publication/391206343\_High-frequency\_dynamics\_of\_the\_Vietnam\_stock\_market](https://www.researchgate.net/publication/391206343_High-frequency_dynamics_of_the_Vietnam_stock_market)  
9. The Effects of Psychology on Individual Investors' Behaviors: Evidence from the Vietnam Stock Exchange \- ResearchGate, accessed March 18, 2026, [https://www.researchgate.net/publication/271061780\_The\_Effects\_of\_Psychology\_on\_Individual\_Investors'\_Behaviors\_Evidence\_from\_the\_Vietnam\_Stock\_Exchange](https://www.researchgate.net/publication/271061780_The_Effects_of_Psychology_on_Individual_Investors'_Behaviors_Evidence_from_the_Vietnam_Stock_Exchange)  
10. The risk-return relationship in Vietnam's stock market: A weak connection, accessed March 18, 2026, [https://www.science-gate.com/IJAAS/2025/V12I9/1021833ijaas202509022.html](https://www.science-gate.com/IJAAS/2025/V12I9/1021833ijaas202509022.html)  
11. Investor Herding Behaviour and Stock Price Volatility: Evidence from Vietnam's Emerging Market during Global Economic Uncertainty \- JEFMS Journal, accessed March 18, 2026, [https://ijefm.co.in/v8i5/Doc/62.pdf](https://ijefm.co.in/v8i5/Doc/62.pdf)  
12. Factors and anomalies in the Vietnamese stock market, accessed March 18, 2026, [https://www.pbcsf.tsinghua.edu.cn/\_\_local/7/F5/A9/E0366D36DF73499C8CBFB66C505\_4D50779F\_1C1EEF.pdf](https://www.pbcsf.tsinghua.edu.cn/__local/7/F5/A9/E0366D36DF73499C8CBFB66C505_4D50779F_1C1EEF.pdf)  
13. Stock Selection for Trading Strategies Based on Risk Factors: A Study of The Ho Chi Minh Stock Exchange \- VU Research Repository, accessed March 18, 2026, [https://vuir.vu.edu.au/45929/1/PHAM\_Hoang\_Thach-Thesis\_nosignature.pdf](https://vuir.vu.edu.au/45929/1/PHAM_Hoang_Thach-Thesis_nosignature.pdf)  
14. Multi-objective optimization for algorithmic trading in the Vietnamese ..., accessed March 18, 2026, [https://beei.org/index.php/EEI/article/download/9288/4269](https://beei.org/index.php/EEI/article/download/9288/4269)  
15. (PDF) Momentum Effect in the Vietnamese Stock Market \- ResearchGate, accessed March 18, 2026, [https://www.researchgate.net/publication/257744813\_Momentum\_Effect\_in\_the\_Vietnamese\_Stock\_Market](https://www.researchgate.net/publication/257744813_Momentum_Effect_in_the_Vietnamese_Stock_Market)  
16. IT Project Management \- Aligning PMBOK Processes and SDLC \- Slideshare, accessed March 18, 2026, [https://www.slideshare.net/slideshow/it-project-management-aligning-pmbok-processes-and-sdlc/65348901](https://www.slideshare.net/slideshow/it-project-management-aligning-pmbok-processes-and-sdlc/65348901)  
17. Phases of the Systems Development Life Cycle | Hunter Business School Blog, accessed March 18, 2026, [https://hunterbusinessschool.edu/the-9-phases-of-the-systems-development-lifecycle-sdlc/](https://hunterbusinessschool.edu/the-9-phases-of-the-systems-development-lifecycle-sdlc/)  
18. Project managing the SDLC \- PMI.org, accessed March 18, 2026, [https://www.pmi.org/learning/library/project-managing-sdlc-8232](https://www.pmi.org/learning/library/project-managing-sdlc-8232)  
19. does vietnam have a stock market — guide \- Bitget, accessed March 18, 2026, [https://www.bitget.com/wiki/does-vietnam-have-a-stock-market](https://www.bitget.com/wiki/does-vietnam-have-a-stock-market)  
20. Systems Development Life Cycle (SDLC), accessed March 18, 2026, [https://www.ou.edu/class/mis5003/mbapm.ppt](https://www.ou.edu/class/mis5003/mbapm.ppt)  
21. BABOK-Business-Analysis-Body-of-Knowledge | PDF \- Scribd, accessed March 18, 2026, [https://www.scribd.com/document/979609749/BABOK-Business-Analysis-Body-of-Knowledge](https://www.scribd.com/document/979609749/BABOK-Business-Analysis-Body-of-Knowledge)  
22. Understanding BABOK Requirements Life Cycle Management \- Watermark Learning, accessed March 18, 2026, [https://www.watermarklearning.com/blog/babok-requirements-life-cycle-management/](https://www.watermarklearning.com/blog/babok-requirements-life-cycle-management/)  
23. Requirement Elicitation: The Skill That Makes or Breaks Projects, accessed March 18, 2026, [https://thebusinessanalystjobdescription.com/requirement-elicitation/](https://thebusinessanalystjobdescription.com/requirement-elicitation/)  
24. Mastering Requirement Elicitation Techniques for Business Analysts \- The BA Guide, accessed March 18, 2026, [https://thebaguide.com/blog/mastering-requirement-elicitation-techniques-for-business-analysts/](https://thebaguide.com/blog/mastering-requirement-elicitation-techniques-for-business-analysts/)  
25. Requirements Made Simple: A Practical Guide Using BABOK | by Nataliia Trester \- Medium, accessed March 18, 2026, [https://medium.com/@trester.nv/requirements-made-simple-a-practical-guide-using-babok-e9799cf46ef7](https://medium.com/@trester.nv/requirements-made-simple-a-practical-guide-using-babok-e9799cf46ef7)  
26. How Do Business Analysts Verify Requirements? (BABOK 6.5) \- Bridging the Gap, accessed March 18, 2026, [https://www.bridging-the-gap.com/what-are-your-requirements-verification-practices-babok-6-5/](https://www.bridging-the-gap.com/what-are-your-requirements-verification-practices-babok-6-5/)  
27. Sample client guide | FastConnect API \- SSI, accessed March 18, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-trading/sample-client-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-trading/sample-client-guide)  
28. SSI-Securities-Corporation/python-fcdata \- GitHub, accessed March 18, 2026, [https://github.com/SSI-Securities-Corporation/python-fcdata](https://github.com/SSI-Securities-Corporation/python-fcdata)  
29. Fast Connect API \- SSI, accessed March 18, 2026, [https://www.ssi.com.vn/en/individual-customer/fast-connect-api](https://www.ssi.com.vn/en/individual-customer/fast-connect-api)  
30. Introduction | FastConnect API \- SSI, accessed March 18, 2026, [https://guide.ssi.com.vn/ssi-products](https://guide.ssi.com.vn/ssi-products)  
31. General Information | FastConnect API \- SSI, accessed March 18, 2026, [https://guide.ssi.com.vn/ssi-products/general-information](https://guide.ssi.com.vn/ssi-products/general-information)  
32. API Specs | FastConnect API \- SSI, accessed March 18, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs)  
33. Sample client guide | FastConnect API \- SSI, accessed March 18, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide)  
34. ssi-fc-data \- PyPI, accessed March 18, 2026, [https://pypi.org/project/ssi-fc-data/](https://pypi.org/project/ssi-fc-data/)  
35. The Smart Trader's Guide to Kelly's Criterion \- tastylive, accessed March 18, 2026, [https://www.tastylive.com/news-insights/smart-trader-guide-kellys-criterion](https://www.tastylive.com/news-insights/smart-trader-guide-kellys-criterion)  
36. Kelly Criterion Trading: Formula & Risk Management Guide | LiteFinance, accessed March 18, 2026, [https://www.litefinance.org/blog/for-beginners/best-technical-indicators/kelly-criterion-trading/](https://www.litefinance.org/blog/for-beginners/best-technical-indicators/kelly-criterion-trading/)  
37. The Kelly Criterion and Its Application to Portfolio Management | by Jatin Navani | Medium, accessed March 18, 2026, [https://medium.com/@jatinnavani/the-kelly-criterion-and-its-application-to-portfolio-management-3490209df259](https://medium.com/@jatinnavani/the-kelly-criterion-and-its-application-to-portfolio-management-3490209df259)  
38. Behavioral Factors on Individual Investors' Decision Making and Investment Performance: A Survey from the Vietnam Stock Market \- KoreaScience, accessed March 18, 2026, [https://koreascience.kr/article/JAKO202106438543576.view](https://koreascience.kr/article/JAKO202106438543576.view)  
39. Behavioral Risk Management in Investment Strategies: Analyzing Investor Psychology, accessed March 18, 2026, [https://www.mdpi.com/2227-7072/13/2/53](https://www.mdpi.com/2227-7072/13/2/53)  
40. Research on the Impact of Personality Traits on Attitude towards Risk in Investment among Individual Investors in Vietnam \- ijsrm, accessed March 18, 2026, [https://www.ijsrm.net/index.php/ijsrm/article/view/6305/3921](https://www.ijsrm.net/index.php/ijsrm/article/view/6305/3921)

---

# **Evaluation, Comparison, and Improvement Proposal for the Quant Trading System**

As the Academic Board, we have performed a deep analysis of the latest research materials and cross-referenced them with the previously generated strategy. Below is the evaluation, comparison, and technical improvement roadmap.

### **1\. Comparative Analysis and Evaluation**

The research material validates our core strategy while providing critical empirical evidence for the Vietnamese context:

* **Model Validation:** Research confirms that the **VN-4 Model** (Market, Size, EP, and Turnover) significantly outperforms the traditional Fama-French 3-factor model in Vietnam. The **Turnover factor** is a vital proxy for retail speculation, which accounts for \>80% of market volume.  
* **T+2.5 Liquidity Singularity:** Empirical data verifies a modified U-shaped intraday volatility pattern with a sharp peak at 13:00 (1:00 PM), coinciding with the T+2.5 asset release.  
* **The SHVaR Edge:** A significant finding suggests that a **SHVaR portfolio** (Small-size \+ High Value-at-Risk) generates superior returns (\~2.38% monthly) by exploiting market inefficiencies that large caps do not exhibit.

### **2\. Proposed Improvements**

To achieve "absolute precision" and maximize risk-adjusted returns for F0 investors, we propose the following enhancements:

1. **Risk Management Upgrade:** Replace the standard Kelly Criterion with a **Catastrophic Loss Kelly model**. This incorporates a "probability of ruin" ($r$) and "catastrophic loss" ($\\lambda$) to safeguard capital against extreme market shocks common in frontier/emerging transitions.  
2. **Streaming Infrastructure:** Move from REST API polling to a **Full-Duplex WebSocket Streaming** architecture using SSI’s X (Best prices) and B (Real-time OHLC) channels to ensure zero-latency execution during the 13:00 volatility spike.  
3. **Behavioral Filter:** Implement a **Herding Bias Monitor** using Cross-Sectional Absolute Deviation (CSAD) to detect when the market is moving purely on sentiment rather than fundamentals, preventing the algorithm from "buying high" during retail-driven panics.

### **3\. Formulas and Implementation Code**

The following core logic has been converted into Python code for direct use.

#### **A. Kelly Criterion with Catastrophic Loss**

This formula adapts research to calculate the optimal position size ($f^\*$) while accounting for extreme risks.

Python

def calculate\_kelly\_with\_catastrophe(p, q, r, gamma, lambd):  
    """  
    p: Win probability  
    q: Average loss probability  
    r: Catastrophic loss probability  
    gamma: Gain per unit bet  
    lambd: Catastrophic loss size per unit bet  
      
    """  
    expectation \= (gamma \* p) \- q \- (lambd \* r)  
      
    \# Solving the quadratic equation for optimal f:  
    \# 0 \= E \- f \* (p\*gamma\*(1+lambd) \+ q\*(gamma-lambd) \+ r\*lambd\*(gamma-1)) \+ gamma\*lambd\*f^2  
    a \= gamma \* lambd  
    b\_coeff \= \-(p \* gamma \* (1 \+ lambd) \+ q \* (gamma \- lambd) \+ r \* lambd \* (gamma \- 1))  
    c \= expectation  
      
    import math  
    delta \= b\_coeff\*\*2 \- 4 \* a \* c  
    if delta \< 0: return 0  
      
    f\_star \= (-b\_coeff \- math.sqrt(delta)) / (2 \* a)  
    return max(0, f\_star) \# Ensure non-negative

#### **B. PSO Position Update (RSI/MACD Optimization)**

Adjusts indicator parameters dynamically based on the swarm's performance.

Python

def update\_pso\_parameters(position, velocity, pbest, gbest, w=0.7, c1=1.4, c2=1.4):  
    """  
    position: Current parameter vector (e.g., RSI period, MACD EMAs)  
    velocity: Current velocity vector  
    pbest: Particle's best position  
    gbest: Swarm's global best position  
      
    """  
    import numpy as np  
    r1, r2 \= np.random.rand(2)  
      
    \# Update Velocity: V\_i(t+1) \= w\*V\_i \+ c1\*r1\*(pbest \- P\_i) \+ c2\*r2\*(gbest \- P\_i)  
    new\_velocity \= (w \* velocity \+   
                    c1 \* r1 \* (np.array(pbest) \- np.array(position)) \+   
                    c2 \* r2 \* (np.array(gbest) \- np.array(position)))  
      
    \# Update Position: P\_i(t+1) \= P\_i \+ V\_i  
    new\_position \= np.array(position) \+ new\_velocity  
    return new\_position, new\_velocity

#### **C. SSI FastConnect WebSocket Integration**

The recommended setup for capturing the T+2.5 liquidity spike.

Python

from ssi\_fc\_data.fc\_md\_stream import MarketDataStream  
from ssi\_fc\_data.fc\_md\_client import MarketDataClient

def ssi\_streaming\_handler():  
    config \= {  
        "url": "https://fc-data.ssi.com.vn/",  
        "consumerID": "YOUR\_CONSUMER\_ID",  
        "consumerSecret": "YOUR\_CONSUMER\_SECRET",  
        "auth\_type": "Bearer"  
    }  
      
    client \= MarketDataClient(config)  
    stream \= MarketDataStream(config, client)  
      
    def on\_message(message):  
        \# Processes 'B' (Realtime OHLC) or 'X' (Best Prices)  
        print(f"Real-time Data Received: {message}")

    \# Subscribe to Real-time OHLC channel (B) for VN30 index  
    stream.start(on\_message, lambda err: print(err), "B:VN30")

The Academic Board confirms that these improvements will lead to a more resilient system, specifically tailored to the unique high-volatility and retail-heavy dynamics of the 2026 Vietnamese stock market.

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAloAAAAvCAYAAAA7K2SxAAAPXElEQVR4Xu2cCag0RxHH60MFReMV74OQoAGNJ5LESMQYFSNBUaNENJqAiIIRjEI8QHkiEhRvjREPvqiIVzBI1BgVs6h4gxrigQd8EQ80qCgqRtHYv9dTbm99PTs7+/aY3f3/oHm7Pbsz3dXVVdXVvc9MiKkcihVCDJ9BqO0gGiHEwtg9jd69Hk9n6PIYevt2Cg2GEGI7kXUTQgghFoycqxBCCCGEEMK0NBBCCCGEEEKIrUcLvx1HCiCGhnRSCCE6kakUQoiILKPYIKSuwpEuCCGEEEIIsbHMF87P9y2xGWzp6G5pt8RakDYJIZaATIsQQvRBVlMIIYQQQlRQmDgUNBJCCDFgZKSFEAUyCULsJpr7QkoghFgvMkJCiCUh8yKEqCPrIMS8aPaIRXJmKreMlWvkxbbdOk7fnhsrA29K5Umxcst4WyoPj5WiF+9N5T6xsuCyVO4QKy3r17aDfonZOIhNYg7XdEwI0XBOKj+MlWuGSXuxbW+wRd++FCsDx9nwxmWR9B3jW6dyz1QeGS9sHLP2uBt0hPk7jTZdm+W7m4zr16zcwrJ+IZfVsThdOChtelLSZpPoBd9VsCW2j2KOvj6VP6Zy2rhqH4zHo1L5TiqPCNfgdql8wI7OZt0qlYtsuWaAtj0zle+n8uRwDV6Uyq9j5UBALr9J5d2pHBuuwXtSeWUqd4sXLGcfXhErLdfHLAPPYey2jaekcmOs7ABZ3JzK5+KFBYDcp2WFlolnEv6cyqObOtryAsv9fWlTF3l5Kj+LlZbn7nNscu6elMp5xXvn7Sb9KmFOPyBWLoBV6tddLOsNtgcbi316aFNXC5KgzSZBm02Kdg8d+32oWxzL9ESiJ7s7GI+3PJFiWpfJ9t1Q57D6+FYqt4kXLE867jcrrARHsXIGCPRGVg+04A2pHB8rBwIO/8up3DZeSFwTKwoIHmuaOkrl37EycYX1Wyki01pQPST+k8pZsbIDMlr/tazri+TeqfwulRPihRWB/qBH74wXLM/BtnlIYPagWGl57jJvIjel8qxQxwJL+jWmTdYHYdX6hQ9g0R35muX+MX6RNpvkbY+gM/iOyOl2tI4JsSnU5sAEGD4m0dNDPZmuw6HOIfuF8a1BENHH6Cwr0GLivjBWLodOGUc+ZNl4HRPq75fKqaGuBCdQA+P4y1hpOTvRJ7gYuiPEuf/I8sq7DziqxTisyaFGtm0B8yrwfpGFiTAHa8E3gRFzlOCzhPfUxwUXsOCqZQOlXxm+18fmzcqq9YsgexQrLesY/Yu7F9Bmk7ztEXSGRU/kTlbXMSH609slLx9PF7MN6JCpYvutDSbEDaHuuFR+ZfleTD5eT7uHs6xAC+NUCz6WwU9T+apNpvgJpAiaaOe/bNIhEQD+1XJa3nmCtWcQgXEahTqCY5f531K5LpUHF9fvbv0M9UEc4VssZ0oY+4+Ea5GHWf7cx1M5N5XfpvKNiU/UQYbNNsXETMI5IuN7pPLAVP6eyhttnHHFgRDcfrD4XMnzUvmHZRmeHK7xWb7zp1Qusby9RhuQu9fzurbVu2zoVy3TgC4h38lzVFlk6F6cM99O5Q+W70WGgv6UvKy5FlmXfnVl0aJ+Mdd66leV91vWLbLOnEs6salnUXe9ZT1mAfqYpt7BDqBf6MqFlrflHPQJ2dM3tyHr0K+2oJ05xNjXgqaaTYptxw6WbUdnsMs1nanpWG8G6GPFstmAQcf4oeCkdJ3zmvo2cGyjUMfEeYble320eU3w1cV8gdahzkALMLBtMDQ8e5YSV/8l/GqGTBT9xiGBr3DJDvgZh73mGtBmsg0YaOfrFrOKk8rD+Q+ChRLkyxkd7oWBO9smDRgywqhh3GZhHkdIKzHOn7HsJHDyte2HEgJ1+opcrrbcPhxYF7UgAUfAM7kfgaoHq9yPc0SeqeH9s1O5q2Wn4c4aueIYcH70hXN/5RkSPnv75jWfY3uDYBb9/ovl81C8xmEunukGhH5F5/QQy2NO8Fj7NtuMcYzRm09avhd9oZQg8/gcWJd+7ZUfCPCMqF/Pt0792hdVTb8cZIRdQ09eZfnenjHnL+/RE64TNJ3SXGM+Mj99XiKvM5rXPJSAjTEDxuBjlvWLRery9WsMQSaZpvKcGXPrdZbnQFycQM0mjdt+aL/tj7PJtrvdrulMTcdEdRqLTQQFv6F5TZCAgyrBeJSrMIxWnGAwz5mC+QKt7owWLHvi0k//xQwr2dOaegKokY2DVQJTUuYO36NtvnomWDtpfHmfGNzRz9pqGydEkFxL6wNjNatzm8cR3mjZsTifSuWbxXuITgLHRAbVx4fn4mBKaoYYnYvta2RyiOxOKR9kThbBHUgpT5e9BxcOjvIym5Ql3/UgjCxZmU2p6Refi/1dFjwfvfPgiBKzPQSNPnd9zjDnIkesfqYGkHlboLIO/fJgAB15ok3aJvQg6tdhm9SvM6x+Rq2mX8CZonKsmb9HLNs7sjroWhmg8NmR5QUrr31MaCeBPAEjeADrQRgZVw+60M+afi0LgimeV+oSfSplGxffbTapq+1tcm7TMbG17FYQyaTwLAQrRjcEDitCfoHotAVavi9fSwsDk5ZfopAZ8EK63bcay3J5/korQwi0HAIsjLEbVDJbGHznszZpWHAQtI3sAqtGVuslBAVXpnLHoq7NqHEPz6TVmOYIo8zZNmIbI9YTTNZgltAPMggRrqEPH04va46dzFPNsNJn+lRz+m0G2nWhzBCizwRar7ZJPUA3eY8sCVJ4/b5UvmL581F3uc42yBds0iowRjX9OsOmH+oloxHlG8uldnSgbRWjxPM9g9fGP208d6cFWgSUzN0a8wZasV9t+kUwWGOafhHM8n/AXmN5WzDarDb9eqrlX11ea0efR2vTL9pwpHhfLm5Otqw3nDFy+PzIxgEa+vUJy1tpJ44/9v9FAJ+53pqt7maU6XNNv0rIZkdZ1sosMN+6nscvD8tFSJtN6mp7m5xr4yXE1oChYGKQEmeV3wVOjDR6hAkWjVcX68poYajL1VtbwTDXHFMJ5xDcyfsK94Tx5aN+FeYOZJTKD2z80/xpYJQJGiKMRS3747B9yvblLPTNOHDfuAUawRDX5Ef/D8fKBsa0ZnSRI44tguPjfqUT4D3BEYFNGbQhRzIkZDTanHgJeoLcb7DJLKUvKtYF+kX7y0xpF76NGoMSDxrb5u60QGtd+oWz9vYS9PhC0anpl2eQnJtD8FrTL9rMd3wx43aH8YcycwbMf95faFlmsV0RGnC+5cCvDFqnBb7LgDZ3Be2RNpvU1XbGrqYzbTomxFaAE2GisdIrwXE9LZXPh3oCC4KJCBPFHRGGY5YDnMsKtDBgrKBXAfLzYAJDTeDqcsBw+usS5E2JTo/3OJCfV+prQUFp5N9qk57jGKv/urGNvo4QpxK3inn+BcX7WqDF6h8ZRafmtAVanLthWygyskk5nGc5i0CQhPPgukMG9bjmNQ4hLhg4QH1/GztQz1LSx73mNeAsCPCYI5c2dS+x/P/RJrz3kiBjSt/KTEoJ15m7MeOAY/QgwWHMR5bHn21s5m6Jn3eKrEu/9or38JNUrired+kXcB+2JUva9Iu+u525pHnvGUfk7LqKvrFQPad5j42MNui1ljNRzPHyuAF6VGbFeUbUr2XRFbSjE+9K5cehfppN8rZzXqtkms7UdEzsBquwmWtnZJNOxWHVT7AUg6rDVl+pYXAQGAcnmWiz0DfQYvuRNnGWgXQ7ho8JH4MZjO0o1C0LMieelcLQ4sDv17yvGSJA3vs/cw4axjYtjpCAoIT+xXEAN058JwZtGFDGalYl7usIgT6wencwyDgMpxZocfaDvuBIa7QFWrQtZgfBtz38bBTbJa7Leza+151t0rl+0cZyRkZnWu6LO/NfNNfY0iHw8gANCLRw5BdY3homq8gZrrbxXhQ4eORJJvTTqdzLJs/ROMideRIDB+ZlrEOuBJz0G5nEuVsGEyXr0q9Sz3k2480vDZ0u/YJTbfK+0KZfZEAvt3yGDz0rAwICJQImYEeA9ro8WLjuz/EG2o19QDf53vmWP0s51yZ/JeqB4gWW9WsZ8Fx06SLLfSD4i3YUCA5ZfET702aTyrbH+6EzzNeaztR0TMxJTcBivXCmpG01gyG9ItT5ZIkwtjgcd3iz0DfQmhX646vFVXCsTQYUOLkYYJTs2dGBkXPE6uPBNkoEWfPs2rzCQR4fK6cwjyMEd/7lmTKnFmgRGEzTkbZACwjwy4PHgOPjOcihbRu1rX3AtcqZqH26rkXB991+WRY0i7lLVqGE97UgZJrsmOt7sdLWr1+nWF7kQHm2rku/CFDPtvpnavpVgiyOxErL7asFvFBrO7T1C/zaUGDcTo+VVrdJ09qOzsQsH8SMsRA7BatFArHHFnUYa1b4bYa5D9zjmlh5QGgfweH+4dINBJnjwO4b6kfWr084/VoAVuVQdla1sxMHoRZodTEt0KK+zETgvMkakNFbN2Qq9iz+/6r1gP6gRwQN5dwFDvefFeqm4WfaSsgY99IvW7x+YYPIntMGsomzQHDlusJWYSTqF0FD2UeC+rjw3AX2LAfjZPVKRtbfJrG9HmFhGXVsafRRWiFWwfdSeYcdrZu851cos5zDWjWk5zmjs6mwVUA2IoKTuMpmM2wYxYtj5Yph5covSvml2XXhWhuc6SAQwKERKMQAiu07zuQA8rjU8j+M5VzWuiFD+WarZ0pWDedqmLsEDXHukgmqZaRrINdyy9Rhe3id+uVn6LzMEvywNVZ+pyaDUr/4teZNNs6M829vhjK+q4SF62VW/0fE89ikqI/omMtcLJUo+i1ly7rJCv5KG1a3cCI1x7BalicR+nZtrAyQUWFctpmrrf5PFMVsoKEE8/HfWZTwb0dqWR/0K57n3DbQL4esKUHCTtHDhM1tkw5lParp2LDoIYyFsY5nisHCimZIKlE777BttJ0Zcjj0veRV99qHnHHukoOYTpeetM0lvrfttPVd1Omai2261vW9YbJ28yeEEEIIIcTOoShcCCGEEEIIIYTYIhax0F/EPYQQQgghhoJiGyGEEEIIIYSYGS2hNoO1jNNaHirEApDuCiEOyO6ZkQ3o8QY0cbORgA+MRCiEEEJsM/L08yG5CSHExjMsUz6s1gjRH+mwEEIIIYQQy0dxtxBiWOySVdqlvgohhNhS5MzEmhig6g2wSUIIIcSOIq9cIGEIIYQQPZDjFEIMj4NbpoPfQQghtp7FmMrF3EUIsRloxgsxHP4H8LcTrqFhaw8AAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAZCAYAAAA8CX6UAAABs0lEQVR4Xp1VMUuDMRC9QwXFggpdCg46OjmITo5uLgoVCi7d3O3mzxB3J3FxdnJwd3Fx7KC7CgVdHOq7S3JJvqR+4IP3JXnvcvdd8pUSEZMDE/spm5ZATJMr/n8Ry4dJS/I/7dJMldJVVCtWD0HRBY/APoL6bsy4By5a9KwsAu/9gO9YbWUm0Qb4DH0UImOu9JXZjCnkJ4xrsg4RfrwAX8BuksRmccmaeQpe5i65AIbO9IpZr7E9B7tKkug0CEnFDvjoyJ3mizS7PQO1LVVj8Ar4AEWKLJiaw6Jlco0BpF5CSS7tfIPDEBgRVq53gVy/HOQH+ObIMt6BJ+By3EBzrG+dJonYwfIL4655ua/w0jn4aUKST6Y35A7athcfdHMddia6b0sPswV8iMcAVZbKSkT7CJAvWlpz8DFlKB/jcU/uEszfBicsLbG2NcV8InqlmECu/gAcI36zaRpm/54zXIG34LxbtuwpbBX0IZ/IgFw3ZZwgiDKmAdpmFMbgOjgyRd1qyjp8qPzmVjMlS9RM2FwHyJYZN6Goe1Gs2u2Ih5I+g1c0kYfKOwfHI/k/yz4Nq+O0X9fqMhc46p02AAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAZCAYAAADXPsWXAAABkklEQVR4Xo1TsS5FQRCdjSeRiIRItCLRaDSikChJKAidP/ABryCioNJTKEUvURGlhEZ8yysJEe85szO7O7t7740T587MmTN7Z+8LIkc5tOaQWiGz5q7cOZH0lHq8VvI8L2qpbDedl6BqbFp384RHR8vAuHxa1g2xzAPCfFpUlewAa4hgsVYLtBhYDifHZ2q1jQmy1UrRKlFzfTwuwF/k+4j3aO0hHotGy/C+oneK/E613TDNWACfwB0MjhC/KO0+hecL+IZ8Uf2r4CfqWynFeoBwhXhCcsi1mhkz4Du4aS6yDv7EQ7Qxr3zwTTEp3BI4gI83EoXoiORlHOPKpD/dkOS+PdF891IHEhwNQN6Ot6wwQvPQ1OEqPCSQl/GhZ6psa/SYIH8VV1wFB/gPG1ebBL/BNdQ9xI3kJ1oBb8KrFOfgEMKWr8LlHX0gPoLPwRgwBo4XGrZzsxTGE6bBOZIZi9IXUOrx49SShdWa/t+yfp7xI58o5+u6VDrQac2aDVe1kGVbmk34v7XDWX8dA9OQ1Pm/P9gRLmyVW2WLAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACcAAAAZCAYAAACy0zfoAAACxElEQVR4Xr1WPWhWMRS9AQVFQaXiD3bqJggOgpOL4CBKQVy7uHVQ3Krg7uCi4KigOIgg4mTBwcFR6KybqFAoIjoITmLrOUney01y8zXfB3rgfC/v3puT+3Jv0opEuGEQR+k9B+2mzzQSTcds0HIuvK2Ab8C3rnet3jiN/jlOBbsDGK5hcFMFzIYsgY5s8p0yLSfBb+A55Wii1lAozeW7gT3gDfABoleM+CVwHULzpWMbXJRR17dGSib0y1nwKngw2nbjdyFGZLgNbmHGcukQX1JXldT4iICUAOF1pda9A+4DX4P3EboLz1WOs6gIONxvPM8Yy/6QWFJ6UtliXBU+YljQ0mW1ToBfwfPgMfAzuGTJbcD4XrjF3qsWxyTHyS6eXQMNO0u0IYNujWuSfPx49jX7u9LbBF+AOzJryIdfT4ELydQDxwWjrst1A57A/lRCLmwb3ghHJez4CL5sIuITng/BuxJKeVrCxFfgI3A8EJPSU8nzo2zdELIIfsD4Op73wHcS1snA7f8DXpGw7jx+14XNGk7QnBRf0wmWNNflqYeu+jjqHorj/eBeP0oBfvt1Sbm1XxDAPgxH29iqwZS58riyVYJuSDqDIT/iFrisAo6D38Ff4KlkBjr/fjEK5S2vEOi6QbdCUM71D4Mf43MA7iYvvIrYrnIaKTd0/Z3HXuxC3GrHe2cAG5MluWwuOwGq1NTlPwu1rqNujtYNMHyhPups4ufgzmQyJ19y/kZ3Km6MpG55NVW6VlKl5YiERn0J/pT8ayeB/cQd5pVggTs3i25ESpPXBUrhunpMgYeplRzV5/BbXKzl3kwL1Tzb4DGCeLoL2BNtayesnGzB0foM5EU9HZRopV8ZhDbLaiScwnhB25MkOJrO/42UyD9LqViitY65LdpQORtQcb1TSrTmlTkO41Z82zED9GJhnNSnWmdScMP3FwmVaYm/s7WPAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADQAAAAZCAYAAAB+Sg0DAAADdklEQVR4XsVXXYhOQRh+p5DNboj8lLJtUty48FNbuBMJaaOUkhu5cSetKLnZC+VCG1dEkgtWWvm5oawS5ZqUKBRCa2+4oaznOTNzzsycmfPNt/uVp55vZt5555l33nnP2bMiAZSh7Yd219YJTFkvXBiOp4dKLU83z4uIeZa22KSP1h7TRwf3aJZqnrVo6dXS4f+jF5wVGnXciehbmtVexxxFKBGOo8hxgs9waKNRmcVsPJ1ANLJHD2yrQmOJyIKOwNzAfPw88GemDR6Guh1Fbh7WgHdCYxMyhAdCQ0u4ohkbOKh575dYyeWiJleg1ItPdwJKtuL3IPgSvGt2suXGEtkDToLjekFb6ILeMbQ3wOPgE/AF+BZcX3qZ07HJOGgv+AzcDh4Cf4qzbBH4EFwIvgI/GLsttx5wOfgG/GXmHMS3N9Yl4COMmCgaB5S+oZngFfAzuEK7JlCXt7FccmzU7LeDXeBlcCP4B7xv7GG50Y8BtAMcRt4hql4zHlZal7D7neagHncFZ65LWEFOIsyNDopmAZ6YZPAsq33arJgB9wFeC95zxpIOo7RPonvE9HnTt6V6ZVOPN361GKWkfGyD41+058VfwVgHQwk4qltoZ4jedAQO3WaOLW+uv5IJl1cwMyzZMak0cMPqnOnThUE5CcwCH4kvYJ9jY6zjUCxLzoLiJ0zfKzcl6ih+L4g+bBr+YbnRmFQHop4tN5YLy4YvhwVhctKpKm6UZTzHsVGTsXeF62gcMn1mks+MBTde5oyJueAouC6wW7DeX4OLzXgEodpyQ4moCUS+wYyJ3aKzzxdGCoyRibVAMorYJhxbCQZ8U4rSK4RHseFXtGc8LwNkYymap+BjsNvLTjVYDT4Hf8D4Ce178KPow4Y4DP4Gd4YTBnwLf4POSdEa19GnNvdogCoydFF0ZpuypaHkmlRllQLnD4DzwokIigPpnHhp4t8sW27UY0LT5Rk864nPk+jys6EhAr7h0h+kUirPFvpFtylucCgxpxGbU/oLoXHzCoo3uCW0RpD7QbpJ4uXIUPmHWD/XkcAjN1qiXsP2fwUffOPtCI0JnPKHVs/T7cNos2twsBKu30XfYALRGOugm396lb02CxGtWP6Ufqs2orasZmgHU1jsLZnC+ija0WnHt+PI39zxNN2iyReoEKsVB82zFXL9XNg1/wAgMnC8/oTgiQAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAYCAYAAADDLGwtAAABP0lEQVR4XoWRMUuDQQyGc6DgJpaOgjiJ4ObQxaGDf0LqX3BRxP/g2EWog5NzF2cR/4OL4ObiIILgJFifJPfd5b4Kpn0vb97kkrv7RLCUdMW7qyz1tYyOxnTDjcZcDlupRN2cdtiSec1yKhwld8o1yX7B/hng1jtKz0LHtrXN1ewMckS0ih+BKfwylmrhMYUnkB/8lHgOH4Nzis+0QKvWwR3YB19oC0v4oDX8G2xHpS20XQI6yQJ+6q9ky4ZqYJIvZusD+EY40CCbNtDjHHqY7P8Oe4INba6NlgnuFWyHzXa2iyDsgQ/0zaCVszyKX25At3vwks8qdr6kN3bxFuUZ/gmuiQddJysFN6I3k/wq/az7NBS7hL1jm4wUciX6BKJfJo3xK39XlrjOKDApxO22riBa3Bi1wr2g9up1rmvd9Qu/LiQVLJs7hgAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAbCAYAAABBTc6+AAABNUlEQVR4Xm2RvUqDUQyGE1AQHASX2lXES3Ao3dQb8ArcCu46uLuLOOkdlOIm9FoKRQqCkw6ik/jzJOf/YHrevElOTpIvFRGVgCBuqbphFK+K/i89u81tDvdJUZpKGJvQBdYd9jm80WXqPvyB+Yszg9dyQtXiyhKwJqm4dvM9or7gcZmgxQ+6K28Sq6j1Fz3DHIEbMIwPPYOp1So8sb57+BC8gQOxffLbRX3jnJaa8gzmyT/S2N89L60r6CXNeIme+LtwaecV69P8AcaSgHGYKTRhaD4dZ4haia87tdctlA19YrEBWIL6+4/BFKx7OudWQiuTPQILYttVRdlB29QP8Du4Tlc5ycl3Ut5VEkJFNym10/zBRfyNjZo8P76seJPTOjOHUon4um3rEgNdXHN1czxQOVH+ALJqJTbbH/ooAAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAloAAAA7CAYAAACjbCQ8AAAFRUlEQVR4Xu3dP4gcVRgA8Bc0oIhGUUFJRAk2NipIECQ2GsEgNmLhn8JCJFhbKIKFhUVUBIMKaiBYiAi2KRSLQ5to6jSCYCSYQrQQDGLQ+D5nhpudXC63t7vz9/eDj9uZt7tzs7PvzTdvZt+kBACwbDuaMxi9wW/zwa8AMGaaKJgYlR6mSM0HAIAekJhDj2yvQm7vVQAAADCH2YPPOQ5Fa0+d41UAbIuWll7xhQQuS0MBbVDTYArUdJiTSgMAQC9ITIH+0TIBTJQdQF+0vSXaXh7dmtj2ntjqArAROwMAAAAYA0f49MtVOd7PcSHHv40yAACW4GyOM82ZAIyJ3h7oSvRovdycCTAg48wixrlWdeNfQybvrhw/5bg7x0c5ri7n78zxQo5HU1ERHsvxWo5by/JViPc+lIplXZHjxRzXzzyDxWjSgFZpdOCJHH/l+DHHgRxf59iV4/Ucb6Wit+uVHB/neKd87ipEYncuFcs9nuPL8m9cR7YNKjdMh/oOrVPttuSGHCdz7KvNi8Qqkq0jtenD5ePq+feV08sUy7myfBzJVSRZkfgBwJCMIwUZx1p0Lk4b/pbjptq8SHjWcuxORcIT0wfLsr2puHB+fzldF8958jIRpwSvqV5Qc1ua/dVjtZw9tXlAK7SuAJuYq5GMXqtIpCrRY1W/MD56lOqn794oy+PU4jIdzfFFbbpaDn2wyVdqkyKAIdCMsVKf5Dhfm46eql9y3FlOv1pG5URaTQIU/0d9OWtp4XG91B36z7cUYNweyfFP+Tja/Ei64td+oTp9dywVF6pH8vVNjlvK8mWKa77eKx/Hrx8jmav3cPWOHSQwp42bjY3nAivyXHNGS2JYhRsb86rTd9EMRFkkW6sU7x/LiYiEb6PrwBagNQNqFmkSFnntwjpdOAxWJBnRkxRjSEUtqsay6tJamj2t2Ja4QP9Umr1AHwBgy37I8WGOv9P64cnDqRjL6pnqSR2JJO/xVPRmnc5x/2zxysTn8HwqPpuvcjw1WzxBDlyB3tJA0W+RxERCVV1YHr1Z3+f4LhW9OdV1Ul24I8e7qRglPqKthOe6tL7MiA9mi/tIQwNQo1GkF+5Jlz415n6D0Dn7CoAhi9Ny8Yu6ahT0utubM+gzO+TBswlZBd8r6MQDOc6kYjiF33P8nOOhmWcAAHRjFIcIG93yZl4xSnsMx7CV2ExcHzaQGMW2B+qmXq2nvv6DsIqNtIr3pC7uBxjJQ3VLmy7dPKBg0DQswEU0DOPU+Xb9NBWJ1iLm6dHqfIXHwgcJwPbZi7TlZI4/mjPn9FIqru/aSjRHewcoaPf7qK9bpa//F1zkwo6e38MPhsl+ABgozddSxWnDMY6VFRf5v5mKgUaBldAaQw+oiD0Ut7R5OsfuHCdy7JotHo04LXquOROATow7IRjK2g3l/xy4IzkO53g7jTfJCtFbd6w5EwAYqmFkintS0dPzebNgRGJLRKL1bLMAFtNyJW95cQCwFftSMeJ9jHy/P8fx5HZCAMBSTfdo+FAqhpO4t5yOxOuz9WIAgM4MPkM7lYpfHlYO5Dhdm76kwa85AMCKnc9xbW06hrCI5AtghoMrgPnVbyu0N8fZHA/W5gGTJK0CWIZf03qL+meOo7UyAAAWcDDHtznWUnEvxp0zpTAZenCWwacIAPSCpAQmQVUHYGLGtOsb07oAAAAj5uCFJt8JAAAAmIcj6Zb5wAEAoG2ycFgd9Yue8FUEGIoJt9gTXvXhs/EA+J8dAgAAACQHyCxsmV+hZb4XwDCMoOUbwSqwGRsYgEmzI2RyfOmhDf8BCY/ATgQymkwAAAAASUVORK5CYII=>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAE4AAAAZCAYAAACfIRhSAAAC5ElEQVR4Xs2Xz6tNURTH1w4DRRKRMkBSrxjJzAgTAyYo5Q9QmJuaGSiDN5R4RlKMGb4y8pQMlIEUUkrJyMTk+a6z9z5n77N/nP3r3OtT3+7d66y19rrr7nXuuURzIcaGJePU4xiWiFmLeu8xLYTqvbwJvMYlEKojZG9Ms22yE00GTDosh+KyFh/YURNtxw6rmpzpwezYaM+O+gw+VqAb0DNoE1qHdsyzVcusObmEcs6JmeY89AC6Tkbj+ELRNjlBAd+A+b/GatycxJvjveoaXYtG9Ne6V4+jx1RDceNCddh2MTYUcQb6CT2C7kNvoA1op3ZwNo0sQwytT8JoXFZctvuIrdBd6Cn0G/oI3YTOQS+hXYMr0V+S95Zt0HboFcnCY6xB3zL0DjrGgYl4TtzQkbreRDlOsjm3hazhqHGN13z/7TgEfUcph/vLRKukGhcpkD/QgQztIStdJLNkEy7rVDCqfib309xSrg/JOjydkddPtOUO9FgMmXdDb6Ff2qEcI2s+7okL5zoBXfZJuLazyMOTFYJz9T0Ybck1Pec3J6E/0Ip2wOs15bCqnziUfUzliTPxmt3GFeDNHLAy6krfA+PSXmW7ygvdODZq9JhycIw1cu9jMTW4xy0MPaYXDdtp6AO0jxdHoB9kP51/Jjmm/BQfxPnOzOPZhmDjUnbqfBIcAy48pnyg+GAx+KUVaKa4pNZd2EHoK/QC+kLmEQ1kbYI/9wWS+1sSgQZK/IlyGWXhffnR4z30GvpE8pHNge8/+0k+jgxjmlqT4+cYChhyBE+PzzZJKKi38xs9pltIjia/2ozS8K/J5Ji6hIpJQcaaGdxsrmVGinrAM83zzcGzkNKCFJ8QpbFGHPeAx7P/1xRG0BWS/xxMnbJ8fKRWKdJd82mWmUfyHpk9EAk9qKfZB0hnhi2zUvbOmVHsnhXioKJzkuT4VlOyWUlMT0FDGrDg7ch/5KwqhkVtcXnxed5xcnLFff8BjhZ9pJmNbP4AAAAASUVORK5CYII=>