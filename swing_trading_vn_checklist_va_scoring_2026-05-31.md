# <span style="color:#0f766e">Swing Trading VN</span>
## <span style="color:#2563eb">Checklist + Scoring Template gọn để dùng hằng ngày</span>

> Ngày biên soạn: 2026-05-31
>
> Mục tiêu: bản rút gọn chỉ tập trung vào swing trading Việt Nam, ưu tiên checklist thực chiến, scorecard ngắn, rule vào/ra lệnh ngắn gọn, và phân tách rõ `FACT` với `[GUESS]`.

---

## <span style="color:#7c3aed">0. Legend</span>

| Nhãn | Ý nghĩa |
|---|---|
| <span style="color:#0f766e"><strong>FACT</strong></span> | Đã xác minh trực tiếp từ nguồn công khai đáng tin |
| <span style="color:#b45309"><strong>[GUESS]</strong></span> | Mô hình hóa hoặc ngưỡng chiến lược chưa được xác minh trực tiếp |
| <span style="color:#2563eb"><strong>RULE</strong></span> | Quy tắc vận hành đề xuất |
| <span style="color:#b91c1c"><strong>AVOID</strong></span> | Điều cần tránh |

---

## <span style="color:#7c3aed">1. FACT nền đủ để swing trading Việt Nam đúng ngữ cảnh</span>

- <span style="color:#0f766e"><strong>FACT</strong></span> SSI iBoard hiển thị top-of-book với `Giá 1/KL1`, `Giá 2/KL2`, `Giá 3/KL3` ở cả bên mua và bên bán.
- <span style="color:#0f766e"><strong>FACT</strong></span> VNDIRECT cũng mô tả màn hình đặt lệnh có `3 bước giá và khối lượng giá bán tốt nhất`, `3 bước giá và khối lượng mua tốt nhất`.
- <span style="color:#0f766e"><strong>FACT</strong></span> DNSE LightSpeed API có cả `Market Data API` và `Trading API`, hỗ trợ realtime market data, trạng thái tài khoản và sổ lệnh.
- <span style="color:#0f766e"><strong>FACT</strong></span> SBV công khai `Tỷ giá trung tâm`, `Lãi suất NHNN`, `Lãi suất liên ngân hàng`, `Tổng phương tiện thanh toán`, `Dư nợ tín dụng`, `Tỷ lệ nợ xấu`, `CPI`.
- <span style="color:#0f766e"><strong>FACT</strong></span> `yfinance` tự ghi rõ là công cụ research/education, personal use, không phải nguồn chính thức của Yahoo hay của thị trường Việt Nam.
- <span style="color:#0f766e"><strong>FACT</strong></span> VNDIRECT xác nhận giao dịch lô lẻ là `1-99` chứng khoán; odd-lot không hỗ trợ `MTL`, `ATO`, `ATC`, và chỉ khớp với lệnh odd-lot đối ứng.

### Kết luận thực dụng
- <span style="color:#2563eb"><strong>RULE</strong></span> Dùng `DNSE` làm feed/execution chính nếu muốn code hóa.
- <span style="color:#2563eb"><strong>RULE</strong></span> Dùng `SSI/VNDIRECT` để đối chiếu top-of-book thủ công.
- <span style="color:#2563eb"><strong>RULE</strong></span> Dùng `SBV + yfinance` để đọc regime, không dùng `yfinance` làm nguồn execution cho cổ phiếu Việt Nam.

---

## <span style="color:#7c3aed">2. [GUESS] Quick regime card</span>

| Regime | Nhận diện nhanh | Tư thế giao dịch |
|---|---|---|
| Bull | VNIndex > MA20 > MA50, breadth tốt, leader sectors đồng thuận | Có thể trade mạnh tay hơn, ưu tiên breakout/pullback |
| Sideways | VNIndex quanh MA20/MA50, breadth trung tính, quay vòng nhanh | Trade ít hơn, chốt nhanh, chỉ chọn mã khỏe |
| Bear | VNIndex < MA50, breadth xấu, nhiều breakout fail | Ưu tiên tiền mặt, long rất chọn lọc, không margin |

### <span style="color:#b91c1c">AVOID</span>
- Dùng cùng một mức độ hung hăng ở cả ba regime.
- Trade nhiều mã beta cao khi thị trường đang bear.

---

## <span style="color:#7c3aed">3. [GUESS] Bộ checklist swing trading VN</span>

### 3.1. Trước phiên
- [ ] Xác định regime: bull, sideways, hay bear.
- [ ] Kiểm tra macro nhanh: FX, lãi suất, tín dụng, dấu hiệu stress thanh khoản từ SBV.
- [ ] Kiểm tra risk-on/risk-off toàn cục từ `yfinance`: SPX, Nasdaq, DXY, VIX, dầu, US10Y.
- [ ] Lọc watchlist theo 3 nhóm: breakout, first pullback, RS leader chưa bùng nổ.
- [ ] Ghi sẵn cho từng mã: `entry`, `stop`, `invalid`, `max size`.
- [ ] Loại bỏ mã có thanh khoản mỏng, spread rộng, hoặc story không rõ.

### 3.2. Trong phiên
- [ ] Không chase ở những phút đầu nếu chưa có setup rõ.
- [ ] So sánh sức mạnh mã với VNIndex và nhóm ngành ngay trong rung lắc đầu phiên.
- [ ] Quan sát top 3 bid/ask: có hấp thụ cung thật hay chỉ treo lệnh.
- [ ] Chỉ vào lệnh khi giá đi qua đúng điểm kích hoạt hoặc hồi về đúng vùng mua đã định.
- [ ] Nếu giá đã cách pivot quá xa, bỏ qua thay vì kéo stop rộng hơn.
- [ ] Nếu thị trường yếu đi mà mã vẫn giữ nền tốt, giữ nó trong watchlist ưu tiên.

### 3.3. Sau phiên
- [ ] Chấm lại từng lệnh: đúng setup hay chỉ là cảm tính.
- [ ] Gắn nhãn breakout thành công, breakout fail, hoặc đang chờ follow-through.
- [ ] Nâng stop cho mã đang chạy đúng hướng.
- [ ] Bỏ các mã yếu khỏi watchlist ngày hôm sau.
- [ ] Cập nhật nhật ký: vì sao mua, vì sao chưa mua, vì sao bán.

---

## <span style="color:#7c3aed">4. [GUESS] Checklist scan ra mã khỏe hơn thị trường</span>

- [ ] `ret_20_stock - ret_20_vnindex > 0`
- [ ] `ret_60_stock - ret_60_vnindex > 0`
- [ ] Giá > MA20, tốt hơn nếu > MA50
- [ ] MA20 dốc lên hoặc ít nhất không dốc xuống rõ
- [ ] Khoảng cách tới đỉnh 52 tuần không quá xa, ví dụ <= `15%`
- [ ] GTGD bình quân 20 phiên đạt chuẩn thanh khoản
- [ ] Tỷ lệ volume phiên tăng / volume phiên giảm > `1`
- [ ] Khi VNIndex giảm, mã giảm ít hơn hoặc vẫn giữ trên nền
- [ ] Nhóm ngành của mã không nằm trong nhóm suy yếu mạnh nhất thị trường
- [ ] Top 3 bid/ask không cho thấy cung đè bất thường quanh pivot

### Cờ đỏ loại nhanh
- [ ] Mã tăng nhưng GTGD quá mỏng
- [ ] Tăng nhờ vài lệnh kéo chứ không có volume nền
- [ ] Có sell wall refresh lặp lại nhiều lần ở vùng breakout
- [ ] Có event risk hoặc red flag công bố thông tin lớn

---

## <span style="color:#7c3aed">5. [GUESS] Scoring template gọn cho swing trading VN</span>

### 5.1. Công thức ngắn

```text
SwingScore = Trend(35) + Sector(20) + OrderBook(15) + LiquidityVolume(15) + Risk(15)
```

> Điểm cuối cùng tính trên 100. Thành phần `Risk` là điểm thuận lợi còn lại sau khi trừ penalty.

### 5.2. Trend score - 35 điểm

| Hạng mục | Điểm |
|---|---:|
| Giá > MA20 | 8 |
| Giá > MA50 | 8 |
| MA20 dốc lên | 5 |
| Gần đỉnh 52 tuần | 6 |
| Relative strength dương vs VNIndex | 8 |

### 5.3. Sector score - 20 điểm

| Hạng mục | Điểm |
|---|---:|
| Ngành nằm trong nhóm mạnh của thị trường | 10 |
| Breadth ngành tốt | 5 |
| Có catalyst ngành/doanh nghiệp | 5 |

### 5.4. Order book score - 15 điểm

| Hạng mục | Điểm |
|---|---:|
| Top 3 bid đỡ tốt quanh pivot | 5 |
| Không có sell wall refresh rõ | 5 |
| Giá giữ tốt gần high-of-day | 5 |

### 5.5. Liquidity/volume score - 15 điểm

| Hạng mục | Điểm |
|---|---:|
| GTGD bình quân đạt chuẩn | 5 |
| Volume co trong nền | 5 |
| Volume nổ lúc breakout | 5 |

### 5.6. Risk score - 15 điểm

| Hạng mục | Điểm |
|---|---:|
| Không có spread quá rộng | 5 |
| Không có event risk gần | 5 |
| Không có red flag tài chính/quản trị rõ | 5 |

### 5.7. Cách dùng nhanh

| Điểm | Hành động |
|---|---|
| >= 75 | Mã swing mạnh, đưa vào watchlist ưu tiên |
| 65-74 | Theo dõi, chờ setup đẹp hơn |
| < 65 | Loại |

---

## <span style="color:#7c3aed">6. [GUESS] Relative strength leader score gọn</span>

### 6.1. Input tối thiểu
- `close`, `volume`, `avg_value_20d`
- `VNIndex`
- `bid1..3`, `ask1..3`, `bid_vol1..3`, `ask_vol1..3`

### 6.2. Công thức gọn

```text
S1 = excess return 20d vs VNIndex
S2 = excess return 60d vs VNIndex
S3 = resilience khi VNIndex điều chỉnh
S4 = trend quality so với MA50
S5 = khoảng cách tới đỉnh 52 tuần
S6 = volume quality
S7 = top-3 book imbalance

RSL = 0.25*S1 + 0.20*S2 + 0.15*S3 + 0.15*S4 + 0.10*S5 + 0.10*S6 + 0.05*S7
```

### 6.3. Ngưỡng dùng

| RSL | Diễn giải |
|---|---|
| >= 75 | Relative strength leader mạnh |
| 68-74 | Watchlist tốt |
| < 68 | Chưa đủ mạnh |

### Cách dùng đúng
- Không mua chỉ vì RSL cao.
- Chỉ mua khi `RSL cao + setup đẹp + regime phù hợp + risk/reward tốt`.

---

## <span style="color:#7c3aed">7. [GUESS] Rule card vào lệnh, stop loss, take profit</span>

### 7.1. Breakout entry
- Giá vượt pivot hoặc đỉnh nền.
- Volume >= `1.5x` trung bình 20 phiên.
- Giá đóng ở nửa trên biên độ ngày.
- Top 3 ask không cho thấy cung đè rõ.

### 7.2. First pullback entry
- Breakout trước đó là breakout tốt.
- Pullback đầu tiên về EMA10/EMA20 hoặc kiểm định pivot cũ.
- Volume pullback thấp hơn volume breakout.
- Mã vẫn khỏe hơn thị trường trong lúc rung.

### 7.3. Stop loss
- Dưới pivot một khoảng an toàn nhỏ.
- Hoặc dưới đáy pullback gần nhất.
- Hoặc theo `1.5 ATR` nếu cấu trúc biến động rộng.

### 7.4. Take profit
- Chốt một phần ở `1.5R`.
- Chốt tiếp một phần ở `2R`.
- Phần còn lại trail theo EMA10 hoặc đáy swing.

### 7.5. Time stop
- Sau `5-8` phiên mà không có follow-through thì giảm hoặc thoát.
- Breakout quay lại nền và đóng dưới pivot thì thoát nhanh.

---

## <span style="color:#7c3aed">8. [GUESS] Mini pseudo-code cho workflow hằng ngày</span>

```python
regime = detect_regime(vnindex, breadth, sbv_macro, global_overlay)

universe = filter_stocks(
    avg_value_20d_gt=20e9,
    min_price=10000,
    avoid_illiquid=True,
)

candidates = []
for stock in universe:
    swing_score = compute_swing_score(stock)
    rsl = compute_rsl(stock, vnindex)
    if swing_score >= 65 and rsl >= 68:
        candidates.append(stock)

watchlist = rank(candidates, by=["swing_score", "rsl", "sector_strength"])

for stock in watchlist:
    if breakout_entry(stock, regime) or first_pullback_entry(stock, regime):
        size = position_size(nav, stop_distance, regime)
        place_order(stock, size)
```

---

## <span style="color:#7c3aed">9. Một trang dùng nhanh</span>

### Làm mỗi sáng
1. Xác định regime.
2. Cập nhật SBV + overlay quốc tế.
3. Lọc RS leader và SwingScore.
4. Chọn 5-10 mã mạnh nhất.
5. Ghi sẵn entry/stop/size.

### Làm trong phiên
1. Không chase.
2. Mua đúng trigger.
3. Quan sát top 3 bid/ask như lớp xác nhận, không phải lý do chính.
4. Nếu sai, cắt nhanh.

### Làm cuối ngày
1. Review lệnh.
2. Nâng stop.
3. Cập nhật watchlist ngày mai.

---

## <span style="color:#7c3aed">10. Nguồn FACT tối thiểu</span>

1. HOSE: https://www.hsx.vn/
2. HNX: https://www.hnx.vn/vi-vn/
3. SBV: https://www.sbv.gov.vn/
4. SSI iBoard: https://iboard.ssi.com.vn/
5. SSI iBoard Pro: https://www.ssi.com.vn/khach-hang-ca-nhan/nen-tang-giao-dich/nen-tang-mobile-trading/iboard-pro
6. VNDIRECT Hướng dẫn giao dịch cổ phiếu: https://support.vndirect.com.vn/hc/vi/articles/4402908551705-H%C6%AF%E1%BB%9ANG-D%E1%BA%AAN-GIAO-D%E1%BB%8ACH-C%E1%BB%94-PHI%E1%BA%BEU
7. VNDIRECT Giao dịch lô lẻ: https://support.vndirect.com.vn/hc/vi/articles/10313129594777-Giao-d%E1%BB%8Bch-l%C3%B4-l%E1%BA%BB-t%E1%BA%A1i-VNDIRECT
8. DNSE LightSpeed API: https://developers.dnse.com.vn/
9. yfinance docs: https://ranaroussi.github.io/yfinance/
10. yfinance PyPI: https://pypi.org/project/yfinance/

---

## <span style="color:#7c3aed">11. Ghi chú cuối</span>

- File này cố tình gọn hơn file playbook tổng.
- Phần `FACT` chỉ giữ nền tối thiểu cần cho swing trading VN.
- Toàn bộ rule, trọng số, ngưỡng điểm, setup, RSL và sizing đều là `[GUESS]` và cần backtest/paper trade trước khi dùng tiền thật.