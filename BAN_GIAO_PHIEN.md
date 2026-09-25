# Bàn giao phiên làm việc — 22/09/2026

Đọc file này trước khi làm gì khác. Nó tóm tắt trạng thái và những phát hiện
mà nếu không biết sẽ mất hàng giờ dò lại.

---

## 1. ĐÃ XONG — dữ liệu OSM khu VinUni ĐẠT, không cần đổi vùng

Câu hỏi cũ: *footprint cam có trùng mái nhà trong ảnh vệ tinh không?* → **CÓ, trùng rất sát.**

Đo bằng số thay vì bằng mắt (`my_client/doi_chieu_vetinh.py`, xem mục 6):

| Phép đo | Kết quả | Nghĩa là |
|---|---|---|
| Quét dịch chuyển toàn cục ±17 m | tốt nhất chỉ lệch **2,5 m**, điểm gần như không tăng (1,039 → 1,068) | **không có lệch hệ thống** — 2,5 m nằm trong sai số căn ảnh của chính Esri |
| Chấm từng toà (trong lòng vs vành ngoài) | **60/80 (75%)** trùng mái rõ, 7 (9%) không trùng | footprint đặt đúng chỗ |
| Khối mái thật mà OSM không có | ~50–82 khối, 1,5–2,2 ha (OSM đang có 4,45 ha) | **thiếu, chứ không lệch** |

**Vì sao trước đó thấy "không tốt lắm":** lỗi của chính hình `task3_61`, không phải của dữ liệu.
Nền ảnh bị làm mờ để footprint nổi lên, nên map trông thưa và lệch. Kẻ viền footprint lên ảnh
vệ tinh **nguyên độ sáng** rồi phóng to thì thấy viền bám mép mái sai lệch chỉ vài pixel:

```
evidence\task3\task3_70_zoom_loi_vinuni.png     ← rõ nhất, xem cái này trước
evidence\task3\task3_71_zoom_the_thao.png
evidence\task3\task3_72_zoom_quang_truong.png
evidence\task3\task3_73_zoom_biet_thu.png
evidence\task3\task3_74_ban_do_do_phu.png       ← xanh = OSM đã có, đỏ = nhà thật còn thiếu
```

**Phân bố chỗ thiếu rất quan trọng** (xem `task3_74`): **lõi VinUni gần như xanh toàn bộ** —
đây là vùng ta cần. Chỗ đỏ dồn ra rìa khung: chung cư góc tây-bắc, dãy biệt thự rìa đông,
và bờ sông đông-nam — đều **ngoài khuôn viên**. Một toà lớn ~3.600 m² (công trình mái cong
góc tây-nam) là chỗ thiếu đáng kể duy nhất ở gần lõi.

> **Hai cảnh báo khi đọc lại số trên**
> - "Không trùng 9%" phần lớn là **mái sẫm màu bị chấm thấp oan**, không phải lệch. Đã kiểm
>   chứng `Nhà A` (điểm −0,05): độ sáng TB 87 so với `Nhà H` 200 — nhìn ảnh `task3_70` thì
>   viền bám mái chuẩn. Phép đo dựa vào độ sáng nên thiên vị mái sáng.
> - Số khối thiếu dao động 50–82 tuỳ ngưỡng vì **lối đi bê tông sáng bị đếm nhầm là mái**.
>   Lấy 50 (ngưỡng chặt) làm mốc thận trọng.

### Kết luận cho hướng đi

Cả hai nhánh dự kiến ban đầu đều **không đúng**:

- ❌ *Không phải lỗi công cụ* — công cụ đã dựng **73/80 = 91%** số footprint sẵn có. Nó làm tốt.
- ❌ *Không cần đổi khu vực* — dữ liệu khu này đúng toạ độ, lõi campus lại được map khá đủ.
- ✅ **Giới hạn thật nằm ở độ dày dữ liệu OSM**: cả khung chỉ có 80 toà cho vùng thực tế
  khoảng 130–160 toà. Map thưa là vì OSM thưa, không vì công cụ hỏng.

Muốn map dày hơn thì **vẽ bổ sung footprint vào file `.osm` cục bộ** (không cần đẩy lên
openstreetmap.org — mà cũng không đẩy được, xem mục 7). Việc này khả thi chính vì phép đo
trên đã chứng minh hệ toạ độ khớp: số hoá tay từ ảnh Esri sẽ rơi đúng chỗ.

---

## 2. Trạng thái 4 task

| # | Task | Trạng thái |
|---|---|---|
| 1 | Scenario Runner + OpenSCENARIO 2 | ✅ **Xong trọn vẹn**, đủ 4/4 trang tài liệu |
| 2 | Cảm biến + ghi dữ liệu + hệ toạ độ | ✅ **Xong**, 100/100 frame, kiểm chứng toạ độ đạt |
| 3 | Tạo map từ OpenStreetMap | ✅ **Xong**, đã kiểm chứng chất lượng dữ liệu bằng số (mục 1) |
| 4 | Hiểu vì sao cần image/container | ✅ Trả lời được (chưa thực hành Docker) |

Báo cáo đầy đủ: `D:\Hunganh\carla_tuan\vinfast\` (README + 4 file task + 2 phụ lục)

---

## 3. Đang chạy trên máy

| Tiến trình | Trạng thái | Ghi chú |
|---|---|---|
| **Unreal Editor** | đang mở | đang mở map `VinUniCampus` |
| **Máy chủ HTTP cục bộ** | cổng 8765 | phục vụ file `.osm` cho widget |
| CARLA server (`-game`) | **đã tắt** | không chạy cùng Editor, tranh GPU |

Bật lại máy chủ nếu cần:
```bat
cd D:\Hunganh\carla-scenario\osm
D:\Hunganh\carla-scenario\.venv-sr\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1
```

---

## 4. Năm điều PHẢI biết về Digital Twin Tool

Tìm ra sau 7 lần thử, 5 lần thất bại. Không có tài liệu nào nói.

### 4.1 ⭐ URL phải chứa `?bbox=...`
Widget **tách `bbox` khỏi chuỗi URL** để đặt gốc toạ độ. Thiếu nó thì toạ độ văng ra 9.300 km,
`GenerateOrderedChunkedMesh` chạy 3 mili giây rồi kết thúc, map rỗng.
Dùng file cục bộ thì **vẫn phải gắn bbox giả** vào URL:
```
http://127.0.0.1:8765/ten_file.osm?bbox=105.94348,20.98706,105.94830,20.99156
```

### 4.2 Ô Geo Coords Origin vô dụng
Giới hạn giao diện đặt ngược so với mã C++ (ô đầu nhận >90, ô sau kẹp ở 90) nên **không nhập
được kinh độ Việt Nam**. Mà dù nhập được cũng bị URL ghi đè. Bỏ qua ô này.

### 4.3 Vùng phải NHỎ
Công cụ chia ô 500 m nhưng tính số ô sai — vùng 800 m chỉ được phủ `2×1` ô, **mất hơn nửa diện
tích**. Đó là lý do bản `VinUni800m` chỉ có 35/206 toà nhà.
Vùng **500×500 m** thì phủ trọn: bản `VinUniCampus` được **73/80 toà (91%)**.

### 4.4 Phải điền `building:levels`
Công cụ chỉ dựng toà nhà có chiều cao. OSM Việt Nam rất thưa thẻ này (VinUni 15%).
Script điền tự động theo loại công trình — xem mục 6.
**Lưu ý:** điền chiều cao chỉ có tác dụng khi vùng đủ nhỏ để phủ trọn (4.3). Đã kiểm chứng:
vùng 800 m dù điền 100% chiều cao vẫn ra đúng 35 toà.

### 4.5 Sập với dữ liệu đô thị dày
```
EXCEPTION_ACCESS_VIOLATION 0xfffffffffffffff0
std::vector<NWWriter_OpenDrive::LanePoint>::back()
osm2odr::ConvertOSMToOpenDRIVE()
```
Gọi `.back()` trên vector rỗng — lỗi trong mã C++ của CARLA. Xảy ra với Hoàn Kiếm.
Không vá được từ ngoài. Cùng file đó, `carla.Osm2Odr.convert()` từ Python chạy tốt.

**Thêm:** hộp thoại `Locate main RenderDoc executable...` chặn Editor khởi động, phải bấm Cancel.

---

## 5. Map đã dựng

```
D:\Hunganh\carla_tuan\Unreal\CarlaUE4\Content\CustomMaps\
├── VinUniCampus\   ← TỐT NHẤT: 404 mesh, 73 toà nhà, vùng 500 m
├── VinUniFullB\    404 mesh nhưng chỉ 35 toà (vùng 800 m, mất nửa diện tích)
└── VinUni800m\     309 mesh, 35 toà — bản đầu tiên
```

Mở map: `File → Open Level` → chọn file có đuôi **`_Tile_0_0`**, không chọn level chính
(nó rỗng, nội dung nằm trong các ô con). Camera thường ở rất xa — chọn một actor trong
World Outliner rồi bấm **`F`**.

Vài thư mục rác còn kẹt do Editor khoá file (`TimesCityGeo`, `TimesCityV2`, `VinUniFull`,
`HoGuom1kmC`, ~19 MB) — xoá được sau khi đóng Editor.

---

## 6. Công cụ tự viết

| File | Vai trò |
|---|---|
| `my_client/khao_sat_osm.py` | chấm điểm chất lượng dữ liệu OSM trước khi dựng |
| `my_client/doi_chieu_vetinh.py` | đối chiếu footprint OSM với ảnh vệ tinh — đo *đúng chỗ* và *đủ* bằng số |
| `my_client/osm_to_map.py` | OSM → OpenDRIVE → world (đường B, không cần Editor) |
| `my_client/loc_osm.py` | lọc bỏ đường không lái xe được |
| `my_client/capture_sync.py` | thu dữ liệu cảm biến đồng bộ (Task #2) |
| `my_client/lidar_on_image.py` | chiếu LiDAR lên ảnh, kiểm chứng hệ toạ độ (Task #2) |
| `run_batch.py` · `watch.py` | chạy hàng loạt kịch bản · camera bám xe (Task #1) |

Điểm khảo sát các khu đã đo:

| Khu | km đường | Nhà có chiều cao | Đường có `lanes` | Điểm |
|---|---|---|---|---|
| Hồ Gươm | 17,4 | 2% | **78%** | 58 |
| Phố cổ | 34,6 | **0%** | 59% | 60 |
| Times City | 25,7 | 21% | 52% | 71 |
| VinUni 800 m | 10,2 | 15% | 31% | 48 |
| **VinUni campus (đã điền)** | 3,1 | **100%** | 38% | **82** |

---

## 7. Mạng

- `openstreetmap.org` **bị chặn DNS** trên máy này (cả trình duyệt)
- `overpass-api.de` vào được nhưng **giới hạn theo IP** — tỉ lệ thành công ~50%, hay trả 504/429
- `server.arcgisonline.com` vào được → dùng lấy ảnh vệ tinh Esri để đối chiếu
- Bash và PowerShell **không phân giải được tên miền** trong sandbox; phải dùng
  `dangerouslyDisableSandbox` hoặc PowerShell cho việc tải

File `.osm` đã tải sẵn trong `osm/` — dùng lại, đừng tải mới nếu không cần.

---

## 8. Việc còn lại

1. ~~Đánh giá ảnh đối chiếu~~ → **xong, xem mục 1.** Dữ liệu đạt, giữ nguyên khu vực.
2. **Thử lại Times City** — 4 lần thất bại trước đều do thiếu `bbox`, chưa được thử công bằng.
   Dữ liệu đã có: `osm/times_city.osm`.
   Chạy `doi_chieu_vetinh.py` cho Times City **trước khi dựng** để khỏi mất công như lần trước
   (cần tải tile vùng đó — script tải tile chưa được lưu lại, phải viết lại).
3. **Bấm `Save Map`** cho `VinUniCampus` — mất hơn 1 giờ, chưa làm
4. *(tuỳ chọn, chỉ khi cần map dày hơn)* vẽ bổ sung ~50 footprint còn thiếu vào
   `osm/vinuni_campus.osm`, ưu tiên toà mái cong ~3.600 m² góc tây-nam
5. **Gom tài liệu bàn giao** cho mentor — người dùng muốn gửi link Drive + link Notion tự làm.
   Markdown trong `vinfast/` nhập thẳng vào Notion được
6. Bài tự dựng lại môi trường Task #1 mà không nhìn ghi chú (phần "master")

---

## 9. Cách làm việc người dùng muốn

- **Tôi viết mẫu có chú thích dày → người dùng đọc hiểu → sau đó tự viết lại.** Giai đoạn luyện
  lại chưa bắt đầu.
- Giải thích **cơ chế bên dưới**, không chỉ cú pháp
- **Nói thẳng khi không chắc**, đừng trấn an. Trong phiên này tôi đã suy đoán sai ba lần ở
  Task #3 (đổ lỗi file đã lọc, khuyên bỏ trống ô toạ độ, giả thuyết chiều cao) và mỗi lần đều
  khiến người dùng mất thêm một lượt thử — cần tránh lặp lại.
