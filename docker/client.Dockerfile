# syntax=docker/dockerfile:1.7
# ============================================================================
#  Image CLIENT: Scenario Runner + script Task 1-3 + PythonAPI cua CARLA 0.9.16
# ----------------------------------------------------------------------------
#  Server KHONG build o day: dung thang image chinh thuc carlasim/carla:0.9.16.
#  Ban build tu source tren may Windows khong sua dong C++ nao (git diff chi
#  khac 1 dau xuong dong + 1 widget), nen server chinh thuc la cung mot ban.
#
#  Build context = goc repo carla-scenario (loc bang .dockerignore o goc).
#  Xem docker/docker-compose.build.yml.
# ============================================================================
FROM python:3.11.9-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgl1/libglib2.0-0: opencv-python (ban ghim cua Scenario Runner la ban co GUI)
# libjpeg/libpng/libtiff/libgomp1: thu vien dong ma wheel carla tren Linux can
# graphviz: py_trees ve cay hanh vi
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git ca-certificates \
        libgl1 libglib2.0-0 libgomp1 \
        libjpeg62-turbo libpng16-16 libtiff6 \
        graphviz \
 && rm -rf /var/lib/apt/lists/*

# PythonAPI cua CARLA dung tag 0.9.16. Cay PythonAPI tren may Windows sach
# (git status khong co thay doi), nen clone tag == ban dang dung.
# Can `agents` vi Scenario Runner import agents.navigation.* - package nay
# KHONG nam trong wheel carla tren PyPI.
ARG CARLA_TAG=0.9.16
RUN git clone --depth 1 --branch ${CARLA_TAG} --filter=blob:none --sparse \
        https://github.com/carla-simulator/carla.git /opt/carla \
 && git -C /opt/carla sparse-checkout set PythonAPI/carla/agents PythonAPI/examples PythonAPI/util \
 && rm -rf /opt/carla/.git /opt/carla/PythonAPI/examples/nvidia/cosmos/client/example_data

# Hai venv tach rieng, giong het may Windows:
#   venv-sr    : Scenario Runner ghim numpy==1.24.4, py-trees==0.8.3, networkx==3.4.2
#   venv-pyapi : PythonAPI/examples, numpy 1.26.4 - cai chung se ha cap goi
COPY docker/requirements-sr.txt docker/requirements-pyapi.txt /tmp/
RUN python -m venv /opt/venv-sr \
 && /opt/venv-sr/bin/pip install --no-cache-dir -r /tmp/requirements-sr.txt \
 && python -m venv /opt/venv-pyapi \
 && /opt/venv-pyapi/bin/pip install --no-cache-dir -r /tmp/requirements-pyapi.txt

# User non-root, UID khop voi user tren may dich de file ghi ra volume khong
# bi dinh quyen root.
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} carla && useradd -m -u ${UID} -g ${GID} carla

# Scenario Runner v0.9.16 (commit 94ff3b8) + phan da sua tren may Windows:
# 2 ban va metric (set_timeout, parser doc log 0.9.16) va kich ban tu viet.
# Luu duoi dang patch vi scenario_runner/ la repo git rieng, khong commit
# thang vao repo nay duoc.
ARG SR_TAG=v0.9.16
COPY docker/scenario_runner.patch /tmp/
RUN git clone --depth 1 --branch ${SR_TAG} \
        https://github.com/carla-simulator/scenario_runner.git /workspace/scenario_runner \
 && git -C /workspace/scenario_runner apply --whitespace=nowarn /tmp/scenario_runner.patch \
 && rm -rf /workspace/scenario_runner/.git \
 && chown -R carla:carla /workspace

WORKDIR /workspace
COPY --chown=carla:carla . /workspace
RUN mkdir -p /workspace/out /workspace/evidence /workspace/scenario_runner/recorder \
 && chown carla:carla /workspace/out /workspace/evidence /workspace/scenario_runner/recorder

ENV CARLA_ROOT=/opt/carla \
    SCENARIO_RUNNER_ROOT=/workspace/scenario_runner \
    PYTHONPATH=/opt/carla/PythonAPI/carla \
    SR_PYTHON=/opt/venv-sr/bin/python \
    PATH=/opt/venv-sr/bin:$PATH

USER carla

# Kiem tra ngay luc build: import duoc carla, agents va Scenario Runner.
RUN python -c "import carla, agents.navigation.basic_agent, py_trees, cv2; print('venv-sr OK', carla.__file__)" \
 && cd /workspace/scenario_runner && python scenario_runner.py --help > /dev/null \
 && /opt/venv-pyapi/bin/python -c "import carla, pygame, numpy; print('venv-pyapi OK')"

CMD ["bash"]
