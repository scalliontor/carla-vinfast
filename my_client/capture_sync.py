#!/usr/bin/env python
"""
Thu dữ liệu cảm biến ĐỒNG BỘ từ CARLA
======================================

MỤC ĐÍCH
    Gắn camera RGB + LiDAR + camera semantic lên một xe, chạy N frame ở chế độ
    đồng bộ, ghi tất cả ra đĩa kèm file hiệu chuẩn (calib.json).

VÌ SAO PHẢI DÙNG CHẾ ĐỘ ĐỒNG BỘ — đây là điều quan trọng nhất của cả script
    Ở chế độ BẤT ĐỒNG BỘ (mặc định), server chạy tự do theo tốc độ của nó, còn
    client nhận được frame nào hay frame đó. Hậu quả: ảnh camera và đám mây điểm
    LiDAR mà ta ghép thành một cặp THỰC RA ĐƯỢC CHỤP Ở HAI THỜI ĐIỂM KHÁC NHAU.
    Xe đang chạy 50 km/h thì lệch 1 frame là lệch gần 0,7 m ngoài đời thật.
    Dữ liệu kiểu đó không dùng để huấn luyện hay hiệu chuẩn được.

    Chế độ ĐỒNG BỘ đảo ngược quyền điều khiển: server chỉ bước MỘT bước khi
    client gọi world.tick(). Nhờ vậy mọi cảm biến chắc chắn thuộc cùng một frame.

BA CÁI BẪY CỦA CHẾ ĐỘ ĐỒNG BỘ
    1. Phải đặt Traffic Manager sang đồng bộ nữa. Quên là xe đứng im không chạy.
    2. PHẢI trả world về bất đồng bộ trước khi thoát. Nếu để world kẹt ở chế độ
       đồng bộ mà không còn ai gọi tick(), server sẽ ĐÓNG BĂNG với mọi client sau
       đó — kể cả Scenario Runner. Vì vậy phần dọn dẹp nằm trong khối `finally`.
    3. LiDAR phải đặt rotation_frequency = 1 / fixed_delta_seconds. LiDAR quét
       xoay tròn; nếu tần số quét không khớp nhịp tick, mỗi frame chỉ nhận được
       MỘT PHẦN vòng quét, đám mây điểm bị khuyết hình quạt.

CHẠY
    .venv-sr\\Scripts\\python.exe my_client\\capture_sync.py --frames 100
"""

import argparse
import json
import os
import queue
import time

import sys

import numpy as np

import carla

# Console Windows mac dinh cp1252, khong in noi chu co dau -> UnicodeEncodeError.
# Neu loi do xay ra trong khoi `finally` thi world KHONG kip tra ve bat dong bo
# va server se dong bang. Ep utf-8 ngay tu dau de loai han rui ro do.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


# ==========================================================================
# Tham số mặc định — gom lên đầu để dễ thí nghiệm
# ==========================================================================
FIXED_DELTA = 0.05          # giây/tick -> 20 Hz. Phải là số cố định, không đổi giữa chừng.
IMAGE_W, IMAGE_H = 1280, 720
CAMERA_FOV = 90.0           # độ, theo chiều NGANG
LIDAR_RANGE = 80.0          # m
LIDAR_CHANNELS = 64
LIDAR_PPS = 600000          # điểm mỗi giây

# Vị trí gắn cảm biến, tính từ TÂM XE. Hệ CARLA: x tới trước, y sang phải, z lên trên.
CAMERA_TF = carla.Transform(carla.Location(x=1.5, z=1.6))
LIDAR_TF = carla.Transform(carla.Location(x=1.0, z=1.8))


def build_intrinsic(width, height, fov_deg):
    """
    Dựng ma trận nội tham số K từ độ phân giải và FOV.

        K = [[fx,  0, cx],
             [ 0, fy, cy],
             [ 0,  0,  1]]

    CARLA KHÔNG cho sẵn K — phải tự tính. Công thức suy ra từ hình học:
    nửa bề rộng ảnh (width/2) nhìn dưới góc nửa FOV, nên

        fx = (width / 2) / tan(fov / 2)

    Viết gọn lại thành width / (2 * tan(fov*pi/360)) vì fov/2 độ = fov*pi/360 radian.
    Ở đây pixel vuông nên fy = fx, và tâm ảnh nằm đúng giữa.
    """
    focal = width / (2.0 * np.tan(fov_deg * np.pi / 360.0))
    k = np.identity(3)
    k[0, 0] = k[1, 1] = focal
    k[0, 2] = width / 2.0
    k[1, 2] = height / 2.0
    return k


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--frames", type=int, default=100, help="so frame can thu")
    ap.add_argument("--out", default=r"D:\Hunganh\carla-scenario\out")
    args = ap.parse_args()

    client = carla.Client(args.host, args.port)
    client.set_timeout(120.0)          # bản build từ source nạp map chậm, đừng để 5-10s
    world = client.get_world()

    # Lưu lại cấu hình gốc để KHÔI PHỤC lúc thoát (xem khối finally).
    original_settings = world.get_settings()

    actors = []
    run_dir = os.path.join(args.out, "run_" + time.strftime("%Y%m%d_%H%M%S"))

    try:
        # ------------------------------------------------------------------
        # 1. Bật chế độ đồng bộ
        # ------------------------------------------------------------------
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = FIXED_DELTA
        world.apply_settings(settings)

        # BẪY SỐ 1: Traffic Manager có vòng lặp riêng, phải đồng bộ nó nữa.
        tm = client.get_trafficmanager()
        tm.set_synchronous_mode(True)

        print("[setup] map = %s | fixed_delta = %.3f s (%.0f Hz)"
              % (world.get_map().name, FIXED_DELTA, 1.0 / FIXED_DELTA))

        # ------------------------------------------------------------------
        # 2. Spawn xe và bật autopilot
        # ------------------------------------------------------------------
        bp_lib = world.get_blueprint_library()
        vehicle_bp = bp_lib.filter("vehicle.tesla.model3")[0]
        spawn_points = world.get_map().get_spawn_points()
        vehicle = world.spawn_actor(vehicle_bp, spawn_points[0])
        actors.append(vehicle)
        vehicle.set_autopilot(True, tm.get_port())
        print("[setup] xe: %s (id=%d)" % (vehicle.type_id, vehicle.id))

        # ------------------------------------------------------------------
        # 3. Gắn cảm biến
        # ------------------------------------------------------------------
        cam_bp = bp_lib.find("sensor.camera.rgb")
        cam_bp.set_attribute("image_size_x", str(IMAGE_W))
        cam_bp.set_attribute("image_size_y", str(IMAGE_H))
        cam_bp.set_attribute("fov", str(CAMERA_FOV))
        # sensor_tick = 0 nghĩa là "chụp mỗi tick". Ở chế độ đồng bộ phải để vậy,
        # đặt số khác sẽ làm cảm biến bỏ frame và phá vỡ tính đồng bộ.
        cam_bp.set_attribute("sensor_tick", "0.0")
        camera = world.spawn_actor(cam_bp, CAMERA_TF, attach_to=vehicle)
        actors.append(camera)

        seg_bp = bp_lib.find("sensor.camera.semantic_segmentation")
        seg_bp.set_attribute("image_size_x", str(IMAGE_W))
        seg_bp.set_attribute("image_size_y", str(IMAGE_H))
        seg_bp.set_attribute("fov", str(CAMERA_FOV))
        # Gắn CÙNG MỘT vị trí với camera RGB -> hai ảnh khớp pixel-với-pixel.
        seg = world.spawn_actor(seg_bp, CAMERA_TF, attach_to=vehicle)
        actors.append(seg)

        lidar_bp = bp_lib.find("sensor.lidar.ray_cast")
        lidar_bp.set_attribute("range", str(LIDAR_RANGE))
        lidar_bp.set_attribute("channels", str(LIDAR_CHANNELS))
        lidar_bp.set_attribute("points_per_second", str(LIDAR_PPS))
        # BẪY SỐ 3: tần số quét phải khớp nhịp tick, nếu không mỗi frame chỉ được
        # một phần vòng quét.
        lidar_bp.set_attribute("rotation_frequency", str(1.0 / FIXED_DELTA))
        lidar = world.spawn_actor(lidar_bp, LIDAR_TF, attach_to=vehicle)
        actors.append(lidar)

        # ------------------------------------------------------------------
        # 4. Hàng đợi — cách ghép cảm biến với tick
        # ------------------------------------------------------------------
        # listen() chạy trên LUỒNG RIÊNG của CARLA, không phải luồng chính. Nên
        # không xử lý dữ liệu ngay trong callback (sẽ làm chậm server và dễ lỗi
        # tranh chấp). Chỉ đẩy vào queue.Queue — vốn an toàn đa luồng — rồi luồng
        # chính lấy ra sau mỗi tick.
        q_rgb, q_seg, q_lidar = queue.Queue(), queue.Queue(), queue.Queue()
        camera.listen(q_rgb.put)
        seg.listen(q_seg.put)
        lidar.listen(q_lidar.put)

        # ------------------------------------------------------------------
        # 5. Chuẩn bị thư mục và file hiệu chuẩn
        # ------------------------------------------------------------------
        for sub in ("rgb", "seg", "lidar"):
            os.makedirs(os.path.join(run_dir, sub), exist_ok=True)

        k = build_intrinsic(IMAGE_W, IMAGE_H, CAMERA_FOV)

        def tf_to_dict(tf):
            return {
                "location": {"x": tf.location.x, "y": tf.location.y, "z": tf.location.z},
                "rotation": {"pitch": tf.rotation.pitch, "yaw": tf.rotation.yaw,
                             "roll": tf.rotation.roll},
            }

        calib = {
            "_ghi_chu": (
                "K tu tinh tu FOV va do phan giai; CARLA khong cung cap san. "
                "He toa do CARLA/UE4 la TAY TRAI: x toi truoc, y sang phai, z len tren. "
                "Don vi carla.Location la MET, carla.Rotation la DO."
            ),
            "camera_rgb": {
                "image_size": [IMAGE_W, IMAGE_H],
                "fov_deg": CAMERA_FOV,
                "K": k.tolist(),
                "transform_tu_tam_xe": tf_to_dict(CAMERA_TF),
            },
            "camera_semantic": {
                "image_size": [IMAGE_W, IMAGE_H],
                "fov_deg": CAMERA_FOV,
                "K": k.tolist(),
                "transform_tu_tam_xe": tf_to_dict(CAMERA_TF),
            },
            "lidar": {
                "range_m": LIDAR_RANGE,
                "channels": LIDAR_CHANNELS,
                "points_per_second": LIDAR_PPS,
                "rotation_frequency_hz": 1.0 / FIXED_DELTA,
                "transform_tu_tam_xe": tf_to_dict(LIDAR_TF),
            },
        }
        with open(os.path.join(run_dir, "calib.json"), "w", encoding="utf-8") as f:
            json.dump(calib, f, indent=2, ensure_ascii=False)

        # ------------------------------------------------------------------
        # 6. Vòng lặp thu dữ liệu
        # ------------------------------------------------------------------
        print("[run ] thu %d frame vao %s" % (args.frames, run_dir))
        dropped = 0
        matrices = []      # lưu ma trận cảm biến -> world từng frame, cho bước chiếu

        for i in range(args.frames):
            # world.tick() đẩy mô phỏng đúng MỘT bước và trả về số frame.
            # Đây là mấu chốt: server chỉ bước khi ta cho phép.
            world_frame = world.tick()

            try:
                # timeout 2 giây: nếu quá lâu mà không có dữ liệu thì coi như rớt
                # frame, ghi nhận lại thay vì treo vĩnh viễn.
                img_rgb = q_rgb.get(timeout=2.0)
                img_seg = q_seg.get(timeout=2.0)
                pts = q_lidar.get(timeout=2.0)
            except queue.Empty:
                dropped += 1
                print("\n[canh bao] ROT FRAME tai buoc %d" % i)
                continue

            # KIỂM TRA ĐỒNG BỘ — dòng quan trọng nhất của script.
            # Nếu ba cảm biến không cùng số frame thì dữ liệu vô nghĩa, dừng ngay
            # còn hơn ghi ra một bộ dữ liệu sai mà không biết.
            assert img_rgb.frame == img_seg.frame == pts.frame == world_frame, (
                "LECH FRAME: rgb=%d seg=%d lidar=%d world=%d"
                % (img_rgb.frame, img_seg.frame, pts.frame, world_frame)
            )

            name = "%06d" % i

            # --- ảnh RGB: CARLA trả về BGRA, chuyển sang RGB ---
            img_rgb.save_to_disk(os.path.join(run_dir, "rgb", name + ".png"))

            # --- ảnh semantic: dùng bảng màu CityScapes cho dễ nhìn ---
            img_seg.save_to_disk(os.path.join(run_dir, "seg", name + ".png"),
                                 carla.ColorConverter.CityScapesPalette)

            # --- LiDAR: raw_data là chuỗi float32 dạng (x, y, z, intensity) ---
            cloud = np.frombuffer(pts.raw_data, dtype=np.float32).reshape(-1, 4)
            np.save(os.path.join(run_dir, "lidar", name + ".npy"), cloud)

            # Lưu ma trận cảm biến -> world tại đúng frame này. Bắt buộc phải lấy
            # ở ĐÂY: xe đang chạy nên sang frame sau là ma trận đã khác.
            matrices.append({
                "frame_index": i,
                "world_frame": world_frame,
                "so_diem_lidar": int(cloud.shape[0]),
                "lidar_to_world": np.array(pts.transform.get_matrix()).tolist(),
                "camera_to_world": np.array(img_rgb.transform.get_matrix()).tolist(),
                "world_to_camera": np.array(img_rgb.transform.get_inverse_matrix()).tolist(),
            })

            if (i + 1) % 10 == 0:
                print("   %3d/%d  frame=%d  diem lidar=%d"
                      % (i + 1, args.frames, world_frame, cloud.shape[0]))

        # ------------------------------------------------------------------
        # 7. Ghi metadata
        # ------------------------------------------------------------------
        meta = {
            "map": world.get_map().name,
            "fixed_delta_seconds": FIXED_DELTA,
            "so_frame_yeu_cau": args.frames,
            "so_frame_ghi_duoc": len(matrices),
            "so_frame_rot": dropped,
            "carla_client_version": client.get_client_version(),
            "carla_server_version": client.get_server_version(),
            "xe": vehicle.type_id,
            "frames": matrices,
        }
        with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        print("\n[xong ] ghi %d/%d frame, rot %d"
              % (len(matrices), args.frames, dropped))
        print("[xong ] thu muc: %s" % run_dir)

    finally:
        # ------------------------------------------------------------------
        # 8. DỌN DẸP — phần bắt buộc, xem BẪY SỐ 2 ở đầu file
        # ------------------------------------------------------------------
        # QUY TAC: KHOI PHUC TRUOC, GHI LOG SAU.
        # Bai hoc tu lan chay dau: mot lenh print co dau tieng Viet da nem
        # UnicodeEncodeError NGAY TRONG khoi finally, truoc khi kip goi
        # apply_settings() -> world ket o che do dong bo, server dong bang voi
        # moi client sau do. Dat viec khoi phuc len TRUOC moi lenh in de du
        # phan ghi log co hong thi trang thai server van sach.
        restore_err = None
        try:
            world.apply_settings(original_settings)
            client.get_trafficmanager().set_synchronous_mode(False)
        except Exception as e:
            restore_err = e

        print("[don ] da tra world ve che do ban dau, dang huy actor...")
        if restore_err is not None:
            print("   canh bao khi khoi phuc settings:", restore_err)

        # Huỷ theo thứ tự NGƯỢC: cảm biến trước, xe sau. Huỷ xe trước khi huỷ
        # cảm biến đang gắn lên nó dễ gây lỗi ở phía server.
        for a in reversed(actors):
            try:
                if hasattr(a, "stop"):
                    a.stop()          # ngừng listen() trước khi destroy
                a.destroy()
            except Exception:
                pass
        print("[don ] xong")


if __name__ == "__main__":
    main()
