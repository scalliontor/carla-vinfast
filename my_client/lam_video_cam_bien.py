#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ghép video từ dữ liệu cảm biến đã thu
======================================

Chạy HOÀN TOÀN OFFLINE: chỉ đọc thư mục `out/run_*`, không cần server CARLA.
Làm được như vậy vì `capture_sync.py` đã lưu sẵn mọi ma trận biến đổi vào
`meta.json` — đó chính là lý do phải lưu chúng ngay lúc thu.

Mỗi khung hình video gồm ba ô cạnh nhau:

    Camera RGB  |  Semantic segmentation  |  RGB có điểm LiDAR chiếu lên

Ô thứ ba là phần đáng xem nhất: nó chứng minh chuỗi biến đổi toạ độ đúng.
Nếu sai dù chỉ một dấu trừ, đám điểm sẽ lệch khỏi mặt đường thấy ngay.

CHẠY
    python my_client\lam_video_cam_bien.py --run out\run_20260922_131523 ^
        --out "duong\dan\video.mp4"
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def chieu_lidar(pts, k, lidar_to_world, world_to_camera, w, h):
    """Chiếu đám mây điểm LiDAR lên mặt phẳng ảnh. Xem lidar_on_image.py."""
    local = np.r_[pts[:, :3].T, np.ones((1, pts.shape[0]))]
    world = lidar_to_world @ local
    cam = world_to_camera @ world

    # Doi quy uoc truc UE4 -> OpenCV. Day la cho hay sai nhat ca quy trinh.
    cam_cv = np.array([cam[1], -cam[2], cam[0]])

    uvw = k @ cam_cv
    depth = uvw[2]
    # Chia cho thanh phan thu ba = phep chieu phoi canh.
    uv = uvw[:2] / np.maximum(depth, 1e-6)

    ok = (depth > 0.1) & (uv[0] >= 0) & (uv[0] < w) & (uv[1] >= 0) & (uv[1] < h)
    return uv[:, ok].astype(np.int32), depth[ok]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=10)
    args = ap.parse_args()

    calib = json.load(open(os.path.join(args.run, "calib.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(args.run, "meta.json"), encoding="utf-8"))
    k = np.array(calib["camera_rgb"]["K"])

    frames = sorted(meta["frames"], key=lambda x: x["frame_index"])
    print("Tong so frame:", len(frames))

    # Bang mau theo khoang cach, dung lai cua OpenCV cho nhanh.
    vw = None
    for n, fm in enumerate(frames):
        i = fm["frame_index"]
        rgb = cv2.imread(os.path.join(args.run, "rgb", "%06d.png" % i))
        seg = cv2.imread(os.path.join(args.run, "seg", "%06d.png" % i))
        pts = np.load(os.path.join(args.run, "lidar", "%06d.npy" % i))
        if rgb is None or seg is None:
            continue
        h, w = rgb.shape[:2]

        uv, d = chieu_lidar(pts, k,
                            np.array(fm["lidar_to_world"]),
                            np.array(fm["world_to_camera"]), w, h)

        phu = rgb.copy()
        if len(d):
            # Mau: gan = vang, xa = tim. Chuan hoa theo nguong 80 m cua LiDAR.
            t = np.clip(d / 80.0, 0, 1)
            mau = cv2.applyColorMap((t * 255).astype(np.uint8), cv2.COLORMAP_PLASMA)
            mau = mau.reshape(-1, 3)
            for (u, v), c in zip(uv.T, mau):
                cv2.circle(phu, (int(u), int(v)), 2, tuple(int(x) for x in c), -1)

        def nhan(img, chu, phu_chu=""):
            img = img.copy()
            cv2.rectangle(img, (0, 0), (w, 62), (0, 0, 0), -1)
            cv2.putText(img, chu, (14, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (255, 255, 255), 2, cv2.LINE_AA)
            if phu_chu:
                cv2.putText(img, phu_chu, (14, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                            (170, 220, 255), 1, cv2.LINE_AA)
            return img

        ghep = np.hstack([
            nhan(rgb, "Camera RGB", "1280x720, FOV 90 do"),
            nhan(seg, "Semantic segmentation", "khop tung pixel voi anh RGB"),
            nhan(phu, "LiDAR chieu len anh RGB", "%d diem trong khung hinh" % len(d)),
        ])

        # Thanh chan duoi ghi so frame — chung minh khong ro frame nao.
        chan = np.zeros((54, ghep.shape[1], 3), np.uint8)
        cv2.putText(chan, "frame %3d/%d   world_frame = %d   fixed_delta = %.2f s"
                    % (i, len(frames) - 1, fm["world_frame"], meta["fixed_delta_seconds"]),
                    (18, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (230, 230, 230), 2, cv2.LINE_AA)
        ghep = np.vstack([ghep, chan])

        # Thu nho lai cho file nhe; 3840 px ngang la qua kho de xem tren Drive.
        ghep = cv2.resize(ghep, (1920, int(ghep.shape[0] * 1920 / ghep.shape[1])))

        if vw is None:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"),
                                 args.fps, (ghep.shape[1], ghep.shape[0]))
        vw.write(ghep)
        if n % 20 == 0:
            print("  ...%d/%d" % (n, len(frames)))

    if vw is not None:
        vw.release()
        print("Da ghi: %s  (%.1f MB, %d frame, %d fps)"
              % (args.out, os.path.getsize(args.out) / 1e6, len(frames), args.fps))


if __name__ == "__main__":
    main()
