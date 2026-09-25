#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quay video kịch bản bằng cách PHÁT LẠI file recorder
=====================================================

VÌ SAO KHÔNG QUAY MÀN HÌNH
    Quay màn hình dính cả cửa sổ Editor, thanh tiêu đề, chuột. Cách này gắn
    thẳng một camera vào xe trong mô phỏng nên hình sạch, và quan trọng hơn:
    KHÔNG cần chạy lại kịch bản. File `.log` của recorder đã ghi đủ mọi vị trí,
    phát lại là dựng lại nguyên trạng.

    Đây cũng chính là thứ module Metrics dựa vào — nó đọc file `.log` này
    chứ không bao giờ chạy lại mô phỏng.

LƯU Ý VỀ ID ACTOR
    Khi phát lại, CARLA tạo actor MỚI với id MỚI, không trùng id lúc ghi.
    Vì vậy phải tìm xe theo thuộc tính `role_name == 'hero'` sau khi phát lại
    đã khởi động, chứ không dùng lại id cũ.

CHẠY
    python my_client\quay_video_replay.py ^
        --log scenario_runner\recorder_vinfast\VinfastCutIn_1.log ^
        --out "duong\dan\video.mp4" --giay 40
"""

import argparse
import os
import sys
import time
from queue import Queue, Empty

import carla
import cv2
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

W, H = 1280, 720


def tim_hero(world, cho_toi_da=25.0):
    """Chờ tới khi phát lại đã dựng xong xe ego."""
    t0 = time.time()
    while time.time() - t0 < cho_toi_da:
        xe = list(world.get_actors().filter("vehicle.*"))
        for v in xe:
            if v.attributes.get("role_name") == "hero":
                return v, xe
        if xe:
            # Khong co 'hero' thi lay xe co id nho nhat — recorder dung ego truoc.
            return sorted(xe, key=lambda a: a.id)[0], xe
        time.sleep(0.5)
    return None, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="file .log cua recorder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--giay", type=float, default=40.0, help="do dai phat lai")
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--tieu-de", default="")
    args = ap.parse_args()

    client = carla.Client("127.0.0.1", 2000)
    client.set_timeout(120.0)

    # Bao server phat lai. Tham so: (file, giay bat dau, do dai, id de bam theo,
    # co phat lai ca cam bien khong). 0 = phat het, 0 = khong bam theo ai.
    print("[1/4] Bao server phat lai:", os.path.basename(args.log))
    print(client.replay_file(os.path.abspath(args.log), 0.0, args.giay + 10, 0, False))

    world = client.get_world()
    xe, tat_ca = tim_hero(world)
    if xe is None:
        raise SystemExit("Khong tim thay xe nao sau khi phat lai — kiem tra file .log")
    print("[2/4] Bam camera vao: %s id=%d  (tong %d xe trong canh)"
          % (xe.type_id, xe.id, len(tat_ca)))

    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(W))
    bp.set_attribute("image_size_y", str(H))
    bp.set_attribute("fov", "90")
    bp.set_attribute("sensor_tick", str(1.0 / args.fps))

    # Camera duoi phia sau — nhin thay ca xe ego lan xe cat dau.
    tf = carla.Transform(carla.Location(x=-7.5, z=3.6), carla.Rotation(pitch=-13))
    cam = world.spawn_actor(bp, tf, attach_to=xe)

    q = Queue()
    cam.listen(q.put)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"),
                         args.fps, (W, H))

    print("[3/4] Dang quay %.0f giay ..." % args.giay)
    t0 = time.time()
    n = 0
    try:
        while time.time() - t0 < args.giay:
            try:
                img = q.get(timeout=2.0)
            except Empty:
                continue
            a = np.frombuffer(img.raw_data, dtype=np.uint8).reshape((H, W, 4))
            frame = a[:, :, :3].copy()          # BGRA -> BGR

            if args.tieu_de:
                cv2.rectangle(frame, (0, 0), (W, 46), (0, 0, 0), -1)
                cv2.putText(frame, args.tieu_de, (16, 32), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, "t = %5.1f s" % (time.time() - t0), (W - 190, H - 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            vw.write(frame)
            n += 1
    finally:
        # Go cam bien TRUOC khi lam bat cu viec gi khac — de treo lai server.
        cam.stop()
        cam.destroy()
        vw.release()
        client.stop_replayer(False)

    print("[4/4] Da ghi: %s  (%.1f MB, %d frame)"
          % (args.out, os.path.getsize(args.out) / 1e6, n))


if __name__ == "__main__":
    main()
