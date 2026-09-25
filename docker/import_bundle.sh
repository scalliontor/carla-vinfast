#!/usr/bin/env bash
# ============================================================================
#  Cai goi du an tren MAY DICH (Linux + GPU NVIDIA)
#
#    bash import_bundle.sh
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

SERVER_IMAGE=carlasim/carla:0.9.16
CLIENT_IMAGE=carla-vinfast-client:0.9.16

command -v docker >/dev/null || { echo "Chua cai Docker"; exit 1; }
docker compose version >/dev/null || { echo "Chua co Docker Compose v2"; exit 1; }
if ! docker info 2>/dev/null | grep -qi nvidia; then
    echo "CANH BAO: khong thay nvidia runtime - can cai NVIDIA Container Toolkit,"
    echo "          neu khong server CARLA se khong co GPU."
fi

echo "[1/3] Nap image..."
docker load -i images/client.tar
if [ -f images/server.tar ]; then
    docker load -i images/server.tar
elif ! docker image inspect "$SERVER_IMAGE" >/dev/null 2>&1; then
    docker pull "$SERVER_IMAGE"
fi

echo "[2/3] Chuan bi .env va thu muc du lieu..."
[ -f .env ] || cp .env.example .env
mkdir -p data/out data/evidence data/recorder
# Server (user carla trong image chinh thuc) va client co the khac UID voi
# user may dich -> mo quyen ghi cho ca hai.
chmod -R a+rwX data

echo "[3/3] Kiem tra image client..."
docker run --rm "$CLIENT_IMAGE" python -c "import carla, agents; print('client OK')"

cat <<'EOF'

Xong. Cac buoc tiep theo:
  docker compose up -d carla-server        # doi den khi 'healthy': docker compose ps
  docker compose run --rm client           # vao shell client
    python run_batch.py                    #   vi du: chay 7 kich ban OSC2
Nhieu nguoi dung chung may: sua COMPOSE_PROJECT_NAME va dai cong trong .env
EOF
