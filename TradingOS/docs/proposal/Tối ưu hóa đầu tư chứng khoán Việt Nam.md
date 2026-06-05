# **Hệ thống Giao dịch Chiến lược (Trading OS): Phân tích và Hóa giải các Mâu thuẫn giữa các Phương pháp Đầu tư Kinh điển trong bối cảnh Đặc thù Thị trường Chứng khoán Việt Nam giai đoạn 2025-2026**

Thị trường chứng khoán Việt Nam đang trải qua một giai đoạn chuyển mình mang tính bước ngoặt, được đánh dấu bởi sự vận hành của hệ thống KRX vào tháng 5 năm 2025 và triển vọng nâng hạng lên thị trường mới nổi (Emerging Market) từ FTSE Russell vào tháng 9 năm 2026\.1 Trong bối cảnh hạ tầng tài chính quốc gia được hiện đại hóa và dòng vốn ngoại dự kiến đổ vào lên tới hàng tỷ USD, các phương pháp đầu tư kinh điển của William O'Neil (CANSLIM), Mark Minervini (VCP), và Richard Wyckoff đòi hỏi một sự tái thẩm định và hiệu chỉnh sâu sắc để tương thích với những đặc thù nội tại của thị trường nội địa, đặc biệt là chu kỳ thanh toán T+2.5 và cơ chế biên độ sàn/trần chặt chẽ.4 Việc xây dựng một hệ điều hành giao dịch (Trading OS) tối ưu không chỉ dừng lại ở việc áp dụng các chỉ báo kỹ thuật, mà còn phải hóa giải các nghịch lý lý thuyết thông qua việc định lượng hóa các tham số và tích hợp các mô hình xác suất nâng cao như Hidden Markov Model (HMM) hay mô phỏng Monte Carlo để quản trị rủi ro và tối đa hóa lợi nhuận trong một môi trường đầy biến động.6

## **Bối cảnh Vĩ mô và Động lực của Chu kỳ Markup 2025-2026**

Dữ liệu thực tế cho thấy VN-Index đã thiết lập mức đỉnh lịch sử mới trên 1.800 điểm vào cuối năm 2025, phản ánh sự phục hồi mạnh mẽ của nền kinh tế và các cải cách chính sách quyết liệt.2 Các báo cáo chiến lược từ những định chế tài chính hàng đầu như JP Morgan, SSI Research và Vietcap Securities đều đưa ra các kịch bản lạc quan cho năm 2026, với mục tiêu VN-Index có thể chạm ngưỡng 2.000 đến 2.300 điểm.10 Sự hưng phấn này không dựa trên sự kỳ vọng thuần túy mà được củng cố bởi các yếu tố nền tảng vững chắc như tốc độ tăng trưởng EPS của các doanh nghiệp niêm yết dự báo đạt 14.5% \- 26.7%, trong khi tỷ lệ P/E dự phóng cho năm 2026 ở mức 12.5x \- 13.9x, vẫn thấp hơn đáng kể so với mức trung bình 10 năm là 14.0x.9

| Chỉ số Dự báo | Kịch bản Cơ sở (Baseline) | Kịch bản Lạc quan (Optimistic) | Ý nghĩa đối với Trading OS |
| :---- | :---- | :---- | :---- |
| Mục tiêu VN-Index | 1,920 \- 2,099 10 | 2,120 \- 2,300 11 | Xác nhận giai đoạn Markup của Wyckoff 5 |
| Tăng trưởng EPS | 18.0% \- 19.0% 1 | \> 25.0% 12 | Phù hợp tiêu chí "A" CANSLIM 5 |
| P/E Forward | 13.5x \- 14.0x 9 | 12.5x \- 12.7x 9 | Không gian cho việc tái định giá (Re-rating) |
| Lãi suất chính sách | 4.5% \- 5.0% 13 | Ổn định quanh 4.5% | Hỗ trợ thanh khoản và chi phí vốn margin 15 |

Đặc biệt, sự chuyển dịch từ cơ chế ký quỹ 100% sang phi tiền ký quỹ (Non-pre-funding) thông qua Thông tư 68/2024 đã tháo gỡ nút thắt lớn nhất cho các nhà đầu tư tổ chức quốc tế.3 Điều này tạo ra một dòng chảy thanh khoản mới, buộc các thuật toán giao dịch phải điều chỉnh để nhận diện đúng dấu chân của các định chế này (Whale Tracking) thay vì chỉ tập trung vào tâm lý bầy đàn của nhà đầu tư cá nhân vốn chiếm ưu thế trong lịch sử.5

## **Phân tích và Hóa giải các Mâu thuẫn trong Phương pháp Đầu tư Kinh điển**

### **Nghịch lý Cắt lỗ 7-8% của O'Neil và Biên độ Sàn/Trần của HOSE**

Trong lý thuyết CANSLIM, William O'Neil khẳng định rằng mọi khoản lỗ 50% đều bắt đầu từ khoản lỗ 10% hoặc 20%, và việc cắt lỗ tuyệt đối tại mức 7-8% là quy tắc "bảo hiểm" sống còn.5 Tuy nhiên, tại sàn HOSE, biên độ dao động tối đa trong một phiên là \+/- 7%.4 Một cổ phiếu có thể mở cửa tại giá tham chiếu và đóng cửa tại mức giá sàn trong tích tắc nếu xảy ra các sự kiện tin tức cực đoan hoặc áp lực giải chấp. Trong tình huống "lock sàn" (mất thanh khoản bên mua), nhà đầu tư không thể thực hiện lệnh cắt lỗ tại mức 7% như lý thuyết, dẫn đến hiện tượng trượt giá (slippage) nghiêm trọng khi cổ phiếu có thể tiếp tục giảm sàn trong nhiều phiên kế tiếp.

Để hóa giải mâu thuẫn này, Trading OS không sử dụng một tỷ lệ cắt lỗ cố định (fixed percentage) mà chuyển sang cơ chế dừng lỗ động dựa trên biến động thực tế (Average True Range \- ATR). Bằng cách thiết lập điểm dừng lỗ tại ngưỡng ![][image1] với ![][image2] dao động từ 1.5 đến 2.0, hệ thống cho phép vị thế có đủ "không gian thở" trước các biến động nhiễu của thị trường.5 Khi một cổ phiếu biến động vượt quá 2 lần ATR, đó là tín hiệu xác nhận một sự thay đổi hành vi giá (Change of Character) thay vì chỉ là một đợt điều chỉnh kỹ thuật thông thường. Điều này giúp nhà đầu tư thoát vị thế ngay khi có dấu hiệu bất thường, trước khi cổ phiếu rơi vào trạng thái mất thanh khoản tại giá sàn.

### **Mâu thuẫn giữa Điểm mua Breakout và Chu kỳ Thanh toán T+2.5**

Mark Minervini và William O'Neil đều ưa thích việc mua vào khi giá vượt qua các điểm Pivot hoặc thoát khỏi nền giá tích lũy với khối lượng lớn.5 Tại thị trường Mỹ, với cơ chế T+0 hoặc T+1, việc quản trị vị thế sau breakout diễn ra rất linh hoạt. Tuy nhiên, tại Việt Nam, chu kỳ T+2.5 tạo ra một "điểm mù" về rủi ro. Cụ thể, lượng hàng mua tại ngày T+0 sẽ về tài khoản vào trưa ngày T+2 và có thể giao dịch vào phiên chiều (sau 13:00).5 Điều này dẫn đến một hành vi lặp đi lặp lại trên thị trường nội địa: giá cổ phiếu thường bị đẩy cao (breakout giả) vào phiên sáng khi áp lực cung còn thấp, nhưng sau đó bị bán ngược trở lại vào phiên chiều T+2 do tâm lý chốt lời hoặc cắt lỗ của nhóm nhà đầu tư ngắn hạn.5

Hệ điều hành Trading OS hóa giải vấn đề này bằng cách áp dụng bộ lọc thời gian và khối lượng tích lũy. Thay vì mua đuổi ngay khi giá vượt Pivot vào phiên sáng, thuật toán sẽ kiểm tra tỷ lệ khối lượng tích lũy so với trung bình (Volume % Change) tại các mốc 10:30 và 14:00.5 Điểm giải ngân tối ưu được chia làm hai phần: 50% vị thế tại điểm Pivot ban đầu và 50% còn lại chỉ được thực hiện nếu giá cổ phiếu đóng cửa duy trì trên mức VWAP (Volume Weighted Average Price) của phiên đó và không có hiện tượng rút chân nến (shadow) phía trên quá lớn.5 Cách tiếp cận này biến chu kỳ T+2.5 từ một rủi ro thành một lợi thế xác nhận độ bền của dòng tiền tổ chức.

### **Sự hội tụ giữa Wyckoff-Weis và CANSLIM trong nhận diện Dòng tiền lớn**

Lý thuyết Wyckoff tập trung vào việc đọc biểu đồ và khối lượng để hiểu về cung \- cầu và ý chí của các nhà tạo lập (Composite Man).5 Trong khi đó, CANSLIM chú trọng vào các yếu tố cơ bản như tăng trưởng lợi nhuận (C, A) và sự bảo trợ của tổ chức (I).5 Mâu thuẫn thường nảy sinh khi các yếu tố cơ bản cực tốt nhưng giá cổ phiếu lại đang ở trong giai đoạn Phân phối (Distribution) hoặc Đè giá (Markdown) của Wyckoff do các tổ chức đang âm thầm thoái vốn.5

Giải pháp của Trading OS là tích hợp chỉ báo VWAP và Fair Value Gaps (FVG) làm công cụ kiểm chứng ý đồ tổ chức.5 VWAP đóng vai trò là mỏ neo định giá "công bằng" cho dòng tiền thông minh. Một cổ phiếu đáp ứng các tiêu chuẩn CANSLIM (lợi nhuận tăng trưởng trên 25%, sản phẩm mới đột phá) chỉ được xem là "Buyable" nếu giá đang vận động trong một xu hướng tăng bền vững phía trên đường VWAP tuần và tháng.5 Nếu giá nằm dưới VWAP bất chấp tin tức lợi nhuận tốt, Trading OS sẽ phân loại đây là bẫy phân phối và kích hoạt chế độ quan sát thay vì thực thi lệnh mua.

## **Thiết kế Mô đun Hệ điều hành Trading OS cho Thị trường Việt Nam**

### **Mô đun 1: Nhận diện Trạng thái Thị trường bằng Hidden Markov Model (HMM)**

Thị trường không vận hành theo một quy luật tuyến tính. Việc áp dụng cùng một bộ tham số trong thị trường tăng giá ổn định và thị trường đi ngang biến động cao sẽ dẫn đến hiệu suất kém.22 Trading OS sử dụng mô hình Hidden Markov Model (HMM) để phân loại VN-Index thành ba trạng thái ẩn với các đặc tính thống kê riêng biệt 6:

1. **Chế độ Bò ổn định (Steady Bull):** Đặc trưng bởi lợi nhuận trung bình dương và độ lệch chuẩn (biến động) thấp. Trong chế độ này, Trading OS ưu tiên các tham số Momentum cao và nắm giữ theo trend.24  
2. **Chế độ Gấu biến động (Volatile Bear):** Lợi nhuận âm và biến động cực cao. Hệ thống sẽ tự động chuyển sang vị thế tiền mặt hoặc ưu tiên bán khống (Short) trên thị trường phái sinh VN30F1M để phòng vệ.8  
3. **Chế độ Chuột túi (Sideways/Kangaroo):** Giá dao động trong biên độ không xu hướng, biến động trung bình. Hệ thống áp dụng chiến lược Swing Trading, mua tại các vùng Wyckoff Spring và bán tại các mức Fibonacci Extension.5

Việc xác định trạng thái thị trường dựa trên biến quan sát là tỷ suất sinh lời hàng ngày và độ biến động thực tế trong cửa sổ 10 phiên giúp Trading OS điều chỉnh tỷ lệ đòn bẩy (margin) một cách tự động, nâng tỷ lệ tiền mặt khi xác suất rơi vào chế độ Bearish vượt ngưỡng 60%.7

### **Mô đun 2: Tín hiệu Alpha và Hiệu chỉnh Động lượng RSI**

RSI (Relative Strength Index) thường được sử dụng với các ngưỡng 30 (quá bán) và 70 (quá mua). Tuy nhiên, trong một thị trường đang Markup mạnh mẽ như dự báo năm 2026, các ngưỡng này thường cung cấp tín hiệu sai lệch, khiến nhà đầu tư chốt lời quá sớm hoặc mua quá sớm trong một xu hướng giảm.26 Trading OS áp dụng các ngưỡng động lượng RSI được hiệu chỉnh cho các chu kỳ khác nhau 19:

| Chỉ số | Vùng Mua (Entry Zone) | Vùng Xác nhận (Confirmation) | Chiến lược Thoát (Exit) |
| :---- | :---- | :---- | :---- |
| RSI (Uptrend) | RSI điều chỉnh về 40-50 26 | Vượt lên trên 50 và giữ vững 19 | RSI \> 80 và bắt đầu suy yếu 19 |
| RSI (Downtrend) | Tránh mua khi RSI \< 30 | RSI không vượt được 60 (Kháng cự) 26 | Thoát hoàn toàn nếu RSI thủng 40 26 |
| RSI (T+ Swing) | RSI trong vùng 50-65 5 | Khối lượng tăng đột biến | Chốt lãi khi RSI chạm 70 5 |

Sự kết hợp giữa RSI và MACD Histogram là cốt lõi của tín hiệu Alpha. Trading OS chỉ thực thi lệnh mua khi MACD Histogram chuyển từ âm sang dương hoặc đang trong xu hướng tăng mạnh, đồng thời giá phải nằm trên đường EMA9 và EMA20 để đảm bảo xu hướng ngắn hạn được duy trì.5

### **Mô đun 3: Whale Tracker và Quản trị Giới hạn Sở hữu Nước ngoài (FOL)**

Một đặc thù quan trọng của thị trường Việt Nam là giới hạn sở hữu nước ngoài (FOL). Những cổ phiếu chất lượng cao thường xuyên ở tình trạng "hết room", dẫn đến việc nhà đầu tư ngoại phải mua qua các quỹ ETF hoặc chấp nhận trả mức chênh lệch (premium) cao.32 Khi một cổ phiếu được nới room hoặc được các tổ chức nước ngoài gom mạnh thông qua giao dịch thỏa thuận, đó thường là tiền đề cho một đợt tăng giá Markup khổng lồ.3

Trading OS tích hợp thuật toán Whale Tracker theo dõi các ngưỡng công bố thông tin theo quy định mới 34:

* **Ngưỡng giá trị:** Theo dõi các bên liên quan của người nội bộ thực hiện giao dịch từ 2.000 USD/ngày hoặc 8.000 USD/tháng.34  
* **Ngưỡng sở hữu:** Cảnh báo khi một tổ chức nâng tỷ lệ sở hữu vượt mốc 5% (trở thành cổ đông lớn), vì theo quy định của Luật Chứng khoán Việt Nam, đây là ngưỡng bắt buộc phải công bố thông tin, thường tạo ra hiệu ứng tâm lý tích cực cho dòng tiền cá nhân.4  
* **Phân tích FOL:** Ưu tiên các cổ phiếu có "Quality Sponsorship" từ các quỹ uy tín như Pyn Elite Fund hay Dragon Capital, thay vì các nhóm đầu cơ ngắn hạn.5

## **Đề xuất Bộ Thông số Tối ưu cho Hệ điều hành Trading OS**

Để đạt được hiệu suất vượt trội trên thị trường Việt Nam trong kỷ nguyên KRX và nâng hạng, Trading OS cần được cấu hình với bộ thông số định lượng như sau:

### **1\. Bộ lọc Chọn lọc Cổ phiếu (CANSLIM Hiệu chỉnh)**

* **C (Lợi nhuận quý):** Tăng trưởng quý gần nhất tối thiểu 25% so với cùng kỳ. Đặc biệt ưu tiên các doanh nghiệp có sự tăng trưởng đột biến hơn 50%.5 Cần loại bỏ các khoản thu nhập bất thường từ bán tài sản hoặc định giá lại để phản ánh đúng năng lực cốt lõi.5  
* **A (Lợi nhuận năm):** Tăng trưởng 5 năm liên tiếp từ 25-50%. Chỉ số ROE (Lợi nhuận trên vốn chủ sở hữu) phải đạt tối thiểu 17%, thể hiện hiệu quả sử dụng vốn vượt trội.5  
* **N (Yếu tố mới):** Sản phẩm mới (như các dự án bất động sản lớn của VHM), ban lãnh đạo mới, hoặc các thay đổi ngành mang tính vĩ mô (như việc triển khai KRX hỗ trợ các công ty chứng khoán).1 Điểm mua lý tưởng là khi cổ phiếu thiết lập đỉnh giá mới (New Highs) thoát ra khỏi nền giá tích lũy ít nhất 7-8 tuần.5  
* **S (Cung/Cầu):** Ưu tiên các cổ phiếu có lượng lưu hành (Float) thấp hoặc có chương trình mua lại cổ phiếu quỹ (Buybacks). Khối lượng tại điểm Breakout phải cao hơn ít nhất 50% mức trung bình.5  
* **L (Dẫn đầu):** Chỉ chọn 2-3 cổ phiếu dẫn đầu nhóm ngành có chỉ số sức mạnh tương đối (Relative Strength \- RS Rating) trên 80\.5 Tuyệt đối tránh các cổ phiếu "lagging" đang hồi phục từ đáy.5

### **2\. Tham số Vận hành Kỹ thuật (Technical Execution)**

| Tham số | Giá trị Tối ưu | Cơ sở Thực nghiệm |
| :---- | :---- | :---- |
| **Stop-loss (Cố định)** | Max 7% 5 | Phù hợp biên độ sàn HOSE để tránh trượt giá quá sâu |
| **Stop-loss (Động)** | **![][image3]** | Lọc nhiễu biến động trong phiên |
| **Trailing Stop** | 5% từ đỉnh lợi nhuận | Bảo vệ lợi nhuận Markup khi có dấu hiệu đảo chiều 5 |
| **Position Sizing** | 2% Risk per Trade | Công thức: ![][image4] 5 |
| **Fibonacci Extension** | 1.618; 2.618; 4.236 | Điểm chốt lãi mục tiêu dựa trên tâm lý tổ chức 20 |
| **VWAP Period** | Daily & Weekly | Xác định vùng giá vốn của Smart Money 5 |

### **3\. Tối ưu hóa cho Chu kỳ T+2.5**

* **Thời điểm mua:** 14:05 \- 14:20 hàng ngày. Đây là thời điểm lượng hàng T+2 đã được thị trường hấp thụ hoàn toàn và xu hướng phiên chiều được xác lập rõ ràng nhất.5  
* **Bộ lọc Breakout:** Chỉ mua nếu giá breakout vào phiên chiều và khối lượng phiên chiều chiếm ít nhất 60% tổng khối lượng cả ngày, xác nhận phe mua hoàn toàn áp đảo lực cung T+2.

## **Quản trị Rủi ro và Phòng vệ bằng Thị trường Phái sinh**

Trong cấu trúc của Trading OS, thị trường phái sinh VN30F1M không chỉ là một công cụ đầu cơ mà là một thành phần không thể thiếu để quản trị rủi ro hệ thống. Các nghiên cứu về mối quan hệ Lead-Lag tại Việt Nam khẳng định thị trường cơ sở (VN30) thường dẫn dắt thị trường phái sinh trong cả ngắn hạn và dài hạn.38 Điều này cho phép nhà đầu tư sử dụng các tín hiệu từ VN30 để thực hiện các chiến lược phòng vệ hiệu quả.

### **Cơ chế Hedging và Basis Trading**

* **Basis Âm (F \< Index):** Khi giá phái sinh thấp hơn đáng kể so với chỉ số cơ sở, Trading OS nhận diện tâm lý thận trọng của các nhà đầu tư lớn. Nếu kết hợp với mô hình HMM đang ở chế độ "Volatile Bear", hệ thống sẽ kích hoạt lệnh bán (Short) VN30F1M để bảo vệ danh mục cổ phiếu cơ sở khỏi các đợt sụt giảm bất ngờ.38  
* **Hồi quy Trung bình (Mean Reversion) phiên ATC:** Tại Việt Nam, giá đóng cửa của hợp đồng phái sinh được tính bằng trung bình số học 30 phút cuối ngày.41 Trading OS sử dụng thuật toán hồi quy để tận dụng các sai lệch giá (noise) trong 5 phút cuối phiên ATC, thực hiện các lệnh đối ứng nhằm tối ưu hóa giá vốn tổng thể.41

## **Phân tích Chế độ Xác suất và Mô phỏng Monte Carlo trong Trading OS**

Để đảm bảo tính bền vững của bộ tham số, Trading OS thực hiện các đợt kiểm thử (Backtest) kết hợp với mô phỏng Monte Carlo. Bằng cách sử dụng chuyển động Brown hình học (Geometric Brownian Motion \- GBM) để tạo ra 1.000 kịch bản đường đi của giá trong 5-10 phiên tiếp theo, hệ thống có thể xác định được xác suất thành công của một vị thế tại điểm mua Pivot.8

* **Đo lường độ bền xu hướng:** Chỉ số Hurst Exponent được tính toán liên tục. Nếu Hurst \> 0.5, Trading OS xác nhận thị trường đang có xu hướng (trending), cho phép nới rộng các mục tiêu lợi nhuận lên mức Fibonacci 2.618. Nếu Hurst \< 0.5, thị trường đang có tính đảo chiều (mean-reverting), hệ thống sẽ thắt chặt các điểm dừng lãi và ưu tiên chốt lời tại mức Fibonacci 1.618.42  
* **Phân tích bầy đàn (Herding Analysis):** Bằng cách áp dụng bộ lọc Kalman vào dữ liệu trạng thái không gian (state-space), Trading OS có thể nhận diện khi nào tâm lý bầy đàn đang ở mức cực đoan (khi các mã cổ phiếu không phân biệt tốt xấu đều tăng/giảm đồng loạt). Đây thường là tín hiệu cảnh báo giai đoạn phân phối của Wyckoff đang bắt đầu, kích hoạt chế độ "Risk-Off" trong hệ điều hành.17

## **Kết luận và Lộ trình Triển khai cho Nhà đầu tư Chuyên nghiệp**

Việc hóa giải các mâu thuẫn giữa các phương pháp đầu tư kinh điển và đặc thù thị trường chứng khoán Việt Nam là một quá trình liên tục của việc định lượng hóa các hành vi thị trường. Trading OS không thay thế tư duy chiến lược của con người, nhưng nó cung cấp một khung vận hành kỷ luật, loại bỏ các thiên kiến tâm lý "Price-paid bias" (giữ cổ phiếu lỗ vì giá mua cao) và tập trung vào hiệu suất tương đối của danh mục.5

Trong giai đoạn 2026, khi Việt Nam chính thức bước vào nhóm các thị trường mới nổi, nhà đầu tư cần tập trung vào các trụ cột sau:

1. **Chuyển dịch sang Tư duy Hệ thống:** Sử dụng ATR làm thước đo dừng lỗ thay vì các con số phần trăm cảm tính để thích ứng với biên độ 7-10% và rủi ro lock sàn.4  
2. **Tận dụng chu kỳ T+2.5:** Biến các đợt rung lắc phiên chiều thành bộ lọc xác nhận dòng tiền lớn, chỉ giải ngân mạnh khi giá duy trì vững chắc trên đường VWAP.5  
3. **Hội tụ Cơ bản và Kỹ thuật:** Áp dụng CANSLIM để chọn lọc các "ngựa chiến" có nội lực tài chính mạnh (EPS Rating \> 80), nhưng chỉ thực thi lệnh trong giai đoạn Markup của Wyckoff được xác nhận bởi mô hình HMM.5  
4. **Phòng vệ Phái sinh:** Sử dụng VN30F1M như một công cụ bảo hiểm danh mục thay vì công cụ đánh bạc, dựa trên mối quan hệ Lead-Lag mật thiết với thị trường cơ sở.38

Thành công trong kỷ nguyên mới của chứng khoán Việt Nam sẽ thuộc về những người biết kết hợp tinh hoa của các bậc thầy kinh điển với sức mạnh của hạ tầng công nghệ hiện đại và các mô hình định lượng tiên tiến. Việc tuân thủ bộ thông số tối ưu trong Trading OS sẽ là chìa khóa để bảo vệ thành quả đầu tư và nắm bắt cơ hội tăng trưởng lịch sử của nền kinh tế quốc gia.

#### **Nguồn trích dẫn**

1. Vietnam's stock market enters its strongest transformation in a decade \- VietNamNet, truy cập vào tháng 3 30, 2026, [https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html](https://vietnamnet.vn/en/vietnam-s-stock-market-enters-its-strongest-transformation-in-a-decade-2470664.html)  
2. Record highs, structural change shape Vietnam's stock market in 2025 \- VOV.VN, truy cập vào tháng 3 30, 2026, [https://english.vov.vn/en/economy/record-highs-structural-change-shape-vietnams-stock-market-in-2025-post1257916.vov](https://english.vov.vn/en/economy/record-highs-structural-change-shape-vietnams-stock-market-in-2025-post1257916.vov)  
3. Sep Strategy Equity Report, truy cập vào tháng 3 30, 2026, [https://shinhansec.com.vn/uploads/report/251003-Equity\_Report-Market\_Classification-E1.pdf](https://shinhansec.com.vn/uploads/report/251003-Equity_Report-Market_Classification-E1.pdf)  
4. Understanding Vietnam's Stock Market Regulations for Foreign Investors, truy cập vào tháng 3 30, 2026, [https://globalreferral.group/understanding-vietnams-stock-market-regulations-for-foreign-investors/](https://globalreferral.group/understanding-vietnams-stock-market-regulations-for-foreign-investors/)  
5. How to Make Money in Stocks \- William J. O'Neil.pdf  
6. Modeling of stock indices with HMM-SV models \- Theoretical and Applied Economics, truy cập vào tháng 3 30, 2026, [https://store.ectap.ro/articole/1268.pdf](https://store.ectap.ro/articole/1268.pdf)  
7. Forecasting The Stock Market Values Using Hidden Markov Model \- Publishing India Group, truy cập vào tháng 3 30, 2026, [http://www.publishingindia.com/GetBrochure.aspx?query=UERGQnJvY2h1cmVzfC8zMzkzLnBkZnwvMzM5My5wZGY=](http://www.publishingindia.com/GetBrochure.aspx?query=UERGQnJvY2h1cmVzfC8zMzkzLnBkZnwvMzM5My5wZGY%3D)  
8. Regime-Aware Short-Term Trading Strategy Using Hidden Markov Models and Monte Carlo Simulation | Communications on Applied Nonlinear Analysis, truy cập vào tháng 3 30, 2026, [https://internationalpubls.com/index.php/cana/article/view/6029](https://internationalpubls.com/index.php/cana/article/view/6029)  
9. Market heads towards 2,000 point-level in 2026 \- Vietnam News, truy cập vào tháng 3 30, 2026, [https://vietnamnews.vn/economy/1733051/market-heads-towards-2-000-point-level-in-2026.html](https://vietnamnews.vn/economy/1733051/market-heads-towards-2-000-point-level-in-2026.html)  
10. VN-Index poised for historic 2,000-point mark in 2026: Experts \- Hanoi Times, truy cập vào tháng 3 30, 2026, [https://hanoitimes.vn/vn-index-poised-for-historic-2-000-point-mark-in-2026-experts.955602.html](https://hanoitimes.vn/vn-index-poised-for-historic-2-000-point-mark-in-2026-experts.955602.html)  
11. Awaiting new peaks in 2026 \- The Saigon Times, truy cập vào tháng 3 30, 2026, [https://english.thesaigontimes.vn/awaiting-new-peaks-in-2026/](https://english.thesaigontimes.vn/awaiting-new-peaks-in-2026/)  
12. Vietnamese brokerages set bold targets for 2026 amid market status upgrade expectations, truy cập vào tháng 3 30, 2026, [https://theinvestor.vn/vietnamese-brokerages-set-bold-targets-for-2026-amid-market-status-upgrade-expectations-d18545.html](https://theinvestor.vn/vietnamese-brokerages-set-bold-targets-for-2026-amid-market-status-upgrade-expectations-d18545.html)  
13. Vietnam Ho Chi Minh Stock Index \- Quote \- Chart \- Historical Data ..., truy cập vào tháng 3 30, 2026, [https://tradingeconomics.com/vietnam/stock-market](https://tradingeconomics.com/vietnam/stock-market)  
14. Vietnam Outlook 2026: Stars are aligning, execution is key \- FSMOne, truy cập vào tháng 3 30, 2026, [https://www.fsmone.com.my/article/349760/vietnam-outlook-2026-stars-are-aligning-execution-is-key](https://www.fsmone.com.my/article/349760/vietnam-outlook-2026-stars-are-aligning-execution-is-key)  
15. Vietnam strategy report, truy cập vào tháng 3 30, 2026, [https://masvn.com/api/attachment/file/1768212082312-MASVN\_RS\_Strategy\_2026\_01.pdf](https://masvn.com/api/attachment/file/1768212082312-MASVN_RS_Strategy_2026_01.pdf)  
16. Vietnam's Market Reform Wave: A Market at a Turning Point | VanEck, truy cập vào tháng 3 30, 2026, [https://www.vaneck.com/us/en/blogs/emerging-markets-equity/vietnams-market-reform-wave-a-market-at-a-turning-point/](https://www.vaneck.com/us/en/blogs/emerging-markets-equity/vietnams-market-reform-wave-a-market-at-a-turning-point/)  
17. Dynamic Herding Analysis in a Frontier Market | Request PDF \- ResearchGate, truy cập vào tháng 3 30, 2026, [https://www.researchgate.net/publication/315539328\_Dynamic\_Herding\_Analysis\_in\_a\_Frontier\_Market](https://www.researchgate.net/publication/315539328_Dynamic_Herding_Analysis_in_a_Frontier_Market)  
18. 3-5-7 Rule in Trading: Everything Traders Should Know \- MetroTrade, truy cập vào tháng 3 30, 2026, [https://www.metrotrade.com/3-5-7-rule-in-trading/](https://www.metrotrade.com/3-5-7-rule-in-trading/)  
19. Mastering the Best RSI Settings for 5-Minute Charts in 2025 \- ePlanet Brokers, truy cập vào tháng 3 30, 2026, [https://eplanetbrokers.com/en-US/training/best-rsi-settings-for-5-minute-charts](https://eplanetbrokers.com/en-US/training/best-rsi-settings-for-5-minute-charts)  
20. 3-Point Fibonacci Extensions Made Easy \- LuxAlgo, truy cập vào tháng 3 30, 2026, [https://www.luxalgo.com/blog/3-point-fibonacci-extensions-made-easy/](https://www.luxalgo.com/blog/3-point-fibonacci-extensions-made-easy/)  
21. Vietnam stock market slides as VN-Index and VN30 retreat \- Chao Hanoi, truy cập vào tháng 3 30, 2026, [https://chaohanoi.com/2026/01/15/vietnam-stock-market-slides-as-vn-index-and-vn30-retreat/](https://chaohanoi.com/2026/01/15/vietnam-stock-market-slides-as-vn-index-and-vn30-retreat/)  
22. Trading Strategy for Market Situation Estimation Based on Hidden Markov Model \- MDPI, truy cập vào tháng 3 30, 2026, [https://www.mdpi.com/2227-7390/8/7/1126](https://www.mdpi.com/2227-7390/8/7/1126)  
23. This work has been submitted to the IEEE for possible publication. Copyright may be transferred without notice, after which this version may no longer be accessible. Adaptive Regime-Aware Stock Price Prediction Using Autoencoder-Gated Dual Node Transformers with Reinforcement Learning Control \- arXiv, truy cập vào tháng 3 30, 2026, [https://arxiv.org/html/2603.19136v1](https://arxiv.org/html/2603.19136v1)  
24. Regime-Switching Factor Investing with Hidden Markov Models \- MDPI, truy cập vào tháng 3 30, 2026, [https://www.mdpi.com/1911-8074/13/12/311](https://www.mdpi.com/1911-8074/13/12/311)  
25. How to use Fibonacci retracements and extensions in technical analysis \- Oanda, truy cập vào tháng 3 30, 2026, [https://www.oanda.com/us-en/trade-tap-blog/analysis/technical/uses-for-fibonacci/](https://www.oanda.com/us-en/trade-tap-blog/analysis/technical/uses-for-fibonacci/)  
26. RSI 40-60 Trend Analysis and Strategy | PDF \- Scribd, truy cập vào tháng 3 30, 2026, [https://www.scribd.com/document/484528999/RSI-Notes](https://www.scribd.com/document/484528999/RSI-Notes)  
27. Relative Strength Index: A Comprehensive Guide to the RSI \- Alchemy Markets, truy cập vào tháng 3 30, 2026, [https://alchemymarkets.com/education/indicators/relative-strength-index/](https://alchemymarkets.com/education/indicators/relative-strength-index/)  
28. How to Master the RSI Indicator for Smarter Trading \- Kavout, truy cập vào tháng 3 30, 2026, [https://www.kavout.com/market-lens/how-to-master-the-rsi-indicator-for-smarter-trading](https://www.kavout.com/market-lens/how-to-master-the-rsi-indicator-for-smarter-trading)  
29. RSI Range-Momentum Trading Strategy (Backtest, Trading Rules with Example), truy cập vào tháng 3 30, 2026, [https://www.quantifiedstrategies.com/rsi-range-momentum-trading-strategy/](https://www.quantifiedstrategies.com/rsi-range-momentum-trading-strategy/)  
30. RSI Indicator Settings: The Best Configurations for Maximum Trading Accuracy \- Axiory, truy cập vào tháng 3 30, 2026, [https://www.axiory.com/trading-resources/technical-indicators/rsi-indicator-settings](https://www.axiory.com/trading-resources/technical-indicators/rsi-indicator-settings)  
31. Best RSI Settings for Day Trading \- Goat Funded Trader, truy cập vào tháng 3 30, 2026, [https://www.goatfundedtrader.com/blog/best-rsi-settings-for-day-trading](https://www.goatfundedtrader.com/blog/best-rsi-settings-for-day-trading)  
32. Economist's Note Understanding Vietnam's Foreign Ownership Limits (FOLs) \- VinaCapital, truy cập vào tháng 3 30, 2026, [https://vinacapital.com/wp-content/uploads/2022/08/VinaCapital-Insights-Understanding-Vietnams-Foreign-Ownership-Limits-FOLs.pdf](https://vinacapital.com/wp-content/uploads/2022/08/VinaCapital-Insights-Understanding-Vietnams-Foreign-Ownership-Limits-FOLs.pdf)  
33. Stock market to attract foreign investors with new reforms \- Vietnam News, truy cập vào tháng 3 30, 2026, [https://vietnamnews.vn/economy/1729686/stock-market-to-attract-foreign-investors-with-new-reforms.html](https://vietnamnews.vn/economy/1729686/stock-market-to-attract-foreign-investors-with-new-reforms.html)  
34. New rules ease foreign access to Vietnam equities, truy cập vào tháng 3 30, 2026, [https://vir.com.vn/new-rules-ease-foreign-access-to-vietnam-equities-146204.html](https://vir.com.vn/new-rules-ease-foreign-access-to-vietnam-equities-146204.html)  
35. Vietnamese (HOSE) Market Analysis & Valuation \- Updated Today, truy cập vào tháng 3 30, 2026, [https://simplywall.st/markets/vn](https://simplywall.st/markets/vn)  
36. VN Technical Analysis and Moving Averages \- Investing.com, truy cập vào tháng 3 30, 2026, [https://www.investing.com/indices/vn-technical](https://www.investing.com/indices/vn-technical)  
37. ATR Trailing Stop with Fibonacci Targets | PDF \- Scribd, truy cập vào tháng 3 30, 2026, [https://www.scribd.com/document/730012729/ATR-Trail-Stop-w-Fib-Targets-Tradovate](https://www.scribd.com/document/730012729/ATR-Trail-Stop-w-Fib-Targets-Tradovate)  
38. (PDF) The Lead and Lag Relationship Between Spot Market and ..., truy cập vào tháng 3 30, 2026, [https://www.researchgate.net/publication/345913800\_The\_Lead\_and\_Lag\_Relationship\_Between\_Spot\_Market\_and\_Futures\_Market\_Empirical\_Evidence\_From\_Vietnam](https://www.researchgate.net/publication/345913800_The_Lead_and_Lag_Relationship_Between_Spot_Market_and_Futures_Market_Empirical_Evidence_From_Vietnam)  
39. The Lead and Lag Relationship Between Spot Market and Futures Market: Empirical Evidence From Vietnam | Phong | Research in World Economy \- Sciedu, truy cập vào tháng 3 30, 2026, [https://www.sciedu.ca/journal/index.php/rwe/article/view/18830](https://www.sciedu.ca/journal/index.php/rwe/article/view/18830)  
40. An empirical study on the relationship between the underlying stock market and the derivatives market in Vietnam \- R Discovery, truy cập vào tháng 3 30, 2026, [https://discovery.researcher.life/article/an-empirical-study-on-the-relationship-between-the-underlying-stock-market-and-the-derivatives-market-in-vietnam/e299d2982d6d392e8aab1bbdad2bf87f](https://discovery.researcher.life/article/an-empirical-study-on-the-relationship-between-the-underlying-stock-market-and-the-derivatives-market-in-vietnam/e299d2982d6d392e8aab1bbdad2bf87f)  
41. Policy Change in Derivatives Expiration – Possibility of Developing Median Regression Algorithm \- Algotrade Knowledge Hub, truy cập vào tháng 3 30, 2026, [https://hub.algotrade.vn/knowledge-hub/20-policy-change-in-derivatives-expiration-possibility-of-developing-median-regression-algorithm/](https://hub.algotrade.vn/knowledge-hub/20-policy-change-in-derivatives-expiration-possibility-of-developing-median-regression-algorithm/)  
42. NEURAL NETWORKS FOR TECHNICAL ANALYSIS: A STUDY ON KLCI \- ResearchGate, truy cập vào tháng 3 30, 2026, [https://www.researchgate.net/publication/263882202\_NEURAL\_NETWORKS\_FOR\_TECHNICAL\_ANALYSIS\_A\_STUDY\_ON\_KLCI](https://www.researchgate.net/publication/263882202_NEURAL_NETWORKS_FOR_TECHNICAL_ANALYSIS_A_STUDY_ON_KLCI)  
43. Time-Varying Price–Volume Relationship and Adaptive Market Efficiency: A Survey of the Empirical Literature \- MDPI, truy cập vào tháng 3 30, 2026, [https://www.mdpi.com/1911-8074/12/2/105](https://www.mdpi.com/1911-8074/12/2/105)  
44. Working Papers, truy cập vào tháng 3 30, 2026, [https://www.wne.uw.edu.pl/download\_file/6095/494](https://www.wne.uw.edu.pl/download_file/6095/494)  
45. Price discovery and information transmission across stock index futures: evidence from VN 30 Index Futures on Vietnam's stock market \- Business Perspectives, truy cập vào tháng 3 30, 2026, [https://www.businessperspectives.org/index.php/journals/investment-management-and-financial-innovations/issue-334/price-discovery-and-information-transmission-across-stock-index-futures-evidence-from-vn-30-index-futures-on-vietnam-s-stock-market](https://www.businessperspectives.org/index.php/journals/investment-management-and-financial-innovations/issue-334/price-discovery-and-information-transmission-across-stock-index-futures-evidence-from-vn-30-index-futures-on-vietnam-s-stock-market)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAaCAYAAABhJqYYAAAA70lEQVR4Xu2SsQtBURSHz0ApShISk00pgzIxWVhNyh9gtygWg9lgthOzySKrwSplNlkUi4Hfuec+Xqc72ZSvvrr3nPvuO++cR/TbtODTelY5Jwl4gBsVd1KCNzjRCRdtkjKaOuFiCi8wrxOaGNxZeZ2GIziHWd85QxFeSW5nlrAOt7DnHfLgOrneDizDMMmDHOv6zhm4A3c4gGMbq5GUwi19kyMZBL+6Cvcktztp0KcEpkCf2jOkutOHD1ixex6ON5ghyYcaQnAFTzBlY9wZ7gDvFzBp42ZxhDMYsLEgyT+yJsc0oyQH/MRhRMX+fMcL2jIoTTHTQ/kAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAK0AAAAWCAYAAACyohz1AAAFBElEQVR4Xu2ae+hsUxTHv0J5v/OWe4XIH5SQxx8URR4Jie5f/pDbzV8UuSL+EFKSvKObRF7xDynEiORVUkRy6155RCFCeVufu85q9uzZ58ydX2Z+nbE/9e3M7H3Onpl11l577XVGqlQqlUqlUqnMgGNM15u2yjsqs+cK01um303/mH5u3j9g+sT0edL3vGkbv2xqtjDt2Bz7znum4/LGhp1Mt5juzzta2Mv0tuk+00WmCxrd2vRVWtjV9K7cMc/J+mA30+umB/OOKVht+sl0dN7RM7Y23aXxybdC7nh/yu348EhvO/uYNsqvSfVZelJlnMNN35m+Nh2U9QVrTVfnjVNAlP7CtH/e0TOOb5TDxD7FdK6md9qPTI+aHjPdYzpbPjkqHaxSefk/LHmN056XvJ8WJkQ+fh+507Rz3piAw03rtIPmuBRIIbbMGxPo2zdv7Dssc+vkhr4p68NRg2tNxzavcTyMvMOwe1MbBmyLEIxfitSME46MgfdsFDci2nbX+JI8b/aQR8Uu5um02OMq+f5j26wPuBe3yXPshSLy2b9NpybtK7L3Ka+YXjJ9bzrRdKU85/2w0YHNeW35GpMEg3NejHO+6UXTU6Y3TffKI9oTpsdN38o/J7hEft2RSdus4bPIy7tYqtOeJLcLG19seWZyThfhuE9qdAXAYe+WVzjaAklvYWP0i9zQVAm+al6j/ZLzUk7X8DqqDWvkxqMM9KvGIyoReb3Gd8MYNMb5QR7JTzb9JT+fHTTOHBFuIB+LMtPT6s7BZ8EZ8sndxVKcdoPpGdNKuR1xYCbk5job11xuerZ5T9Ql+l6j7tSht3DzS0v3ZclrNmo3y50FI2Akcrs/5AYOGIOx8goEuXA6HjAOUb40TkDk4LPYrf+m4QaIFQDnydOZFL4zmxpu3iSxhJKCTILfxwTrYlqnbYPP4t5MUwfGVtgSZ+X1wkIEKznNWc2RH3+7vIYYEO0GGo+etG3QeITGMYnCJQby70A0LcH4H8trx7H84ax5OpNDlOJaItkkbW6+zMT7r532YPk11HdTaBtodN8wib3lZUnSC1KvhQWH7XKaI0yvatQ5o0SWRwKiYdQwd5FvsCJnjvFxpjT3YhzKPW1OU4qqA5Unx6zBkUh/upjWaV+Wn8/ETuGhD33bZ+1tUErEWbEjNntDPiEWEgyWO1+Ac2G4PHWIElm+5ONc5LvkVI/InTtyVoyJbtRo1C6NkxJOwDFYrvIZqxGTvIsupyUlIke/WMN8Fft+aTotTmpgkt6QtbVBVGUlSkuSJ8iftHEPFgqcq81pcIh35A8EVmZ9RAUcMX26tZ2GEZsbc4d8IsTmDDAklYB0ycvHyWHzw3dkogA3u5SDzwM2fUyYLi6Ufz9+Z74JilWDfn4XrJY/SUs3XTjhp81xEkRTomopVTrK9Fpz7D2p8SYJ58uX7oFGc8zgR9Nz8sgdfRxfkJeu1smfHAU4b2mcFG4m5S+i0UPy80s5+DxgIhPhS6sSufFGjdsPxSrBEv6B/D8dhzZt/D6qJO/LqzBr5eNQ9psE34NNZGxQS8Qm+n8P+Wppg0B7+mAg4H3bZqc0TgnGjo1TVw4+aygtzSKXPkD+CJg/y+BouQ0rPYG8kEh1afOeZY7ie7qULgdEeyZhpTIGuTG53XXyeuo3Gn0qtlxE4b60clQqm9IH8tdDtPwRNqAMRT2USVWp9IZ4olej7Rz4FxSYHOQMcEOhAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAXCAYAAADAxotdAAACI0lEQVR4Xu2ZMUgdQRCGJ2ggghKCEhFTWJgiJKIgJCAWghqwEIIKFkkfSZNCRAS7YC8WQkQLLdUyQa0UBBEsAqIgaJMghMRCCNgoGv/fuePulvfe3Qnv3ivmgw+8nb1r5u3szipiGIZhlDlvYBdsgM/gW9gYilfBPjgEX4nOpZXBlFjq4Ds4A9ucmFFEHsExuAr/wxP4Fb4IzWmCy16c/hB9h+8mpQMuwQvY7sSMDKgRTd6AG/CohTtw0A2kgKt4Dz5xA0bxYbllgsfdAHgAJ+AX7+/70gnn3UEjO5jgXAl4DTfhUzeQko/wvTtoZAcTzL3YPTx9g73OWC64ulnKeVircGL8Jr8d3tuNjLmCP0UT5PNS9GSdDyZ1FF7CYe+ZrMNd+Nh7Znnm9+NogfvwV0KPRLsAIwH/PFu9Z7ZHK0E4Jzx0XcNpie7Pi6IJZWIJ93ZWiDi48rkV8EeWxHr48O5NIxau3nBSPsCFIJyTA3gu2h+H8duuftF26jv8HZlhZM62BElphluiPXAhbkTnVTvjhxJUA5b4U9EkGyWECWCCJ0VXLldwHJzP2ykXVgLuwyzzPaI/hCnRfrtQq8VD2CycS6HdjCXE3yfPRA9XSWCJ5i2Xvw9yD/0s0QsTtl5/4XP4KTRuZAyTwgSPuIECcPUci5Z3riZeY65FZmgf/QduSHCqNkoA/8HQLelPpeH+N9/9NMd54jUMwzAMwzAMwyhjbgEOdGZDqaMAFQAAAABJRU5ErkJggg==>