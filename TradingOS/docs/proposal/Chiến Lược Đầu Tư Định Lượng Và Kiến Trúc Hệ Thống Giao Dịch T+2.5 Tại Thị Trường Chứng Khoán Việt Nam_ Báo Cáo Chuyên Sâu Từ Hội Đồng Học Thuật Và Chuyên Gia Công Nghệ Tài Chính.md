# **Chiến Lược Đầu Tư Định Lượng Và Kiến Trúc Hệ Thống Giao Dịch T+2.5 Tại Thị Trường Chứng Khoán Việt Nam: Báo Cáo Chuyên Sâu Từ Hội Đồng Học Thuật Và Chuyên Gia Công Nghệ Tài Chính**

## **Phân Tích Toàn Cảnh Thị Trường Chứng Khoán Việt Nam Giai Đoạn 2025-2026**

Thị trường chứng khoán Việt Nam đang đứng trước ngưỡng cửa của một kỷ nguyên mới, được định nghĩa bởi sự chuyển dịch từ một thị trường cận biên dựa trên tâm lý retail sang một thị trường mới nổi có cấu trúc và minh bạch hơn. Dựa trên các dữ liệu vĩ mô mới nhất, nền kinh tế Việt Nam đã đạt mức tăng trưởng GDP ấn tượng 8,2% trong quý 3 năm 2025, vượt xa các quốc gia trong khu vực ASEAN và thu hút dòng vốn đầu tư trực tiếp nước ngoài (FDI) kỷ lục.1 Sự bùng nổ này không chỉ là kết quả của các yếu tố chu kỳ mà còn là hệ quả của các cải cách thể chế sâu rộng, bao gồm việc triển khai hệ thống giao dịch KRX và nỗ lực nâng hạng thị trường của FTSE Russell dự kiến vào tháng 9 năm 2026\.1

Trong bối cảnh này, chỉ số VN-Index được dự báo sẽ đạt các cột mốc mới, có thể chạm ngưỡng 1.920 đến 2.040 điểm vào năm 2026\. Tuy nhiên, sự tăng trưởng này không diễn ra đồng đều trên tất cả các nhóm ngành. Dữ liệu từ năm 2025 cho thấy một sự phân hóa mạnh mẽ, nơi các cổ phiếu thuộc hệ sinh thái Vingroup dẫn dắt đà tăng đáng kể, trong khi phần còn lại của thị trường có độ rộng hạn chế. Điều này đặt ra một thách thức và đồng thời là cơ hội cho các nhà đầu tư định lượng (Quant) trong việc tìm kiếm alpha thông qua việc khai thác các sai lệch định giá và hành vi thị trường.

### **Các Chỉ Số Vĩ Mô Và Mục Tiêu Thị Trường 2025-2026**

| Chỉ số vĩ mô | Giá trị thực tế / Dự báo (2025-2026) | Ý nghĩa đối với chiến lược đầu tư |
| :---- | :---- | :---- |
| Tăng trưởng GDP | 8,0% \- 8,5% | Hỗ trợ đà tăng trưởng lợi nhuận ròng của doanh nghiệp niêm yết (NPAT) dự kiến đạt 14-20%.4 |
| Lãi suất huy động | 7,0% \- 8,0% | Mức lãi suất mục tiêu để dòng tiền nhàn rỗi dịch chuyển mạnh mẽ vào thị trường chứng khoán. |
| Vốn hóa thị trường / GDP | \~62% (Mục tiêu 100% vào cuối 2025\) | Dư địa tăng trưởng quy mô thị trường còn rất lớn so với các nước khu vực như Thái Lan hay Singapore. |
| Thanh khoản bình quân | 1,0 \- 1,2 tỷ USD/phiên | Đảm bảo tính khả thi cho các thuật toán giao dịch khối lượng lớn mà không gây trượt giá đáng kể.2 |
| Thời điểm nâng hạng (FTSE) | Tháng 9/2026 | Chất xúc tác chính thu hút dòng vốn ngoại ước tính 6-8 tỷ USD. |

Sự chuyển dịch cơ cấu sang nền kinh tế số và công nghệ cao cũng tạo ra những động lực mới. Chính phủ Việt Nam đã xác định các ưu tiên chiến lược trong hạ tầng và chuyển đổi số, điều này trực tiếp thúc đẩy các nhóm ngành như công nghệ thông tin, vật liệu xây dựng và năng lượng tái tạo. Đối với nhà đầu tư F0, việc hiểu rõ các chu kỳ vĩ mô này là bước đầu tiên để xây dựng một tư duy đầu tư dựa trên dữ liệu thay vì cảm xúc.

## **Phân Tích Chuyên Sâu Blueprint Hệ Điều Hành 'Trading OS'**

Dựa trên tài liệu đề xuất 'Trading OS', hệ thống được định nghĩa là một "Strategic Trading Framework" coi thị trường chứng khoán là một hệ thống phân tán phức tạp, nơi hành động giá là các bản ghi nhật ký (output log) của ý đồ tổ chức.16

### **Kiến Trúc Hệ Thống Đa Tầng (Layered Microservices)**

Hội đồng đánh giá cao mô hình Microservices được đề xuất để đảm bảo tính sẵn sàng cao và khả năng mở rộng 16:

1. **Data Provider Service:** Kết nối trực tiếp SSI FastConnect và DNSE LightSpeed API. Điểm đột phá là việc sử dụng **gRPC** để truyền tải dữ liệu thời gian thực nội bộ, giúp giảm độ trễ tối đa cho các lệnh T+.16  
2. **Market Intelligence Service:** Lớp xử lý trung tâm sử dụng Pandas và TA-Lib (Python) để nhận diện tự động các mẫu hình Wyckoff và tính toán các chỉ số kỹ thuật nâng cao.16  
3. **Risk Management Module:** Tự động hóa việc kiểm tra tính hợp lệ của lệnh (lô 100 cổ phiếu tại HOSE) và quản trị rủi ro margin theo thời gian thực.16  
4. **Execution Layer:** Module thực thi tự động các chiến thuật dựa trên tín hiệu Fair Value Gap (FVG), VWAP và Spring.16

### **Các Module Logic Giao Dịch Cốt Lõi**

'Trading OS' phân tách logic giao dịch thành 4 module mang tính hệ thống cao 16:

* **Module 1: Market Cycles (Chu kỳ thị trường):** Sử dụng lý thuyết Wyckoff để định danh trạng thái hệ thống: Tích lũy (Accumulation), Đẩy giá (Markup), Phân phối (Distribution) và Đè giá (Markdown). Kết hợp với Elliott Wave để đo lường độ sâu xu hướng, ưu tiên tìm kiếm Sóng 3 (sóng tăng mạnh nhất).16  
* **Module 2: Bottom Identification & Entry (Nhận diện đáy và Điểm vào):**  
  * **Wyckoff Spring:** Bẫy giảm giá loại bỏ các vị thế margin yếu trước khi tăng tốc.16  
  * **Fair Value Gap (FVG):** Nhận diện sự mất cân bằng cung cầu qua mẫu hình 3 nến. Điểm mua được kích hoạt khi giá hồi quy (retrace) lấp đầy ít nhất 50% vùng FVG.16  
  * **Bullish Divergence:** Tín hiệu phân kỳ dương khi giá tạo đáy thấp hơn nhưng RSI tạo đáy cao hơn.16  
* **Module 3: Top Identification & Exit (Nhận diện đỉnh và Điểm thoát):**  
  * **Buying Climax:** Thoát lệnh khi giá tăng theo phương thẳng đứng kèm tin tốt tràn ngập và khối lượng kỷ lục nhưng giá không tăng thêm.16  
  * **Fibonacci Extensions:** Sử dụng các mốc ![][image1] và ![][image2] làm mục tiêu chốt lời định lượng, nơi các thuật toán tổ chức thường đóng vị thế.16  
* **Module 4: Execution & Quantitative Risk (Thực thi và Rủi ro định lượng):**  
  * **VWAP (Volume Weighted Average Price):** Đóng vai trò là "Fair Price" (giá trị thực). Chỉ mua khi ![][image3] và bán khi giá cắt xuống dưới đường VWAP với khối lượng lớn.16

## **Tích Hợp Các Biến Số Đặc Thù Thị Trường Việt Nam Vào Thuật Toán**

Để tối ưu hóa 'Trading OS' cho bối cảnh nội địa, thuật toán cần lập trình hóa các biến số cấu trúc như biên độ biến động, FOL và áp lực thanh toán.7

### **1\. Hiệu Ứng Biên Độ (+-7% HOSE & \+-10% HNX)**

Biên độ giới hạn tạo ra hiệu ứng "Nam châm" (Magnet Effect). Thuật toán sử dụng chỉ số **Limit Distance (LD)** 8:

![][image4]

* **Logic:** Nếu ![][image5] (Gần giá trần), tạm dừng mua mới để tránh đu đỉnh kỹ thuật. Nếu ![][image6] (Gần giá sàn), kích hoạt bộ lọc "Vùng đáy tiềm năng" tìm tín hiệu Spring.16

### **2\. Giới Hạn Sở Hữu Nước Ngoài (FOL)**

FOL đóng vai trò là ranh giới cung cầu mạnh mẽ cho các mã blue-chip. Sử dụng chỉ số **Room Availability (RA)** 9:

![][image7]

* **Chiến lược FOL-Arbitrage:** Khi ![][image8] (gần hết room), hệ thống tăng "Conviction Score" cho vị thế mua do cổ phiếu thường được định giá cao hơn (premium) khi khan hiếm.9

### **3\. Áp Lực Phiên Chiều T+2.5 Và Phiên Định Kỳ**

Cơ chế T+2.5 khiến thanh khoản tập trung đột biến sau 13:00. Thuật toán 'Trading OS' tập trung khai thác khung giờ 14:15 \- 14:45 để đưa ra quyết định thoát lệnh cuối cùng, tránh áp lực bán từ "hàng về".16

## **Thuật Toán "T+ Swing Alpha" Và Quản Trị Rủi Ro**

Mục tiêu cốt lõi của hệ thống là đạt lợi nhuận 15% mỗi lệnh Swing với độ chính xác tuyệt đối.

### **Công Thức Chốt Lời Và Cắt Lỗ**

16  
Thuật toán áp dụng tỷ lệ Risk/Reward (R/R) tối thiểu 1:2.

* **Mục tiêu (Target):** ![][image9]  
* **Cắt lỗ (Stop Loss) dựa trên ATR:**  
  ![][image10]  
  Với ![][image11] để loại bỏ nhiễu thị trường.  
* **Tỷ lệ R/R định lượng:**  
  ![][image12]

### **Quy Tắc Quản Lý Vốn 2% (Position Sizing)**

Để bảo vệ tài khoản F0, mỗi giao dịch chỉ được phép rủi ro tối đa 2% tổng tài sản 16:

![][image13]

## **Phân Tích Kỹ Thuật Fetch Dữ Liệu Từ SSI iBoard**

Dựa trên phân tích request logs (SSI\_HARrequestLogs.txt), hệ thống iBoard vận hành trên hạ tầng phân tán phức tạp.

### **Chiến Lược Khai Thác Dữ Liệu**

* **Dữ liệu Real-time:** Kết nối SignalR Hub qua wss://fc-data.ssi.com.vn/ để nhận giá đẩy ngay lập tức.  
* **Cơ chế xác thực:** Sử dụng Bearer Token kết hợp với device-id duy nhất. Đối với đặt lệnh tự động, bắt buộc ký số RSA \+ SHA256 với PrivateKey.13  
* **Tối ưu hóa API:** Sử dụng GraphQL để lọc các trường dữ liệu cần thiết từ endpoint /stock/group/VN100, giảm dung lượng phản hồi từ 170KB xuống mức tối thiểu nhằm tăng tốc độ xử lý.16

| Endpoint Tham Chiếu | Chức Năng | Phương Thức |
| :---- | :---- | :---- |
| /statistics/charts/history | Lấy dữ liệu nến lịch sử (OHLC) | GET |
| /le-table/stock/{symbol} | Lấy sổ lệnh khớp thực tế (Tape reading) | GET |
| /statistics/company/ssmi/finance-indicator | Các chỉ số tài chính cơ bản | GET |

## **Trí Tuệ Nhân Tạo Có Khả Năng Giải Thích (Explainable AI \- XAI)**

Để tăng độ tin cậy cho nhà đầu tư F0, 'Trading OS' tích hợp module sinh báo cáo bằng ngôn ngữ tự nhiên (NLG) sử dụng mô hình **PhoBERT**.

* **Phân tích tâm lý:** PhoBERT phân loại tin tức từ CafeF/Vietstock sang các trạng thái Tích cực/Tiêu cực với độ chính xác \>81%.  
* **Giải thích SHAP:** Hệ thống giải thích lý do cụ thể cho mỗi khuyến nghị.  
  * *Ví dụ:* "Hệ thống khuyến nghị MUA HPG do xuất hiện mẫu hình Spring tại hỗ trợ 28.5, kết hợp với dòng tiền ngoại (Net Buy) liên tục 3 phiên và điểm tâm lý tích cực 0.8".16

## **Quy Trình Phát Triển Sản Phẩm (SDLC) Theo BABOK & PMBOK**

Toàn bộ quá trình phát triển 'Trading OS' phải tuân thủ nghiêm ngặt các tiêu chuẩn quốc tế để đảm bảo độ tin cậy tuyệt đối.

1. **Business Analysis (BABOK):** Nhóm BA thực hiện quản lý vòng đời yêu cầu (Requirements Life Cycle Management), đảm bảo mọi tính năng từ lọc 200 mã đến đặt lệnh ATC đều được xác thực bởi Stakeholders.  
2. **Project Management (PMBOK):** Software Director áp dụng quản lý phạm vi (Scope Management) để tránh phình to tính năng (Scope Creep), tập trung vào MVP cho chiến thuật T+2.5.  
3. **Kiểm thử thuật toán (Backtesting):** Sử dụng framework Backtesting.py (Python) để kiểm thử hồi quy trên dữ liệu VN-Index 2018-2024, nhắm tới tỷ lệ thắng (Win rate) \>60% thông qua tối ưu hóa bầy đàn (PSO).

## **Kết Luận Và Khuyến Nghị**

Hệ thống **'Trading OS'** đại diện cho sự kết hợp hoàn hảo giữa lý thuyết tài chính kinh điển (Wyckoff, Elliott) và công nghệ hiện đại (Microservices, gRPC, AI). Bằng việc tích hợp các đặc thù của thị trường Việt Nam (T+2.5, FOL, Biên độ), hệ thống không chỉ là một công cụ lướt sóng mà là một nền tảng đầu tư chuyên nghiệp, kỷ luật.

Hội đồng khuyến nghị:

1. Triển khai hạ tầng **gRPC** để kết nối trực tiếp SSI FastConnect nhằm khai thác lợi thế về tốc độ thực thi lệnh.16  
2. Tuân thủ tuyệt đối quy tắc **Risk/Reward \>= 2.0** và **Quản lý vốn 2%** để bảo vệ tài sản trong mọi điều kiện thị trường.16  
3. Tận dụng module **Explainable AI** để đào tạo tư duy đầu tư cho F0, biến các con số khô khan thành kiến thức actionable.19

# ---

**Quantitative Investment Strategy and T+2.5 Trading System Architecture in the Vietnam Stock Market: A Comprehensive Report by the Academic Board and Fintech Experts**

## **Overview of the Vietnam Stock Market 2025-2026**

The Vietnamese stock market is entering a new era, shifting from a retail-driven frontier market to a structured emerging market. GDP growth hit 8.2% in Q3 2025, attracting record FDI.1 Key catalysts include the KRX trading system and the FTSE Russell emerging market upgrade expected in September 2026\.1

Projected VN-Index targets range from 1,920 to 2,040 points by 2026\. However, growth is divergent, led by Vingroup ecosystem stocks in 2025\. This provides a significant opportunity for Quantitative (Quant) investors to exploit mispricing.

### **Macro Indicators and Market Targets 2025-2026**

| Macro Indicator | Value / Forecast (2025-2026) | Investment Strategy Significance |
| :---- | :---- | :---- |
| GDP Growth | 8.0% \- 8.5% | Supports listed companies' NPAT growth of 14-20%.4 |
| Deposit Rates | 7.0% \- 8.0% | Target level for moving idle funds into equities. |
| Market Cap / GDP | \~62% (Target 100% by 2025\) | High growth potential vs regional peers. |
| Average Liquidity | $1.0 \- $1.2 billion/session | Supports high-volume algorithms without slippage.2 |
| Upgrade (FTSE) | September 2026 | Catalyst for $6-8 billion foreign inflow. |

## **Deep Dive into the 'Trading OS' System Blueprint**

The 'Trading OS' is defined as a "Strategic Trading Framework" treating the market as a complex distributed system where price action is the output log of institutional intent.16

### **Layered Microservices Architecture**

The Board endorses the proposed Microservices model for scalability and high availability 16:

1. **Data Provider Service:** Directly connects to SSI FastConnect and DNSE LightSpeed. It utilizes **gRPC** for internal real-time data streaming to minimize T+ latency.16  
2. **Market Intelligence Service:** The central engine using Python (Pandas/TA-Lib) for automated Wyckoff pattern recognition and advanced technical analytics.16  
3. **Risk Management Module:** Automates order validation (e.g., 100-share lots at HOSE) and real-time margin risk control.16  
4. **Execution Layer:** Automates strategies based on Fair Value Gap (FVG), VWAP, and Spring signals.16

### **Core Trading Logic Modules**

'Trading OS' partitions logic into four systematic modules 16:

* **Module 1: Market Cycles:** Uses Wyckoff to identify system states (Accumulation, Markup, Distribution, Markdown). Integrates Elliott Wave to target Wave 3 surges.16  
* **Module 2: Bottom ID & Entry:**  
  * **Wyckoff Spring:** A shakeout trap to trigger stops before a vertical move.16  
  * **Fair Value Gap (FVG):** Detects supply/demand imbalance via 3-candle patterns. Entry triggers when price retraces to fill \>= 50% of the FVG.16  
  * **Bullish Divergence:** Triggers when price makes a Lower Low but RSI makes a Higher Low.16  
* **Module 3: Top ID & Exit:**  
  * **Buying Climax:** Exiting during vertical rallies accompanied by extreme hype and record volume without price progress.16  
  * **Fibonacci Extensions:** Uses ![][image1] and ![][image2] as quantitative exit targets where institutional algorithms often close positions.16  
* **Module 4: Execution & Quantitative Risk:**  
  * **VWAP:** Serves as the "Fair Price" anchor. Buy only if ![][image3] and sell if price crosses below VWAP on high volume.16

## **Integrating Vietnam-Specific Market Variables**

To optimize 'Trading OS', the algorithm must programmatically include local structural variables like price bands, FOL, and settlement pressure.7

### **1\. Price Limit Effects (+-7% HOSE & \+-10% HNX)**

Price limits create a "Magnet Effect." The algorithm uses the **Limit Distance (LD)** index 8:

![][image4]

* **Logic:** If ![][image5] (Near ceiling), suspend new buys to avoid chasing technical peaks. If ![][image6] (Near floor), trigger the "Potential Bottom" filter for Spring signals.16

### **2\. Foreign Ownership Limit (FOL)**

FOL acts as a supply/demand boundary for blue-chips. Use the **Room Availability (RA)** index 9:

![][image7]

* **FOL-Arbitrage:** When ![][image8] (nearly full), increase "Conviction Score" for Buy positions as stocks often trade at a premium when scarce.9

### **3\. T+2.5 Afternoon Pressure**

T+2.5 settlement concentrates liquidity after 13:00. 'Trading OS' exploits the 14:15 \- 14:45 window for final exit decisions to avoid the "shares arriving" sell pressure.16

## **"T+ Swing Alpha" Algorithm and Risk Management**

The system aims for a 15% profit target per swing trade with absolute precision.

### **Profit/Loss Formulas**

16  
The algorithm applies a minimum Risk/Reward (R/R) ratio of 1:2.

* **Target:** ![][image9]  
* **ATR-based Stop Loss:**  
  ![][image10]  
  Where ![][image11] to filter market noise.  
* **Quantitative R/R Ratio:**  
  ![][image12]

### **2% Risk Rule (Position Sizing)**

To protect F0 accounts, each trade risks a maximum of 2% of total assets 16:

![][image13]

## **SSI iBoard Data Fetching Technical Analysis**

Based on the SSI\_HARrequestLogs.txt analysis, iBoard operates on a complex distributed infrastructure.

### **Data Extraction Strategy**

* **Real-time Data:** Connects to the SignalR Hub via wss://fc-data.ssi.com.vn/ for instant push notifications.  
* **Authentication:** Uses Bearer Tokens and unique device-id. Automated trading requires RSA \+ SHA256 digital signatures with PrivateKey.13  
* **API Optimization:** Uses GraphQL to filter necessary fields from the /stock/group/VN100 endpoint, reducing response size from 170KB to speed up client-side processing.16

## **Explainable AI (XAI) for Transparency**

To build trust for F0 investors, 'Trading OS' integrates a Natural Language Generation (NLG) module using the **PhoBERT** model.

* **Sentiment Analysis:** PhoBERT classifies CafeF/Vietstock news into Positive/Negative states with \>81% accuracy.  
* **SHAP Explanations:** Explains the "Why" behind each recommendation.  
  * *Example:* "System recommends BUY HPG due to a Spring pattern at 28.5 support, combined with 3-session net foreign buying and a positive sentiment score of 0.8."16

## **Conclusion and Recommendations**

The **'Trading OS'** represents the perfect synergy between classical finance (Wyckoff, Elliott) and modern tech (Microservices, gRPC, AI). By integrating Vietnam-specific factors (T+2.5, FOL, Price Bands), it transitions from a simple trading tool to a disciplined, professional investment platform.

The Board recommends:

1. Implement a **gRPC** infrastructure for SSI FastConnect to gain an execution speed advantage.16  
2. Strictly adhere to the **Risk/Reward \>= 2.0** and **2% Risk Rule** to safeguard capital.16  
3. Leverage the **Explainable AI** module to educate F0 investors, turning raw data into actionable knowledge.19

#### **Works cited**

1. Vietnam: The ASEAN powerhouse \- LSEG, accessed March 27, 2026, [https://www.lseg.com/en/insights/ftse-russell/vietnam-the-asean-powerhouse](https://www.lseg.com/en/insights/ftse-russell/vietnam-the-asean-powerhouse)  
2. Vietnam's stock market enters its strongest transformation in a decade \- VietNamNet, accessed March 27, 2026, [https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html](https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html)  
3. Vietnam Ho Chi Minh Stock Index \- Quote \- Chart \- Historical Data \- Trading Economics, accessed March 28, 2026, [https://tradingeconomics.com/vietnam/stock-market](https://tradingeconomics.com/vietnam/stock-market)  
4. Monthly Market Outlook \- SSI, accessed March 27, 2026, [https://www.ssi.com.vn/en/organization-customer/monthly-market-outlook](https://www.ssi.com.vn/en/organization-customer/monthly-market-outlook)  
5. Stock Market Outlook for 2026: "The Era of Growth – The Great Wave of Transformation", accessed March 27, 2026, [https://bidvinfo.com.vn/en/stock-market-outlook-for-2026-the-era-of-growth-the-great-wave-of-transformation-10013749.html](https://bidvinfo.com.vn/en/stock-market-outlook-for-2026-the-era-of-growth-the-great-wave-of-transformation-10013749.html)  
6. The Wyckoff Pattern Springs Setup Trading Strategy That Works \- Traders Mastermind, accessed March 28, 2026, [https://tradersmastermind.com/wyckoff-pattern-springs-setup/](https://tradersmastermind.com/wyckoff-pattern-springs-setup/)  
7. Kiến thức cơ bản về chứng khoán nhà đầu tư nhất định phải biết \- Vietcap, accessed March 28, 2026, [https://www.vietcap.com.vn/kien-thuc/kien-thuc-co-ban-ve-chung-khoan-nha-dau-tu-nhat-dinh-phai-biet](https://www.vietcap.com.vn/kien-thuc/kien-thuc-co-ban-ve-chung-khoan-nha-dau-tu-nhat-dinh-phai-biet)  
8. Understanding Vietnam's Stock Market Regulations for Foreign Investors, accessed March 28, 2026, [https://globalreferral.group/understanding-vietnams-stock-market-regulations-for-foreign-investors/](https://globalreferral.group/understanding-vietnams-stock-market-regulations-for-foreign-investors/)  
9. Economist's Note Understanding Vietnam's Foreign Ownership Limits (FOLs) \- VinaCapital, accessed March 28, 2026, [https://vinacapital.com/wp-content/uploads/2022/08/VinaCapital-Insights-Understanding-Vietnams-Foreign-Ownership-Limits-FOLs.pdf](https://vinacapital.com/wp-content/uploads/2022/08/VinaCapital-Insights-Understanding-Vietnams-Foreign-Ownership-Limits-FOLs.pdf)  
10. VN-Index loses over 51 points on rising selling force \- Vietnam News, accessed March 28, 2026, [https://vietnamnews.vn/economy/1777791/vn-index-loses-over-51-points-on-rising-selling-force.html](https://vietnamnews.vn/economy/1777791/vn-index-loses-over-51-points-on-rising-selling-force.html)  
11. Choosing Factors for the Vietnamese Stock Market \- IDEAS/RePEc, accessed March 28, 2026, [https://ideas.repec.org/a/gam/jjrfmx/v14y2021i3p96-d507713.html](https://ideas.repec.org/a/gam/jjrfmx/v14y2021i3p96-d507713.html)  
12. Market Regime using Hidden Markov Model \- QuantInsti Blog, accessed March 28, 2026, [https://blog.quantinsti.com/regime-adaptive-trading-python/](https://blog.quantinsti.com/regime-adaptive-trading-python/)  
13. Connection guide | FastConnect API \- SSI, accessed March 27, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-trading/connection-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-trading/connection-guide)  
14. General Information \- FastConnect API \- SSI, accessed March 27, 2026, [https://guide.ssi.com.vn/ssi-products/general-information](https://guide.ssi.com.vn/ssi-products/general-information)  
15. Service registration \- FastConnect API \- SSI, accessed March 28, 2026, [https://guide.ssi.com.vn/ssi-products/service-registration](https://guide.ssi.com.vn/ssi-products/service-registration)  
16. Trading OS 331e99f8329680de87c5c94098527c2f.md  
17. Ssi.py \- gists · GitHub, accessed March 28, 2026, [https://gist.github.com/Kingkha/0fef4306652e84e5d00812815e485f79](https://gist.github.com/Kingkha/0fef4306652e84e5d00812815e485f79)  
18. Python for Algorithmic Trading: Essential Libraries \- LuxAlgo, accessed March 28, 2026, [https://www.luxalgo.com/blog/python-for-algorithmic-trading-essential-libraries/](https://www.luxalgo.com/blog/python-for-algorithmic-trading-essential-libraries/)  
19. AI-Powered Stock Forecasting Model in Vietnam \- Fundopedia, accessed March 28, 2026, [https://chenjiazizhong.com/2025/03/26/ai-powered-stock-forecasting-model-in-vietnam/](https://chenjiazizhong.com/2025/03/26/ai-powered-stock-forecasting-model-in-vietnam/)  
20. Day of the Week Effect in the Vietnam Stock Market: Evidence from the VN Index | IJRISS, accessed March 27, 2026, [https://rsisinternational.org/journals/ijriss/view/day-of-the-week-effect-in-the-vietnam-stock-market-evidence-from-the-vn-index](https://rsisinternational.org/journals/ijriss/view/day-of-the-week-effect-in-the-vietnam-stock-market-evidence-from-the-vn-index)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAXCAYAAABwOa1vAAAC30lEQVR4XsVWT6hPQRQ+k5RQIol6ehtZ+BPyb2mlWNhYSlmJLCW2JAtWsqBYvCgbic2zIItXNlZkgdKzoKyEKCXy5/vmzNz5f3/3Jz1ffffe+c6ZM2fO3Jl7RQhjr/8Zc57EPx5wrHCJc9azGcgbmg5VBO/aUw8S90E9iKGTaaOvS9VWimY+Lpv7Z1xNlNcL4FXwQGyu4JC9loGJNeAZ0ThrJalgeFwF/gafge/Bfc7DOtXiRtoS8CH4yrVXgE/AvZ2HyHV0YPx34HO2bf8y8G5wMpJ3gB/Bg9osOywGZyRJOEbRgcJF8Be4x2mbwC8wdTGyXqeEEygNbE1lMh9vgveC5GTnNDDhLuR60RVh1ZY7ja/UYXCRd8oQEk7hx2b/GPTlCqYYlnCB26Kv0iVwHYK8xX0a3JZ4pSgTDiU9KhpvFtouyKdFizGRL5PH6IRtx673I6MD3AHvgkvBs+AP75DC9isTdjBaXcazNKyskZWZW4LRCad4Ixr8E7jBadyEj0VfF4usOEjYtDYdcU1C0rPgdqvWff86YWwKsyDSWUG+JjWMqvALcD/4VDT2d1jYrmJwwm7CM6JBmUQMtjkZHpcJjEu4UuGt4NeupTZWl/uCY1SRJNxYBQtn45HTSjg+OWK0KnxE7HFYgNXlsVnFuAlzECacJ3BO9OwMr0kIViastuPgh8qoaeUdjNHl2wK+Bk+ItsOSGlmI633RDbaxU/VU+Cndh8Pww8GzmZP34DNjTYA3wAfgpNM8+P7eEr/JFPxMvwRPRpoFA7qdabK7m7NOnMtzRbrD3Yr8QEyB38RWznyW7KA3rKp+mjua8BxjmejyT8Of/xLYcHJeio9JsQpEVWyBzvxR4c/PTnBebhwDjHMMvAyuzmz98AOFAcuhSyWgZqtp8RI2McKcIMTrS90js5hCUbECr9atc4UxRh/kOtqpz6NmG1LhGhpeVm7YUgxyGoQyUqkEOJt3ye5/AJjWgtl5X7VUAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAXCAYAAABwOa1vAAADLklEQVR4Xq1WT4hOURQ/t4mEmkgyRbNhFv4kMWRlRSxs2KGUEllSbEkWZKFZDA01fcoGsWHhz2LKRik2/pRsKCshSjFi/H7vvPvevefd9773zedXv+++e+4555537rnnfSJd4aygBq6VqqqkFI3MT1OqaWG/cLN222iXXEwKY7RQUZhMtbb7P2h37BZNJtlaSiElMxgCT0BzAuMOcI5Zj5DwR9EFkPb7vKAGB6NZpOhW4ueMqJ8RiSqrTNgGcFW5INfAGfBlettINojpY4xv8/lS8Dl0dnkFaHck8+c+YnwlOvdrobvt4HAg2wx+weRAoZFjDDwkXs3JWvx+FQ26CdS/BP4Fd+ay9eB3cLdXCgGDUxIEHMBhbdLKwBvg/VC4EJwC34uWRShjVlIp9lgDfhLN2pJcxlI6DLsFhVaMmoCd39OWInQdTzDCAKKaF8wXgc+ke4Zvi+rghNxqjB8w3sO4KVaLUBcwf46K+nsHbgNPiyZjeaFTk76tWPmF8Y9d8MjtnohucAe8K/qiZ8HfXs/CloTZn9mlP09mdlmkUUXmgrVEA97UQGzhWEbUY72z7olBqD4VLZcUyoCTPuWqlAEz06ORYtUmkzCzt4QdoBk+YF6KsKQY0Jj3nY3lRgjYdar7ZmCGX4N7wBdOfU/nc0lFOwy+kajwq0oBpkSdMmshOOfL+EscIstwwutG8IfZbxRT3Iv0XWI2H4EXdZp1bLaouaULZ/w5tpy6gIvOYYKrC/iIaDu0YHbZNsV6uoI5gw3byv7gOQHHTRhwxyyck2qZeNR0CTkOfrZCKTIfY69wY8fNXXhLw6OYDz4QvWDr8nflwK7Ams8/HI6nwt7MvurBZ5YH29N18KHT8gtKxjFRNyW7ZAX4mWaJngyTW34ksoAjlm+WGTgez2WJT4EfiEnwp2iT/ybajgo4ZjWdjJnwkPG8WPT42cvZoaYhPJ+/TKFkS6MBpaJ/yu05jIj++dkCDuTLswH9HIPHcThdYRf7RupdUzJF/UplrUk1TlcNorUmRY82OjHUome70qA306pdb/Zd0Mapf+OqTlUSonm1TzQ5b1pTdNfoGyaz/wD0lpHJbLQaPgAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,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>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFoAAAAZCAYAAACxZDnAAAAEjUlEQVR4XuVYTYgVRxCuxgiGFUUNisSgq4kiQSKoiCYeFA+CoIIGBIN4EwT1FIWQS1APehAx5CKKGBBBxVsgeNp4UvcmhoAibIIYkuBFWPGHqPVNdc/U9HT3zJv3swt+8O17U39dU13985aoKxhf0EN0H7txBM+wsV8tehcpR6uQrZwEcde4ZqCYJGm0Rin/ti/TxK+JTQmdONTaOoO0YVo7EahmVJUMEoaG+M9W/rYLNPaTCdlQybbAbOZ2gp3J7TV3MKcU5kDqNT1d+jEOo20be3WGtrkpPGK+ZZ7wFQk8JfHZ5smNKeIdKWtKTxZBYSuoSDOZ95nL7PNc5gPmwtxCwctglCT/lczP7POdkgXRKpL308R4n2qjEF4z3zA3+4oEEPxv5mJfwVjLHGe+9BUF/ALrZ19XIK7JAZMzzA0lCdG/zKvMqVroYTpJHbYo2UaS+miHrNCmKPJB5odKH4HJjMeYH3uacD4ig88vzGklneAD5nUSmwiyIOi035iHy7quMMx8zPzIk4+QTD6KFANWp98885l/ejLEgLwjoCgoCAqD70nYumPm67aaSyQ208OzlWMG83vmT8xPPF0boFhveUh/3Eu2ofZroYfvKCuq0UWcxRzlSHtUuFaF/opkaeCzBnYkw4PGVoAAXY5ut4VuDByiOGj/IDmQy4dqcr5yqAn25FJo5JUhEA6Ng+7VRcTK+J0krgMK/Q3zHvMJ8y7zS6UP4ihJIH+ppXCW0isAEzBG8sIxmwrUi+PrTZIYewtxI8QLLfIRT64R2jqWkxz8eaGNFPoyyWoEzjP/Z+50Nj5c512k4AQHkS0lkgkKwsihikMlsUdHUM4Ct4afSbYW91I5Igl3U2j4+Kt7H4mf7uglJDcbBxQe+z+6OwjMHGYwtm+hG/29yAVNbTVYgkjuP1/RGfJSniTpKtwm6tBNoQFcA28xFzDXMG+QXN10oX3Mo+xKaKKN5QoS2jbwlscCMnR/cEvIymKyDxxGSA63CqfxvrmHSF+KeJhkvGBHR4CmSRUa215DZEm4W4drLEwAzhD9+wFjjcQKbZXZ4KG3/Zxk79ZwB0MwoMV65l8kF/4EQkPmgLLtHu0Od2xxGu5w9n9g+fiBuUBl5+K5rWIdye8DfeOyHR2ui9vkQ8pFJPvwr57cDfpcC21S+NhNsq0gdhu4Wwcmc5N9jkLGrUwYCnKbqj+kEPMhFVdI/OrDbQEdamHQSKgHDrdMQLKqcd44IC46XK8wt52O63S+YD4jCZgiLv3D1kcfbjEep8o92I1aKQZlMhHPMLX36JC/Q1CHDewFf14hTL6hH0nGsL8KM6w2coasUDIAzXeNeY6kob6lsh+A/wP9Y2Q7usB8xTxEujGCadWi6qUlVW0NCgcUFl1V/p9IbzCH+TXzNI+HO69Fbbbwg/1p+z2GpcwDzFNUvoH0ATbn2tQboTdRYuhv9B4inmhcMxkw4dkNJoFBjNLtGM38m1l1iCxoXyIPHtXXqEqaIOWV0vUFnQ3YmXUGo71a+E82tH2FJn5NbPqG2sFrDWrQrf/7jhb1eweU3NhkQjY8OAAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFoAAAAZCAYAAACxZDnAAAAEbElEQVR4XtWYTYgVRxDHq9GAoiT4QURUkvUTlWAgghjXW25CDMSAoAdvC4Ie9eJNPZhDkM01IexBBJG9CTmIvJvB3IIiJAibECIavAiKuuha/+npN9Xd1TM9b+Yt7A9rZ6ar/9091d01/STSMN4ln9YCiYn06ebSnsUiHkFcEtNQp8Ed0K72aJhF6aUtYxnTWBotGF/LefTUf0/N1LIYfXSl0xg7iS2r2I6wHQsMZfBprGU7SrHGmqFv+Lqsqq7gBq69gFbWF439ao5+ecS2wHY5dNTwjKzma1dQDhMX1945z1OLUHfnI7b7bLvK54/Z/mT7ZFgjzW2qtNDdIauVfMG2YOw7OoNmu1dLYZ7tHdtXoaMGNP6YbWvoYA6wvWB7HTo8tKBqZYLKnawIx1X+e1iW8L+nfHeD7YNheeWWtxjzUMsFO8hqpa4ItLAzbCuFPwkqz7FtCsrrWOBR3OLritDBLGe7SbbdBMlAaSCNnWK7G5RrTLD9y7Y+KB+QnXwEKQW0D8jXriarlTrcbxTPWSAoCAgCg/sc0Hl9qjE0Q7YO6roy/6o/huCFnrD9UN43gVTm92tx45kKO6weDbQD0rVT4pkDbXLG4jFJNnVMNryw5ATV7wCscqx2rPpw0E3gQ/ol2bx4nJStrlINPp5gvxzjSoE6A9K15e4tOkKgT/L1D7b/2O6xHaqq65yneLs0MU3RDqh+VBg7AXNkXyx3lyCgCCwCjIHXn1zSNAV6EJRL6gIty5E6rrF9WD7/xPaW7dvyOQIzhJn6hRp38JA1bL+TnaAU+Kji46rn6Lgn5GCcYmbZ9pBWIx8OimkRaK+rMKBqOSu2kT3ZOBB45H+sbhWcGHBykPlHgtUY5iLXKFIOJWKC3I2X+j90BCDAV9ieU9xPA2q/QKzoKIhKoCUmCnTZQlQesIGKI20xwSouIFraQB8Xq1t7Y+zqr0sJqAw/zpU4h+aAgGM1zLK664rGoqlb0Uh7KaAdkK6dLke1me0hid8PZOsPKLGDpdNE72ZoL9ncLQsxIShTGyzBh+wfts9DR4TfZV85mneamee2keIk9uPsB6hADAO7FGlRat2H3ekOkj1ryxNXuaL1uOym6tedoOj2U7Id/uq5qhPKy6AcQIhAIa2g7Zi8dZo+deTpkTt/o/KHlJBggfzFtqV8xg8RTChWqAPa8EeYW1xOB9/fVH0I0YdLp7Ah+8jmRARYWJFfxLU49E+UGvlxS5i5RNVg6qkLWOHzKqwjcY6O3So4Ar3i63Wyk/Uj2wXyj4r7yX5DPhNl4DSb00L3hqxWglSHMc2w/UyoY+gsabuweaySxf7/4Ki3/F+GlRQT9B1hggzhzNsGp4UO9xo7yU7K9+SfQPohCsGSp/6NYm9VEvtGoZdWTE/tlKhtqYUt6KoP6Lm5fDp23FGu4zU6lh66kjGojCopRpWOqvMYoZH2ko4znK3o2M/IhF2Fz0uDUUfdTtdfbdPvhHeUlw3ErcQlDSQFSUdLMtrJqNI37wGYrtbYlDhcbgAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA/CAYAAABdEJRVAAALh0lEQVR4Xu3de4htVR3A8d+lB6WVj96U+ayIrEuEhs8ilJLK6qYlJUlIWfSCLC2JuhS9oNSsiEJTgx72gP4oigq5GFTUH1ZQiiVcxQcVGUj+kZG1vq69PGvW7H3uzJ05M+fs8/3Aj5mz9j57zln7PH6zXjtCkiRJq+1oCzpD5ZL6+I5ZDOM/T+N/htIW8I0k6SF+IEiLzfewtNz8DJC0Xn5ujIwnVJIkSdIm8d8LSdvIjyBpvmz4PbnhA0iStpcf5GtmVUmaR342SZI2m98tkiRJkqTZ8b9OSZIkSZIkSdLWs3VakiTNnAmH1srXirS5fE/Nma04IVvxN9ZvPh+VJEmStOgOTHF7ivtT/C/F37rbxD1d2W0pntrt/5Ru3+emeESKXd2+Z0Z/1l4fh5/cHgPq7dvRX2/EUL19JXK9Pabb777or7dbU9wV+Tjcj32vqXfQYuo72ZpjS3HCluJJSqNxZYo9kROJ2rNT/CLFY1O8NMXfUzxnxR4Rh6f4b4rTm/LifSnuTnFUu2EEqDeSqv2tt1tiuN52Rj72m9oNkiRp+bwwcksPrWR9SEqOT/HP7mcf7v+ftjB5cuTWoovbDSPB8yap6rOWeqPuqbeT2w0xnERLmsoWI0njRAsOSUfdAnZq9fsnU9yU4uMx/El4Z/QnLiQiQwnJmgz9wTnBc6b1sKDeSt2tpd6eEfkYFzTlh6T4bYpPNOXSUhh6w0jSMvtjrEy2Tkrxp+r2HZG3P7wqaz0Q/Qnb92Lf911UT4j83Oqkinorie9a6u20yPvQbVzrS6IlSbPh/whaCCQGdNud1QXj0eokhO33Vrdbj468DwlKi0SObsNpaJF6W1vY4/1tQYM33HdT/KjdMCO0ilFvb41cb1+I9dfbTyLX25HNtjaJnleMy9vXeZG0cSYUo+Wp1RrsyK0/JAZ1kvPTyC0/BduZ8Tjk2Mj7fLHdELmc5KNVD8CnFY7xWvvy87agB92I+xovVxLTfcW0dxH1xuOm3h7VlTHWbL31RsJHvbV/i25kkt0Wf2Mtye1WIUFdy3mRJEkb0DfGjPFTdQIxLfF4QeSk46JYnXTQncd92/FZx6T4VeQuxddEboEjyWK5Czws8mD8V6V4XIpXpHh3is9EXk6j3odjlTLQWvX06vas9NUbj2mt9QbqjX3aeutLoovrUpxT3aYOLoncWocLq23UP+XU83tTHJDi5ZHrFO+MvOwIx3tJV1bq9ZWR70vdvrErZ1/OJT8p57xw7urzIkkag/abSduORIlZnMzmHELy8I+2sEPrCttLslVj1ilf6CQAtcsjtyo9LXJL1s0pzo3JWK/rU3yoK/t9ilenuDRy12NJTL4TeTD/VyN34YKXV93iNUvUG8/7wXobeF1Pq7eDIm/n8beoF7b1tRTeGJNzRWJKPR2W4urILXavjXx/kLweFzmhIjFmmZGzU1wROdElCebxkRj/ubvP71K8K8V5KT6d4iMpXp/im5GP89EUv05xaOTzUrqEy3mRJGm0Dm4LtgBJDUtNsOAriQ+tJkOJTlmaou7ue2aKX6b4QKxO1rjNOmQkF4wp49glKOMLn4QFJBf1OmO7YzLQviwJQjfgnq4MJ8TkPrT4lC5XEsP6Mc4CdcTzoN5Iqsrz6tNXb6DeWAy3rTfyvsenuCzyrNudMTn+1yP/PZ47dsfK2akku6z5xpg4jkPQZUs5j5n6Kokc2JftJHrsSwva5yK3xJ0fuYuapIyWM1oRS9JNFyjdzuC8OItVszPwn9BCGtNzkbbPfr+TXhSrxz0RQ2tu9SnJyFavtVVaxurgi3oILTXssydy9ycJx1X1DhW+7Ntj17H7oT1zMkNiApIDHldJHMv6cIx3Y+HZghmVZQwcCQeJB9qkZBb66o0Y0tYbP6m3vm7bM2L1cdsoiS6Pg2j9tftJN2iZecoLnHoqLZjF3liZLHO8o2N1aystfRwPe2KSpHEOeMySNGP7/T09R8bwHBYfX6R1wkVrBd10tK7sC5cfYpzTUCvN2F0b+VVMVx0Jxbe626Dl7HWREwa680iQ2UarGi1E/E5CRwvQKZGTCX6flniOBfVEt3LxscivO15L1AtdpUdEbj0lIeZ11qKljPGKBS1sJak7MfIxSytnwX0oOzLyeeE8lPMyMiN8SpK0xEjU+lpY+OKkfNqnPl+OjCEiSovRsmH806diMlj+8O72h1O8uCujFY7kja5C0MrEPp+P3CrENT0fGTnh+Fr0t16NDfVE8kRy+v2YjCH7TeR6oX5I6Binxhi1m7rttXZ2Ktc75X4ck9Y5jkkrZ52wMcatjLvjvHCeynmRJGluMbC+HktUMIOwL5ErGKt0Q+QvRPaza0mSpM0yrblES4kZdw8uv1C9NhhMThLGDMchdCcxroiWNfalFUSSJG0lE7ulQLJFdyYLzdJN9IPIg/FJ4Ka9BEjoShcgg7lJ2FhLawhjk76U4vY1xDUxPNtTkiQNm/bdrQXGDDuSredHnjTA4G5uf7neqceumMz2K2Pgrp1s7sV+9fIYQ7HVs00lKfyekzTPGPTdjlNjHay2rMasvXtiZasY+++p9pklWt/4e4Yxq+AqFloXkx1JmiW+nMqircW0yQa0fr29LYy8P7NKh9glqszv9XWxuqQN8k2kEWBJDhKtsmhrUVoZwD5PrLaRrPV1WbL/vW2hpO3gN5QkjUFflyKLmBY/7srOi7zYK61j13VlBEuAHNXty7b2WPXK85KWlGmjJM0WSRhrq5F4HdNskyRJkpbKpSn+Fbllsm8iB1EuWs5SKlwqjAHxdEtzm+VX2KdcJaD2rBR3RN7OZcY45s9W7LGkbPnR8mlf9e1taRpfLxK4hBJJVXvR9yeluD7yZaq45BKXsHpzrHznkLSxft7lTXnBNTM5drnYuSRJkvbD3shJVR+uHsHadGy/qNlWlHXw+pIyksG9sToZlCRJ0jqwjApRcPWJs7vfSdhYxJgLonPt1j5l4seDlxdrMAOYYLavtBz62polSdqAMmO3XlrlDylO7n4vS68cOdm8Srk0GF2mLRLBciwtPDMRSdKcWZKvJpZHIdli4gGTApgkcGvksWf19mktZExKYJ8r2w2pEiknoZMkSdJ+YtwZV5qok6oLqt/pEh0a3wZmh3IpsZtikuQVJdlrkfy9pbr9wRRHV7f7vCfFcW1hg9ZCZrGe1m6QFsOS/JsoSVoXJgvsSXF1TL4pKKu7MHdFf9JVnB55yY6+y4WRON3XFibHpvhhdfuuFDur233Y54y2sMfecILDHDEBka8BSRvhZwjOjJyMTUuWGLs2lLBRi2y7pd0QK5PBFi16JG0npjgnxQ0pzqq2Hxb5Khcsmvy8btvNKc6t9mGNNxZWPiAm1309JMUlD+0hSZK0wFg7je7LGyMnXCzbQQxhMsHuyPcrPpvigcjrs7UOTvGOyMd+WUyOzyK990dO0gpa4UrCSALIem4Hdbfprj0w8qzVunXtwph0v94Zk0uR8dPWtWn8R0WSNsgPUm0dJgeQTLUx5NDI2/+S4vwU34i8zMep9U4dkq97Y/Wx66hnnF4cuWUMJ6T4d7WNx8nivbQElmvHcl8mRhR0lZLQ8Q66OiatbZIkSdoEtIbt7X4/JcUVkbtLCxK/0rUKEjMW4r27u01yRlJH6x0zVbm01vEpjui2S5IkaYNIsmgtOyh2xGWRu0pZUgTMPuWSVyRjt0XujqWLlC7Uss9JkbtB3xB5NivHYp92tqokSZI2gESMKyXU6Aaty/i9Hj8HWt5Ad23ZRoubgwvmgqdhHnlWJEnSUjMZkqQF4we3tL18D0qSJEnS+vm/lCRJkiRJkhaSDVuStpEfQctqDGd+DM9hVDwhkrRefnJK88n3ppaYL39JmhU/YaVN5ptKkiRJGhmTfEnaRH6oalH52t1a1re0v3z3SJIWyhi/uMb4nCRJkiRJSv4PfUe/oi7RvZQAAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFoAAAAZCAYAAACxZDnAAAAEtElEQVR4XtVYT6gWVRQ/gwpGkoRliJI8oYUFtXi6kHKhiCCSaAoVQS1c6CJaFPkHXBjRooWgIgiiiAsFpY0LsaKFJIhU0CZpU6AhiUi1MirRPL85987ce+aemTvffJ8Pf3DeN3PO+Z05c+695955RDOCInH1eMDO17aUiMwdvp0Yyp8kxpLbWIJ4+GDtQdutw9AWu82mMc51Y0ewLd3o5HY6hJjFMkcrHy3yJk83UvyUTiPwcZdPsGxg2ZaQzSwviFsPFPQG/31dqyeBnFceDQMi29TSco3lf5bdsY2eYjP037DMVzYNBPqUdBz7wRUyXPpiK8sekpWFFfY2yy7Ke9R/VHPBu0fC9YD+KMsrLItYMLHwzhc5fFeN6C5JwNdidZkXgkA2xbYGpllus/zDcljZYkSvm/PuDsrVYL7Ecofi9gXXf/nv6kCX4oN7jmpuwT6fE7g13mL5KbgHfiep0cFU0BBw+pXlOW2gutAfaoPCeZaPSWb/KWWL0ZFMAi+SxDykDQnsJ8lXA7qTZD291Bb7+c+O2FC2QXA9D3ngfknlQXTE6W7Krf0IOH3BMjvhBBtGdJU2KHzFzHkkiaDYTyr7KMCy38jyg/ud1cguBp5/idKFxqpFi3wmVlcRPVfvL1ip4ILH+RRnSeKH9UCrhA5+JtAu4DCtXgKz6EeSWdp2igDtoKyyEnjoDSr7l4rYUSWHBSz72PcE/07lUSr4oliFfsCyThscPNcqtOP5jKLMMEnxzKuhUgNLBTP2NMsxEuc/Wf5iOSAura+LvvcdLpzXjkKWULi02iMIplhOsOMfhL6YIqR0MabZJyp0QPF6XUiPrkJrfYi7/KD71LKPcasoR+MMyQ7qd9HfSHZfXDdRZ4/l9jXfvlkby4TKFRLo2oBoL5NspNvJaDndNS7RNaOl0OlgVkEtvQdOGijy+9RIs75dzHKd5Z1KI1hDcgpxzd1AQTv575csz1M9UO+y/M2yMvC08CpJe/qZg6EfD0VeodOwClrqi0of1RItFV0A75wePgffxJ9WeiwB6FFsCydZ9lLwAHexvBCuHjwLfkbjiGTO6BwUsmFdI7vQaEvLtcHBc5OFpiYPZ+tfAv1czgCzugE20AVKJ/UZde+i37Ms1Ep+W8xqcHd3DHIF8SqmCD1aioGzaz9IEN8K43cSGzbCSyTtLgXPDSZIASo2QXBDHiJeLuJ9CEfjb4P7CstYbpFOKj4i+dbxLMWNHgVO92+ZGeAe14ZMyKlDio7id0INJz4oUoV2g18CRcU19qKQDi4mWQgcFnSNtpJ83Ph2CXmP5UrohKmOWQNyKHiIxwqSryuM5Ecsl1mWkpxOak4RJYVzZWwX0W2pD9C311Jwjo7NJjDTeBIVH5C0I3zJhUvff0bj/VD0ECgWJiC44PH+UXHDFZOS9i9iA9wri/X8u4XwPw8Tee1hIPp8GXqgt+7i7D5x1wYa+WMwS677zR3cSaOR6HiQHTbbMQNjjGWHMiyGOkSGSxaacZqaQUiGSypnGj2SynHN8XGwXW1LhQyX/ugTtI+vQ0lRvJwwOT6jYXKRB2FYWsPYjxSDUh1EngmMMPVHxVhjG8EM9QQw6pNG5T2+eAi7fONr+fP3agAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAG8AAAAZCAYAAAA/vnC8AAAFU0lEQVR4Xu2ZW8hmUxjHnxVT5JRDDqGRUISZGhK5kFwop3Jo1ODGlBvKYWbEjUHukLigQZJSNJJEQs0XhUy5UChRHyUhKSGHGP//evba+9nrXWu/a+93v9/3zcev/vPtdx2etfbzrPWs9b4jsky46h//N0W2YhkZMKfQZUDX6XQZzdelaroisRfSepfV9GIjMqZbxrS1dJTNuqzVvEit5OIZFTecATfOKKMYGcYBGP0S/L26QGz3P2Mzc/CdfIl/90APxBXgJOhzaHeirpTjoM+gl+OKLMXmixv2ImH1HOgF6CdRXx3Yru7kRuhp6BvoK+iYdrWH9mjX6k/oGtsoxV/QP9BFcUXF3dDbcWEPLhedzM64opuRUts4MAA3QbdI/+DtgLZBm6Q8eE+KLvqpsPEidGxUHuCgz7aLMm5NFz8qOgZffmWRnm8H7jJJBa/MzgbJBM+pPdqejhlrX2l2BZ8D90FX6KO7U3T3DYUp91fRyfeizCeSa3ir5Gq0/Hpoc1wxhXTwysgGT/oEz8BUybR5fvX5SOgR6EPo0NCogtv4XegG6APoXOhN0Z21Ffoberxqewr0EfQ1tAee+qV6psPIHdBt8CH7PCZql5eiT6GHoEOg16D7RZ11bdWPXCA6VpQNJqCNt6AHo3IGbhd0dDa0ecqDF2w3Y0wL3s3Qi9D3lfh5jVanJ8pLis21KucDEkNj26tnOo6H93nVZ06IE6MsHJU2mXoDR0FvQGdDv4kG4iroVfFtHS8G20UDh/6O/e/Vrp4wZ2aEaTCAr0vtBNkHugs6rG7Rj47gTUYrIhM83572eHE8syrcKOoXnpdJ9hNd3c+IWqC4E5nirjTtAnQCdyh35G603mgmmgveEdCP0KmmjBcYrrBNVWD4TOe+I37CjoHkjjlRmrTOPoEFaWeLDPXcGMCnoINFdyFt12RdnaYjeCla1jPB8zAW6/2TdqH9BdGxktA530r7IkHDTJnB2YeL7jh8J5QNTp3MOgaEgQnQkXTogikjnDDPPJuC1wptOL9omFLtrgwwJTNwp4t+zeBuDXDsRclfsFI8J7rLuQAZzKEUBS+zIHzwXDp4nqgfF1x2rJB+4rPN8r6oIwO0751uygjPwD+k3ZbO3ynpXUy4w+PAWqrV5+KvMBz79qisi86d15Oi4GVoBc8Ein7iXYGyl0YeCxxrIth2W2YWii/nObS/KeNu+0TU8Zaw62h3i6ijQlubMjU1KBjb0am5GYRUbHaYY6ALUmZNc+bpGOVnXnpOMwdPJoPBOXLxxws57LyJxR1SX7SD6hnzgYfmxU2dhxMIO8ZCO0yv7Pi86ApimmXbg6o2/LXm+OqZ9tknlTID66Cfpe0ojo8F4WzKzlHfNps4+Cf+s0t422wVd1E36AreyaJHTu7LdSt4ZsiQoU5rimDfTZ5561BIh7CwRAY/3BOiv8ZEQXW/izqEP6WFsjVOUwEvJF9AlzZ1cobojdPu6pQTLxTt+5LoORef0cpkP8LFlK7R8j7f80IKi1UHA5wFoz+Ivpsl7hPEYAbQ1TEur0A7nPqYfpueIXrAWxEvMbFTWM6X4F8L2/GyEa7qtjxum4P9Ka5oXl54iUkQT2me2LHGGtfRr/wt82HoBBa0q1ufLE1Nvs2SwhT0MfSeKbtOuGJd61CfAyvEA3sx4Sa8WH1eK5qSTVrOMfQH7eVfwMlxk4WjMLcX5ll4D/Sd6E2M/6cYp17P0HGL+xU3nCdhEiWT8W26AjNZMiqV+a5RuuqKGcXICmC1vMfs/Bc80fWO0c5t0VW3BMxv5JEtz2ZuQO8BXQL5rqmaVNnq5l8d4wxRWojnxgAAAABJRU5ErkJggg==>

[image10]: <data:image/png;base64,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>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGcAAAAZCAYAAAAsaTBIAAAE/ElEQVR4Xt2Yz8tWRRTHz2BKkWBmKFJSCAUWVOJKMdrUIsIWaRgUJbgIIiIQclEL8Q+QsB9i0cJlENFGXRTxUhCC20KQgl7oBxW6EJR+kHW+98zc98zvuc+9z/uSHzg8z3Nm5szM+d75cR+iCBM6PMqlEzJ1RyYIWI1frbBCjBrXqMZVzJzjF5mw61SolO9/TWpCKd+0TNGDjeFCTRFyGdjBdtUavhdJzinpnBejO9vMtsj2L9thOFIRd7EdZHuP7eGgbC6kBkEiyKehM0smyBDaQrTV6lBVi638QgjTidMRNuQzczd//M22XhxecZkhdcukxNnG9iHbTyRP2ObGDteyLZC00fYMpQLEHsdqthNsD5E86U+TxDnLtk7VS4Hyz9m+sfE3sn3BdlHVAYeNFifBSySdriQpcZ5ge53tObZrJAkqYvMcivMX2wcFESxRhWcJyfX5mSTmW4Hfw0j5n2yPKPe9bL+RiO7wV07ATWwf03hxNvCADvHnP6SeViNPCp6aGilxHO48qopjceLs8bxR7qucIpnHXcr3jvX9qHwpUP4t2x3K58alz9SiOHey/cB2KfC3sortVbZf2Y7Y37NQEcdE4hRyHYhTqOmIq2AeH5EIsVP5kUj4MJ4SqLNgZCwaCI6dytGL4w3B/sCeh0DHSZbbG2yfkDzxOojFhBP5jKL9N55pAxVxCisn7s6J8wrJNnLZfurthKRh3LiC22XOhQUBnTikxZGuIM5ptputt7hyUBGBnmJ7l+0A2xbryzaybKKGa28jnTiZVPXiZMpD1hpJzPf2N5rtZ3ufIoEGg3Fg60a+SpTE0f6iOL9Y2872pPXdx/Y7yS0lwEvPY7T0BIwlu3JMbeVoZHgY01HSrwamSwYS9nzvGw52CAiDFVl7TmJxhFPcUvuL4rj9E4fXULCn76sYbly3uAYFenG6WftTD8TRhbUceeQS1hIFKw4r7wVqqp7ta2nlSBQljh/2VrbrplsBBgfgdZK9tHaHd6iV0zLeItmVQ5E4VU6QJAefCgPfIrXHcbPCdf47I+9dAHPG6vHxUyDiyIrVQByc747sytlKcuVzV0UMHEnA7Qh76uOuYgY5cxK6JFw1xotj+n7xgCE553Wx8snLtqUyVhR/xR/6Oo15f6l+p8BLfdeXig9Rccbr84qFMUlxsOXomwPEwSGKzuG3V0gVPp5J4raWwbYNQ9jfg8Wx7bBlniSZiwM3Kk4o3a987szRicC5hJvca8q3hHSwl+0Bkr6dvcj2dV9PXjQvkJ8HPCA4y7EAHHjnwfGBC5cbv79yrHMNSTL0Hf4Qydv0Gba7lb9E+J7jXxDQWagG6H39l9RtDWcaEhoahBJMl5Cz5F/7EQZnwxWSc2KBZMu+3ash2x78ECikfzk3cf8wvTXhbx3kTT886OFltj+M/NPwtq3zpqoDOnFSKQr3Q3AbycoZivuHAAPQk8j/Q+CPqLRyZmUD2zGSJ/0ev8hbyPjTd164MeCWiO8h2TOnnZS0U2LmIk4LbgtfBpJJLIsTNYkcPpXimLYGKyUOnmhsObNhWqeXpSzOeEYOT5hInEFjeZTtwdDZEYTBz1zkof6AYeJ4QRt7mAB3I7NX+ZjlG4pj1h6b2uHysEjxDbKFpg5uQOI1MjwTw1ukCeOEvwsMqDqS2Xsa2nJo/SKTBZssUIZ5x6dCF/FiyNNar71ikVSU/wByqvTaIlzPUQAAAABJRU5ErkJggg==>

[image12]: <data:image/png;base64,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>

[image13]: <data:image/png;base64,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>