#!/usr/bin/env python
"""
Chiếu đám mây điểm LiDAR lên ảnh RGB — bài kiểm chứng hệ toạ độ
================================================================

VÌ SAO BÀI NÀY QUAN TRỌNG
    Hệ toạ độ là nguồn sai lầm ÂM THẦM số một khi thu dữ liệu cảm biến. Sai một
    dấu trừ thì script vẫn chạy, vẫn ra ảnh, vẫn ghi file — chỉ có điều dữ liệu
    sai. Không có cách nào phát hiện bằng cách đọc code.

    Phép thử dứt khoát: chiếu điểm LiDAR đè lên ảnh camera CÙNG FRAME.
        - Điểm bám đúng mặt đường, thân xe, cột đèn  -> toàn bộ chuỗi biến đổi ĐÚNG
        - Điểm lệch, lộn ngược, hoặc dồn một góc     -> SAI, và thấy ngay lập tức

BA HỆ TOẠ ĐỘ PHẢI PHÂN BIỆT
    CARLA / UE4      TAY TRÁI:  x tới trước,  y sang PHẢI,  z lên trên
                     carla.Location đơn vị MÉT, carla.Rotation đơn vị ĐỘ

    Camera OpenCV               z tới trước,  x sang phải,  y XUỐNG DƯỚI
                     (đây là quy ước mà ma trận K giả định)

    ROS              TAY PHẢI:  x tới trước,  y sang TRÁI,  z lên trên
                     -> so với CARLA phải ĐẢO DẤU y (và pitch, yaw)

CHUỖI BIẾN ĐỔI — năm bước
    1. Điểm LiDAR nằm trong hệ toạ độ RIÊNG của cảm biến LiDAR
    2. LiDAR -> world      : nhân ma trận lidar_to_world (4x4)
    3. world -> camera     : nhân ma trận world_to_camera (4x4, là nghịch đảo)
    4. UE4 -> OpenCV       : (x, y, z) -> (y, -z, x)      <- CHỖ HAY SAI NHẤT
    5. camera 3D -> ảnh 2D : nhân ma trận K rồi chia cho thành phần thứ ba

    Bước 4 không phải phép xoay tuỳ tiện mà là đổi tên trục:
        trục "tới trước" của UE4 là x  -> thành z của OpenCV
        trục "sang phải" của UE4 là y  -> thành x của OpenCV
        trục "lên trên"  của UE4 là z  -> thành -y của OpenCV (vì OpenCV y hướng XUỐNG)

    Script này đọc dữ liệu ĐÃ LƯU (không cần server), nhờ meta.json đã ghi sẵn
    ma trận của từng frame lúc thu.

CHẠY
    .venv-sr\\Scripts\\python.exe my_client\\lidar_on_image.py --frame 50
"""

import argparse
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")          # không cần cửa sổ, chỉ lưu ảnh
import matplotlib.pyplot as plt

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def newest_run(out_dir):
    runs = sorted(d for d in os.listdir(out_dir) if d.startswith("run_"))
    if not runs:
        raise SystemExit("Khong tim thay thu muc run_* nao trong " + out_dir)
    return os.path.join(out_dir, runs[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="thu muc run_*; mac dinh lay cai moi nhat")
    ap.add_argument("--out-root", default=r"D:\Hunganh\carla-scenario\out")
    ap.add_argument("--frame", type=int, default=50)
    ap.add_argument("--save", default=r"D:\Hunganh\carla-scenario\evidence\task2")
    args = ap.parse_args()

    run_dir = args.run or newest_run(args.out_root)
    name = "%06d" % args.frame

    # ----------------------------------------------------------------------
    # 1. Đọc dữ liệu đã lưu
    # ----------------------------------------------------------------------
    with open(os.path.join(run_dir, "calib.json"), encoding="utf-8") as f:
        calib = json.load(f)
    with open(os.path.join(run_dir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)

    k = np.array(calib["camera_rgb"]["K"])
    img = plt.imread(os.path.join(run_dir, "rgb", name + ".png"))
    cloud = np.load(os.path.join(run_dir, "lidar", name + ".npy"))

    frame_meta = next(f for f in meta["frames"] if f["frame_index"] == args.frame)
    lidar_to_world = np.array(frame_meta["lidar_to_world"])
    world_to_camera = np.array(frame_meta["world_to_camera"])

    print("run          :", run_dir)
    print("frame        :", args.frame, "(world_frame %d)" % frame_meta["world_frame"])
    print("so diem LiDAR:", cloud.shape[0])
    print("anh          :", img.shape)

    # ----------------------------------------------------------------------
    # 2. LiDAR local -> world
    # ----------------------------------------------------------------------
    # cloud có 4 cột: x, y, z, intensity. Chỉ lấy 3 cột đầu, chuyển vị thành
    # (3, N) rồi thêm một hàng toàn số 1 để thành toạ độ thuần nhất (4, N) —
    # có vậy mới nhân được với ma trận 4x4.
    xyz = cloud[:, :3].T
    intensity = cloud[:, 3]
    homogeneous = np.r_[xyz, np.ones((1, xyz.shape[1]))]

    world_points = lidar_to_world @ homogeneous

    # ----------------------------------------------------------------------
    # 3. world -> camera (vẫn còn trong quy ước UE4)
    # ----------------------------------------------------------------------
    sensor_points = world_to_camera @ world_points

    # ----------------------------------------------------------------------
    # 4. UE4 -> OpenCV   (x, y, z) -> (y, -z, x)
    # ----------------------------------------------------------------------
    # Nếu bỏ qua bước này, ảnh chiếu sẽ xoay 90 độ và lộn ngược — triệu chứng
    # rất đặc trưng, thấy một lần là nhớ.
    points_camera = np.array([
        sensor_points[1],        # y cua UE4  -> x cua OpenCV (sang phai)
        -sensor_points[2],       # -z cua UE4 -> y cua OpenCV (xuong duoi)
        sensor_points[0],        # x cua UE4  -> z cua OpenCV (toi truoc)
    ])

    # ----------------------------------------------------------------------
    # 5. Chiếu 3D -> 2D bằng K
    # ----------------------------------------------------------------------
    points_2d = k @ points_camera

    # Chia cho thành phần thứ ba (độ sâu) — đây chính là phép chiếu phối cảnh:
    # vật càng xa thì càng dồn về tâm ảnh.
    depth = points_2d[2, :]
    points_2d = np.array([
        points_2d[0, :] / depth,
        points_2d[1, :] / depth,
        depth,
    ])

    # ----------------------------------------------------------------------
    # 6. Lọc điểm hợp lệ
    # ----------------------------------------------------------------------
    h, w = img.shape[0], img.shape[1]
    # depth > 0: loại điểm nằm SAU lưng camera. Không lọc thì chúng vẫn ra toạ
    # độ pixel hợp lệ (do phép chia đổi dấu hai lần) và vẽ ra những điểm ma.
    mask = (points_2d[2] > 0.1) & \
           (points_2d[0] >= 0) & (points_2d[0] < w) & \
           (points_2d[1] >= 0) & (points_2d[1] < h)

    u = points_2d[0, mask]
    v = points_2d[1, mask]
    d = points_2d[2, mask]
    inten = intensity[mask]

    print("so diem roi vao khung hinh: %d / %d  (%.1f%%)"
          % (mask.sum(), cloud.shape[0], 100.0 * mask.sum() / cloud.shape[0]))
    print("khoang cach min/max        : %.1f / %.1f m" % (d.min(), d.max()))

    # ----------------------------------------------------------------------
    # 7. Vẽ
    # ----------------------------------------------------------------------
    os.makedirs(args.save, exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(13, 14))

    axes[0].imshow(img)
    axes[0].set_title("Anh RGB goc — frame %d" % args.frame)
    axes[0].axis("off")

    axes[1].imshow(img)
    sc = axes[1].scatter(u, v, c=d, s=2.5, cmap="viridis_r", alpha=.85)
    axes[1].set_title("LiDAR chieu len anh — mau theo khoang cach\n"
                      "%d diem trong khung hinh" % mask.sum())
    axes[1].axis("off")
    cb = fig.colorbar(sc, ax=axes[1], fraction=.035, pad=.01)
    cb.set_label("Khoang cach [m]")

    fig.tight_layout()
    out_path = os.path.join(args.save, "task2_01_lidar_chieu_len_rgb_frame%d.png" % args.frame)
    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    print("Da luu:", out_path)


if __name__ == "__main__":
    main()
