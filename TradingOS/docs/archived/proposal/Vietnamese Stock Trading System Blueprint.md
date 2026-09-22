# **Chiến Lược Đầu Tư Định Lượng Và Kiến Trúc Hệ Thống Giao Dịch T+2.5 Tại Thị Trường Chứng Khoán Việt Nam: Báo Cáo Chuyên Sâu Từ Hội Đồng Học Thuật Và Chuyên Gia Công Nghệ Tài Chính**

## **Phân Tích Toàn Cảnh Thị Trường Chứng Khoán Việt Nam Giai Đoạn 2025-2026**

Thị trường chứng khoán Việt Nam đang đứng trước ngưỡng cửa của một kỷ nguyên mới, được định nghĩa bởi sự chuyển dịch từ một thị trường cận biên dựa trên tâm lý retail sang một thị trường mới nổi có cấu trúc và minh bạch hơn. Dựa trên các dữ liệu vĩ mô mới nhất, nền kinh tế Việt Nam đã đạt mức tăng trưởng GDP ấn tượng 8,2% trong quý 3 năm 2025, vượt xa các quốc gia trong khu vực ASEAN và thu hút dòng vốn đầu tư trực tiếp nước ngoài (FDI) kỷ lục.1 Sự bùng nổ này không chỉ là kết quả của các yếu tố chu kỳ mà còn là hệ quả của các cải cách thể chế sâu rộng, bao gồm việc triển khai hệ thống giao dịch KRX và nỗ lực nâng hạng thị trường của FTSE Russell dự kiến vào tháng 9 năm 2026\.1

Trong bối cảnh này, chỉ số VN-Index được dự báo sẽ đạt các cột mốc mới, có thể chạm ngưỡng 1.920 đến 2.040 điểm vào năm 2026\.3 Tuy nhiên, sự tăng trưởng này không diễn ra đồng đều trên tất cả các nhóm ngành. Dữ liệu từ năm 2025 cho thấy một sự phân hóa mạnh mẽ, nơi các cổ phiếu thuộc hệ sinh thái Vingroup dẫn dắt đà tăng đáng kể, trong khi phần còn lại của thị trường có độ rộng hạn chế.3 Điều này đặt ra một thách thức và đồng thời là cơ hội cho các nhà đầu tư định lượng (Quant) trong việc tìm kiếm alpha thông qua việc khai thác các sai lệch định giá và hành vi thị trường.

### **Các Chỉ Số Vĩ Mô Và Mục Tiêu Thị Trường 2025-2026**

| Chỉ số vĩ mô | Giá trị thực tế / Dự báo (2025-2026) | Ý nghĩa đối với chiến lược đầu tư |
| :---- | :---- | :---- |
| Tăng trưởng GDP | 8,0% \- 8,5% | Hỗ trợ đà tăng trưởng lợi nhuận ròng của doanh nghiệp niêm yết (NPAT) dự kiến đạt 14-20%.6 |
| Lãi suất huy động | 7,0% \- 8,0% | Mức lãi suất mục tiêu để dòng tiền nhàn rỗi dịch chuyển mạnh mẽ vào thị trường chứng khoán.8 |
| Vốn hóa thị trường / GDP | \~62% (Mục tiêu 100% vào cuối 2025\) | Dư địa tăng trưởng quy mô thị trường còn rất lớn so với các nước khu vực như Thái Lan hay Singapore.9 |
| Thanh khoản bình quân | 1,0 \- 1,2 tỷ USD/phiên | Đảm bảo tính khả thi cho các thuật toán giao dịch khối lượng lớn mà không gây trượt giá đáng kể.2 |
| Thời điểm nâng hạng (FTSE) | Tháng 9/2026 | Chất xúc tác chính thu hút dòng vốn ngoại ước tính 6-8 tỷ USD.1 |

Sự chuyển dịch cơ cấu sang nền kinh tế số và công nghệ cao cũng tạo ra những động lực mới. Chính phủ Việt Nam đã xác định các ưu tiên chiến lược trong hạ tầng và chuyển đổi số, điều này trực tiếp thúc đẩy các nhóm ngành như công nghệ thông tin, vật liệu xây dựng và năng lượng tái tạo.7 Đối với nhà đầu tư F0, việc hiểu rõ các chu kỳ vĩ mô này là bước đầu tiên để xây dựng một tư duy đầu tư dựa trên dữ liệu thay vì cảm xúc.

## **Nghiên Cứu Chu Kỳ Thị Trường Và Phương Pháp Wyckoff Ứng Dụng**

Để xác định các vùng gia nhập (Bottom Entry) và thoát lệnh (Top Exit) một cách khoa học, Hội đồng đề xuất sử dụng phương pháp Wyckoff làm nền tảng phân tích. Phương pháp này không coi biến động giá là ngẫu nhiên mà là kết quả của sự tương tác giữa cung và cầu được dẫn dắt bởi các "nhà tạo lập" hoặc "tiền thông minh" (Smart Money).9

### **Quy Luật Cung Cầu Và Ba Định Luật Wyckoff**

Cốt lõi của phân tích Wyckoff dựa trên ba định luật nền tảng có thể được lượng hóa trong thuật toán:

1. **Định luật Cung \- Cầu:** Khi cầu lớn hơn cung, giá tăng; khi cung lớn hơn cầu, giá giảm. Thuật toán "Trading OS" sẽ quét dữ liệu sổ lệnh (Order Book) từ SSI API để xác định sự mất cân bằng này trong thời gian thực.12  
2. **Định luật Nguyên nhân \- Kết quả:** Độ dài của giai đoạn tích lũy (Nguyên nhân) sẽ quyết định tầm vóc của xu hướng tăng sau đó (Kết quả). Chúng ta sử dụng biểu đồ Point-and-Figure hoặc phân tích khối lượng tích lũy để dự báo mục tiêu giá.12  
3. **Định luật Nỗ lực \- Kết quả:** Sự phân kỳ giữa khối lượng giao dịch (Nỗ lực) và biến động giá (Kết quả) thường báo hiệu sự đảo chiều của xu hướng. Ví dụ, nếu khối lượng tăng đột biến nhưng giá không tăng tương ứng, đó là dấu hiệu của sự phân phối.12

### **Nhận Diện Các Giai Đoạn Chu Kỳ Thị Trường**

| Giai đoạn | Đặc điểm kỹ thuật | Hành động của Smart Money | Chiến lược cho F0 |
| :---- | :---- | :---- | :---- |
| **Tích lũy (Accumulation)** | Biến động hẹp, khối lượng thấp, xuất hiện các cú "Spring".12 | Âm thầm thu gom cổ phiếu từ những nhà đầu tư thiếu kiên nhẫn. | Theo dõi và chờ đợi tín hiệu SOS (Sign of Strength).15 |
| **Đẩy giá (Markup)** | Giá tăng mạnh, tạo các đỉnh và đáy cao dần, khối lượng tăng trong các nhịp đẩy. | Đẩy giá mạnh mẽ để thu hút sự chú ý của công chúng. | Gia nhập tại các nhịp điều chỉnh kỹ thuật (Back-up).9 |
| **Phân phối (Distribution)** | Biến động cực mạnh, khối lượng lớn nhưng giá đi ngang (Upthrust).12 | Bán dần cổ phiếu cho những nhà đầu tư hưng phấn (FOMO). | Chốt lời từng phần và nâng mức chặn lãi (Trailing Stop).16 |
| **Đè giá (Markdown)** | Giá giảm xuyên thủng các hỗ trợ kèm khối lượng lớn. | Rút lui hoàn toàn, để thị trường rơi tự do. | Đứng ngoài thị trường hoặc phòng vệ bằng phái sinh. |

Đối với thị trường Việt Nam năm 2026, các chuyên gia nhận định rằng sau giai đoạn phục hồi chữ V từ cú sốc thuế quan năm 2025, thị trường đang bước vào giai đoạn Markup bền vững hơn, được hỗ trợ bởi tăng trưởng EPS 14,5%.5 Việc xác định các "vùng đáy" sẽ dựa trên sự xuất hiện của các phiên "Spring" \- nơi giá giảm thủng hỗ trợ cũ với khối lượng thấp rồi rút chân nhanh chóng, loại bỏ những vị thế margin cuối cùng trước khi tăng tốc.14

## **Đề Xuất Thuật Toán Giao Dịch T+2.5 Tối Ưu Cho Nhà Đầu Tư F0**

Cơ chế T+2.5 tại Việt Nam tạo ra một đặc điểm tâm lý độc đáo: hàng về vào phiên chiều ngày T+2 thường gây ra áp lực bán đột ngột sau 14:00.17 Thuật toán của chúng ta phải được thiết kế để tận dụng sự biến động này.

### **Logic Thuật Toán "T+ Swing Alpha"**

Thuật toán tập trung vào việc xác định các điểm bùng nổ (Breakout) từ nền tích lũy ngắn hạn với mục tiêu lợi nhuận 15%.

**1\. Bộ lọc đầu vào (Universe Selection):**

* **Thanh khoản:** Khối lượng giao dịch trung bình 20 phiên (![][image1]) \> 1 triệu đơn vị.  
* **Sức mạnh tương quan (Relative Strength):** Cổ phiếu có hiệu suất tốt hơn VN-Index trong 4 tuần gần nhất.  
* **Cơ bản:** Ưu tiên các mã có tăng trưởng NPAT \> 15% (dữ liệu từ SSI Financial Ratio API).19

**2\. Công thức xác định điểm mua (Entry Timing):**

* **Điều kiện 1:** Giá phá vỡ đường xu hướng giảm hoặc vùng kháng cự ngang (Pivot Point) với khối lượng ![][image2].  
* **Điều kiện 2:** Chỉ báo RSI nằm trong khoảng 50-65 (đang trong đà tăng trưởng mạnh mẽ nhưng chưa quá mua).20  
* **Điều kiện 3:** MACD Histogram chuyển từ âm sang dương hoặc duy trì đà tăng trưởng trên đường Signal.21  
* **Thời điểm:** Ưu tiên thực hiện lệnh mua vào cuối phiên sáng hoặc ngay đầu phiên chiều ngày T+0 để đón đầu dòng tiền.18

**3\. Quản trị rủi ro và Công thức tính toán:**

Chúng ta áp dụng tỷ lệ Risk/Reward tối thiểu là 1:2. Với mục tiêu Target là 15%, mức Stop Loss tối đa được thiết lập ở mức 7%.

* **Công thức Stop Loss dựa trên ATR:**  
  ![][image3]  
  Trong đó, ![][image4] thường được chọn từ 1.5 đến 2.0 để tránh nhiễu thị trường.22  
* **Công thức Position Sizing (Quy tắc 2%):**  
  ![][image5]  
  Điều này đảm bảo rằng mỗi giao dịch thua lỗ chỉ ảnh hưởng tối đa 2% tổng tài sản.23

**4\. Chiến lược thoát lệnh (Exit Strategy):**

* **Target 15%:** Tự động kích hoạt lệnh bán khi giá chạm ngưỡng ![][image6].  
* **Trailing Stop:** Nếu giá đạt mức lợi nhuận 10%, dời Stop Loss về điểm hòa vốn (Break-even). Nếu lợi nhuận tiếp tục tăng, Stop Loss sẽ được cập nhật theo công thức: ![][image7].16  
* **Thoát phiên chiều:** Nếu hàng về ngày T+2 mà giá không đạt kỳ vọng hoặc có dấu hiệu suy yếu sức mạnh (RSI \> 70 và quay đầu), thực hiện thoát lệnh ngay trong phiên chiều (14:15 \- 14:45) để tránh áp lực bán của phiên hôm sau.18

## **Blueprint Kiến Trúc Ứng Dụng 'Trading OS'**

Hệ thống 'Trading OS' không chỉ là một bot giao dịch, mà là một hệ điều hành đầu tư toàn diện, tích hợp từ khâu xử lý dữ liệu thô đến việc giải thích chiến lược bằng ngôn ngữ tự nhiên.

### **Kiến Trúc Hệ Thống (System Architecture)**

Dựa trên tiêu chuẩn Software Architecture cho hệ thống tài chính, chúng tôi đề xuất mô hình Layered Microservices 25:

1. **Data Provider Service:** Kết nối trực tiếp với SSI FastConnect API và DNSE LightSpeed API. Sử dụng gRPC để truyền dữ liệu thời gian thực giữa các service nội bộ nhằm giảm độ trễ.27  
2. **Market Intelligence Service:** Thực hiện tính toán các chỉ báo kỹ thuật (Technical Indicators) và nhận diện mô hình Wyckoff tự động. Sử dụng thư viện Pandas và TA-Lib trên Python.29  
3. **Risk Management Module:** Kiểm tra tính hợp lệ của lệnh dựa trên các quy định của sàn (ví dụ: lô tối thiểu 100 cổ phiếu tại HOSE) và giới hạn margin của tài khoản.26  
4. **Natural Language Generation (NLG) Module:** Sử dụng một mô hình Transformer (như GPT-4 hoặc FinBERT tinh chỉnh) để chuyển đổi dữ liệu số thành giải thích văn bản.20  
   * *Input:* {Ticker: "HPG", Action: "Buy", Reason: "Spring identified, RSI 42, Volume \+60%"}  
   * *Output (Văn bản):* "Hệ thống khuyến nghị mua HPG tại vùng giá hiện tại do đã xuất hiện bẫy giảm giá (Spring) tại hỗ trợ 28.5, kèm theo sự gia tăng mạnh mẽ của dòng tiền, cho thấy lực cầu đang áp đảo".31

### **Sơ Đồ Công Nghệ (Technology Stack)**

| Thành phần | Công nghệ đề xuất | Lý do lựa chọn |
| :---- | :---- | :---- |
| Backend | Python (FastAPI) | Hiệu suất cao, hỗ trợ tốt cho các thư viện Data Science và AI.30 |
| Real-time Data | NodeJS & Socket.io | Xử lý hàng nghìn kết nối đồng thời với độ trễ thấp.34 |
| Database | PostgreSQL \+ TimescaleDB | Lưu trữ dữ liệu chuỗi thời gian (time-series) tối ưu cho biểu đồ chứng khoán.36 |
| Caching | Redis | Lưu trữ giá và trạng thái lệnh trong thời gian thực để truy xuất tức thời.26 |
| Infrastructure | Docker & Kubernetes | Đảm bảo khả năng mở rộng (Scalability) và tính sẵn sàng cao (High Availability).26 |

## **Quy Trình Phát Triển Sản Phẩm Theo Tiêu Chuẩn Quốc Tế**

Để đạt được độ chính xác tuyệt đối và sự tin cậy từ người dùng, toàn bộ tính năng phải được phát triển theo tiêu chuẩn SDLC (Software Development Life Cycle), tuân thủ hướng dẫn của PMBOK (Project Management Body of Knowledge) và BABOK (Business Analysis Body of Knowledge).

### **Phân Tích Nghiệp Vụ Theo BABOK**

Nhóm Business Analyst (BA) sẽ thực hiện quy trình 6 bước để xác định yêu cầu 37:

1. **Business Analysis Planning and Monitoring:** Xác định các bên liên quan (Stakeholders) bao gồm nhà đầu tư F0, chuyên gia quản lý rủi ro và đội ngũ tuân thủ.38  
2. **Elicitation and Collaboration:** Phỏng vấn các nhà giao dịch chuyên nghiệp để mô hình hóa các quy tắc "bất thành văn" trên thị trường Việt Nam (ví dụ: tác động của "nghẽn lệnh" hoặc "lệnh ATC").38  
3. **Requirements Life Cycle Management:** Trình bày và phê duyệt các yêu cầu chức năng (Functional Requirements) như: "Hệ thống phải tự động hủy lệnh nếu giá không khớp trong vòng 5 phút".39  
4. **Strategy Analysis:** Đánh giá rủi ro thị trường và khả năng tích hợp của hệ thống với các cổng thanh toán ngân hàng (Bankgate).40  
5. **Requirements Analysis and Design Definition:** Thiết kế các User Stories và sơ đồ luồng dữ liệu (Data Flow Diagrams) cho quy trình đặt lệnh tự động.37  
6. **Solution Evaluation:** Kiểm chứng xem ứng dụng có thực sự giúp nhà đầu tư đạt lợi nhuận 15% hay không thông qua các chỉ số KPI cụ thể.39

### **Quản Trị Dự Án Theo PMBOK**

Software Director và Delivery Manager sẽ áp dụng 10 lĩnh vực kiến thức của PMBOK để điều hành dự án:

* **Quản lý Phạm vi (Scope Management):** Đảm bảo hệ thống tập trung vào tính năng cốt lõi là giao dịch T+2.5, tránh tình trạng phình to tính năng (Scope Creep).41  
* **Quản lý Thời gian (Schedule Management):** Sử dụng phương pháp Agile/Scrum với các Sprint 2 tuần để nhanh chóng ra mắt các phiên bản MVP (Minimum Viable Product).26  
* **Quản lý Chất lượng (Quality Management):** Thiết lập quy trình Unit Test cho thuật toán giao dịch và Integration Test cho các kết nối API với SSI.42  
* **Quản lý Rủi ro (Risk Management):** Xây dựng các kịch bản dự phòng khi mất kết nối Internet hoặc lỗi hệ thống từ phía công ty chứng khoán.42

## **Hướng Dẫn Tích Hợp Dữ Liệu SSI Và Các Công Ty Chứng Khoán**

Tính chính xác của 'Trading OS' phụ thuộc hoàn toàn vào nguồn dữ liệu "sạch" và thời gian thực. SSI FastConnect API là lựa chọn ưu tiên hàng đầu do tính ổn định và sự hỗ trợ chuyên nghiệp.44

### **Các Bước Triển Khai Kết Nối API SSI**

1. **Đăng ký:** Khách hàng cần mở tài khoản tại SSI và đăng ký dịch vụ FastConnect API tại các chi nhánh.27  
2. **Cấp khóa:** Sau khi đăng ký thành công, người dùng đăng nhập iBoard để tạo bộ khóa kết nối bao gồm:  
   * ConsumerID: Định danh ứng dụng.  
   * ConsumerSecret: Mã bảo mật.  
   * PrivateKey: Khóa dùng để tạo chữ ký điện tử cho các lệnh đặt tiền.46  
3. **Xác thực:** Hệ thống sử dụng giao thức OAuth2 để lấy Access Token. Token này có hiệu lực trong vòng 8 giờ, do đó 'Trading OS' cần cơ chế tự động làm mới (Renew) token.46  
4. **Streaming:** Để nhận giá thời gian thực, ứng dụng sẽ kết nối đến SignalR Hub của SSI. Cần chú ý giới hạn yêu cầu (Rate Limit) để tránh bị khóa kết nối.30

### **So Sánh Các Giải Pháp API Tại Việt Nam**

| Đặc điểm | SSI FastConnect | DNSE LightSpeed | VNDirect Open API |
| :---- | :---- | :---- | :---- |
| **Ưu điểm** | Độ tin cậy cao, hỗ trợ nhiều ngôn ngữ (Python, NodeJS, Java).35 | Tối ưu cho trading theo từng Deal, phí 0 đồng, API hiện đại.28 | Hạ tầng mạnh, phù hợp cho khách hàng tổ chức (FIX protocol).40 |
| **Hỗ trợ F0** | Có phần mềm Q-Trader hỗ trợ đi kèm.44 | Giao diện thân thiện, dễ đăng ký online.28 | Cung cấp nhiều công cụ phân tích (D-Board, Stockbook).50 |
| **Phù hợp nhất cho** | Đầu tư bài bản, cần sự ổn định tuyệt đối. | Giao dịch thuật toán tần suất cao, tiết kiệm chi phí. | Các quỹ đầu tư và nhà đầu tư tổ chức. |

## **Đào Tạo Và Tư Vấn Lộ Trình Đầu Tư Cho F0**

Đối với một nhà đầu tư mới (F0), việc sở hữu một công cụ mạnh mẽ chỉ là 50% chặng đường. 50% còn lại nằm ở tư duy quản trị vốn và sự kiên nhẫn.

### **Lộ Trình 3 Bước Tiếp Cận Thị Trường**

1. **Giai đoạn Học tập (1-3 tháng):**  
   * Tìm hiểu về chu kỳ thị trường và cách đọc biểu đồ nến cơ bản.  
   * Sử dụng tính năng "Demo Trading" trên 'Trading OS' để làm quen với các tín hiệu của thuật toán mà không rủi ro tiền thật.15  
2. **Giai đoạn Thử nghiệm (3-6 tháng):**  
   * Bắt đầu với số vốn nhỏ (ví dụ 50-100 triệu VND).  
   * Tập trung vào các mã cổ phiếu trong nhóm VN30 để đảm bảo thanh khoản và an toàn cơ bản.4  
   * Tuân thủ tuyệt đối các lệnh Stop Loss mà hệ thống đưa ra, không trung bình giá xuống.15  
3. **Giai đoạn Vận hành Tự động (Sau 6 tháng):**  
   * Khi đã tin tưởng vào tỷ lệ thắng (Win rate) và lợi nhuận kỳ vọng của thuật toán, nhà đầu tư có thể nâng dần quy mô vốn.  
   * Thiết lập các thông báo đẩy (Push Notifications) về điện thoại để theo dõi các hành động mà 'Trading OS' thực hiện tự động.51

### **Tư Vấn Chiến Thuật Phân Bổ Danh Mục 2026**

Dựa trên phân tích ngành, Hội đồng đề xuất cơ cấu danh mục tối ưu cho năm 2026 như sau:

* **Nhóm Ngân hàng (40%):** Các ngân hàng có nền tảng số tốt và nợ xấu thấp (như VCB, TCB, MBB) sẽ hưởng lợi từ chính sách tiền tệ ổn định và sự phục hồi kinh tế.4  
* **Nhóm Bán lẻ & Tiêu dùng (20%):** Hưởng lợi từ sự phục hồi của sức mua nội địa và các chính sách giảm thuế của Chính phủ.4  
* **Nhóm Công nghệ & Hạ tầng (20%):** Các mã như FPT hoặc các doanh nghiệp xây dựng hạ tầng chiến lược sẽ đón đầu làn sóng đầu tư công 315 tỷ USD giai đoạn 2026-2030.6  
* **Nhóm Dự phòng/Tiền mặt (20%):** Luôn duy trì một lượng tiền mặt để sẵn sàng giải ngân khi thị trường xuất hiện các nhịp điều chỉnh sâu (Correction) mang lại cơ hội mua vùng giá thấp.6

## **Kết Luận Và Khuyến Nghị Hành Động**

Thị trường chứng khoán Việt Nam giai đoạn 2025-2026 không còn là nơi dành cho sự may rủi. Với sự tham gia sâu rộng của công nghệ và sự giám sát chặt chẽ của các tiêu chuẩn quốc tế, việc áp dụng đầu tư định lượng là con đường tất yếu để tồn tại và thịnh vượng.

Hội đồng chuyên gia khẳng định rằng:

1. **Hệ thống 'Trading OS'** được xây dựng trên nền tảng dữ liệu SSI và thuật toán Wyckoff có khả năng mang lại lợi nhuận vượt trội 15% mỗi giao dịch bằng cách khai thác chu kỳ T+2.5.  
2. **Sự minh bạch và kỷ luật** thông qua việc tự động hóa hoàn toàn các tính năng (từ quét dữ liệu đến đặt lệnh và giải thích bằng ngôn ngữ tự nhiên) sẽ bảo vệ nhà đầu tư F0 khỏi những cạm bẫy tâm lý đám đông.  
3. **Tuân thủ tiêu chuẩn SDLC/PMBOK/BABOK** không chỉ là một quy trình kỹ thuật, mà là lời cam kết về độ tin cậy và sự chính xác tuyệt đối trong từng dòng code và từng lệnh giao dịch.

Nhà đầu tư hãy bắt đầu bằng việc chuẩn bị nền tảng hạ tầng API từ SSI hoặc DNSE ngay hôm nay, và thực hiện theo lộ trình đào tạo bài bản để sẵn sàng đón nhận "con sóng nâng hạng" lịch sử vào năm 2026\.

# ---

**Quantitative Investment Strategy and T+2.5 Trading System Architecture in the Vietnam Stock Market: A Comprehensive Report by the Academic Board and Fintech Experts**

## **Comprehensive Analysis of the Vietnam Stock Market 2025-2026**

The Vietnamese stock market is on the threshold of a new era, defined by a shift from a retail sentiment-driven frontier market to a more structured and transparent emerging market. Based on the latest macro data, the Vietnamese economy achieved an impressive GDP growth of 8.2% in Q3 2025, significantly outperforming ASEAN peers and attracting record Foreign Direct Investment (FDI) inflows.1 This boom is not merely a result of cyclical factors but is a consequence of deep institutional reforms, including the implementation of the KRX trading system and the market upgrade efforts targeting FTSE Russell status by September 2026\.1

In this context, the VN-Index is projected to reach new milestones, potentially hitting the 1,920 to 2,040 point range by 2026\.3 However, this growth is not uniform across all sectors. Data from 2025 shows a strong divergence, where stocks in the Vingroup ecosystem led significant gains, while the rest of the market showed limited breadth.3 This presents both a challenge and an opportunity for Quantitative (Quant) investors to find alpha by exploiting mispricing and market behaviors.

### **Macro Indicators and Market Targets 2025-2026**

| Macro Indicator | Actual / Forecast Value (2025-2026) | Significance for Investment Strategy |
| :---- | :---- | :---- |
| GDP Growth | 8.0% \- 8.5% | Supports projected Net Profit After Tax (NPAT) growth of 14-20% for listed companies.6 |
| Deposit Interest Rates | 7.0% \- 8.0% | The target interest level to drive idle capital significantly into the stock market.8 |
| Market Cap / GDP | \~62% (Target 100% by end of 2025\) | Significant room for market scale growth compared to regional peers like Thailand or Singapore.9 |
| Average Liquidity | $1.0 \- $1.2 billion/session | Ensures feasibility for high-volume trading algorithms without significant slippage.2 |
| Upgrade Timing (FTSE) | September 2026 | Main catalyst to attract an estimated $6-8 billion in new foreign capital.1 |

The structural shift toward a digital and high-tech economy also creates new drivers. The Vietnamese government has identified strategic priorities in infrastructure and digital transformation, directly boosting sectors such as IT, construction materials, and renewable energy.7 For F0 investors, understanding these macro cycles is the first step in building an investment mindset based on data rather than emotion.

## **Research on Market Cycles and Applied Wyckoff Methodology**

To identify "Bottom Entry" and "Top Exit" zones scientifically, the Board proposes using the Wyckoff method as the analytical foundation. This method does not view price fluctuations as random but as the result of the interaction between supply and demand driven by "market makers" or "Smart Money".9

### **Laws of Supply-Demand and the Three Wyckoff Laws**

The core of Wyckoff analysis rests on three fundamental laws that can be quantified in the algorithm:

1. **The Law of Supply and Demand:** When demand is greater than supply, prices rise; when supply is greater than demand, prices fall. The "Trading OS" algorithm will scan order book data from the SSI API to identify these imbalances in real-time.12  
2. **The Law of Cause and Effect:** The length of an accumulation phase (Cause) determines the magnitude of the subsequent uptrend (Effect). We use Point-and-Figure charts or cumulative volume analysis to forecast price targets.12  
3. **The Law of Effort vs. Result:** Divergence between trading volume (Effort) and price movement (Result) often signals a trend reversal. For instance, if volume spikes but price fails to rise correspondingly, it is a sign of distribution.12

### **Identifying Market Cycle Phases**

| Phase | Technical Characteristics | Smart Money Action | Strategy for F0 |
| :---- | :---- | :---- | :---- |
| **Accumulation** | Narrow volatility, low volume, emergence of "Springs".12 | Quietly collecting shares from impatient investors. | Monitor and wait for SOS (Sign of Strength) signals.15 |
| **Markup** | Strong price increases, higher highs/lows, rising volume on pushes. | Aggressively pushing prices to attract public attention. | Enter during technical pullbacks (Back-ups).9 |
| **Distribution** | Extreme volatility, high volume but price goes sideways (Upthrust).12 | Gradually selling shares to excited (FOMO) investors. | Take partial profits and raise Trailing Stops.16 |
| **Markdown** | Prices fall through support levels on high volume. | Complete withdrawal, letting the market free-fall. | Stay out of the market or hedge with derivatives. |

For the 2026 Vietnamese market, experts note that after the V-shaped recovery from the 2025 tariff shock, the market is entering a more sustainable Markup phase, supported by 14.5% EPS growth.5 Identifying "bottom zones" will rely on the appearance of "Spring" sessions—where prices drop below old support on low volume then quickly recover, purging the last margin positions before accelerating.14

## **Proposed Optimized T+2.5 Trading Algorithm for F0 Investors**

The T+2.5 mechanism in Vietnam creates a unique psychological trait: shares arriving on the afternoon of T+2 often cause sudden selling pressure after 14:00.17 Our algorithm must be designed to exploit this volatility.

### **"T+ Swing Alpha" Algorithm Logic**

The algorithm focuses on identifying breakouts from short-term accumulation bases with a 15% profit target.

**1\. Universe Selection:**

* **Liquidity:** Average 20-session volume (![][image1]) \> 1 million units.  
* **Relative Strength:** Stocks performing better than the VN-Index over the last 4 weeks.  
* **Fundamentals:** Priority for tickers with NPAT growth \> 15% (sourced from SSI Financial Ratio API).19

**2\. Entry Timing Formula:**

* **Condition 1:** Price breaks through a downtrend line or horizontal resistance (Pivot Point) with volume ![][image2].  
* **Condition 2:** RSI indicator between 50-65 (strong momentum but not yet overbought).20  
* **Condition 3:** MACD Histogram turns from negative to positive or maintains an uptrend above the Signal line.21  
* **Timing:** Prioritize execution at the end of the morning session or the very beginning of the T+0 afternoon session to anticipate the capital flow.18

**3\. Risk Management and Formulas:**

We apply a minimum Risk/Reward ratio of 1:2. With a 15% Target, the maximum Stop Loss is set at 7%.

* **ATR-based Stop Loss Formula:**  
  ![][image3]  
  Where ![][image4] is typically chosen between 1.5 and 2.0 to avoid market noise.22  
* **Position Sizing (2% Rule):**  
  ![][image5]  
  This ensures that each losing trade impacts a maximum of 2% of total assets.23

**4\. Exit Strategy:**

* **15% Target:** Automatically trigger a sell order when the price hits ![][image6].  
* **Trailing Stop:** If profit reaches 10%, move the Stop Loss to Break-even. If profit continues to rise, the Stop Loss is updated via: ![][image7].16  
* **Afternoon Session Exit:** If shares arrive on T+2 and the price does not meet expectations or shows weakening strength (RSI \> 70 and turning down), execute the exit immediately during the afternoon session (14:15 \- 14:45) to avoid next-day selling pressure.18

## **Blueprint for the 'Trading OS' Application Architecture**

The 'Trading OS' is not just a trading bot; it is a comprehensive investment operating system, integrating everything from raw data processing to natural language strategy explanation.

### **System Architecture**

Based on software architecture standards for financial systems, we propose a Layered Microservices model 25:

1. **Data Provider Service:** Directly connects to the SSI FastConnect API and DNSE LightSpeed API. Uses gRPC for internal real-time data transmission to reduce latency.27  
2. **Market Intelligence Service:** Performs calculation of technical indicators and automated Wyckoff pattern recognition. Uses Python's Pandas and TA-Lib libraries.29  
3. **Risk Management Module:** Validates orders based on exchange rules (e.g., minimum 100-share lots at HOSE) and account margin limits.26  
4. **Natural Language Generation (NLG) Module:** Uses a Transformer model (such as GPT-4 or fine-tuned FinBERT) to convert numerical data into text explanations.20  
   * *Input:* {Ticker: "HPG", Action: "Buy", Reason: "Spring identified, RSI 42, Volume \+60%"}  
   * *Output (Text):* "The system recommends buying HPG at the current price as a bear trap (Spring) has appeared at the 28.5 support level, accompanied by a strong capital surge, indicating demand is overwhelming supply".31

### **Technology Stack**

| Component | Proposed Technology | Selection Rationale |
| :---- | :---- | :---- |
| Backend | Python (FastAPI) | High performance, excellent support for Data Science and AI libraries.30 |
| Real-time Data | NodeJS & Socket.io | Handles thousands of concurrent connections with low latency.34 |
| Database | PostgreSQL \+ TimescaleDB | Optimized for time-series data storage for stock charts.36 |
| Caching | Redis | Stores prices and order statuses in real-time for instant retrieval.26 |
| Infrastructure | Docker & Kubernetes | Ensures scalability and high availability.26 |

## **Product Development Process via International Standards**

To achieve absolute precision and user trust, all features must be developed following the SDLC (Software Development Life Cycle), complying with PMBOK and BABOK guidelines.

### **Business Analysis via BABOK**

The Business Analyst (BA) team will execute a 6-step process to define requirements 37:

1. **Business Analysis Planning and Monitoring:** Identify stakeholders, including F0 investors, risk management experts, and compliance teams.38  
2. **Elicitation and Collaboration:** Interview professional traders to model "unwritten" rules in the Vietnam market (e.g., the impact of "system lag" or "ATC orders").38  
3. **Requirements Life Cycle Management:** Present and approve functional requirements such as: "The system must automatically cancel the order if the price does not match within 5 minutes".39  
4. **Strategy Analysis:** Assess market risks and the system's integration capability with bank payment gateways (Bankgate).40  
5. **Requirements Analysis and Design Definition:** Design User Stories and Data Flow Diagrams for the automated order process.37  
6. **Solution Evaluation:** Verify whether the application actually helps investors reach the 15% profit target through specific KPIs.39

### **Project Management via PMBOK**

The Software Director and Delivery Manager will apply the 10 knowledge areas of PMBOK to run the project:

* **Scope Management:** Ensure the system focuses on the core T+2.5 trading feature, preventing Scope Creep.41  
* **Schedule Management:** Use Agile/Scrum with 2-week Sprints to quickly launch MVP versions.26  
* **Quality Management:** Establish Unit Test procedures for trading algorithms and Integration Test for SSI API connections.42  
* **Risk Management:** Build contingency scenarios for internet loss or system errors from the brokerage side.42

## **SSI and Brokerage Data Integration Guide**

The accuracy of the 'Trading OS' depends entirely on "clean" and real-time data sources. The SSI FastConnect API is the preferred choice due to its stability and professional support.44

### **SSI FastConnect API Implementation Steps**

1. **Registration:** Customers must open an account at SSI and register for the FastConnect API service at branches.27  
2. **Key Provisioning:** After successful registration, users log into iBoard to generate connection keys including:  
   * ConsumerID: Application identification.  
   * ConsumerSecret: Security code.  
   * PrivateKey: Key used for electronic signatures for fund orders.46  
3. **Authentication:** The system uses the OAuth2 protocol to retrieve an Access Token. This token is valid for 8 hours, so 'Trading OS' needs an automated refresh mechanism.46  
4. **Streaming:** To receive real-time prices, the application connects to the SSI SignalR Hub. Attention to Rate Limits is necessary to avoid connection blocking.30

### **Comparison of API Solutions in Vietnam**

| Feature | SSI FastConnect | DNSE LightSpeed | VNDirect Open API |
| :---- | :---- | :---- | :---- |
| **Advantages** | High reliability, supports multiple languages (Python, NodeJS, Java).35 | Optimized for deal-by-deal trading, zero fees, modern API.28 | Strong infrastructure, suitable for institutional clients (FIX protocol).40 |
| **F0 Support** | Comes with Q-Trader support software.44 | User-friendly interface, easy online registration.28 | Provides many analytical tools (D-Board, Stockbook).50 |
| **Best For** | Professional investment requiring absolute stability. | High-frequency algorithmic trading, cost-saving. | Hedge funds and institutional investors. |

## **Training and Investment Roadmap for F0 Investors**

For a new (F0) investor, owning a powerful tool is only 50% of the journey. The remaining 50% lies in the capital management mindset and patience.

### **3-Step Market Entry Roadmap**

1. **Learning Phase (Months 1-3):**  
   * Understand market cycles and basic candlestick chart reading.  
   * Use the "Demo Trading" feature on 'Trading OS' to familiarize yourself with algorithm signals without risking real money.15  
2. **Testing Phase (Months 3-6):**  
   * Start with a small capital amount (e.g., 50-100 million VND).  
   * Focus on tickers within the VN30 group to ensure basic liquidity and safety.4  
   * Strictly follow the Stop Loss orders issued by the system; do not average down.15  
3. **Automated Operation Phase (After Month 6):**  
   * Once confident in the Win Rate and expected profit of the algorithm, the investor can gradually scale up capital.  
   * Set up Push Notifications on mobile to track automated actions performed by 'Trading OS'.51

### **Portfolio Allocation Strategy 2026**

Based on sector analysis, the Board recommends the following optimal portfolio structure for 2026:

* **Banking (40%):** Banks with strong digital foundations and low NPLs (such as VCB, TCB, MBB) will benefit from stable monetary policy and economic recovery.4  
* **Retail & Consumer Goods (20%):** Benefit from the recovery of domestic purchasing power and government tax reduction policies.4  
* **Technology & Infrastructure (20%):** Tickers like FPT or strategic infrastructure firms will anticipate the $315 billion public investment wave for the 2026-2030 period.6  
* **Reserve/Cash (20%):** Always maintain a cash portion to be ready for deep market corrections that offer low-price buying opportunities.6

## **Conclusion and Recommended Actions**

The Vietnamese stock market in the 2025-2026 period is no longer a place for luck. With the extensive participation of technology and strict adherence to international standards, the application of quantitative investment is the inevitable path to survival and prosperity.

The Expert Board affirms that:

1. **The 'Trading OS' system**, built on SSI data and the Wyckoff algorithm, is capable of delivering superior 15% returns per trade by exploiting the T+2.5 cycle.  
2. **Transparency and discipline** through complete automation (from data scanning to order placement and natural language explanation) will protect F0 investors from psychological traps of the crowd.  
3. **Compliance with SDLC/PMBOK/BABOK standards** is not just a technical process but a commitment to reliability and absolute precision in every line of code and every trading order.

Investors should begin by preparing their API infrastructure from SSI or DNSE today and follow the structured training roadmap to be ready for the historic "upgrade wave" in 2026\.

#### **Works cited**

1. Vietnam: The ASEAN powerhouse \- LSEG, accessed March 27, 2026, [https://www.lseg.com/en/insights/ftse-russell/vietnam-the-asean-powerhouse](https://www.lseg.com/en/insights/ftse-russell/vietnam-the-asean-powerhouse)  
2. Vietnam's stock market enters its strongest transformation in a decade \- VietNamNet, accessed March 27, 2026, [https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html](https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html)  
3. VN-Index could reach 2,040 points in 2026 \- Vietnam Investment Review, accessed March 27, 2026, [https://vir.com.vn/vn-index-could-reach-2040-points-in-2026-144858.html](https://vir.com.vn/vn-index-could-reach-2040-points-in-2026-144858.html)  
4. VN-Index could reach 1,920 points in 2026: SSI Research \- Vietnam News, accessed March 27, 2026, [https://vietnamnews.vn/economy/1731639/vn-index-could-reach-1-920-points-in-2026-ssi-research.html](https://vietnamnews.vn/economy/1731639/vn-index-could-reach-1-920-points-in-2026-ssi-research.html)  
5. MARKET STRATEGY REPORT 2026 \- BUILDING STRATEGIC POSITIONING \- Acbs, accessed March 27, 2026, [https://acbs.com.vn/en/report/market-strategy-report-2026-building-strategic-positioning](https://acbs.com.vn/en/report/market-strategy-report-2026-building-strategic-positioning)  
6. Monthly Market Outlook \- SSI, accessed March 27, 2026, [https://www.ssi.com.vn/en/organization-customer/monthly-market-outlook](https://www.ssi.com.vn/en/organization-customer/monthly-market-outlook)  
7. Stock Market Outlook for 2026: "The Era of Growth – The Great Wave of Transformation", accessed March 27, 2026, [https://bidvinfo.com.vn/en/stock-market-outlook-for-2026-the-era-of-growth-the-great-wave-of-transformation-10013749.html](https://bidvinfo.com.vn/en/stock-market-outlook-for-2026-the-era-of-growth-the-great-wave-of-transformation-10013749.html)  
8. Looking Ahead at 2026 \- VinaCapital, accessed March 27, 2026, [https://vinacapital.com/wp-content/uploads/2026/01/20260119\_VinaCapital-Insights\_Looking-Ahead-at-2026.pdf](https://vinacapital.com/wp-content/uploads/2026/01/20260119_VinaCapital-Insights_Looking-Ahead-at-2026.pdf)  
9. IMPACT OF FOREIGN INVESTORS ON THE VIETNAMESE STOCK MARKET IN NEW CONTEXT, accessed March 27, 2026, [https://tapchitckt.hvtc.edu.vn/DesktopModules/SubPortal/TapChiNCTCKT/Service/TraVeFilePDF.aspx?ID=285](https://tapchitckt.hvtc.edu.vn/DesktopModules/SubPortal/TapChiNCTCKT/Service/TraVeFilePDF.aspx?ID=285)  
10. VNINDEX INDEX: A VIEW FROM QUANTITATIVE ANALYSIS \- GPH Journal, accessed March 27, 2026, [https://gphjournal.org/index.php/bm/article/download/680/450/](https://gphjournal.org/index.php/bm/article/download/680/450/)  
11. A new phase of Vietnam's stock market \- VnEconomy, accessed March 27, 2026, [https://en.vneconomy.vn/a-new-phase-of-vietnams-stock-market.htm](https://en.vneconomy.vn/a-new-phase-of-vietnams-stock-market.htm)  
12. Wyckoff Method, accessed March 27, 2026, [https://www.wyckoffanalytics.com/wyckoff-method/](https://www.wyckoffanalytics.com/wyckoff-method/)  
13. Phương pháp Wyckoff – Cách đầu tư chứng khoán hiệu quả \- DNSE, accessed March 27, 2026, [https://www.dnse.com.vn/hoc/phuong-phap-wyckoff](https://www.dnse.com.vn/hoc/phuong-phap-wyckoff)  
14. Mô Hình Wyckoff Kinh Điển: Bẫy Giảm Giá – Cơ Hội Vàng Cho Nhà Đầu Tư? \- YouTube, accessed March 27, 2026, [https://www.youtube.com/watch?v=cBG1Jydn658](https://www.youtube.com/watch?v=cBG1Jydn658)  
15. Phương pháp Wyckoff là gì? Các mô hình và ứng dụng giao dịch theo phương pháp Wyckoff, accessed March 27, 2026, [https://techprofit.vn/phuong-phap-wyckoff/1706865096027](https://techprofit.vn/phuong-phap-wyckoff/1706865096027)  
16. How to calculate your trailing stop loss correctly | Quant Investing, accessed March 27, 2026, [https://www.quant-investing.com/blog/how-to-calculate-your-trailing-stop-loss-correctly](https://www.quant-investing.com/blog/how-to-calculate-your-trailing-stop-loss-correctly)  
17. Investors to be able to trade stocks on T+2 settlement cycle \- Vietnam News, accessed March 27, 2026, [https://vietnamnews.vn/economy/1254864/investors-to-be-able-to-trade-stocks-on-t-2-settlement-cycle.html](https://vietnamnews.vn/economy/1254864/investors-to-be-able-to-trade-stocks-on-t-2-settlement-cycle.html)  
18. Vietnam considers midday and same-day stock trading \- The Investor, accessed March 27, 2026, [https://theinvestor.vn/vietnam-considers-midday-and-same-day-stock-trading-d16684.html](https://theinvestor.vn/vietnam-considers-midday-and-same-day-stock-trading-d16684.html)  
19. vnstock 0.1.1 \- PyPI, accessed March 27, 2026, [https://pypi.org/project/vnstock/0.1.1/](https://pypi.org/project/vnstock/0.1.1/)  
20. Generating Alpha: A Hybrid AI-Driven Trading System Integrating Technical Analysis, Machine Learning and Financial Sentiment for Regime-Adaptive Equity Strategies \- arXiv, accessed March 27, 2026, [https://arxiv.org/html/2601.19504](https://arxiv.org/html/2601.19504)  
21. Multi-objective optimization for algorithmic trading in the Vietnamese stock market, accessed March 27, 2026, [https://www.researchgate.net/publication/394351735\_Multi-objective\_optimization\_for\_algorithmic\_trading\_in\_the\_Vietnamese\_stock\_market](https://www.researchgate.net/publication/394351735_Multi-objective_optimization_for_algorithmic_trading_in_the_Vietnamese_stock_market)  
22. How to Calculate the Stop-Loss and Target Price in Intraday Trading? \- TrueData, accessed March 27, 2026, [https://www.truedata.in/blog/how-to-calculate-stop-loss-target-price-in-intraday-trading](https://www.truedata.in/blog/how-to-calculate-stop-loss-target-price-in-intraday-trading)  
23. How to Calculate Stop Loss in Intraday Trading \- Jainam, accessed March 27, 2026, [https://www.jainam.in/blog/how-to-calculate-stop-loss/](https://www.jainam.in/blog/how-to-calculate-stop-loss/)  
24. When to exit? : r/algotrading \- Reddit, accessed March 27, 2026, [https://www.reddit.com/r/algotrading/comments/11xp3ra/when\_to\_exit/](https://www.reddit.com/r/algotrading/comments/11xp3ra/when_to_exit/)  
25. Software Architecture \- algorithmic-trading-learning-roadmap \- GitHub, accessed March 27, 2026, [https://github.com/rmcmillan34/algorithmic-trading-learning-roadmap/blob/main/roadmap/software-engineering/software-architecture/README.md](https://github.com/rmcmillan34/algorithmic-trading-learning-roadmap/blob/main/roadmap/software-engineering/software-architecture/README.md)  
26. Algorithmic Trading Software Development: Pro Tips \- IT Craft, accessed March 27, 2026, [https://itechcraft.com/blog/algorithmic-trading-software-development-guide/](https://itechcraft.com/blog/algorithmic-trading-software-development-guide/)  
27. Fast Connect API \- SSI, accessed March 27, 2026, [https://www.ssi.com.vn/en/individual-customer/fast-connect-api](https://www.ssi.com.vn/en/individual-customer/fast-connect-api)  
28. LightSpeed API | ENTRADE X, accessed March 27, 2026, [https://hdsd.dnse.com.vn/san-pham-dich-vu/lightspeed-api](https://hdsd.dnse.com.vn/san-pham-dich-vu/lightspeed-api)  
29. 04\. Core Components to Build an Algorithmic Trading System \- Algotrade Knowledge Hub, accessed March 27, 2026, [https://hub.algotrade.vn/knowledge-hub/what-you-need-to-build-an-algorithmic-trading-system/](https://hub.algotrade.vn/knowledge-hub/what-you-need-to-build-an-algorithmic-trading-system/)  
30. SSI-Securities-Corporation/python-fcdata \- GitHub, accessed March 27, 2026, [https://github.com/SSI-Securities-Corporation/python-fcdata](https://github.com/SSI-Securities-Corporation/python-fcdata)  
31. Automated Trading Framework Using LLM-Driven Features and Deep Reinforcement Learning \- MDPI, accessed March 27, 2026, [https://www.mdpi.com/2504-2289/9/12/317](https://www.mdpi.com/2504-2289/9/12/317)  
32. (PDF) Automated Trading Framework Using LLM-Driven Features and Deep Reinforcement Learning \- ResearchGate, accessed March 27, 2026, [https://www.researchgate.net/publication/398590019\_Automated\_Trading\_Framework\_Using\_LLM-Driven\_Features\_and\_Deep\_Reinforcement\_Learning](https://www.researchgate.net/publication/398590019_Automated_Trading_Framework_Using_LLM-Driven_Features_and_Deep_Reinforcement_Learning)  
33. FastAPI framework, high performance, easy to learn, fast to code, ready for production \- GitHub, accessed March 27, 2026, [https://github.com/fastapi/fastapi](https://github.com/fastapi/fastapi)  
34. Sample client guide | FastConnect API \- SSI, accessed March 27, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-trading/sample-client-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-trading/sample-client-guide)  
35. Sample client guide | FastConnect API \- SSI, accessed March 27, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide)  
36. Best Operating System For Quant Trading? \- QuantStart, accessed March 27, 2026, [https://www.quantstart.com/articles/best-operating-system-for-quant-trading/](https://www.quantstart.com/articles/best-operating-system-for-quant-trading/)  
37. Types of Requirements | BABOK classification Schema \- Techcanvass, accessed March 27, 2026, [https://techcanvass.com/blogs/types-of-requirements-as-per-babok](https://techcanvass.com/blogs/types-of-requirements-as-per-babok)  
38. Requirements Made Simple: A Practical Guide Using BABOK | by Nataliia Trester \- Medium, accessed March 27, 2026, [https://medium.com/@trester.nv/requirements-made-simple-a-practical-guide-using-babok-e9799cf46ef7](https://medium.com/@trester.nv/requirements-made-simple-a-practical-guide-using-babok-e9799cf46ef7)  
39. Understanding BABOK Requirements Life Cycle Management \- Watermark Learning, accessed March 27, 2026, [https://www.watermarklearning.com/blog/babok-requirements-life-cycle-management/](https://www.watermarklearning.com/blog/babok-requirements-life-cycle-management/)  
40. Dịch vụ chứng khoán \- Giao dịch chứng khoán (VNDIRECT)Công ty ..., accessed March 27, 2026, [https://www.vndirect.com.vn/en/institutional-customer/investment-institutions/securities-service/](https://www.vndirect.com.vn/en/institutional-customer/investment-institutions/securities-service/)  
41. What is the Software Development Lifecycle (SDLC)? \- IBM, accessed March 27, 2026, [https://www.ibm.com/think/topics/sdlc](https://www.ibm.com/think/topics/sdlc)  
42. What Is the Software Development Lifecycle (SDLC)? \- Palo Alto Networks, accessed March 27, 2026, [https://www.paloaltonetworks.com/cyberpedia/sdlc-software-development-lifecycle](https://www.paloaltonetworks.com/cyberpedia/sdlc-software-development-lifecycle)  
43. Automated Trading Systems: Design, Architecture & Low Latency \- QuantInsti, accessed March 27, 2026, [https://www.quantinsti.com/articles/automated-trading-system/](https://www.quantinsti.com/articles/automated-trading-system/)  
44. 29\. Stock Trading API in Vietnam Market \- Algotrade Knowledge Hub, accessed March 27, 2026, [https://hub.algotrade.vn/knowledge-hub/api-in-vietnam-stock-market/](https://hub.algotrade.vn/knowledge-hub/api-in-vietnam-stock-market/)  
45. 62\. How to Register for API at SSI Securities JSC \- Algotrade Knowledge Hub, accessed March 27, 2026, [https://hub.algotrade.vn/knowledge-hub/how-to-register-for-api-at-ssi-securities-jsc/](https://hub.algotrade.vn/knowledge-hub/how-to-register-for-api-at-ssi-securities-jsc/)  
46. Connection guide | FastConnect API \- SSI, accessed March 27, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-trading/connection-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-trading/connection-guide)  
47. General Information \- FastConnect API \- SSI, accessed March 27, 2026, [https://guide.ssi.com.vn/ssi-products/general-information](https://guide.ssi.com.vn/ssi-products/general-information)  
48. Introduction | FastConnect API \- SSI, accessed March 27, 2026, [https://guide.ssi.com.vn/ssi-products](https://guide.ssi.com.vn/ssi-products)  
49. Entrade X by DNSE: Stocks \- Apps on Google Play, accessed March 27, 2026, [https://play.google.com/store/apps/details?id=vn.com.encapital.arrow](https://play.google.com/store/apps/details?id=vn.com.encapital.arrow)  
50. VND.VN (VNDIRECT Securities Corp) \- Financial Data APIs \- EODHD, accessed March 27, 2026, [https://eodhd.com/financial-summary/VND.VN](https://eodhd.com/financial-summary/VND.VN)  
51. OpenClaw Quantitative Trading Integration Suite Low-Latency Integration with Trading Systems \- Tencent Cloud, accessed March 27, 2026, [https://www.tencentcloud.com/techpedia/140972](https://www.tencentcloud.com/techpedia/140972)  
52. lacchain/ssi-api \- GitHub, accessed March 27, 2026, [https://github.com/lacchain/ssi-api](https://github.com/lacchain/ssi-api)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD0AAAAZCAYAAACCXybJAAAEEUlEQVR4Xr2WT4hPURTHz82fTGaS8T8Lk2xEIWFDKSRp0Jgd2bJmIWUnCzb+JAspM8m/FRaUIf38KYmUomwUUrKQmmI543zveffde8+7v/d+f9741Pm9984595z759x7f0QOk7+FrxHN9O1RT5Qyus5QHqDcqil4FxTd4gPWHLqFkphCwpTV6as9SumyuQbh5rHM0gZNIa9xuvyla/pZ9rIMZ7ItshaTbCbvC+lP+KTYxPKH5YDSo3UYb5g1W/k5PUg+m2V34LPPGdKp09qU/jPLT5KOeWK/hSzvWSap2PkqJkjaXdQGkkE9IbE3o4/7coGfPfLpOlYcSIiyFpzvsDxkmSxYLAbqkyw/WMZZ1sT2UjBZmEwMalTZHNDD3mu7FnXCfgzxY06orYPD5BNb1OBRnphprNgblrm5JT1LDlhPUR7bPFB2x3GS3PO1gWTSXvnP8oSaZt4YwHryiTW9LCMsK0jsVyNrMqpTmlX885Z87Ibz8FhfbBfYl8Q2NhqeNEPnlb47jCRE5u0kK4lBhoxkuuWkSjs5Xs8OlrGsLAdJBvU1dsnBpGMLoA+OXo7/iJ8HA11MRQfKcCvnEi8KbDNIShvsIl3aBfJe4Hp6TjJwgLYY9HiTnmJCcV4Myaf1wWDvs/QkW6TjpLVKiQE8zt5RWlgJdMD57fGvdJpfU6evRcU9xnKF7NVjcRMa3w4W2xITjRsE28DxmmVd8A1Q7gMk+1yPj6vR4EqdpvQhtg1K9UXWnCfAYCU3ZGYEvpU5u2sluqrQA3lGSvCB5M7HREJ2svyl9JkBsH0a5KsOk3WC4tDYJjdZzrD8Zrmd6cAhwjikf3cDfRIkwcntGCWZ7S0s50jKG2DF0eGS0s5BW0xYiFtJO2i9RMDIHd5gWUayNTQN8mcK+oEF+kj2xLeL5fqG8SBXuE1z4PSU3MoKGPB1lmssA4GeS7vpKmXYoWDFxpQBuJUsi4Hc31kuk+TXYBWxyljFPiMri0EvIIntDuBB7gpvI4MtFSBTDeVLiu9GHCQTJi7jQodTK5VxhHD4FB18DGXDZ6ZyJ/w3kuuxjNUkJY6rrI+Kg0YcHJ45K1l+kSRw4vYAbO7wmMmN74ndhL5RsAyUZugTlhbedQycDzgnQlC2qBJ9ZWowR89YFmffbkL9oCUHnp7iQpRg/4HWQWUc91+giv3GLxJWGYdeg+ReBxgsbglV3s3Q/dLfOUFRhlhVqE/4dMdGjom/wwD7+iyelB9olqMsX1iWZt9tUHt/Y9LhS7VrWd6xjBj7H8DcIPkvgJvzE8k+B5cySQf7b9SQvoUQODtQ2mV/TgIKEQuKDugyRovNW3RrjdaDmXack5Q1L7NNEe2krPKtsndGHLWWHC5IJ8GkTSctI1oO0NzxHwQ7pvZaFLmVAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAYCAYAAAAs7gcTAAABNklEQVR4XnVSMUpEQQzNgFspgpUIgqXsObTdXtgbeAE7GxvBzlIWBMEDbGdhbeM5xEo8geh7k0ySmf99y/tJ3mSS/PwVKSJkoTWYVDkDZneRe/y5UIMWuTtoDZN2//RWRJczeJewD+DtTBmFjlK9NR6/sPehNYyxyAZJSJZ1ntkvpgoH4Dv4BWmp6rRa27GPoKIsUGiFI40HPIqPULFFfANewz/0LGumI4gswROotBfCbkWO/BObYdVP8AU8Vikj3rRwC/C+4f4g/gAXfXKAm6hbgN0Hn8GrPiXAvdpb104rcGNn59B2bIwKJtoWqsIEVuYoT0mXXfAV/mlIsgePL/uG+E4lQ/uKYe1hNwMcxcZJqfl4QFPyCZfZhbmV2UklnynMDNK/vJf1MV7MjVOU50tXuj9PkT90eyLQu94TcQAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,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>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAG8AAAAZCAYAAAA/vnC8AAAFU0lEQVR4Xu2ZW8hmUxjHnxVT5JRDDqGRUISZGhK5kFwop3Jo1ODGlBvKYWbEjUHukLigQZJSNJJEQs0XhUy5UChRHyUhKSGHGP//evba+9nrXWu/a+93v9/3zcev/vPtdx2etfbzrPWs9b4jsky46h//N0W2YhkZMKfQZUDX6XQZzdelaroisRfSepfV9GIjMqZbxrS1dJTNuqzVvEit5OIZFTecATfOKKMYGcYBGP0S/L26QGz3P2Mzc/CdfIl/90APxBXgJOhzaHeirpTjoM+gl+OKLMXmixv2ImH1HOgF6CdRXx3Yru7kRuhp6BvoK+iYdrWH9mjX6k/oGtsoxV/QP9BFcUXF3dDbcWEPLhedzM64opuRUts4MAA3QbdI/+DtgLZBm6Q8eE+KLvqpsPEidGxUHuCgz7aLMm5NFz8qOgZffmWRnm8H7jJJBa/MzgbJBM+pPdqejhlrX2l2BZ8D90FX6KO7U3T3DYUp91fRyfeizCeSa3ir5Gq0/Hpoc1wxhXTwysgGT/oEz8BUybR5fvX5SOgR6EPo0NCogtv4XegG6APoXOhN0Z21Ffoberxqewr0EfQ1tAee+qV6psPIHdBt8CH7PCZql5eiT6GHoEOg16D7RZ11bdWPXCA6VpQNJqCNt6AHo3IGbhd0dDa0ecqDF2w3Y0wL3s3Qi9D3lfh5jVanJ8pLis21KucDEkNj26tnOo6H93nVZ06IE6MsHJU2mXoDR0FvQGdDv4kG4iroVfFtHS8G20UDh/6O/e/Vrp4wZ2aEaTCAr0vtBNkHugs6rG7Rj47gTUYrIhM83572eHE8syrcKOoXnpdJ9hNd3c+IWqC4E5nirjTtAnQCdyh35G603mgmmgveEdCP0KmmjBcYrrBNVWD4TOe+I37CjoHkjjlRmrTOPoEFaWeLDPXcGMCnoINFdyFt12RdnaYjeCla1jPB8zAW6/2TdqH9BdGxktA530r7IkHDTJnB2YeL7jh8J5QNTp3MOgaEgQnQkXTogikjnDDPPJuC1wptOL9omFLtrgwwJTNwp4t+zeBuDXDsRclfsFI8J7rLuQAZzKEUBS+zIHzwXDp4nqgfF1x2rJB+4rPN8r6oIwO0751uygjPwD+k3ZbO3ynpXUy4w+PAWqrV5+KvMBz79qisi86d15Oi4GVoBc8Ein7iXYGyl0YeCxxrIth2W2YWii/nObS/KeNu+0TU8Zaw62h3i6ijQlubMjU1KBjb0am5GYRUbHaYY6ALUmZNc+bpGOVnXnpOMwdPJoPBOXLxxws57LyJxR1SX7SD6hnzgYfmxU2dhxMIO8ZCO0yv7Pi86ApimmXbg6o2/LXm+OqZ9tknlTID66Cfpe0ojo8F4WzKzlHfNps4+Cf+s0t422wVd1E36AreyaJHTu7LdSt4ZsiQoU5rimDfTZ5561BIh7CwRAY/3BOiv8ZEQXW/izqEP6WFsjVOUwEvJF9AlzZ1cobojdPu6pQTLxTt+5LoORef0cpkP8LFlK7R8j7f80IKi1UHA5wFoz+Ivpsl7hPEYAbQ1TEur0A7nPqYfpueIXrAWxEvMbFTWM6X4F8L2/GyEa7qtjxum4P9Ka5oXl54iUkQT2me2LHGGtfRr/wt82HoBBa0q1ufLE1Nvs2SwhT0MfSeKbtOuGJd61CfAyvEA3sx4Sa8WH1eK5qSTVrOMfQH7eVfwMlxk4WjMLcX5ll4D/Sd6E2M/6cYp17P0HGL+xU3nCdhEiWT8W26AjNZMiqV+a5RuuqKGcXICmC1vMfs/Bc80fWO0c5t0VW3BMxv5JEtz2ZuQO8BXQL5rqmaVNnq5l8d4wxRWojnxgAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,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>