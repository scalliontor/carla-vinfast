# Task #1 — Scenario Runner + OpenSCENARIO 2: hồ sơ dựng môi trường

Tài liệu gốc: https://scenario-runner.readthedocs.io/en/latest/getting_scenariorunner/
Ngày dựng: 2026-09-22 · Máy: Windows 11, RTX 3090 Ti, CARLA build **từ source**

---

## 1. Môi trường cuối cùng

| Thành phần | Giá trị |
|---|---|
| CARLA | source, tag `0.9.16`, commit `294096e`, tại `D:\Hunganh\carla_tuan` |
| Scenario Runner | tag **`v0.9.16`**, tại `D:\Hunganh\carla-scenario\scenario_runner` |
| Python | 3.11.9 |
| venv | `D:\Hunganh\carla-scenario\.venv-sr` (**riêng**, xem mục 2) |
| Server | `UE4Editor.exe ... -game` (xem `start_server.bat`) |

Cây thư mục — cố ý mô phỏng workstation `/home/robotaxi/ws_quyet/carla-scenario/`:

```
D:\Hunganh\carla-scenario\
├── scenario_runner\     clone v0.9.16
├── .venv-sr\            venv riêng
├── env.bat              biến môi trường
├── start_server.bat     khởi động CARLA server
├── my_client\           script Task #2
├── out\                 dữ liệu cảm biến
├── notes\               ghi chú
└── evidence\            bằng chứng nộp mentor
```

CARLA source **không bị đụng vào** (trừ 1 sửa lỗi ở mục 4) → `git status` của repo CARLA sạch.

---

## 2. Vì sao phải dùng venv RIÊNG — không phải cẩn thận thừa

`requirements.txt` của Scenario Runner ghim cứng:

```
py-trees==0.8.3            ← bản 1.x đổi tên hằng số API, srunner chưa hỗ trợ
antlr4-python3-runtime==4.10
numpy==1.24.4
networkx==3.4.2
Shapely==2.1.1
xmlschema==1.0.18
opencv-python==4.7.0.72
```

Venv client CARLA đang chạy được có `numpy 1.26.4`, `networkx 3.6.1`, `Shapely 2.1.2`.
**Cài đè sẽ hạ cấp cả ba** và có thể phá môi trường đang hoạt động.

> Đây chính là lập luận Docker ở quy mô nhỏ: hai dự án trên **cùng một máy** cần hai bộ
> thư viện **xung khắc nhau**. Một người → tách bằng venv. Nhiều người trên máy trạm
> dùng chung, cần khoá cả thư viện hệ điều hành + driver GPU → tách bằng **container**.

Lưu ý: `carla` **không** nằm trong `requirements.txt`, phải cài riêng:
`pip install carla==0.9.16`

---

## 3. Điều tài liệu bảo làm mà thực tế KHÔNG cần

### 3.1 Không cần cài Java / ANTLR tool

Tài liệu mục "OpenSCENARIO 2.0 support" bảo cài `openjdk-17-jdk`, tải
`antlr-4.10.1-complete.jar`, đặt `CLASSPATH`.

**Không cần.** Repo đã ship sẵn parser đã generate:

```
srunner/osc2/osc2_parser/OpenSCENARIO2Parser.py     ← đã có sẵn
srunner/osc2/osc2_parser/OpenSCENARIO2Lexer.py
srunner/osc2/osc2_parser/OpenSCENARIO2Listener.py
srunner/osc2/osc2_parser/OpenSCENARIO2.g4           ← grammar nguồn
```

Java + file `.jar` chỉ cần khi muốn **generate lại** parser từ `.g4`. Ta chỉ cần
**runtime Python** `antlr4-python3-runtime==4.10`, đã có trong requirements.

Vì sao đúng đúng bản 4.10? Vì parser sinh sẵn tự kiểm tra:
```python
# OpenSCENARIO2Parser.py:11798
self.checkVersion("4.10.1")
```
Lệch version → `ANTLR runtime and generated code versions disagree`. Đây là lỗi số 1
của OSC2, và venv riêng bảo vệ ta khỏi việc pip nâng cấp ngầm.

### 3.2 Bỏ qua dòng `.egg` trên PYTHONPATH

Tài liệu yêu cầu 2 đường dẫn:

```
%CARLA_ROOT%\PythonAPI\carla\dist\carla-<VERSION>.egg   ← BỎ QUA
%CARLA_ROOT%\PythonAPI\carla                            ← BẮT BUỘC
```

- Dòng 1 bỏ được vì `dist\` đang trống (chưa chạy `BuildPythonAPI.bat`), và module
  `carla` đã cài bằng pip vào venv → `import carla` vẫn tìm thấy.
- Dòng 2 **bắt buộc**: srunner import `agents.navigation.*` (BasicAgent, LocalPlanner,
  GlobalRoutePlanner). Package `agents` **không** nằm trong wheel PyPI, chỉ có trong
  source tree CARLA. Thiếu → `ModuleNotFoundError: No module named 'agents'`.

---

## 4. Hai lỗi thật đã gặp và cách sửa

### Lỗi 1 — Server thoát ngay khi khởi động: `Incompatible or missing module`

**Triệu chứng** (`Unreal/CarlaUE4/Saved/Logs/CarlaUE4.log`):
```
LogInit: Warning: Incompatible or missing module: ModelingToolsEditorMode
LogInit: Warning: Incompatible or missing module: MeshModelingTools
... (7 module)
LogCore: Engine exit requested (reason: EngineExit() was called)
```

**Nguyên nhân gốc:** `CarlaUE4.uproject` bị sửa lúc 19/09 21:39, thêm:
```json
{ "Name": "ModelingToolsEditorMode", "Enabled": true }
```
DLL của plugin này **có tồn tại** nhưng được build cho bản engine **cũ hơn** engine vừa
rebuild → UE4 coi là "Incompatible". Editor GUI chỉ cảnh báo rồi chạy tiếp, nhưng chế độ
`-game` không có hộp thoại hỏi rebuild nên **thoát luôn**.

Bằng chứng mốc thời gian:

| Thời điểm | Việc | Log |
|---|---|---|
| 19/09 21:17 | editor GUI + bấm Play | **thành công**, 3.4 MB |
| 19/09 21:39:21 | uproject bị sửa | — |
| 19/09 21:39 | chạy lại | **gãy**, 9.8 KB |
| 22/09 10:45 | chạy lại | **gãy**, 10 KB |

**Cách sửa:** bỏ 4 dòng đó khỏi `CarlaUE4.uproject`. CARLA không cần plugin này (nó là
công cụ sửa mesh trong editor). Sau khi sửa: **0 cảnh báo** missing module.
Bản backup: `D:\Hunganh\carla-scenario\CarlaUE4.uproject.bak_with_modelingtools`

**Bài học:** bật plugin trong UE editor sẽ ghi vào `.uproject`. Nếu plugin đó chưa được
biên dịch khớp engine, chế độ `-game`/headless sẽ chết im lặng.

### Lỗi 2 — `time-out of 10000ms` khi load map

**Triệu chứng:**
```
File "srunner/scenarioconfigs/osc2_scenario_configuration.py", line 423, in _set_carla_town
    self.client.load_world(self.town)
RuntimeError: time-out of 10000ms while waiting for the simulator
```

**Quan trọng:** lỗi này xảy ra **sau** khi file `.osc` đã parse xong (chạy tới được bước
đặt map) → chuỗi ANTLR hoạt động tốt. Vấn đề hoàn toàn nằm ở thời gian nạp map.

**Nguyên nhân:** bản build **từ source chưa cook** phải biên dịch shader khi nạp map lần đầu:
```
LogLoad: Took 370.046416 seconds to LoadMap(/Game/Carla/Maps/Town04)
```
**370 giây** — trong khi `scenario_runner.py:578` đặt `--timeout` mặc định **10.0 giây**.
Lúc đó có 20 tiến trình `ShaderCompileWorker` chạy song song.

**Cách sửa:** `--timeout 600`. Lần nạp sau nhanh hơn nhiều vì shader đã vào cache (DDC).

**Bài học:** đây là khác biệt lớn giữa bản **source** và bản **release đã package**.
Bản release nạp map trong vài giây vì content đã cook sẵn. → Cũng là một lý do nữa
để dùng **image dựng sẵn** thay vì build tay trên từng máy.

### Đường cụt đã thử — `CarlaUE4.exe` standalone

Đã thử chạy thẳng `Unreal\CarlaUE4\Binaries\Win64\CarlaUE4.exe` (173 MB) để né module editor.
Không được:
```
Your application is built to load COOKED content. No COOKED content was found;
This usually means you did not cook content for this build.
```
Muốn dùng cách này phải chạy `Package.bat` trước (~2-4 giờ). → Bỏ.

---

## 5. Cảnh báo version — tiếng ồn, không phải lỗi

```
WARNING: Version mismatch detected
WARNING: Client API version     = 0.9.16
WARNING: Simulator API version  = 294096e
```

`294096e` là **commit hash của chính tag 0.9.16** (khớp `git log`). Bản build từ source tự
đặt tên theo commit thay vì semver.

Không chặn Scenario Runner, vì srunner kiểm tra version qua **package pip**, không qua server:
```python
# scenario_runner.py:46
return Version(pkg_resources.get_distribution("carla").version)   # -> 0.9.16
# scenario_runner.py:62
MIN_CARLA_VERSION = '0.9.14'                                      # 0.9.16 >= 0.9.14 -> qua
```

---

## 6. Quy trình chạy (tóm tắt để làm lại)

```bat
REM  Cua so 1 — server (doi ~1-6 phut lan dau moi map)
cd /d D:\Hunganh\carla-scenario
start_server.bat

REM  Cua so 2 — kich ban
cd /d D:\Hunganh\carla-scenario
call env.bat
cd scenario_runner
"%SR_PYTHON%" scenario_runner.py --sync --timeout 600 ^
    --openscenario2 srunner/examples/cut_in_and_slow_range.osc --reloadWorld
```

`--openscenario2` là cờ đúng (`scenario_runner.py:597`).

---

## 7. Đuôi file — chỗ rất dễ nhầm

| Chuẩn | Đuôi | Định dạng | Cờ |
|---|---|---|---|
| OpenSCENARIO **1.x** | `.xosc` | XML | `--openscenario` |
| OpenSCENARIO **2.x** | `.osc` | ngôn ngữ riêng, parse bằng ANTLR | `--openscenario2` |

Mentor giao **OSC2** → dùng `.osc`.

Trong `srunner/examples/` có **18 file `.osc`**, nhưng:
- **17 file chạy được** (có `scenario top:`)
- **`basic.osc` KHÔNG chạy được** — nó là **file thư viện**, chỉ khai báo đơn vị SI
  (`kph`, `m`, `s`, `deg`) và actor nền (`dut`, `Path`, `Model3`, `Rubicon`).
  Các file khác mở đầu bằng `import basic.osc`.

Map mà kịch bản yêu cầu nằm ở biến `global my_map` trong chính file `.osc`
(vd `cut_in_and_slow_range.osc` → `"Town04"`).

---

## 8. Bug 3 — `--outputDir` làm crash khi dùng với OSC2

**Triệu chứng:**
```
FileNotFoundError: [Errno 2] No such file or directory:
  'D:\Hunganh\carla-scenario\evidence\task1\srunner/examples/cut_in_and_slow_range.osc2026-...json'
```

**Nguyên nhân** — `scenario_runner.py:279`:
```python
config_name = os.path.join(self._args.outputDir, config_name)
```
Với OSC2, `config_name` **chính là đường dẫn file `.osc`** (`srunner/examples/x.osc`), nên ghép
vào thành đường dẫn có thư mục con `srunner/examples/` chưa tồn tại.

Với `--scenario FollowLeadingVehicle_1` thì tên không có dấu `/` nên không lộ bug.

Tệ hơn — `result_writer.py:49-63` chạy theo thứ tự: ghi junit → ghi json → tạo text →
ghi txt → **`print(output)`**. Crash ở bước json **nuốt luôn** bảng tiêu chí đáng lẽ in ra.

**Cách vá:** tạo trước thư mục `<outputDir>\srunner\examples\`.

## 9. Bug 4 — `UnicodeEncodeError` khi in bảng kết quả

**Triệu chứng:**
```
File "...\result_writer.py", line 63, in write
    print(output)
UnicodeEncodeError: 'charmap' codec can't encode characters in position 233-279
```

Bảng kết quả dùng ký tự kẻ khung Unicode (`╒ ═ ╤ │ ╘`), console Windows mặc định **cp1252**
không mã hoá được.

**Cách vá:** đặt `PYTHONIOENCODING=utf-8` trước khi chạy.

Lưu ý: file `.txt`/`.json` **vẫn được ghi đúng** dù stdout crash, vì chúng mở bằng
`encoding='utf-8'` tường minh và ghi **trước** lệnh `print`. Nên khi gặp lỗi này, cứ vào
`evidence/task1/srunner/examples/` là có đủ kết quả.

---

## 10. Đọc hiểu kết quả — điểm quan trọng nhất của Task #1

### Hiệu năng: chứng minh được ảnh hưởng của shader cache

Cùng một kịch bản, cùng một máy, chỉ khác việc shader đã cache hay chưa:

| Lần chạy | Nhịp mô phỏng | Ghi chú |
|---|---|---|
| Khi đang biên dịch shader | **~0,7 tick/giây** | frame `[446]→[501]` trong 80 s |
| Sau khi DDC ấm | **Ratio 6,222** | 56,05 s mô phỏng trong 9,01 s thực |

`Ratio (Game / System)` trong bảng kết quả là số cần nhìn: **>1 là mô phỏng chạy nhanh hơn
thời gian thực**. Đây là chi phí **một lần cho mỗi map**.

### FAILURE không đồng nghĩa với "làm sai"

| Kịch bản | Kết quả | Va chạm |
|---|---|---|
| `keep_lane.osc` | **SUCCESS** | 0 |
| `cut_in_and_slow_range.osc` | **FAILURE** | 3 |

Cùng môi trường, cùng lệnh. Khác biệt nằm ở **nội dung kịch bản**:

- `keep_lane.osc` — ego giữ làn, NPC chạy song song. Không có tình huống nguy hiểm → 0 va chạm.
- `cut_in_and_slow_range.osc` — NPC **cắt vào làn ego rồi giảm còn 10–12 kph**, trong khi ego
  bị kịch bản ép chạy `speed([30kph..31kph])` và **không có logic phanh** → đâm là tất yếu.

Chìa khoá: `dut` trong OSC2 = **Device Under Test**. Kịch bản là một **bài kiểm tra**, và
`CollisionTest FAILURE` nghĩa là *đối tượng được kiểm tra đã không vượt qua*, không phải
môi trường hỏng.

Xác nhận bằng chính trợ giúp của công cụ:
```
'--agent', help="Agent used to execute the route. Not compatible with non-route-based scenarios."
```
→ Ở chế độ OSC2 **không cắm được** agent biết tránh va chạm; xe ego chạy theo `speed()`/`lane()`
ghi cứng trong file `.osc`. Muốn kịch bản này đạt thì phải có stack lái tự động thật.

---

## 11. Map của từng kịch bản — và vì sao phải để ý

`_set_carla_town` (`osc2_scenario_configuration.py:410-424`) **chỉ nạp lại map khi map hiện tại
khác map cần**:
```python
if world is None or (wmap is not None and wmap.name.split("/")[-1] != self.town):
    self.client.load_world(self.town)
```
→ Ở sẵn đúng map thì **bỏ qua hoàn toàn** bước nạp 370 giây. Vì vậy nên **gom các kịch bản
cùng map chạy liền nhau**.

**15/17 kịch bản dùng Town04.** Chỉ 2 ngoại lệ:
`cut_in_and_slow_single_over_junction.osc` → Town03 · `follow_trajectory.osc` → Town10HD_Opt

Lưu ý khi tra map: có file khai báo qua `global my_map`, có file gọi thẳng
`path.set_map("Town04")` trong `scenario top:`. Grep một kiểu sẽ sót.

---

## 12. Lệnh chuẩn (đã gộp cả 4 cách vá)

```bat
set PYTHONIOENCODING=utf-8
mkdir D:\Hunganh\carla-scenario\evidence\task1\srunner\examples
"%SR_PYTHON%" scenario_runner.py --sync --timeout 600 ^
    --openscenario2 srunner/examples/keep_lane.osc ^
    --output --file --json --outputDir D:\Hunganh\carla-scenario\evidence\task1
```

Hoặc dùng `run_batch.py` — đã gộp sẵn cả 4 cách vá và in bảng tổng kết.
