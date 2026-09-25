# Báo cáo Task #1 — Chạy ví dụ OpenSCENARIO 2 với Scenario Runner

**Ngày:** 22/09/2026 · **Môi trường:** Windows 11, RTX 3090 Ti, CARLA **build từ source** (tag `0.9.16`, commit `294096e`)
**Tài liệu tham chiếu:** https://scenario-runner.readthedocs.io/en/latest/getting_scenariorunner/

---

## 1. Kết quả

Đã chạy **7 kịch bản OpenSCENARIO 2**, toàn bộ vòng đời hoạt động: parse `.osc` → nạp map →
spawn diễn viên → chạy cây hành vi → chấm tiêu chí → dọn dẹp.

| Kịch bản | Kết quả | Va chạm | Game time |
|---|---|---|---|
| `keep_lane.osc` | SUCCESS | 0 | 38,1 s |
| `acceleration.osc` | SUCCESS | 0 | 38,1 s |
| `change_lane.osc` | SUCCESS | 0 | 15,1 s |
| `overtake1.osc` | SUCCESS | 0 | 18,1 s |
| `one_of.osc` | SUCCESS | 0 | 100,1 s |
| `cut_in_and_slow_range.osc` | **FAILURE** | **3** | 57,0 s |
| `my_cutin.osc` *(em tự sửa)* | **SUCCESS** | **0** | 57,4 s |

Kết quả chi tiết (`.txt` + `.json` + ảnh): `evidence/task1/`

**Môi trường:** Scenario Runner tag `v0.9.16` (khớp đúng CARLA 0.9.16), Python 3.11.9, venv
riêng với đúng các version mà `requirements.txt` ghim: `py-trees==0.8.3`,
`antlr4-python3-runtime==4.10`, `numpy==1.24.4`, `networkx==3.4.2`, `Shapely==2.1.1`.

---

## 2. FAILURE của `cut_in_and_slow_range.osc` không phải lỗi cấu hình

Đây là phần em muốn báo cáo kỹ nhất, vì thoạt nhìn dễ tưởng là chạy sai.

`keep_lane.osc` chạy **SUCCESS với 0 va chạm** trên **cùng môi trường, cùng lệnh**. Khác biệt
nằm ở nội dung kịch bản:

- `keep_lane.osc` — ego giữ làn, NPC chạy song song. Không có tình huống nguy hiểm.
- `cut_in_and_slow_range.osc` — NPC cắt vào làn ego rồi **giảm còn 10–12 km/h**, trong khi ego
  bị kịch bản ép chạy `speed([30kph..31kph])` và **không có logic phanh**.

`dut` trong OSC2 viết tắt của **Device Under Test**. Kịch bản là một **bài kiểm tra** dựng tình
huống nguy hiểm; `CollisionTest FAILURE` nghĩa là *đối tượng được kiểm tra không vượt qua*.
Ở chế độ OSC2 không cắm được agent biết tránh va chạm — xác nhận bằng chính trợ giúp của công cụ:

```
'--agent', help="Agent used to execute the route. Not compatible with non-route-based scenarios."
```

Muốn kịch bản này đạt thì phải có stack lái tự động thật thay cho xe ego chạy theo kịch bản.

### Thí nghiệm đối chứng để chứng minh đã hiểu đúng nguyên nhân

Em copy kịch bản gốc thành `my_cutin.osc` và **chỉ đổi đúng một dòng** — tốc độ NPC ở pha `slow`:

| | Tốc độ NPC pha `slow` | Va chạm | Kết quả |
|---|---|---|---|
| Gốc | `speed([10kph..12kph])` | 3 | FAILURE |
| Sửa | `speed([32kph..34kph])` | **0** | **SUCCESS** |

Mọi tham số khác giữ nguyên. Loại bỏ chênh lệch tốc độ tiếp cận (~20 km/h) thì va chạm biến mất.

---

## 3. Ba vấn đề đã gặp và cách xử lý

### 3.1 Server CARLA thoát im lặng khi khởi động

```
LogInit: Warning: Incompatible or missing module: ModelingToolsEditorMode
... (7 module)
LogCore: Engine exit requested
```

`CarlaUE4.uproject` có bật plugin `ModelingToolsEditorMode`; DLL của nó được build cho bản
engine **cũ hơn** engine hiện tại nên UE4 coi là *Incompatible*. Editor GUI chỉ cảnh báo rồi
chạy tiếp, nhưng chế độ `-game` (headless) **thoát luôn** vì không có hộp thoại hỏi rebuild.

Đối chiếu log xác nhận: lần chạy thành công cuối cùng là **trước** thời điểm plugin được bật.

**Xử lý:** bỏ plugin đó khỏi `.uproject` (CARLA không dùng tới). Sau đó: 0 cảnh báo.

### 3.2 `time-out of 10000ms` khi `load_world`

`--timeout` mặc định của Scenario Runner là **10 giây**. Bản build từ source **chưa cook** nạp
Town04 mất **370 giây**:

```
LogLoad: Took 370.046416 seconds to LoadMap(/Game/Carla/Maps/Town04)
```

Lúc đó 20 tiến trình `ShaderCompileWorker` đang biên dịch shader, kèm dựng mesh distance field
(29,7 giây cho **một** mesh cây thông).

**Xử lý:** `--timeout 600`. Chi phí này chỉ một lần cho mỗi map vì kết quả được cache (DDC).

### 3.3 Hai bug của Scenario Runner trên Windows

**a) `--outputDir` làm crash.** `scenario_runner.py:279` ghép thẳng đường dẫn file `.osc` vào
tên file kết quả, sinh ra thư mục con chưa tồn tại nên `FileNotFoundError`. Với
`--scenario <tên>` thì không lộ vì tên không chứa dấu gạch chéo.
**Vá:** tạo trước `<outputDir>/srunner/examples/`.

**b) `UnicodeEncodeError` khi in bảng kết quả.** Bảng dùng ký tự kẻ khung Unicode, console
Windows mặc định cp1252.
**Vá:** đặt `PYTHONIOENCODING=utf-8`.

*(Hai lỗi này có thể không xảy ra trên Linux — em sẽ kiểm chứng lại khi lên máy trạm.)*

---

## 4. Hiệu năng — con số cho thấy ảnh hưởng của shader cache

`Ratio (Game / System)` trong bảng kết quả = thời gian mô phỏng chia thời gian thực.

| Điều kiện | Ratio | Ý nghĩa |
|---|---|---|
| Đang biên dịch shader | *không đo được* | mô phỏng bò, đo được **~0,7 tick/giây** từ bộ đếm frame trong log UE4 |
| DDC đã ấm, có `--sync` | **6,2 → 14,3** | nhanh hơn thời gian thực 6–14 lần |
| Bỏ `--sync` | **0,99** | đúng thời gian thực (để xem bằng mắt) |

Rút ra: dùng `--sync` để chạy nhanh và tất định (thu dữ liệu); bỏ `--sync` khi cần xem trực quan.

---

## 5. Về câu hỏi "vì sao dev CARLA cần image" và "vì sao cần container riêng"

Ba vấn đề ở mục 3 **đều** là bệnh của việc build tay trên từng máy, không phải trùng hợp:

| Gặp phải trong buổi làm | Image giải quyết thế nào |
|---|---|
| Nạp map 370 s, biên dịch shader, dựng distance field lúc chạy | Image đóng gói content **đã cook** + shader biên dịch sẵn |
| Plugin lệch bản engine làm server chết im lặng | Image đóng băng một tổ hợp engine + plugin đã kiểm chứng |
| SR ghim `numpy==1.24.4`, `py-trees==0.8.3`; client CARLA cần `numpy<2.0` nên phải tách venv | Cùng nguyên lý, mở rộng ra cả thư viện hệ điều hành + driver GPU |
| Server tự xưng version `294096e` (commit hash) thay vì `0.9.16` | Image gắn nhãn version tường minh |

Việc em phải **tách venv riêng** cho Scenario Runner chính là bài toán Docker ở quy mô nhỏ: hai
dự án trên cùng một máy cần hai bộ thư viện xung khắc nhau.

**Vì sao trên máy trạm phải có container riêng:**

- Máy dùng chung — cài đè vào Python hệ thống sẽ phá phiên bản thư viện của người khác
- Mỗi server CARLA chiếm cổng **2000** (RPC) + **2001** (streaming) + **2002**, Traffic Manager
  **8000**, nên hai người chạy cùng lúc phải khác bộ cổng; container cho network namespace riêng
- Chia GPU tường minh qua `--gpus` / `NVIDIA_VISIBLE_DEVICES`
- Hỏng thì xoá container dựng lại, **không cần sudo**, không ảnh hưởng ai
- Code để ở volume mount nên code bền, môi trường là thứ vứt đi được
- Lỗi trở nên **tái lập được**, không còn tình trạng "máy em chạy được"

---

## 6. Ghi chú kỹ thuật đáng lưu ý

- **Đuôi file:** `.xosc` là OpenSCENARIO **1.x** (XML, cờ `--openscenario`); `.osc` là
  OpenSCENARIO **2.x** (ngôn ngữ riêng, parse bằng ANTLR, cờ `--openscenario2`).
- **Không cần cài Java/ANTLR tool** như tài liệu ghi — repo đã ship sẵn parser đã generate
  (`OpenSCENARIO2Parser.py`). Java chỉ cần khi muốn generate lại từ `.g4`. Chỉ cần runtime
  Python `antlr4-python3-runtime==4.10`, vì parser tự gọi `checkVersion("4.10.1")`.
- **Dòng `.egg` trên PYTHONPATH bỏ được** (module `carla` cài bằng pip), nhưng
  `%CARLA_ROOT%\PythonAPI\carla` là **bắt buộc** — srunner import `agents.navigation.*`,
  package này không có trong wheel PyPI, chỉ có trong source tree CARLA.
- Trong `srunner/examples/` có 18 file `.osc` nhưng chỉ **17 file chạy được**. `basic.osc` là
  **thư viện** khai báo đơn vị SI và actor nền, không có `scenario top:`.
- **15/17 kịch bản dùng Town04.** Nên gom kịch bản cùng map chạy liền nhau, vì
  `_set_carla_town` chỉ nạp lại map khi map hiện tại khác map cần — tránh được 370 giây nạp lại.
- Ego trong OSC2 có `role_name='ego_vehicle'`.

---

## 7. Câu hỏi gửi anh

1. Khi nào em được cấp tài khoản và quyền Docker trên workstation `robotaxi`?
2. Team đã có **image CARLA dựng sẵn** chưa, hay em tự viết Dockerfile? Nếu có thì tên
   image/registry là gì?
3. Bản CARLA trên workstation là **release đã package** hay build từ source? (quyết định có
   phải chịu 370 giây nạp map và biên dịch shader như máy này không)
4. Scenario Runner trên workstation đang ở bản nào, có khớp CARLA 0.9.16 không?
5. Trên máy dùng chung, **quy tắc chia cổng** (2000/2001/2002, TM 8000) và chia GPU thế nào?
6. Team dùng bộ kịch bản OSC2 có sẵn hay tự viết `.osc` riêng? Nếu tự viết thì em nên đọc thêm
   phần nào của chuẩn ASAM OSC 2.0?
