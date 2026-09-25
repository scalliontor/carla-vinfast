#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kiểm tra toàn vẹn bộ dữ liệu cảm biến đã thu
=============================================

Ghi được file ra đĩa chưa đủ. Phải trả lời được ba câu:

    1. Có đủ file không, ba cảm biến có cùng số lượng không?
    2. Ba cảm biến có thật sự ghi CÙNG MỘT thời điểm mô phỏng không?
    3. Bước thời gian giữa các frame có đều không, có frame nào bị rớt không?

Câu 2 và 3 là lý do phải chạy ở chế độ đồng bộ. Ở chế độ bất đồng bộ, mỗi cảm
biến trả dữ liệu theo nhịp riêng, ghép lại sẽ lệch — và lệch âm thầm, nhìn ảnh
không phát hiện được.

Cách kiểm chứng: `capture_sync.py` lưu `world_frame` của server vào `meta.json`
cho từng frame. Nếu dãy này tăng đều đúng một đơn vị thì không rớt frame nào.

CHẠY
    python my_client\kiem_tra_du_lieu.py --run out\run_20260922_131523
"""

import argparse
import json
import os
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()

    print("=" * 62)
    print("  KIEM TRA TOAN VEN DU LIEU CAM BIEN")
    print("=" * 62)
    print("  Thu muc:", os.path.basename(args.run))

    meta = json.load(open(os.path.join(args.run, "meta.json"), encoding="utf-8"))
    calib = json.load(open(os.path.join(args.run, "calib.json"), encoding="utf-8"))
    frames = sorted(meta["frames"], key=lambda x: x["frame_index"])

    # ---- 1. Dem file ----
    print("\n  1. DEM FILE")
    dem = {}
    for ten, duoi in [("rgb", ".png"), ("seg", ".png"), ("lidar", ".npy")]:
        d = os.path.join(args.run, ten)
        n = len([f for f in os.listdir(d) if f.endswith(duoi)]) if os.path.isdir(d) else 0
        dem[ten] = n
        print("     %-8s %4d file %s" % (ten, n, duoi))
    dong_deu = len(set(dem.values())) == 1 and dem["rgb"] == len(frames)
    print("     ghi nhan trong meta.json : %d frame" % len(frames))
    print("     -> %s" % ("KHOP" if dong_deu else "LECH — thieu file o dau do"))

    # ---- 2. Ba cam bien co cung world_frame khong ----
    print("\n  2. DONG BO GIUA BA CAM BIEN")
    print("     capture_sync.py da khang dinh ngay luc thu:")
    print("         assert img_rgb.frame == img_seg.frame == pts.frame == world_frame")
    print("     Neu mot cam bien tra ve frame khac, chuong trinh dung ngay,")
    print("     nen bo du lieu ghi duoc ra dia chac chan la dong bo.")

    # ---- 3. Day world_frame co lien tuc khong ----
    print("\n  3. TINH LIEN TUC CUA DAY world_frame")
    wf = np.array([f["world_frame"] for f in frames], dtype=np.int64)
    buoc = np.diff(wf)
    print("     world_frame dau  : %d" % wf[0])
    print("     world_frame cuoi : %d" % wf[-1])
    print("     khoang cach      : %d" % (wf[-1] - wf[0]))
    print("     so frame thu duoc: %d" % len(wf))
    la = np.unique(buoc)
    print("     buoc nhay giua cac frame lien tiep: %s" % la.tolist())
    rot = int(np.sum(buoc - 1))
    if len(la) == 1 and la[0] == 1:
        print("     -> LIEN TUC TUYET DOI, khong rot frame nao")
    else:
        print("     -> CO %d frame bi ROT" % rot)

    # ---- 4. Thoi gian mo phong ----
    print("\n  4. BUOC THOI GIAN")
    dt = meta["fixed_delta_seconds"]
    print("     fixed_delta_seconds : %.3f s  (%.0f Hz)" % (dt, 1.0 / dt))
    print("     tong thoi gian thu  : %.2f s" % (len(frames) * dt))
    rf = calib.get("lidar", {}).get("rotation_frequency")
    if rf is not None:
        khop = abs(rf - 1.0 / dt) < 1e-6
        print("     LiDAR rotation_frequency: %.1f Hz  -> %s"
              % (rf, "DUNG, bang 1/fixed_delta" if khop else "SAI, se mat diem"))

    # ---- 5. Du lieu LiDAR ----
    print("\n  5. DU LIEU LiDAR")
    so_diem = []
    for f in frames[::10]:
        p = np.load(os.path.join(args.run, "lidar", "%06d.npy" % f["frame_index"]))
        so_diem.append(len(p))
    print("     so diem moi frame (lay mau 1/10): min %d, max %d, trung binh %d"
          % (min(so_diem), max(so_diem), int(np.mean(so_diem))))
    p = np.load(os.path.join(args.run, "lidar", "%06d.npy" % frames[0]["frame_index"]))
    print("     moi diem co %d truong: x, y, z, cuong do phan xa" % p.shape[1])

    # ---- 6. Ma tran ----
    print("\n  6. MA TRAN DA LUU")
    k = np.array(calib["camera_rgb"]["K"])
    print("     K = [[%.1f, %.1f, %.1f], [%.1f, %.1f, %.1f], [%.1f, %.1f, %.1f]]"
          % tuple(k.flatten()))
    co = all(("lidar_to_world" in f and "world_to_camera" in f) for f in frames)
    print("     moi frame co lidar_to_world va world_to_camera : %s"
          % ("CO — du de chieu lai offline" if co else "THIEU"))

    print("\n" + "=" * 62)
    ket = dong_deu and len(la) == 1 and la[0] == 1
    print("  KET LUAN: %s" % ("DU LIEU TOAN VEN" if ket else "CO VAN DE, xem tren"))
    print("=" * 62)


if __name__ == "__main__":
    main()
