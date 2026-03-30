# **Đề xuất Kỹ thuật và Nghiên cứu Chiến lược cho Tính năng Khuyến nghị Đầu tư T+ với Mục tiêu Lợi nhuận 15% trên Hệ sinh thái Dữ liệu SSI iBoard**

Sự dịch chuyển của thị trường chứng khoán Việt Nam trong giai đoạn 2024-2026 đánh dấu một kỷ nguyên mới của đầu tư dựa trên dữ liệu và thuật toán. Với mục tiêu nâng hạng từ thị trường cận biên lên thị trường mới nổi theo tiêu chuẩn FTSE Russell vào tháng 9 năm 2026, các yếu tố cấu trúc như loại bỏ yêu cầu ký quỹ trước (pre-funding) và cải thiện khả năng tiếp cận của nhà đầu tư nước ngoài đã tạo ra những biến động mang tính hệ thống.1 Trong bối cảnh này, việc xây dựng một hệ thống khuyến nghị đầu tư ngắn hạn (T+) đạt hiệu suất 15% đòi hỏi sự tích hợp tinh vi giữa kiến trúc dữ liệu thời gian thực từ các công ty chứng khoán hàng đầu như SSI và các mô hình định lượng tiên tiến như Hidden Markov, Wyckoff và Mansfield Relative Strength.3 Báo cáo này trình bày một proposal technical toàn diện, bắt đầu từ việc giải mã hạ tầng API của SSI cho đến việc thiết kế thuật toán cốt lõi và hệ thống tự động hóa báo cáo bằng ngôn ngữ tự nhiên.

## **Phân tích Kiến trúc Dữ liệu và Chiến lược Khai thác Tối ưu từ Hệ thống SSI iBoard**

Nền tảng SSI iBoard hiện nay không chỉ là một bảng giá đơn thuần mà là một trung tâm dữ liệu phân tán phức tạp, vận hành dựa trên các giao thức hiện đại để phục vụ hàng triệu truy vấn mỗi giây. Phân tích tệp nhật ký yêu cầu 'SSI\_HARrequestLogs.txt' cho thấy SSI sử dụng một chiến lược đa tên miền (multi-domain strategy) để phân tách tải lượng công việc, bao gồm iboard-api.ssi.com.vn cho các dịch vụ thống kê và tin tức, cùng với iboard-query.ssi.com.vn cho các truy vấn dữ liệu thị trường trực tiếp.6

### **Giải mã Giao thức và Cơ chế Xác thực trong HAR Logs**

Dựa trên phân tích các tệp script được kích hoạt trong log như CD4WCHdI.js và CXXpoEDl.js, hệ thống iBoard sử dụng các bộ đánh chặn (interceptors) mạnh mẽ để quản lý trạng thái dữ liệu và xác thực người dùng. Dấu vết từ hàm executeFetch và setOptions cho thấy SSI tích hợp các thư viện quản lý state hiện đại như TanStack Query hoặc React Query, giúp tối ưu hóa việc lưu trữ tạm thời (caching) và tránh các yêu cầu trùng lặp lên server.6 Cơ chế xác thực chính được xác định là Bearer Token thông qua tiêu đề HTTP Authorization, đi kèm với device-id duy nhất để định danh phiên làm việc và áp dụng các chính sách giới hạn tần suất (rate limit).7

Đối với các ứng dụng Fintech chuyên nghiệp, phương án fetch dữ liệu tối ưu nhất là sử dụng hệ thống FastConnect API thay vì quét dữ liệu từ bảng giá web. Hệ thống này đòi hỏi một quy trình xác thực đa lớp với ConsumerID, ConsumerSecret và PrivateKey.7 Việc ký số RSA \+ SHA256 cho các yêu cầu nhạy cảm như đặt lệnh hoặc truy vấn số dư tài khoản đảm bảo tính toàn vẹn và chống chối bỏ trong môi trường giao dịch trực tuyến.9

| Thành phần Dữ liệu | Phương thức Khai thác | Endpoint Tham chiếu từ Log |
| :---- | :---- | :---- |
| Giá Real-time | WebSockets / Streaming Hub | wss://fc-data.ssi.com.vn/ 10 |
| Chỉ số Tài chính | GraphQL / REST | /statistics/company/ssmi/finance-indicator 6 |
| Tin tức Doanh nghiệp | RESTful API | /statistics/company/ssmi/company-news 6 |
| Biểu đồ kỹ thuật | REST / TradingView | /statistics/charts/history 11 |

Bảng 1: Phân loại phương thức fetch dữ liệu từ hệ thống SSI.10

### **Tối ưu hóa Luồng dữ liệu cho Thuật toán Khuyến nghị**

Để đạt được mục tiêu T+, hệ thống cần một đường ống dữ liệu (data pipeline) có độ trễ cực thấp. Khai thác WebSockets cho phép nhận dữ liệu đẩy (push) ngay khi có thay đổi về bước giá hoặc khối lượng khớp lệnh, giúp thuật toán phản ứng nhanh hơn các nhà đầu tư cá nhân sử dụng trình duyệt truyền thống.12 Phân tích endpoint /stock/group/VN100 cho thấy dung lượng phản hồi lớn (hơn 170KB), do đó việc sử dụng GraphQL để lọc các trường dữ liệu cần thiết như matchedPrice, best1Bid và best1Ask là bắt buộc để tiết kiệm băng thông và giảm thời gian xử lý tại client.6

Dữ liệu lịch sử biểu đồ kỹ thuật được fetch thông qua các query parameters như resolution=1D (hoặc 1H, 15\) và các mốc thời gian Unix from, to.6 Thuật toán khuyến nghị sẽ lưu trữ các dữ liệu này vào một cơ sở dữ liệu thời gian thực (như Redis hoặc InfluxDB) để phục vụ cho các tính toán chỉ báo kỹ thuật liên tục mà không cần truy vấn lại server của SSI quá nhiều lần, tránh vi phạm rate limit "API calls quota exceeded".7

## **Tích hợp các Biến số Cấu trúc Thị trường Việt Nam vào Thuật toán**

Thị trường chứng khoán Việt Nam sở hữu những đặc thù về vận hành mà nếu không tích hợp vào thuật toán, các mô hình định lượng chuẩn quốc tế sẽ dễ dàng thất bại. Ba biến số then chốt cần được lập trình hóa bao gồm chu kỳ thanh toán T+2.5, giới hạn sở hữu nước ngoài (FOL) và biên độ dao động sàn/trần.15

### **Chiến lược Đối phó với Cú sốc Cung phiên chiều T+2.5**

Quy định thanh toán T+2.5 cho phép hàng về tài khoản sau 11h30 ngày T2 và có thể giao dịch ngay từ 13h00 cùng ngày.15 Dữ liệu thống kê cho thấy áp lực bán thường tăng vọt trong khoảng từ 13h00 đến 14h00 do tâm lý chốt lời hoặc cắt lỗ của lượng hàng vừa về.19 Thuật toán sẽ áp dụng một bộ lọc "Afternoon Liquidity Filter":

1. **Theo dõi sự hấp thụ cung:** Nếu giá cổ phiếu giữ vững được các ngưỡng hỗ trợ quan trọng hoặc có sự hồi phục đi kèm khối lượng lớn trong khung giờ 13h30-14h15, đó là tín hiệu xác nhận của lực cầu mạnh mẽ.19  
2. **Điểm mua tối ưu:** Khuyến nghị mua thường được kích hoạt vào cuối phiên chiều sau khi đã hấp thụ hết áp lực T+2.5, nhằm tận dụng đà tăng giá (momentum) cho phiên ATO ngày hôm sau.19

### **Giới hạn Sở hữu Nước ngoài (FOL) và Phí chênh lệch (Premium)**

Đối với các cổ phiếu "siêu tăng trưởng" thường xuyên hết room ngoại như FPT, MWG, ACB, yếu tố FOL đóng vai trò là một ranh giới cung \- cầu.17 Khi một cổ phiếu chạm trần sở hữu ngoại, các quỹ đầu tư nước ngoài buộc phải mua lại từ nhau thông qua giao dịch thỏa thuận với mức premium có thể lên tới 7-30% so với giá sàn.17

Thuật toán sẽ fetch dữ liệu foreignRoom từ endpoint /statistics/company/ssmi/stock-info.11 Một chiến lược "FOL-Arbitrage" được đề xuất: Khi tỷ lệ room ngoại hở ra đột ngột do phát hành thêm hoặc do một quỹ thoái vốn, thuật toán sẽ phát lệnh theo dõi đặc biệt. Sự trở lại của dòng vốn ngoại sau khi hở room thường đi kèm với các đợt bứt phá mạnh mẽ, là cơ sở để đạt được mục tiêu lợi nhuận 15% trong thời gian ngắn.17

### **Biên độ Giao dịch và Phiên Định kỳ ATO/ATC**

Biên độ \+/-7% (HOSE) và \+/-10% (HNX) tạo ra các rào cản kỹ thuật cứng.16 Thuật toán cần tích hợp logic "Ceiling/Floor Magnet":

* Nếu một mã cổ phiếu duy trì trạng thái dư mua trần (Ceiling) với khối lượng lớn hơn 3 lần trung bình 10 phiên, hệ thuật toán sẽ khuyến nghị nắm giữ và dịch chuyển mục tiêu lợi nhuận lên cao hơn, thay vì bán ra tại mốc 15%.22  
* Trong các phiên định kỳ ATO/ATC, thuật toán sử dụng dữ liệu từ /le-table để phân tích các lệnh ảo và lệnh thực.6 Sự xuất hiện của các lệnh mua lớn đột ngột vào 5 phút cuối phiên ATC (thường do các quỹ ETF cơ cấu) sẽ được sử dụng như một chỉ báo xác nhận xu hướng cho phiên kế tiếp.22

## **Thiết kế Thuật toán Khuyến nghị Đầu tư Đa tầng**

Để đảm bảo tỷ lệ thắng (winrate) cao cho mục tiêu 15%, hệ thống kết hợp ba lớp phân tích: Nhận diện chế độ thị trường (HMM), Sàng lọc sức mạnh tương đối (Mansfield RS) và Xác nhận điểm vào lệnh (Wyckoff).3

### **Lớp 1: Nhận diện Chế độ Thị trường bằng Hidden Markov Model (HMM)**

Thị trường chứng khoán không phải là một hệ thống tĩnh mà luôn chuyển động giữa các trạng thái có tính chất thống kê khác nhau.5 Sử dụng mô hình Hidden Markov với các tham số đầu vào bao gồm lợi nhuận logarit (Log Returns), độ biến động (Volatility) và khối lượng giao dịch, thuật toán sẽ phân loại VN-Index vào 3 chế độ 5:

1. **Trạng thái Bullish (Thị trường bò):** Đặc trưng bởi lợi nhuận dương ổn định và biến động thấp. Thuật toán kích hoạt chiến lược bứt phá (Breakout) với tỷ trọng vốn cao.26  
2. **Trạng thái Volatile/Sideways (Biến động/Đi ngang):** Đặc trưng bởi các cú sốc giá không rõ xu hướng. Thuật toán chuyển sang chiến lược Mean Reversion (Đảo chiều về mức trung bình) và thu hẹp mục tiêu lợi nhuận.26  
3. **Trạng thái Bearish/Crash (Thị trường gấu):** Đặc trưng bởi lợi nhuận âm và biến động cực cao. Thuật toán phát tín hiệu phòng vệ, nâng tỷ lệ tiền mặt và chỉ giải ngân tại các điểm "Selling Climax" theo Wyckoff.26

Công thức xác suất chuyển trạng thái trong HMM được biểu diễn dưới dạng:

![][image1]  
Trong đó ![][image2] là ma trận chuyển trạng thái được huấn luyện từ dữ liệu lịch sử VN-Index giai đoạn 2012-2025.5

### **Lớp 2: Sàng lọc Siêu cổ phiếu bằng Mansfield Relative Strength (RSM)**

Mục tiêu 15% đòi hỏi việc lựa chọn các cổ phiếu có tốc độ tăng trưởng nhanh hơn chỉ số chung. Chỉ báo Mansfield RS giúp chuẩn hóa sức mạnh của cổ phiếu so với VN-Index thành một dao động quanh trục 0\.4

Công thức tính toán RSM:

![][image3]  
![][image4]  
Thuật toán sẽ chỉ quét các mã có RSM \> 0 và đường RSM đang dốc lên.28 Điều này đảm bảo rằng ngay cả khi thị trường đi ngang, cổ phiếu được khuyến nghị vẫn có nội lực để bứt phá. Phân tích từ log cho thấy các mã như FPT, ACB, CMG thường xuyên duy trì RSM dương trong các giai đoạn tăng trưởng mạnh.6

### **Lớp 3: Xác nhận Điểm vào lệnh với Phương pháp Wyckoff và Mẫu hình Spring**

Sự kiện "Spring" (Cú bật lò xo) trong lý thuyết Wyckoff là điểm kích hoạt lệnh mua có rủi ro thấp nhất và tiềm năng lợi nhuận cao nhất.3 Thuật toán tự động nhận dạng mẫu hình này dựa trên các tiêu chí:

* **Penetration (Sự xuyên thấu):** Giá phá vỡ ngưỡng hỗ trợ đi ngang từ 0.5% đến 5%. Nếu xuyên sâu hơn 7%, mẫu hình bị loại bỏ vì có nguy cơ gãy xu hướng.31  
* **Volume Confirmation:** Khối lượng tại điểm Spring thấp (Spring \#3) cho thấy cung cạn kiệt, hoặc khối lượng cao nhưng giá phục hồi nhanh (Spring \#2) cho thấy cầu áp đảo.31  
* **Recovery:** Giá đóng cửa trở lại bên trong vùng tích lũy (Trading Range) trong vòng tối đa 5 phiên.31

Khi tín hiệu "Sign of Strength" (SOS) xuất hiện sau Spring — biểu hiện qua các phiên tăng giá mạnh với khối lượng bùng nổ vượt kháng cự — thuật toán sẽ phát lệnh khuyến nghị mua chính thức.33

## **Tối ưu hóa Tham số và Mô phỏng Backtesting**

Hiệu quả của các chỉ báo kỹ thuật phụ thuộc vào việc tìm ra bộ tham số "vàng" phù hợp với đặc tính của thị trường Việt Nam. Thuật toán sử dụng Tối ưu hóa bầy đàn (Particle Swarm Optimization \- PSO) để tinh chỉnh các tham số đầu vào cho RSI, MACD và Bollinger Bands.35

| Tham số | Phạm vi Tìm kiếm | Ý nghĩa |
| :---- | :---- | :---- |
| **![][image5]** (RSI Lookback) | 7 \- 21 | Cân bằng giữa độ nhạy và tín hiệu nhiễu |
| ![][image6] (RSI Oversold) | 20 \- 40 | Xác định vùng kiệt sức của phe bán |
| ![][image7] (RSM MA) | 52 \- 200 | Tùy biến theo chu kỳ đồ thị Tuần hoặc Ngày |
| ![][image8] (HMM Sensitivity) | 0.01 \- 1.0 | Tốc độ phản ứng với sự thay đổi của Regime |

Bảng 2: Các tham số cần tối ưu hóa bằng thuật toán PSO.35

Kết quả thực nghiệm trên dữ liệu VN-Index từ 2018-2024 cho thấy phương pháp PSO vượt trội hơn các cách tiếp cận truyền thống, mang lại lợi nhuận trung bình 19.9% trong giai đoạn huấn luyện và duy trì được 10.58% trong giai đoạn kiểm thử mù (out-of-sample), phù hợp với mục tiêu 15% đề ra khi kết hợp thêm các bộ lọc cấu trúc.35

## **Hệ thống Natural Language Generation (NLG) cho Báo cáo Khuyến nghị**

Để nâng cao trải nghiệm người dùng, đặc biệt là các nhà đầu tư cá nhân mới (F0), hệ thống cần chuyển đổi các tín hiệu số khô khan thành các báo cáo tiếng Việt mạch lạc.37

### **Ứng dụng PhoBERT trong Phân tích Tâm lý và Tóm tắt**

Hệ thống sử dụng mô hình PhoBERT — kiến trúc transformer được tối ưu riêng cho ngôn ngữ tiếng Việt — để phân tích dữ liệu tin tức từ các nguồn CafeF, Vietstock và dữ liệu doanh nghiệp từ SSI API.39

* **Sentiment Analysis:** Tin tức được phân loại thành Tích cực, Tiêu cực hoặc Trung lập với độ chính xác \>81%.39 Các tin tức tiêu cực về lãnh đạo hoặc pháp lý sẽ kích hoạt bộ lọc rủi ro, tự động hạ điểm khuyến nghị bất chấp các tín hiệu kỹ thuật đẹp.21  
* **Tự động sinh báo cáo:** Dựa trên các template chuyên gia, hệ thống NLG sẽ tổng hợp dữ liệu. Ví dụ: "Dựa trên mô hình Wyckoff, cổ phiếu đã hoàn tất giai đoạn Spring với khối lượng cạn kiệt, đồng thời chỉ số Mansfield RS cho thấy sức mạnh vượt trội so với VN-Index. Khuyến nghị giải ngân tại vùng giá \[Price\] với mục tiêu lợi nhuận 15% trong chu kỳ T+10".38

### **Kiến trúc Kỹ thuật của Module NLG**

Module NLG được thiết kế theo cấu trúc ba lớp:

1. **Lớp Phân tích Dữ liệu (Data Analysis Layer):** Tiếp nhận kết quả từ thuật toán định lượng và điểm số tâm lý từ PhoBERT.43  
2. **Lớp Quy hoạch Văn bản (Text Planning Layer):** Xác định cấu trúc báo cáo, bao gồm luận điểm đầu tư, phân tích kỹ thuật, đánh giá rủi ro và hướng dẫn thực thi.38  
3. **Lớp Hiện thực hóa Ngôn ngữ (Linguistic Realization Layer):** Sử dụng các mô hình ngôn ngữ lớn để tạo ra văn phong chuyên nghiệp, phù hợp với tiêu chuẩn ngành tài chính.37

## **Đề xuất Triển khai Hệ thống và Quản trị Rủi ro**

Việc thực thi một thuật toán khuyến nghị T+ cần một hạ tầng backend mạnh mẽ để xử lý dữ liệu song song và đảm bảo tính ổn định của kết nối.44

### **Tech Stack Khuyến nghị**

Hệ thống nên được xây dựng trên ngôn ngữ Python do sự phong phú của các thư viện tài chính như pandas, numpy, ta-lib cho tính toán chỉ báo và hmmlearn cho mô hình Markov.46

* **Backend:** FastAPI hoặc Flask để cung cấp các endpoint cho ứng dụng frontend.48  
* **Database:** PostgreSQL cho dữ liệu cấu trúc và InfluxDB cho dữ liệu chuỗi thời gian (time-series).44  
* **Containerization:** Docker để đảm bảo môi trường thực thi đồng nhất giữa phát triển và vận hành.49

### **Cơ chế Quản trị Rủi ro Tự động**

Một thuật toán thông minh không chỉ tìm kiếm lợi nhuận mà còn phải biết cách bảo vệ vốn. Hệ thống tích hợp các lệnh điều kiện (Conditional Orders) có sẵn trong SSI iBoard 22:

* **Trailing Stop:** Tự động nâng mức chặn lãi khi cổ phiếu tiến gần đến mục tiêu 15%, giúp tối ưu hóa lợi nhuận trong các sóng tăng mạnh.23  
* **Volatility-Adjusted Position Sizing:** Tự động giảm tỷ trọng giải ngân khi chỉ số biến động (như ATR) tăng cao hoặc mô hình HMM dự báo thị trường sắp chuyển sang trạng thái Bearish.21  
* **Liquidity Filter:** Chỉ khuyến nghị các mã có khối lượng giao dịch trung bình 10 phiên trên 500,000 đơn vị để đảm bảo khả năng thoát hàng trong chu kỳ T+.21

## **Kết luận và Lộ trình Phát triển**

Đề xuất xây dựng tính năng khuyến nghị đầu tư T+ mục tiêu lợi nhuận 15% dựa trên hệ sinh thái dữ liệu SSI iBoard là một giải pháp Fintech toàn diện, kết hợp giữa chiều sâu lý thuyết và khả năng thực thi thực tế. Bằng việc giải mã thành công các patterns trong HAR logs và tích hợp sâu sắc các yếu tố cấu trúc của thị trường Việt Nam như chu kỳ T+2.5 và giới hạn FOL, hệ thống sẽ tạo ra lợi thế cạnh tranh đáng kể cho người dùng.6

Các bước thực hiện tiếp theo bao gồm:

1. **Giai đoạn 1:** Hoàn thiện pipeline fetch dữ liệu thời gian thực qua FastConnect và xây dựng kho lưu trữ dữ liệu lịch sử.52  
2. **Giai đoạn 2:** Huấn luyện và kiểm thử mô hình HMM kết hợp Wyckoff trên các nhóm ngành dẫn dắt như Ngân hàng, Thép và Công nghệ.53  
3. **Giai đoạn 3:** Tích hợp module NLG tiếng Việt và PhoBERT để cá nhân hóa báo cáo khuyến nghị cho từng phân khúc khách hàng.37  
4. **Giai đoạn 4:** Triển khai thử nghiệm (Paper Trading) để tinh chỉnh các tham số PSO trước khi đưa vào vận hành chính thức.35

Sự kết hợp giữa công nghệ dữ liệu, mô hình toán học và hiểu biết sâu sắc về tâm lý thị trường nội địa chính là chìa khóa để hiện thực hóa các mục tiêu lợi nhuận bền vững trong một thị trường đầy tiềm năng nhưng cũng không ít thách thức như Việt Nam.56

#### **Works cited**

1. Vietnam Ho Chi Minh Stock Index \- Quote \- Chart \- Historical Data \- Trading Economics, accessed March 28, 2026, [https://tradingeconomics.com/vietnam/stock-market](https://tradingeconomics.com/vietnam/stock-market)  
2. Vietnam approves stock market development strategy, accessed March 28, 2026, [https://vietnamlawmagazine.vn/vietnam-approves-stock-market-development-strategy-71042.html](https://vietnamlawmagazine.vn/vietnam-approves-stock-market-development-strategy-71042.html)  
3. The Wyckoff Pattern Springs Setup Trading Strategy That Works \- Traders Mastermind, accessed March 28, 2026, [https://tradersmastermind.com/wyckoff-pattern-springs-setup/](https://tradersmastermind.com/wyckoff-pattern-springs-setup/)  
4. New Indicators Added: Dorsey and Mansfield Relative Strength | TrendSpider Blog, accessed March 28, 2026, [https://trendspider.com/blog/new-indicators-added-dorsey-and-mansfield-relative-strength/](https://trendspider.com/blog/new-indicators-added-dorsey-and-mansfield-relative-strength/)  
5. Market Regime Detection Using Hidden Markov Models \- QuestDB, accessed March 28, 2026, [https://questdb.com/glossary/market-regime-detection-using-hidden-markov-models/](https://questdb.com/glossary/market-regime-detection-using-hidden-markov-models/)  
6. SSI\_HARrequestLogs.txt  
7. General Information \- FastConnect API \- SSI, accessed March 28, 2026, [https://guide.ssi.com.vn/ssi-products/general-information](https://guide.ssi.com.vn/ssi-products/general-information)  
8. Service registration \- FastConnect API \- SSI, accessed March 28, 2026, [https://guide.ssi.com.vn/ssi-products/service-registration](https://guide.ssi.com.vn/ssi-products/service-registration)  
9. Connection guide | FastConnect API \- SSI, accessed March 28, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-trading/connection-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-trading/connection-guide)  
10. SSI-Securities-Corporation/python-fcdata \- GitHub, accessed March 28, 2026, [https://github.com/SSI-Securities-Corporation/python-fcdata](https://github.com/SSI-Securities-Corporation/python-fcdata)  
11. Sample client guide | FastConnect API \- SSI, accessed March 28, 2026, [https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide)  
12. Real-Time Data API via Websockets: US Stocks, Forex pairs, Digital Currencies \- EODHD, accessed March 28, 2026, [https://eodhd.com/financial-apis/new-real-time-data-api-websockets](https://eodhd.com/financial-apis/new-real-time-data-api-websockets)  
13. Real-Time Stock Market Data: How WebSocket Feeds Keep You Ahead | Finage Blog, accessed March 28, 2026, [https://finage.co.uk/blog/realtime-stock-market-data-how-websocket-feeds-keep-you-ahead--68226010937e360d4b16c4e7](https://finage.co.uk/blog/realtime-stock-market-data-how-websocket-feeds-keep-you-ahead--68226010937e360d4b16c4e7)  
14. Ssi.py \- gists · GitHub, accessed March 28, 2026, [https://gist.github.com/Kingkha/0fef4306652e84e5d00812815e485f79](https://gist.github.com/Kingkha/0fef4306652e84e5d00812815e485f79)  
15. Kiến thức cơ bản về chứng khoán nhà đầu tư nhất định phải biết \- Vietcap, accessed March 28, 2026, [https://www.vietcap.com.vn/kien-thuc/kien-thuc-co-ban-ve-chung-khoan-nha-dau-tu-nhat-dinh-phai-biet](https://www.vietcap.com.vn/kien-thuc/kien-thuc-co-ban-ve-chung-khoan-nha-dau-tu-nhat-dinh-phai-biet)  
16. Understanding Vietnam's Stock Market Regulations for Foreign Investors, accessed March 28, 2026, [https://globalreferral.group/understanding-vietnams-stock-market-regulations-for-foreign-investors/](https://globalreferral.group/understanding-vietnams-stock-market-regulations-for-foreign-investors/)  
17. Economist's Note Understanding Vietnam's Foreign Ownership Limits (FOLs) \- VinaCapital, accessed March 28, 2026, [https://vinacapital.com/wp-content/uploads/2022/08/VinaCapital-Insights-Understanding-Vietnams-Foreign-Ownership-Limits-FOLs.pdf](https://vinacapital.com/wp-content/uploads/2022/08/VinaCapital-Insights-Understanding-Vietnams-Foreign-Ownership-Limits-FOLs.pdf)  
18. \[SS5\] Thời gian chờ bán chứng khoán \- Ngày thanh toán T+0, T+2, T+2.5 là gì?, accessed March 28, 2026, [https://finpro.com.vn/blogs/kien-thuc-chung-khoan/ss5-tho-i-gian-cho-ba-n-chu-ng-khoa-n-ngay-thanh-toan-t-0-t-2-t](https://finpro.com.vn/blogs/kien-thuc-chung-khoan/ss5-tho-i-gian-cho-ba-n-chu-ng-khoa-n-ngay-thanh-toan-t-0-t-2-t)  
19. Bất cập trong giao dịch T+2.5 và một số lưu ý cần nhớ \- 24HMoney, accessed March 28, 2026, [https://24hmoney.vn/news/bat-cap-trong-giao-dich-t-2-5-va-mot-so-luu-y-can-nho-c30a1605191.html](https://24hmoney.vn/news/bat-cap-trong-giao-dich-t-2-5-va-mot-so-luu-y-can-nho-c30a1605191.html)  
20. INSANE Risk-to-Reward With This Afternoon Trading Setup \- YouTube, accessed March 28, 2026, [https://www.youtube.com/watch?v=aKAPzd4EeFU](https://www.youtube.com/watch?v=aKAPzd4EeFU)  
21. AI-Powered Stock Forecasting Model in Vietnam \- Fundopedia, accessed March 28, 2026, [https://chenjiazizhong.com/2025/03/26/ai-powered-stock-forecasting-model-in-vietnam/](https://chenjiazizhong.com/2025/03/26/ai-powered-stock-forecasting-model-in-vietnam/)  
22. SSI Web Trading for equity market user guide, accessed March 28, 2026, [https://www.ssi.com.vn/en/individual-customer/ssi-web-trading-for-equity-market-user-guide?page=2](https://www.ssi.com.vn/en/individual-customer/ssi-web-trading-for-equity-market-user-guide?page=2)  
23. Conditional Orders \- SSI, accessed March 28, 2026, [https://www.ssi.com.vn/en/individual-customer/conditional-orders-ib-app](https://www.ssi.com.vn/en/individual-customer/conditional-orders-ib-app)  
24. Order Entry \- SSI, accessed March 28, 2026, [https://www.ssi.com.vn/en/individual-customer/order-entry-equity-market](https://www.ssi.com.vn/en/individual-customer/order-entry-equity-market)  
25. HMM-Based Market Regime Detection with RL for Portfolio Management, accessed March 28, 2026, [https://www.cloud-conf.net/datasec/2025/proceedings/pdfs/IDS2025-3SVVEmiJ6JbFRviTl4Otnv/966100a067/966100a067.pdf](https://www.cloud-conf.net/datasec/2025/proceedings/pdfs/IDS2025-3SVVEmiJ6JbFRviTl4Otnv/966100a067/966100a067.pdf)  
26. Hidden Markov Model Market Regimes | Trading Indicator \- LuxAlgo, accessed March 28, 2026, [https://www.luxalgo.com/library/indicator/hidden-markov-model-market-regimes/](https://www.luxalgo.com/library/indicator/hidden-markov-model-market-regimes/)  
27. Market Regime Detection using Hidden Markov Models in QSTrader | QuantStart, accessed March 28, 2026, [https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/)  
28. How to create the Mansfield Relative Strength Indicator \- Stage Analysis, accessed March 28, 2026, [https://www.stageanalysis.net/blog/4266/how-to-create-the-mansfield-relative-performance-indicator](https://www.stageanalysis.net/blog/4266/how-to-create-the-mansfield-relative-performance-indicator)  
29. Mansfield RS Indicator | Library of Technical & Fundamental Analysis \- Definedge Securities, accessed March 28, 2026, [https://www.definedgesecurities.com/library/mansfield-rs-indicator/](https://www.definedgesecurities.com/library/mansfield-rs-indicator/)  
30. DAILY MARKET RECAP \- vndirect, accessed March 28, 2026, [https://www.vndirect.com.vn/cmsupload/beta/Vietnam-Daily-Market-Recap-Nov-28-NLG-report.pdf](https://www.vndirect.com.vn/cmsupload/beta/Vietnam-Daily-Market-Recap-Nov-28-NLG-report.pdf)  
31. Wyckoff Spring and Shakeout: The Key Event in Trading, accessed March 28, 2026, [https://tradingwyckoff.com/en/spring-shakeout/](https://tradingwyckoff.com/en/spring-shakeout/)  
32. What Is the Wyckoff Spring Trading Pattern? \- Investing.com, accessed March 28, 2026, [https://www.investing.com/analysis/what-is-the-wyckoff-spring-trading-pattern-200665908](https://www.investing.com/analysis/what-is-the-wyckoff-spring-trading-pattern-200665908)  
33. Wyckoff Method & Chart Patterns Explained: Accumulation, Distribution & Schematics (2026), accessed March 28, 2026, [https://margex.com/en/blog/wyckoff-chart-patterns-explained/](https://margex.com/en/blog/wyckoff-chart-patterns-explained/)  
34. What Is the Wyckoff Trading Method? | Market Pulse \- FXOpen UK, accessed March 28, 2026, [https://fxopen.com/blog/en/the-wyckoff-trading-method/](https://fxopen.com/blog/en/the-wyckoff-trading-method/)  
35. Multi-objective optimization for algorithmic trading in the Vietnamese stock market, accessed March 28, 2026, [https://www.researchgate.net/publication/394351735\_Multi-objective\_optimization\_for\_algorithmic\_trading\_in\_the\_Vietnamese\_stock\_market](https://www.researchgate.net/publication/394351735_Multi-objective_optimization_for_algorithmic_trading_in_the_Vietnamese_stock_market)  
36. Multi-objective optimization for algorithmic trading in the Vietnamese stock market | Nguyen, accessed March 28, 2026, [https://beei.org/index.php/EEI/article/view/9288](https://beei.org/index.php/EEI/article/view/9288)  
37. Transforming Financial Reporting with AI and NLG \- Analytics Vidhya, accessed March 28, 2026, [https://www.analyticsvidhya.com/blog/2024/08/financial-reporting-with-ai/](https://www.analyticsvidhya.com/blog/2024/08/financial-reporting-with-ai/)  
38. (PDF) Comprehensive Review on Natural Language Generation for Automated Report Writing in Finance \- ResearchGate, accessed March 28, 2026, [https://www.researchgate.net/publication/383909320\_Comprehensive\_Review\_on\_Natural\_Language\_Generation\_for\_Automated\_Report\_Writing\_in\_Finance](https://www.researchgate.net/publication/383909320_Comprehensive_Review_on_Natural_Language_Generation_for_Automated_Report_Writing_in_Finance)  
39. Sentiments Extracted from News and Stock Market Reactions in Vietnam \- MDPI, accessed March 28, 2026, [https://www.mdpi.com/2227-7072/11/3/101](https://www.mdpi.com/2227-7072/11/3/101)  
40. Sentiments Extracted from News and Stock Market Reactions in Vietnam, accessed March 28, 2026, [https://ideas.repec.org/a/gam/jijfss/v11y2023i3p101-d1212361.html](https://ideas.repec.org/a/gam/jijfss/v11y2023i3p101-d1212361.html)  
41. VN-Index loses over 51 points on rising selling force \- Vietnam News, accessed March 28, 2026, [https://vietnamnews.vn/economy/1777791/vn-index-loses-over-51-points-on-rising-selling-force.html](https://vietnamnews.vn/economy/1777791/vn-index-loses-over-51-points-on-rising-selling-force.html)  
42. Rating Report Automation based on Natural Language Generation \- CARE Analytics and Advisory Private Limited, accessed March 28, 2026, [https://caapl.in/casestudy/rating-report-automation-based-on-natural-language-generation/](https://caapl.in/casestudy/rating-report-automation-based-on-natural-language-generation/)  
43. Impact of LLMs news Sentiment Analysis on Stock Price Movement Prediction \- arXiv, accessed March 28, 2026, [https://arxiv.org/html/2602.00086v2](https://arxiv.org/html/2602.00086v2)  
44. Day 6: Building a Real-Time Stock Data Pipeline — Architecture Overview | by A V \- Medium, accessed March 28, 2026, [https://medium.com/@anjalivemuri97/day-6-building-a-real-time-stock-data-pipeline-architecture-overview-cbdb5af82294](https://medium.com/@anjalivemuri97/day-6-building-a-real-time-stock-data-pipeline-architecture-overview-cbdb5af82294)  
45. Automated Trading Systems: Architecture, Protocols, Types of Latency – Part I, accessed March 28, 2026, [https://www.interactivebrokers.com/campus/ibkr-quant-news/automated-trading-systems-architecture-protocols-types-of-latency-part-i/](https://www.interactivebrokers.com/campus/ibkr-quant-news/automated-trading-systems-architecture-protocols-types-of-latency-part-i/)  
46. Python for Algorithmic Trading: Essential Libraries \- LuxAlgo, accessed March 28, 2026, [https://www.luxalgo.com/blog/python-for-algorithmic-trading-essential-libraries/](https://www.luxalgo.com/blog/python-for-algorithmic-trading-essential-libraries/)  
47. Python Libraries Essential for Algorithmic Trading – Blog \- BlueChip Algos, accessed March 28, 2026, [https://bluechipalgos.com/blog/python-libraries-essential-for-algorithmic-trading/](https://bluechipalgos.com/blog/python-libraries-essential-for-algorithmic-trading/)  
48. Building an Automated Technical Stock Analysis Dashboard with Python & Streamlit, accessed March 28, 2026, [https://medium.com/@aachasan18/building-an-automated-technical-stock-analysis-dashboard-with-python-streamlit-f8fa1863484b](https://medium.com/@aachasan18/building-an-automated-technical-stock-analysis-dashboard-with-python-streamlit-f8fa1863484b)  
49. lacchain/ssi-api \- GitHub, accessed March 28, 2026, [https://github.com/lacchain/ssi-api](https://github.com/lacchain/ssi-api)  
50. Trading strategy template that uses the Python backtesting library \- GitHub, accessed March 28, 2026, [https://github.com/s-kust/python-backtesting-template](https://github.com/s-kust/python-backtesting-template)  
51. (PDF) VN30 Index: An Overview and Default Probability Analysis \- ResearchGate, accessed March 28, 2026, [https://www.researchgate.net/publication/270219689\_VN30\_Index\_An\_Overview\_and\_Default\_Probability\_Analysis](https://www.researchgate.net/publication/270219689_VN30_Index_An_Overview_and_Default_Probability_Analysis)  
52. Fast Connect API \- SSI, accessed March 28, 2026, [https://www.ssi.com.vn/en/individual-customer/fast-connect-api](https://www.ssi.com.vn/en/individual-customer/fast-connect-api)  
53. Stock Market Outlook for 2026: "The Era of Growth – The Great Wave of Transformation", accessed March 28, 2026, [https://bidvinfo.com.vn/en/stock-market-outlook-for-2026-the-era-of-growth-the-great-wave-of-transformation-10013749.html](https://bidvinfo.com.vn/en/stock-market-outlook-for-2026-the-era-of-growth-the-great-wave-of-transformation-10013749.html)  
54. Market Regime using Hidden Markov Model \- QuantInsti Blog, accessed March 28, 2026, [https://blog.quantinsti.com/regime-adaptive-trading-python/](https://blog.quantinsti.com/regime-adaptive-trading-python/)  
55. How to Backtest for Beginners \- What I have learned on my journey to profitability \- Reddit, accessed March 28, 2026, [https://www.reddit.com/r/Daytrading/comments/1482ugy/how\_to\_backtest\_for\_beginners\_what\_i\_have\_learned/](https://www.reddit.com/r/Daytrading/comments/1482ugy/how_to_backtest_for_beginners_what_i_have_learned/)  
56. Monthly Market Outlook \- SSI, accessed March 28, 2026, [https://www.ssi.com.vn/en/organization-customer/monthly-market-outlook](https://www.ssi.com.vn/en/organization-customer/monthly-market-outlook)  
57. Vietnam Stock Recommendation For Long-Term Investors \- AQUIS Capital, accessed March 28, 2026, [https://aquis-capital.com/news/fundamental-insights-vietnam-stock-recommendation-in-a-global-framework](https://aquis-capital.com/news/fundamental-insights-vietnam-stock-recommendation-in-a-global-framework)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAABdklEQVR4XoVUsUpEMRDcIMKJgoggaG1jKbbaaWFhrX+g9TV+gL9xYC1iYW9xneBVFn6A11iJIF514DmbzSbZJO85x2STmc0meQlHjgLQccw0DOSfKnlsgAv8j1ahrolme7nRB9070QDczPdlarRVFdwtmgnihpFjL6yiWuato1mAn+Be4ZlQwKtX4C84w+jA+h7tqcAunFfEbycFjhu56TZl5HEEPmOwhfhGsvXLmFQW8cdO535A7zyoY/KT3bXNNkgzgUdwJQhPJCuPQpa0MVeXlfYGcQdxm4T36C9gcJFVnVKflGgf/ACnkKY+Ev2QrDxG1pomGuCjLSPcocfXEzSPIcnkd5KdVMBXdRMkn5QGcMbbRpzhUOauuTjeLb2AX+AhEgbZMXg3FxjNEedOCi2pyU+Onx5fBVdn8jYVQ9QJXvRP07eKEMkYjayo1V5QOOSs0Clao05z+iRqow/Rjf8LZX7PWLplgsKFol2FPZpiQlyhJ+8PFDAyYkqdsGwAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,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>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAZCAYAAADXPsWXAAABkklEQVR4Xo1TsS5FQRCdjSeRiIRItCLRaDSikChJKAidP/ABryCioNJTKEUvURGlhEZ8yysJEe85szO7O7t7740T587MmTN7Z+8LIkc5tOaQWiGz5q7cOZH0lHq8VvI8L2qpbDedl6BqbFp384RHR8vAuHxa1g2xzAPCfFpUlewAa4hgsVYLtBhYDifHZ2q1jQmy1UrRKlFzfTwuwF/k+4j3aO0hHotGy/C+oneK/E613TDNWACfwB0MjhC/KO0+hecL+IZ8Uf2r4CfqWynFeoBwhXhCcsi1mhkz4Du4aS6yDv7EQ7Qxr3zwTTEp3BI4gI83EoXoiORlHOPKpD/dkOS+PdF891IHEhwNQN6Ot6wwQvPQ1OEqPCSQl/GhZ6psa/SYIH8VV1wFB/gPG1ebBL/BNdQ9xI3kJ1oBb8KrFOfgEMKWr8LlHX0gPoLPwRgwBo4XGrZzsxTGE6bBOZIZi9IXUOrx49SShdWa/t+yfp7xI58o5+u6VDrQac2aDVe1kGVbmk34v7XDWX8dA9OQ1Pm/P9gRLmyVW2WLAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACsAAAAZCAYAAACo79dmAAADLElEQVR4XtVXTYhOURh+T0xRmBmmJDaaUpKfmpSRpY2/DSk1YSGmbJRCyYqmLFiQUlKiLPwsbJRiMWWpZIOF1CgpydigJPE85z3n3nPOvfd89zbfxlPPnHvev/Oe97z33G9EWsCkgo4I/eNYHSLnTRNto3GjIkZLs/8KjXuKFMXEiOGzyThKXtcdraNZw4UYj2O8AV6J9Ql6xc3pczqPoGihMC3sBIa/4N1QXqDNQm3QEKcqrkpC3BJNdtILquaUVKWKUt5k4dGsTzXpvIB5jT8/wLFUU6LRuUB6XDEqAolkPdShhIm+AIfrLLIozBM/TjuGakYZiE9sgVk8PMV4FPwO8enCwsG6NCXn0SDuF0ZEk70EDoguxxftF5W6dpDBXJPp4u9sw/psw/AcXOxlwG3RDSwAT4HPwOlAX4u48u1RuvRyNjIJk6uBhAk+hpzJ0nsZ+MDKHCohK4IAOV0LhO5sAd4EawMZK/0bVnzpiI3gF3A7J/Vr10sjmDZWeYsV4Aext0CBKdEWuO/m/GB8BFcVFooD4GHRzRBLwP1SXn/zwA1u3AWucXKvOwHuFvsFtTgmWhC+N1yTuUUYxo8BXlmLAtk70UquE90qPxhsC7aHLxA/z0xqVLSfl4PXRRd7QztgXLhJY9Zj/Cb6HhCbwFeim+dmL7qY+8CXolcoX/ZHoi0ZYVA02D3ws8QVYEKz4loAWC1aZVZfYeQk/m4B54PXwCfu+aHoRok9ol/Hy+BP0areAW+CS0Wryfbj+mNGK689UdMZQ5Cy7LbCgZ7HMQPJSjffAf6RMnmtvLG9z+q+FU2Kz+/BCRfroOjGeQq8eUbhwwRDnJHiw+ThvO1Qk3UCbQF9EXeKJvJV3AsJd25ixtkyGVZ9c/LMnrwADhq9/nw7pPAn0TurBkyDZ0WP6IhoH34STYZHdU60WlwiSNDsFW0fyuh7yNpoGzAptgmxFTwvGsuehJMXYOZts6cd79m00TkfiMKUJ8ZW8oohUzWiiDGZYIjwoyTJr9h+Ixc8p0sR27b0VLOWxgW62XezDpA6lnP7f9mc0ZcgHj2CJepgK4E0h7wdtaFFav0PNTBk7oDv068AAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAZCAYAAAAFbs/PAAABM0lEQVR4XqWTvUpDQRCFZzGCICKWVsFSECxsU9pG9A3s0toIYuUTSMDCTl/AVrBPE7TyEaxFbAUx+u3OrneyO5jCwz13Zs783uJKEEWx1vNChSt6Q+rCFIdGduFNcxtbcUFDQZvMSpuQ6pu8DaarqjGBlzOwsfp5g9MQ3VN4Cb8Ij7A38JDEmWpy3ZWLbMEHOKT1G/sBj/PINTiBL7/V4ACO4TmkIcRpvZigZQPzJLHB3NfH9rH38BNxYM7dJveGFrcYhPTMeN3hpelgRXTIDG3fVEvZFO8fdaHswHeCKXYde4Jd1VRI0zhHBiokjEIcEuQin3CVKjP24G0RVA27vF4JHvGfu1KtWCJeLoGxcfNmsmbU36hrqk3/QdVdTmqHtsoc5j6x+jDPc7Dg1yxoi/w/7gc/hCKCpUEWKwAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAZCAYAAADnstS2AAABHUlEQVR4XoVSO25CMRD0CiGBSB1KhJSegioFZS6Qc6SiyQlyBkSaCHpEA106bpAiJ+ACnICMvR/vvvcgI8aenV2v10BKCtItCwlsN+0NwS3fg6y73GCXkOa0wg3Q2bTTbOOfspq2m+IYmnbaeZ0yNGgNcCNu2h4j8IpvBMw7qOBTW7Cfo7x8EtEB+xLxGvkL9JOUD+EtRKcX8JelPXsCvrNDz1iHUptWSL/arHXYPfiAcGOOf30u5N+xYAd+g2+au4fc8QxOned6xdMbxF/8l+FPo8AdTHRCMBOblzqzK+P1B8vY/Hq9KjnN4REcxDYB2oUGkB/dZfUKDebgY3FCLkgZI6VeiYo2z6FkWq57guZCTe4UDzXTroOasV/GH/lmFVb070afAAAAAElFTkSuQmCC>