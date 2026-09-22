# **Chiến lược Đầu tư Định lượng và Xây dựng Hệ thống Giao dịch Tự động hóa tại Thị trường Chứng khoán Việt Nam: Báo cáo Tư vấn Tổng thể từ Hội đồng Học thuật và Chuyên gia Công nghệ**

## **Tầm nhìn Chiến lược và Bối cảnh Kinh tế Vĩ mô Việt Nam Giai đoạn 2025-2026**

Thị trường chứng khoán Việt Nam đang bước vào một giai đoạn chuyển mình mang tính lịch sử, được thúc đẩy bởi sự hội tụ của các cải cách pháp lý, nâng cấp hạ tầng công nghệ và sự bùng nổ của dòng vốn tín dụng. Với tư cách là Hội đồng Học thuật bao gồm các Giáo sư Tài chính tính toán, chuyên gia giao dịch định lượng và các giám đốc công nghệ, báo cáo này được thiết lập nhằm cung cấp một lộ trình toàn diện cho việc phát triển hệ thống giao dịch tự động, tối ưu hóa theo cơ chế thanh toán T+2.5, và tuân thủ nghiêm ngặt các tiêu chuẩn quản trị quốc tế.

Bối cảnh vĩ mô của Việt Nam trong năm 2025 ghi nhận sự tăng trưởng ấn tượng với GDP quý 3 đạt 8,23%, mức cao thứ hai trong giai đoạn 2011-2025.1 Sự ổn định này được củng cố bởi dòng vốn FDI cam kết đạt 28,54 tỷ USD trong 9 tháng đầu năm, phản ánh niềm tin mạnh mẽ của các nhà đầu tư quốc tế vào môi trường kinh doanh nội địa.1 Đặc biệt, sự bùng nổ tín dụng với khoảng 2,6 triệu tỷ đồng được bơm vào nền kinh tế trong năm 2025 đã tạo ra một lực đẩy thanh khoản chưa từng có, với giá trị giao dịch trung bình hàng ngày trên thị trường chứng khoán đạt mốc 29,5 nghìn tỷ đồng.2

| Chỉ số Vĩ mô | Giá trị Ghi nhận (2025) | Ý nghĩa đối với Thị trường Chứng khoán |
| :---- | :---- | :---- |
| Tăng trưởng GDP | 8,23% (Q3/2025) | Nền tảng vững chắc cho sự tăng trưởng lợi nhuận doanh nghiệp 1 |
| Tăng trưởng Tín dụng | 16,56% (tính đến tháng 11\) | Nguồn cung tiền dồi dào thúc đẩy định giá tài sản 2 |
| Vốn hóa Thị trường | \>9,68 triệu tỷ đồng (\~387 tỷ USD) | Quy mô thị trường tương đương 84,1% GDP 2024 3 |
| Số lượng Tài khoản | \>11 triệu tài khoản | Sự gia tăng mạnh mẽ của nhà đầu tư cá nhân (F0) 3 |

Lộ trình nâng hạng thị trường từ "Cận biên" (Frontier) lên "Mới nổi thứ cấp" (Secondary Emerging) bởi FTSE Russell vào tháng 9 năm 2026 là chất xúc tác quan trọng nhất.1 Điều này đòi hỏi các hệ thống giao dịch phải đạt đến độ chính xác tuyệt đối và khả năng xử lý dữ liệu ở quy mô lớn để đón nhận dòng vốn ngoại dự kiến sẽ đổ vào các cổ phiếu vốn hóa lớn thuộc chỉ số VN30.4

## **Phân tích Cơ chế Thanh toán T+2.5 và Động lực học Tần suất cao**

Việc rút ngắn chu kỳ thanh toán từ T+3 xuống T+2.5 (chính thức áp dụng từ tháng 8/2022) đã thay đổi hoàn toàn cấu trúc hành vi của thị trường.6 Theo quy định mới, chứng khoán và tiền sẽ được chuyển vào tài khoản nhà đầu tư trong khoảng thời gian từ 11:30 đến 12:30 của ngày T+2, cho phép họ thực hiện giao dịch ngay trong phiên chiều của cùng ngày.6

Cơ chế này tạo ra một "điểm kỳ dị" về thanh khoản vào lúc 13:00 hàng ngày. Các nghiên cứu về dữ liệu tần suất cao (High-frequency data) tại Việt Nam cho thấy mô hình biến động trong ngày (Intraday volatility) tuân theo hình chữ U cải biên, với một đỉnh nhọn xuất hiện ngay khi mở cửa phiên chiều.8 Hiện tượng này là hệ quả của việc giải phóng đồng loạt các vị thế mua từ ngày T+0, kết hợp với sự tích tụ thông tin và tâm lý kỳ vọng trong giờ nghỉ trưa.8 Đối với nhà đầu tư F0, đây là thời điểm dễ xảy ra các sai lệch hành vi do áp lực chốt lời hoặc cắt lỗ ngắn hạn, tạo ra sự phi hiệu quả mà các thuật toán định lượng có thể khai thác.8

| Mốc Thời gian | Quy trình T+2.5 (Hiện hành) | Tác động Chiến lược |
| :---- | :---- | :---- |
| T+0 | Thực hiện giao dịch mua/bán | Xác định vị thế gốc |
| T+2 (11:30-12:30) | VSDC hoàn tất bù trừ và chuyển tài sản | Cổ phiếu khả dụng để bán vào phiên chiều 6 |
| T+2 (13:00) | Mở cửa phiên chiều | Thanh khoản bùng nổ, biến động giá mạnh 8 |
| T+3 | Bắt đầu chu kỳ giao dịch mới | Hoàn tất chu trình tài chính |

Sự phi hiệu quả này còn được khuếch đại bởi thực tế là hơn 80% khối lượng giao dịch đến từ nhà đầu tư cá nhân, những người thường xuyên phản ứng thái quá với các tín hiệu nhiễu.8 Thuật toán được đề xuất sẽ tập trung vào việc nhận diện các tín hiệu đảo chiều hoặc tiếp diễn xu hướng ngay tại ngưỡng 13:00 dựa trên sự bất đối xứng thông tin và thanh khoản.8

## **Đề xuất Thuật toán Giao dịch Định lượng Tối ưu cho Nhà đầu tư F0**

Dưới sự chỉ đạo của các Giáo sư Tài chính tính toán và Chuyên gia Giao dịch Định lượng, chúng tôi đề xuất một thuật toán lai (Hybrid Algorithm) kết hợp giữa Tối ưu hóa Bầy đàn (Particle Swarm Optimization \- PSO) và các mô hình nhân tố đặc thù của thị trường Việt Nam (VN-4 Model).

### **Mô hình Đa nhân tố VN-4 và Chiến lược Chọn lọc Cổ phiếu**

Nghiên cứu sâu về các yếu tố ảnh hưởng đến lợi nhuận tại Việt Nam cho thấy mô hình Fama-French 3 nhân tố truyền thống không đủ để giải thích các biến động bất thường.12 Thay vào đó, mô hình VN-4 được chứng minh là có khả năng giải thích vượt trội bằng cách tích hợp thêm nhân tố Vòng quay (Turnover).12

1. **Nhân tố Thị trường (Market Factor)**: Phản ánh biến động chung của VN-Index.  
2. **Nhân tố Quy mô (Size Factor)**: Tận dụng hiệu ứng cổ phiếu vốn hóa nhỏ (Small-cap) thường mang lại lợi nhuận cao hơn trong dài hạn tại các thị trường mới nổi.12  
3. **Nhân tố Giá trị (Value Factor \- EP)**: Sử dụng tỷ số Earnings-to-Price (EP) thay vì Book-to-Market (BM), vì EP được chứng minh là nhạy bén hơn với các đặc thù kế toán và định giá tại Việt Nam.12  
4. **Nhân tố Vòng quay (Turnover Factor)**: Đây là biến đại diện cho sự chú ý và đầu cơ của nhà đầu tư cá nhân. Các cổ phiếu có vòng quay cao thường có xu hướng mang lại lợi nhuận thấp hơn trong tương lai do sự phản ứng thái quá của đám đông, giúp thuật toán loại bỏ các mã cổ phiếu đang ở trạng thái "quá nóng".12

### **Tối ưu hóa Chỉ báo Kỹ thuật bằng PSO (Particle Swarm Optimization)**

Thay vì sử dụng các tham số cố định cho RSI hoặc MACD, hệ thống sẽ tự động điều chỉnh các bộ tham số thông qua thuật toán PSO để thích ứng với biến động của phiên chiều T+2.5.14 Thuật toán PSO mô phỏng hành vi của đàn chim để tìm kiếm điểm tối ưu trong không gian đa chiều, thực hiện tối ưu hóa đồng thời ba mục tiêu:

* Maximizing Total Return (Lợi nhuận tổng).  
* Maximizing Win Rate (Tỷ lệ thắng).  
* Minimizing Number of Trades (Giảm tần suất giao dịch để tối ưu chi phí thuế và phí).14

![][image1]  
![][image2]  
Trong đó, vectơ vị trí ![][image3] bao gồm các tham số của RSI (chu kỳ ![][image4], ngưỡng ![][image5]) và MACD (chu kỳ ![][image6]).14 Việc tối ưu hóa này cho phép thuật toán nhận diện được liệu sự biến động lúc 13:00 là một cú đảo chiều ngắn hạn (Mean Reversion) hay là sự xác nhận của một xu hướng mạnh mẽ (Momentum).14

## **Quy trình Phát triển Phần mềm (SDLC) theo Tiêu chuẩn PMBOK và BABOK**

Việc xây dựng một ứng dụng giao dịch định lượng với độ chính xác tuyệt đối đòi hỏi sự kết hợp chặt chẽ giữa quản trị dự án (PMBOK) và phân tích nghiệp vụ (BABOK). Dưới sự điều hành của Giám đốc Phần mềm và Quản lý Triển khai, mọi tính năng khi phát hành phải trải qua các bước kiểm soát nghiêm ngặt.

### **Quản trị Dự án theo PMBOK (6th/7th Edition)**

Chúng tôi áp dụng mô hình SDLC kết hợp (Hybrid) giữa Waterfall cho các thành phần cốt lõi và Agile cho các chiến lược giao dịch.16

1. **Nhóm Quy trình Khởi tạo**: Thiết lập Project Charter xác định mục tiêu là "Hệ thống giao dịch tự động không sai sót".18 Xác định các ràng buộc về hạ tầng KRX và quy định của SSC/VSDC.3  
2. **Nhóm Quy trình Lập kế hoạch**: Xây dựng Cấu trúc phân chia công việc (WBS) tập trung vào các module: Thu thập dữ liệu, Động cơ tính toán thuật toán, Quản trị rủi ro và Thực thi lệnh.20  
3. **Nhóm Quy trình Giám sát và Kiểm soát**: Sử dụng các mốc quan trọng (Milestones) như hoàn tất tích hợp API SSI, hoàn tất backtesting 5 năm dữ liệu lịch sử.18

### **Phân tích Nghiệp vụ theo BABOK (Version 3\)**

Đội ngũ Business Analyst (BA) thực hiện khơi gợi yêu cầu thông qua mô hình Core Concept Model (BACCM), tập trung vào việc tạo ra "Giá trị" (Value) cho nhà đầu tư F0 trong bối cảnh "Bối cảnh" (Context) thị trường Việt Nam đầy biến động.21

* **Elicitation & Collaboration**: BA thực hiện phân tích tài liệu (Document Analysis) đối với các đặc tả kỹ thuật của SSI Fast Connect API và quy định thanh toán T+2.5 để đảm bảo logic nghiệp vụ không vi phạm quy tắc thị trường.22  
* **Requirements Life Cycle Management**: Mọi yêu cầu từ chiến lược đầu tư (ví dụ: lệnh dừng lỗ tự động khi giá chạm ngưỡng Kelly) phải được truy xuất nguồn gốc (Traceability) từ giai đoạn thiết kế đến khi kiểm thử chấp nhận người dùng (UAT).22

### **Các Giai đoạn SDLC cụ thể cho Ứng dụng Quant Trading**

| Giai đoạn | Nhiệm vụ Trọng tâm | Deliverables chính |
| :---- | :---- | :---- |
| Preliminary Analysis | Đánh giá tính khả thi về công nghệ và dữ liệu SSI | Feasibility Report 17 |
| Systems Analysis | Định nghĩa logic thuật toán T+2.5 và VN-4 | Business Requirements Document (BRD) 20 |
| Systems Design | Thiết kế kiến trúc Microservices, Database SQL/NoSQL | System Architecture Design 17 |
| Development | Lập trình Python/Node.js tích hợp SSI SDK | Source Code & Unit Test Results 27 |
| Integration & Testing | Kiểm thử hồi quy, Stress test hệ thống dưới áp lực phiên chiều | QA Report & Backtest Analysis 17 |
| Deployment | Triển khai song song (Parallel Run) với giao dịch tay | Production System 17 |

## **Tích hợp Chuyên sâu SSI Fast Connect API và Dữ liệu Thị trường**

Để đảm bảo tính "tiêu chuẩn, chính xác và cập nhật", hệ thống được thiết kế để kết nối trực tiếp với SSI Fast Connect API thông qua hai dòng sản phẩm chính: FC Data và FC Trading.29

### **Kiến trúc Kết nối và Bảo mật**

Quá trình tích hợp bắt đầu bằng việc thiết lập các khóa định danh: ConsumerID, ConsumerSecret và PrivateKey.29 Hệ thống sử dụng thuật toán RSA với chữ ký SHA256 để đảm bảo mỗi lệnh giao dịch gửi đi đều được xác thực và không thể bị thay đổi.31

1. **FC Data (Dữ liệu Thị trường)**:  
   * Sử dụng giao thức REST API để lấy danh sách chứng khoán (/securities), chi tiết báo cáo tài chính (/securities\_details) và dữ liệu lịch sử OHLCV (/securities\_chart).32  
   * Sử dụng WebSocket (Streaming) để nhận cập nhật giá thời gian thực với độ trễ thấp nhất. Các kênh đăng ký bao gồm: X (Giá tốt nhất), B (Nến Realtime OHLC) và MI (Chỉ số VN30).28  
2. **FC Trading (Giao dịch Tự động)**:  
   * Hỗ trợ đặt lệnh (/NewOrder), sửa lệnh (/ModifyOrder) và hủy lệnh (/CancelOrder).27  
   * Quản lý danh mục đầu tư (/portfolio) và tài sản (/asset) theo thời gian thực để cập nhật sức mua và tỷ lệ ký quỹ.29

### **Cấu trúc Dữ liệu JSON Điển hình từ SSI**

Hệ thống phải xử lý cấu trúc JSON phản hồi từ SSI với độ chính xác cao. Ví dụ, khi truy vấn dữ liệu lịch sử cho mã cổ phiếu SSI tại sàn HOSE:

JSON

{  
  "data":,  
  "status": 200,  
  "message": "Success"  
}

32

Dữ liệu này được đẩy vào pipeline tính toán của thuật toán PSO để đưa ra quyết định giao dịch ngay lập tức khi điều kiện thị trường thỏa mãn các tham số đã tối ưu.28

## **Chiến lược Quản trị Rủi ro và Tâm lý học Nhà đầu tư F0**

Một hệ thống Quant Trading hoàn hảo không chỉ nằm ở thuật toán tìm điểm vào lệnh mà còn ở khả năng bảo vệ vốn thông qua các mô hình toán học và kiểm soát sai lệch tâm lý.

### **Tối ưu hóa Vị thế bằng Tiêu chuẩn Kelly**

Chúng tôi áp dụng công thức Kelly để xác định quy mô vốn tối ưu cho mỗi vị thế, dựa trên xác suất thắng (![][image7]) và tỷ lệ lợi nhuận/rủi ro (![][image8]) được tính toán từ dữ liệu backtesting thực tế trên SSI.35

![][image9]  
Trong đó ![][image10] là xác suất thua. Để phù hợp với nhà đầu tư F0 vốn thường có tâm lý nhạy cảm với sự biến động (Volatility), hệ thống sẽ áp dụng "Fractional Kelly" (ví dụ: Half-Kelly), giúp giảm 50% rủi ro biến động tài khoản nhưng vẫn giữ lại được khoảng 71% lợi nhuận tiềm năng của mức Kelly đầy đủ.35

### **Giải quyết Sai lệch Tâm lý và Hành vi Bầy đàn**

Nhà đầu tư F0 tại Việt Nam thường bị ảnh hưởng bởi các yếu tố:

* **Overconfidence (Quá tự tin)**: Dẫn đến việc giao dịch quá mức và bỏ qua các quy tắc dừng lỗ.9  
* **Herding Behavior (Tâm lý bầy đàn)**: Chạy theo đám đông trong các phiên bùng nổ thanh khoản lúc 13:00, thường dẫn đến việc mua đuổi ở vùng giá cao.9  
* **Anchoring Bias (Sự neo đậu)**: Bám víu vào mức giá đỉnh cũ mà không nhận ra sự thay đổi của các nhân tố vĩ mô.38

Hệ thống tự động hóa hoàn toàn (Fully Automated) giúp loại bỏ triệt để các rào cản tâm lý này. Lệnh sẽ được thực thi dựa trên các ngưỡng định lượng xác định, không có sự can thiệp của cảm xúc, từ đó đảm bảo tính kỷ luật tuyệt đối \- yếu tố then chốt để thành công trên thị trường chứng khoán Việt Nam.39

## **Lộ trình Chuyển đổi và Tầm nhìn 2026: Hệ thống KRX và Nâng hạng FTSE**

Thị trường chứng khoán Việt Nam giai đoạn 2026 sẽ chứng kiến những thay đổi mang tính bước ngoặt với việc chính thức vận hành hệ thống công nghệ KRX.3 Điều này không chỉ giúp tăng tốc độ xử lý lệnh lên hàng triệu lệnh mỗi giây mà còn mở đường cho các sản phẩm tài chính mới như giao dịch trong ngày (T+0) và bán khống (Short-selling).5

Chúng tôi tư vấn rằng, hệ thống Quant Trading cần được xây dựng theo kiến trúc mở để sẵn sàng tích hợp các tính năng này khi pháp lý cho phép. Việc nắm giữ lợi thế về dữ liệu SSI chuẩn và một thuật toán đã được kiểm chứng qua chu kỳ T+2.5 sẽ là nền tảng vững chắc để nhà đầu tư F0 trở thành những nhà đầu tư chuyên nghiệp, sẵn sàng cho một thị trường "Mới nổi" với quy mô vốn hóa dự kiến vượt mốc 500 tỷ USD vào cuối thập kỷ.1

Hội đồng Học thuật khẳng định rằng, sự kết hợp giữa toán học tài chính, kỹ nghệ phần mềm chuẩn mực và sự am hiểu sâu sắc về bối cảnh địa phương là con đường duy nhất để đạt được lợi nhuận bền vững và quản trị rủi ro tuyệt đối trong kỷ nguyên giao dịch số hóa tại Việt Nam.

# ---

**Quantitative Investment Strategy and Automated Trading System Development for the Vietnam Stock Market: A Comprehensive Report from the Academic Board and Technology Experts**

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

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAZCAYAAAA8CX6UAAABs0lEQVR4Xp1VMUuDMRC9QwXFggpdCg46OjmITo5uLgoVCi7d3O3mzxB3J3FxdnJwd3Fx7KC7CgVdHOq7S3JJvqR+4IP3JXnvcvdd8pUSEZMDE/spm5ZATJMr/n8Ry4dJS/I/7dJMldJVVCtWD0HRBY/APoL6bsy4By5a9KwsAu/9gO9YbWUm0Qb4DH0UImOu9JXZjCnkJ4xrsg4RfrwAX8BuksRmccmaeQpe5i65AIbO9IpZr7E9B7tKkug0CEnFDvjoyJ3mizS7PQO1LVVj8Ar4AEWKLJiaw6Jlco0BpF5CSS7tfIPDEBgRVq53gVy/HOQH+ObIMt6BJ+By3EBzrG+dJonYwfIL4655ua/w0jn4aUKST6Y35A7athcfdHMddia6b0sPswV8iMcAVZbKSkT7CJAvWlpz8DFlKB/jcU/uEszfBicsLbG2NcV8InqlmECu/gAcI36zaRpm/54zXIG34LxbtuwpbBX0IZ/IgFw3ZZwgiDKmAdpmFMbgOjgyRd1qyjp8qPzmVjMlS9RM2FwHyJYZN6Goe1Gs2u2Ih5I+g1c0kYfKOwfHI/k/yz4Nq+O0X9fqMhc46p02AAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAZCAYAAADXPsWXAAABkklEQVR4Xo1TsS5FQRCdjSeRiIRItCLRaDSikChJKAidP/ABryCioNJTKEUvURGlhEZ8yysJEe85szO7O7t7740T587MmTN7Z+8LIkc5tOaQWiGz5q7cOZH0lHq8VvI8L2qpbDedl6BqbFp384RHR8vAuHxa1g2xzAPCfFpUlewAa4hgsVYLtBhYDifHZ2q1jQmy1UrRKlFzfTwuwF/k+4j3aO0hHotGy/C+oneK/E613TDNWACfwB0MjhC/KO0+hecL+IZ8Uf2r4CfqWynFeoBwhXhCcsi1mhkz4Du4aS6yDv7EQ7Qxr3zwTTEp3BI4gI83EoXoiORlHOPKpD/dkOS+PdF891IHEhwNQN6Ot6wwQvPQ1OEqPCSQl/GhZ6psa/SYIH8VV1wFB/gPG1ebBL/BNdQ9xI3kJ1oBb8KrFOfgEMKWr8LlHX0gPoLPwRgwBo4XGrZzsxTGE6bBOZIZi9IXUOrx49SShdWa/t+yfp7xI58o5+u6VDrQac2aDVe1kGVbmk34v7XDWX8dA9OQ1Pm/P9gRLmyVW2WLAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACcAAAAZCAYAAACy0zfoAAACxElEQVR4Xr1WPWhWMRS9AQVFQaXiD3bqJggOgpOL4CBKQVy7uHVQ3Krg7uCi4KigOIgg4mTBwcFR6KybqFAoIjoITmLrOUney01y8zXfB3rgfC/v3puT+3Jv0opEuGEQR+k9B+2mzzQSTcds0HIuvK2Ab8C3rnet3jiN/jlOBbsDGK5hcFMFzIYsgY5s8p0yLSfBb+A55Wii1lAozeW7gT3gDfABoleM+CVwHULzpWMbXJRR17dGSib0y1nwKngw2nbjdyFGZLgNbmHGcukQX1JXldT4iICUAOF1pda9A+4DX4P3EboLz1WOs6gIONxvPM8Yy/6QWFJ6UtliXBU+YljQ0mW1ToBfwfPgMfAzuGTJbcD4XrjF3qsWxyTHyS6eXQMNO0u0IYNujWuSfPx49jX7u9LbBF+AOzJryIdfT4ELydQDxwWjrst1A57A/lRCLmwb3ghHJez4CL5sIuITng/BuxJKeVrCxFfgI3A8EJPSU8nzo2zdELIIfsD4Op73wHcS1snA7f8DXpGw7jx+14XNGk7QnBRf0wmWNNflqYeu+jjqHorj/eBeP0oBfvt1Sbm1XxDAPgxH29iqwZS58riyVYJuSDqDIT/iFrisAo6D38Ff4KlkBjr/fjEK5S2vEOi6QbdCUM71D4Mf43MA7iYvvIrYrnIaKTd0/Z3HXuxC3GrHe2cAG5MluWwuOwGq1NTlPwu1rqNujtYNMHyhPups4ufgzmQyJ19y/kZ3Km6MpG55NVW6VlKl5YiERn0J/pT8ayeB/cQd5pVggTs3i25ESpPXBUrhunpMgYeplRzV5/BbXKzl3kwL1Tzb4DGCeLoL2BNtayesnGzB0foM5EU9HZRopV8ZhDbLaiScwnhB25MkOJrO/42UyD9LqViitY65LdpQORtQcb1TSrTmlTkO41Z82zED9GJhnNSnWmdScMP3FwmVaYm/s7WPAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADQAAAAZCAYAAAB+Sg0DAAADdklEQVR4XsVXXYhOQRh+p5DNboj8lLJtUty48FNbuBMJaaOUkhu5cSetKLnZC+VCG1dEkgtWWvm5oawS5ZqUKBRCa2+4oaznOTNzzsycmfPNt/uVp55vZt5555l33nnP2bMiAZSh7Yd219YJTFkvXBiOp4dKLU83z4uIeZa22KSP1h7TRwf3aJZqnrVo6dXS4f+jF5wVGnXciehbmtVexxxFKBGOo8hxgs9waKNRmcVsPJ1ANLJHD2yrQmOJyIKOwNzAfPw88GemDR6Guh1Fbh7WgHdCYxMyhAdCQ0u4ohkbOKh575dYyeWiJleg1ItPdwJKtuL3IPgSvGt2suXGEtkDToLjekFb6ILeMbQ3wOPgE/AF+BZcX3qZ07HJOGgv+AzcDh4Cf4qzbBH4EFwIvgI/GLsttx5wOfgG/GXmHMS3N9Yl4COMmCgaB5S+oZngFfAzuEK7JlCXt7FccmzU7LeDXeBlcCP4B7xv7GG50Y8BtAMcRt4hql4zHlZal7D7neagHncFZ65LWEFOIsyNDopmAZ6YZPAsq33arJgB9wFeC95zxpIOo7RPonvE9HnTt6V6ZVOPN361GKWkfGyD41+058VfwVgHQwk4qltoZ4jedAQO3WaOLW+uv5IJl1cwMyzZMak0cMPqnOnThUE5CcwCH4kvYJ9jY6zjUCxLzoLiJ0zfKzcl6ih+L4g+bBr+YbnRmFQHop4tN5YLy4YvhwVhctKpKm6UZTzHsVGTsXeF62gcMn1mks+MBTde5oyJueAouC6wW7DeX4OLzXgEodpyQ4moCUS+wYyJ3aKzzxdGCoyRibVAMorYJhxbCQZ8U4rSK4RHseFXtGc8LwNkYymap+BjsNvLTjVYDT4Hf8D4Ce178KPow4Y4DP4Gd4YTBnwLf4POSdEa19GnNvdogCoydFF0ZpuypaHkmlRllQLnD4DzwokIigPpnHhp4t8sW27UY0LT5Rk864nPk+jys6EhAr7h0h+kUirPFvpFtylucCgxpxGbU/oLoXHzCoo3uCW0RpD7QbpJ4uXIUPmHWD/XkcAjN1qiXsP2fwUffOPtCI0JnPKHVs/T7cNos2twsBKu30XfYALRGOugm396lb02CxGtWP6Ufqs2orasZmgHU1jsLZnC+ija0WnHt+PI39zxNN2iyReoEKsVB82zFXL9XNg1/wAgMnC8/oTgiQAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAYCAYAAADDLGwtAAABP0lEQVR4XoWRMUuDQQyGc6DgJpaOgjiJ4ObQxaGDf0LqX3BRxP/g2EWog5NzF2cR/4OL4ObiIILgJFifJPfd5b4Kpn0vb97kkrv7RLCUdMW7qyz1tYyOxnTDjcZcDlupRN2cdtiSec1yKhwld8o1yX7B/hng1jtKz0LHtrXN1ewMckS0ih+BKfwylmrhMYUnkB/8lHgOH4Nzis+0QKvWwR3YB19oC0v4oDX8G2xHpS20XQI6yQJ+6q9ky4ZqYJIvZusD+EY40CCbNtDjHHqY7P8Oe4INba6NlgnuFWyHzXa2iyDsgQ/0zaCVszyKX25At3vwks8qdr6kN3bxFuUZ/gmuiQddJysFN6I3k/wq/az7NBS7hL1jm4wUciX6BKJfJo3xK39XlrjOKDApxO22riBa3Bi1wr2g9up1rmvd9Qu/LiQVLJs7hgAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAbCAYAAABBTc6+AAABNUlEQVR4Xm2RvUqDUQyGE1AQHASX2lXES3Ao3dQb8ArcCu46uLuLOOkdlOIm9FoKRQqCkw6ik/jzJOf/YHrevElOTpIvFRGVgCBuqbphFK+K/i89u81tDvdJUZpKGJvQBdYd9jm80WXqPvyB+Yszg9dyQtXiyhKwJqm4dvM9or7gcZmgxQ+6K28Sq6j1Fz3DHIEbMIwPPYOp1So8sb57+BC8gQOxffLbRX3jnJaa8gzmyT/S2N89L60r6CXNeIme+LtwaecV69P8AcaSgHGYKTRhaD4dZ4haia87tdctlA19YrEBWIL6+4/BFKx7OudWQiuTPQILYttVRdlB29QP8Du4Tlc5ycl3Ut5VEkJFNym10/zBRfyNjZo8P76seJPTOjOHUon4um3rEgNdXHN1czxQOVH+ALJqJTbbH/ooAAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA9CAYAAAAQ2DVeAAAFQUlEQVR4Xu3dP4gcVRgA8BeSgAH/RFSiJCCKjQS0CEGQVP4BJdgEETWChUgQxFa0EsQiVhqChQipRBRbG7WziVpZBEEQogSstBBioWh8X94uOzfcsbd3u7Mzb34/+LibeXs3szszb795b+ZNSgAAfbOnPQOGyI7M4NmJAVgF3y9QCQczlbOLw/A5jgF2S00KAAAAwFAsqy1rWf8HlsH+CABQN/neonxi0AeORGpifwYA+kBOMjg2GQAAALBLvWle6M2K0LmRbvuRvm0AAAAAgN4aWbvtyN4ug/FQjnM5PmwXAADQH7/luNKeCQBAf1zL8UV7JgAwcjX3EA/svd2Y458cJ9oF1enRhunRqrBStnTP7GCD7OBPxsOHAx26P8flHA+kch3b842yl3M8kcpBeTLHBznuapSvyplUlrc3xys5Dm4sBgAYl7jh4PscRybTp3K8leOeHIdS6S79d1IWLuX4oTG9TJEwTpcVy/4xxzuz4no4LQUAtuvWVJK14415T+X4Osdrk+lI2M7Oiq+//mpjepliWZ9Mfr8hlevqHpsVAwCMz+lUkqRpg0/8vJBKohQJ0+FU7iC9d1Ie/svxe2N66kCOJ3M8PSeiq3MzsS6XU1lmiEQtlhXrAQAwWtEdGgnb1LTF7fXJdCRN0+RtKl5/sTG9LB/l+DzHvsl0dIU2142+0J8LAJ2KpKjZvRlJUzNJimQtukin4gaEL1O5s3TZ3kyzRDHEel1uTAMVkv8DzPd4ml3kH/VmDO/xxqz4endodJHuz3Ffjp9y3NkoX6ZjOc6nsh5xx2okjtHi1mu+bIAlU61Az73YntGhGKrjtvbMNLu+LcoiaVu1WEbcHRrLW9HYcOpCoCNrr27WvgJQlUhSYryxGHssjq6jG4vXZjqg7jrE2HAxfMjt7QIAgC5Et2IMmfF3mp3+PJrj51QGre2iJWueuG7tsxy/pPJw+K7E5/FwKp9RXCv37MbiEXOiDAyaSmwkqtrQ0c347eRniNa17ybzolXpmcn8dXo/lUFsI7pMmm7O8XaaLTuerABAnar6cqcuD6aSlG2meYckfaaKAYCqRVfjVnc+3t2eAayJpJwu2M+gd+K6rCupDKHxRyrXqz2y4RUAAMNU1elH3PkYj3Ta7Z2PMQTHduLg9A82EU80iGvoBhRV7QvAdoztsN/q/W41n56ywYYunrMZyUcfno0ZCdsdAwsAoG69yHY/TiVh2612S9pWEYPP9uKN18QHCtATKmRWJB6q/md75g78us34Km3+9AIAhq/P6Uqf1w3murZn6ztEgaXznQHA4qI7tOax1mKA3XdzvNQuYEgkOcNkuzEidndW4ECO53IcznExxy0bi6sSNzJEt+/xdgEAQJ+9msrzOGPA3Pi9ZsdyXE27H7aENenspLWzBQH1UHGwWkdy/JXj03ZBhS6k5dwFywgtVhUv9uqlWMMiAWAVLqXSwvZCKg9ujwe5A8wnIQboTLSuxXAiU9GyuK8xDQDAGkViFgnbqca8aG071JiGFdNMAx1xsMFAncjxTY6bGvMigXMDArAQmQCwZKqVhjM5zjWmpy1uo/+QRv8BVMA2BKAWp1MZumQqBgh+rzENAMCaHc1xPpXGiJOpXL8WgwYDANAj+1O5yWBvu2BMdJ/RLXtclWxWABgP3/v0x8j3xpG/fdbJzgewPeusL1e17FX9XwAYNV+wAMOj7mYe+wjAIoZQaw5hHQEAWIwcDwAAgIFxKkvP2CVps08A1EjtDoyYKhAAAGCknBACAHNJGGARjhgAAKiMJB+SAwHW73+mMb4wjrbRUgAAAABJRU5ErkJggg==>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAE4AAAAZCAYAAACfIRhSAAAC5ElEQVR4Xs2Xz6tNURTH1w4DRRKRMkBSrxjJzAgTAyYo5Q9QmJuaGSiDN5R4RlKMGb4y8pQMlIEUUkrJyMTk+a6z9z5n77N/nP3r3OtT3+7d66y19rrr7nXuuURzIcaGJePU4xiWiFmLeu8xLYTqvbwJvMYlEKojZG9Ms22yE00GTDosh+KyFh/YURNtxw6rmpzpwezYaM+O+gw+VqAb0DNoE1qHdsyzVcusObmEcs6JmeY89AC6Tkbj+ELRNjlBAd+A+b/GatycxJvjveoaXYtG9Ne6V4+jx1RDceNCddh2MTYUcQb6CT2C7kNvoA1op3ZwNo0sQwytT8JoXFZctvuIrdBd6Cn0G/oI3YTOQS+hXYMr0V+S95Zt0HboFcnCY6xB3zL0DjrGgYl4TtzQkbreRDlOsjm3hazhqHGN13z/7TgEfUcph/vLRKukGhcpkD/QgQztIStdJLNkEy7rVDCqfib309xSrg/JOjydkddPtOUO9FgMmXdDb6Ff2qEcI2s+7okL5zoBXfZJuLazyMOTFYJz9T0Ybck1Pec3J6E/0Ip2wOs15bCqnziUfUzliTPxmt3GFeDNHLAy6krfA+PSXmW7ygvdODZq9JhycIw1cu9jMTW4xy0MPaYXDdtp6AO0jxdHoB9kP51/Jjmm/BQfxPnOzOPZhmDjUnbqfBIcAy48pnyg+GAx+KUVaKa4pNZd2EHoK/QC+kLmEQ1kbYI/9wWS+1sSgQZK/IlyGWXhffnR4z30GvpE8pHNge8/+0k+jgxjmlqT4+cYChhyBE+PzzZJKKi38xs9pltIjia/2ozS8K/J5Ji6hIpJQcaaGdxsrmVGinrAM83zzcGzkNKCFJ8QpbFGHPeAx7P/1xRG0BWS/xxMnbJ8fKRWKdJd82mWmUfyHpk9EAk9qKfZB0hnhi2zUvbOmVHsnhXioKJzkuT4VlOyWUlMT0FDGrDg7ch/5KwqhkVtcXnxed5xcnLFff8BjhZ9pJmNbP4AAAAASUVORK5CYII=>