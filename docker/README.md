# Chạy dự án CARLA / Scenario Runner bằng Docker

Gói này chuyển toàn bộ dự án (CARLA 0.9.16, Scenario Runner, script Task 1–3, dữ liệu đã thu)
từ máy Windows sang một máy **Linux có GPU NVIDIA**.

## Gồm hai image

| Image | Nguồn | Nội dung |
|---|---|---|
| `carlasim/carla:0.9.16` | image chính thức trên Docker Hub | server CARLA, content và shader đã cook sẵn |
| `carla-vinfast-client:0.9.16` | build từ `client.Dockerfile` | Scenario Runner v0.9.16 **kèm 2 bản vá metric và kịch bản tự viết**, `my_client/`, `osm/`, PythonAPI 0.9.16, hai venv giống máy cũ |

Server không cần build lại: bản build từ source trên Windows **không sửa dòng C++ nào** so với
tag `0.9.16`. Image chính thức là cùng một phiên bản, và đã cook sẵn nên không còn mất 370 giây
khi nạp Town04 lần đầu.

Hai venv trong client giữ nguyên cách tách như trên máy cũ:

| Venv | Dùng cho | Là `python` mặc định? |
|---|---|---|
| `/opt/venv-sr` | Scenario Runner và mọi script trong `my_client/` | có |
| `/opt/venv-pyapi` | `/opt/carla/PythonAPI/examples` | không, gọi `/opt/venv-pyapi/bin/python` |

## Máy đích cần có

- Docker Engine và Docker Compose v2
- Driver NVIDIA và [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- Khoảng 30 GB ổ đĩa trống

## Cài đặt

```bash
bash import_bundle.sh            # nạp image, tạo .env và data/
docker compose up -d carla-server
docker compose ps                # chờ trạng thái "healthy"
docker compose run --rm client   # vào shell client, đứng ở /workspace
```

Trong shell client, các lệnh giống hệt `Code/Huong dan chay lai.md`, chỉ khác là không cần
`env.bat` vì image đã đặt sẵn biến môi trường:

```bash
python run_batch.py                                   # 7 kịch bản OpenSCENARIO 2
python my_client/capture_sync.py --frames 100         # thu dữ liệu cảm biến, ghi ra out/
python my_client/osm_to_map.py --osm osm/vinuni_campus.osm --road-set full
```

Mọi script vẫn gọi `127.0.0.1:2000`, **không phải sửa gì**. Lý do: client dùng chung
network namespace với server.

## Dữ liệu nằm ở đâu

| Thư mục máy đích | Trong container | Ghi chú |
|---|---|---|
| `data/out/` | `/workspace/out` | dữ liệu cảm biến |
| `data/evidence/` | `/workspace/evidence` | kết quả tiêu chí của `run_batch.py` |
| `data/recorder/` | `/workspace/scenario_runner/recorder`, **mount ở cả server lẫn client** | file `.log` của CARLA recorder |

File recorder là thứ **server** ghi và đọc, không phải client. Scenario Runner ghép thành
`$SCENARIO_RUNNER_ROOT/<--record>/<tên>.log` rồi gửi nguyên đường dẫn đó cho server. Vì vậy
thư mục này được mount ở **cùng một đường dẫn** trong cả hai container. Khi ghi, luôn đặt
`--record` bắt đầu bằng `recorder/`:

```bash
cd scenario_runner
python scenario_runner.py --scenario VinfastCutIn_1 --timeout 600 --record recorder/vinfast --output
python ../my_client/quay_video_replay.py --log /workspace/scenario_runner/recorder/vinfast/VinfastCutIn_1.log --out /workspace/out/video.mp4 --giay 40
```

Đặt `--record` ra ngoài `recorder/` thì server sẽ ghi vào bên trong container của chính nó, và
client không thấy file đó. Các file recorder cũ nằm sẵn ở `data/recorder/recorder_vinfast/`,
`recorder_osc2/` và `recordings/`.

## Xem server có cửa sổ

Mặc định server chạy `-RenderOffScreen`, tức là không có cửa sổ. Muốn nhìn kịch bản như
Task 1 (kết hợp `watch.py`):

```bash
xhost +local:
docker compose -f docker-compose.yml -f docker-compose.gui.yml up -d carla-server
```

## Nhiều người dùng chung một máy

Sửa `.env` cho mỗi người: đặt `COMPOSE_PROJECT_NAME` riêng, dải cổng riêng (ví dụ
`CARLA_HOST_PORT=3000`, `CARLA_HOST_PORT_END=3002`) và GPU riêng (`NVIDIA_VISIBLE_DEVICES=1`).
Bên trong container, server vẫn nghe ở cổng 2000, nên script không phải đổi.

## Không có trong image

| Thứ | Vì sao | Cách thay thế |
|---|---|---|
| Map Digital Twin `CustomMaps/VinUni*`, `TimesCity*`, `HoGuom1kmC` | là `.umap` chưa cook, dựng trong Unreal Editor trên Windows. Server Linux chỉ chạy được content đã cook cho Linux | **Đường OpenDRIVE** vẫn chạy được: `osm/*.xodr` có sẵn trong image, `osm_to_map.py` nạp bằng `generate_opendrive_world`, chỉ không có nhà cửa. Muốn có đủ map thì build CARLA từ source trên Linux (`Util/Docker/Development.Dockerfile`, cần tài khoản GitHub đã liên kết Epic), import map rồi `make package` |
| Unreal Editor | cần build từ source, khoảng 100 GB, vài giờ | như trên |
| `quay_map_digitaltwin.py` | cần map Digital Twin ở trên | |

## Cách khác: clone repo rồi build ngay trên máy đích

Không cần gói `export_bundle`. Máy đích chỉ cần có mạng:

```bash
git clone <repo> carla-scenario && cd carla-scenario/docker
cp .env.example .env               # sửa HOST_UID/HOST_GID = $(id -u)/$(id -g)
docker compose -f docker-compose.yml -f docker-compose.build.yml build client
mkdir -p data/out data/evidence data/recorder && chmod -R a+rwX data
docker compose up -d carla-server
docker compose run --rm client
```

Cách này không mang theo dữ liệu cũ (`out/`, `evidence/`, file recorder), vì các thư mục đó
không nằm trong git.

## Build lại image và đóng gói (trên máy Windows nguồn)

```powershell
cd D:\Hunganh\carla-scenario\docker
docker compose -f docker-compose.yml -f docker-compose.build.yml build client
powershell -ExecutionPolicy Bypass -File export_bundle.ps1   # đóng gói sang máy khác
```

Build context là gốc repo. File `.dockerignore` loại `.venv-sr`, `out/`, `evidence/` và
`scenario_runner/` ra khỏi context. Scenario Runner được clone từ tag `v0.9.16`, sau đó áp
[`scenario_runner.patch`](scenario_runner.patch).

Sửa Scenario Runner trên Windows thì phải tạo lại patch (chạy trong Git Bash):

```bash
cd scenario_runner
git diff --binary > ../docker/scenario_runner.patch
git ls-files --others --exclude-standard -- srunner | grep -v '\.bak$' | while read f; do
  git diff --no-index --binary -- /dev/null "$f"; done >> ../docker/scenario_runner.patch
```
