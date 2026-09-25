#!/usr/bin/env python
"""
Tạo map CARLA từ OpenStreetMap — đường nhanh (OSM → OpenDRIVE → world)
=======================================================================

HAI ĐƯỜNG TẠO MAP TỪ OSM, ĐỪNG NHẦM

    A. Digital Twin Tool (widget trong Unreal Editor)
       -> sinh môi trường 3D ĐẦY ĐỦ: đường + nhà + cây + texture
       -> cần Unreal Editor, ~10 phút sinh, HƠN 1 GIỜ để lưu map
       -> tài liệu: https://carla.readthedocs.io/en/latest/adv_digital_twin/

    B. Script này: OSM -> OpenDRIVE -> world
       -> chỉ sinh MẠNG LƯỚI ĐƯỜNG, không nhà không cây
       -> chạy bằng Python thuần, vài giây tới vài phút, không cần Editor
       -> dùng khi chỉ cần hình học đường để thử thuật toán điều hướng

CHUỖI XỬ LÝ CỦA ĐƯỜNG B

    file .osm  --carla.Osm2Odr.convert-->  chuỗi .xodr  --generate_opendrive_world-->  world

    Bước 1 chạy hoàn toàn phía client (thư viện osm2odr biên dịch sẵn trong CARLA).
    Bước 2 bảo server dựng map tạm ngay trong bộ nhớ — map này KHÔNG được lưu lại,
    tắt server là mất. Đó là khác biệt lớn so với đường A.

LẤY FILE .osm Ở ĐÂU
    Máy này không có kết nối mạng từ shell, nên phải tải bằng trình duyệt —
    đúng như tài liệu CARLA hướng dẫn:
        1. Vào https://www.openstreetmap.org
        2. Di chuyển tới khu vực muốn lấy
        3. Bấm "Export", chỉnh khung chọn nếu cần, rồi tải file .osm về
        4. Lưu vào D:\\Hunganh\\carla-scenario\\osm\\
    Nên chọn vùng khoảng 2x2 km. Vùng quá rộng sẽ nặng và lâu.

CHẠY
    REM  Tu file OSM tai ve
    .venv-sr\\Scripts\\python.exe my_client\\osm_to_map.py --osm osm\\khu_vuc.osm

    REM  Hoac kiem chung nua sau chuoi bang file .xodr co san cua CARLA
    .venv-sr\\Scripts\\python.exe my_client\\osm_to_map.py ^
        --xodr "D:\\Hunganh\\carla_tuan\\Unreal\\CarlaUE4\\Content\\Carla\\Maps\\OpenDrive\\Town01.xodr"
"""

import argparse
import os
import sys
import time

import carla

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


# Những loại đường OSM sẽ được đưa vào OpenDRIVE.
# OSM gắn thẻ `highway=` cho mọi con đường; danh sách này quyết định giữ loại nào.
# Bỏ bớt -> map thưa hơn nhưng nhẹ; thêm 'service', 'living_street' -> dày hơn.
#
# BA BO CHON SAN. Duong THAT (khac map game) co rat nhieu doan ngan va nut giao
# phuc tap; bo cang day thi cang de sinh hinh hoc loi khien CARLA sap voi
# assertion "s <= road->GetLength()". Bat dau tu bo nho roi noi rong dan.
OSM_WAY_SETS = {
    # Chi truc chinh — it nut giao nhat, on dinh nhat
    "minimal": [
        "motorway", "motorway_link",
        "trunk", "trunk_link",
        "primary", "primary_link",
    ],
    # Them duong cap quan/phuong — can bang giua do phu va do on dinh
    "major": [
        "motorway", "motorway_link",
        "trunk", "trunk_link",
        "primary", "primary_link",
        "secondary", "secondary_link",
        "tertiary", "tertiary_link",
    ],
    # Day du, gom ca duong khu dan cu — phu rong nhat nhung de loi nhat
    "full": [
        "motorway", "motorway_link",
        "trunk", "trunk_link",
        "primary", "primary_link",
        "secondary", "secondary_link",
        "tertiary", "tertiary_link",
        "unclassified",
        "residential",
    ],
}


def osm_to_xodr(osm_path, lane_width, traffic_lights, all_junctions_lights, center_map,
                way_set="full"):
    """Bước 1: đọc file .osm, chuyển thành chuỗi OpenDRIVE (.xodr)."""
    with open(osm_path, encoding="utf-8") as f:
        osm_data = f.read()

    settings = carla.Osm2OdrSettings()
    types = OSM_WAY_SETS[way_set]
    settings.set_osm_way_types(types)
    print("      bo loai duong: %s (%d loai)" % (way_set, len(types)))

    # Dữ liệu OSM KHÔNG có độ rộng làn, nên phải tự đặt. Đây là giả định lớn
    # nhất của cả quy trình — đường thật rộng hẹp khác nhau, ở đây gán đều.
    settings.default_lane_width = lane_width

    settings.generate_traffic_lights = traffic_lights
    settings.all_junctions_with_traffic_lights = all_junctions_lights

    # center_map dời gốc toạ độ về giữa vùng. Nên bật, vì toạ độ OSM gốc là
    # kinh/vĩ độ quy đổi ra mét, có thể lên tới hàng trăm nghìn -> sai số dấu
    # phẩy động lớn và xe spawn ở chỗ rất xa gốc.
    settings.center_map = center_map

    print("[1/3] Dang chuyen OSM -> OpenDRIVE ...")
    t0 = time.time()
    xodr = carla.Osm2Odr.convert(osm_data, settings)
    print("      xong sau %.1fs, chuoi xodr dai %d ky tu" % (time.time() - t0, len(xodr)))
    return xodr


def load_world(client, xodr, vertex_distance, wall_height, extra_width):
    """Bước 2: bảo server dựng map từ chuỗi OpenDRIVE."""
    params = carla.OpendriveGenerationParameters(
        # Khoang cach giua cac dinh khi chia nho duong cong thanh doan thang.
        # Nho hon = duong muot hon nhung mesh nang hon.
        vertex_distance=vertex_distance,
        # Do dai toi da moi doan duong truoc khi cat.
        max_road_length=50.0,
        # Tuong chan hai ben de xe khong roi khoi duong. 0 = khong co tuong.
        wall_height=wall_height,
        # Noi them le duong.
        additional_width=extra_width,
        # Dung mesh nhin thay duoc. Tat di thi map vo hinh (chi con vat ly).
        enable_mesh_visibility=True,
        # Sinh du lieu dieu huong cho nguoi di bo. Tat cho nhanh.
        enable_pedestrian_navigation=False,
    )

    print("[2/3] Dang bao server dung map (co the mat vai phut) ...")
    t0 = time.time()
    world = client.generate_opendrive_world(xodr, params)
    print("      xong sau %.1fs" % (time.time() - t0))
    return world


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--osm", help="file .osm tai tu openstreetmap.org")
    src.add_argument("--xodr", help="file .xodr co san (bo qua buoc chuyen doi)")

    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--lane-width", type=float, default=4.0, help="m, do rong lan mac dinh")
    ap.add_argument("--traffic-lights", action="store_true", help="sinh den giao thong")
    ap.add_argument("--all-junctions-lights", action="store_true")
    ap.add_argument("--no-center", action="store_true", help="KHONG doi goc toa do ve giua")
    ap.add_argument("--vertex-distance", type=float, default=2.0)
    ap.add_argument("--wall-height", type=float, default=0.0)
    ap.add_argument("--extra-width", type=float, default=0.6)
    ap.add_argument("--save-xodr", default=None, help="luu chuoi xodr ra file de xem lai")
    # Buoc chuyen OSM -> OpenDRIVE chay hoan toan phia CLIENT (thu vien osm2odr
    # bien dich san trong CARLA), khong can server. Co nay cho phep tach rieng
    # de lam truoc, hoac de kiem tra chat luong du lieu OSM ma khong ton GPU.
    ap.add_argument("--convert-only", action="store_true",
                    help="chi chuyen OSM -> xodr roi dung, khong dung map")
    ap.add_argument("--road-set", choices=list(OSM_WAY_SETS), default="full",
                    help="bo loai duong OSM dua vao map (minimal|major|full)")
    # Mac dinh script chay mai cho toi khi bam Ctrl+C. De chay tu dong (lay log,
    # quay video) thi dat so giay o day roi no tu thoat.
    ap.add_argument("--chay-trong", type=float, default=0.0,
                    help="so giay chay roi tu thoat; 0 = chay mai cho Ctrl+C")
    ap.add_argument("--video", default=None,
                    help="gan camera vao xe va ghi ra file mp4")
    args = ap.parse_args()

    client = carla.Client(args.host, args.port)
    client.set_timeout(300.0)      # dung map moi rat lau, dung de timeout nho

    # ---------------- Bước 1 ----------------
    if args.osm:
        xodr = osm_to_xodr(args.osm, args.lane_width, args.traffic_lights,
                           args.all_junctions_lights, not args.no_center,
                           way_set=args.road_set)
        if args.save_xodr:
            with open(args.save_xodr, "w", encoding="utf-8") as f:
                f.write(xodr)
            print("      da luu:", args.save_xodr)
    else:
        with open(args.xodr, encoding="utf-8") as f:
            xodr = f.read()
        print("[1/3] Doc san file .xodr: %s (%d ky tu)" % (args.xodr, len(xodr)))

    if not xodr or len(xodr) < 100:
        raise SystemExit("Chuoi OpenDRIVE rong hoac qua ngan — kiem tra lai vung OSM "
                         "co du duong duoc gan the khong.")

    if args.convert_only:
        print("[xong ] --convert-only: da dung o buoc chuyen doi, khong dung map.")
        return

    # ---------------- Bước 2 ----------------
    world = load_world(client, xodr, args.vertex_distance, args.wall_height, args.extra_width)

    # ---------------- Bước 3: kiểm chứng ----------------
    print("[3/3] Kiem chung map vua dung:")
    carla_map = world.get_map()
    spawn_points = carla_map.get_spawn_points()
    print("      ten map        :", carla_map.name)
    print("      so diem spawn  :", len(spawn_points))

    # Đếm waypoint để ước lượng độ dài mạng lưới đường. Nếu số này quá nhỏ thì
    # vùng OSM chọn quá thưa đường.
    waypoints = carla_map.generate_waypoints(5.0)
    print("      so waypoint    : %d  (~%.1f km duong, lay mau moi 5 m)"
          % (len(waypoints), len(waypoints) * 5.0 / 1000.0))

    if not spawn_points:
        print("      CANH BAO: khong co diem spawn nao -> vung OSM khong du duong.")
        return

    # Spawn thử một xe và cho chạy autopilot, để chứng minh map dùng được thật.
    bp = world.get_blueprint_library().filter("vehicle.tesla.model3")[0]
    vehicle = None
    for sp in spawn_points[:20]:
        try:
            vehicle = world.spawn_actor(bp, sp)
            break
        except RuntimeError:
            continue          # diem spawn bi vat can, thu diem khac

    if vehicle is None:
        print("      CANH BAO: khong spawn duoc xe o 20 diem dau.")
        return

    vehicle.set_autopilot(True)
    print("      spawn OK       : %s tai %s" % (vehicle.type_id, sp.location))

    # Đưa camera quan sát ra sau xe để nhìn thấy map.
    spectator = world.get_spectator()
    tf = vehicle.get_transform()
    fwd = tf.get_forward_vector()
    spectator.set_transform(carla.Transform(
        carla.Location(x=tf.location.x - fwd.x * 12,
                       y=tf.location.y - fwd.y * 12,
                       z=tf.location.z + 6),
        carla.Rotation(pitch=-18, yaw=tf.rotation.yaw)))

    print()
    print("Map da san sang. Xe dang chay autopilot, camera da huong ve xe.")
    # --- Quay video: gan mot camera vao xe dang chay autopilot ---
    cam, hang_anh, ghi_video = None, None, None
    if args.video:
        from queue import Queue
        import cv2
        RONG, CAO, FPS = 1280, 720, 20
        cbp = world.get_blueprint_library().find("sensor.camera.rgb")
        cbp.set_attribute("image_size_x", str(RONG))
        cbp.set_attribute("image_size_y", str(CAO))
        cbp.set_attribute("sensor_tick", str(1.0 / FPS))
        cam = world.spawn_actor(
            cbp,
            carla.Transform(carla.Location(x=-7.0, z=3.4), carla.Rotation(pitch=-12)),
            attach_to=vehicle)
        hang_anh = Queue()
        cam.listen(hang_anh.put)
        thu_muc = os.path.dirname(args.video)
        if thu_muc:
            os.makedirs(thu_muc, exist_ok=True)
        ghi_video = cv2.VideoWriter(args.video, cv2.VideoWriter_fourcc(*"mp4v"),
                                    FPS, (RONG, CAO))
        print("      dang quay video ra:", args.video)

    if args.chay_trong > 0:
        print("Se chay %.0f giay roi tu thoat." % args.chay_trong)
    else:
        print("Nhan Ctrl+C de dung va huy xe.")
    t_bat_dau = time.time()
    try:
        while True:
            world.wait_for_tick()
            if ghi_video is not None:
                from queue import Empty as _Empty
                import numpy as _np
                import cv2 as _cv
                try:
                    anh = hang_anh.get(timeout=2.0)
                except _Empty:
                    anh = None
                if anh is not None:
                    a = _np.frombuffer(anh.raw_data, dtype=_np.uint8).reshape((720, 1280, 4))
                    fr = a[:, :, :3].copy()
                    _cv.rectangle(fr, (0, 0), (1280, 44), (0, 0, 0), -1)
                    _cv.putText(fr, "Map dung tu OpenDRIVE - chi co mang luoi duong, khong nha khong cay",
                                (14, 30), _cv.FONT_HERSHEY_SIMPLEX, 0.62,
                                (255, 255, 255), 2, _cv.LINE_AA)
                    ghi_video.write(fr)
            if args.chay_trong > 0 and time.time() - t_bat_dau > args.chay_trong:
                v = vehicle.get_velocity()
                import math as _m
                print("      sau %.0f giay: xe o %s, toc do %.1f km/h"
                      % (args.chay_trong, vehicle.get_location(),
                         3.6 * _m.sqrt(v.x**2 + v.y**2 + v.z**2)))
                break
    except KeyboardInterrupt:
        pass
    finally:
        # Go cam bien TRUOC, roi moi huy xe — nguoc lai server co the kenh.
        if cam is not None:
            try:
                cam.stop()
                cam.destroy()
            except Exception:
                pass
        if ghi_video is not None:
            ghi_video.release()
            print("      da ghi video: %s (%.1f MB)"
                  % (args.video, os.path.getsize(args.video) / 1e6))
        try:
            vehicle.destroy()
        except Exception:
            pass
        print("\nDa huy xe.")


if __name__ == "__main__":
    main()
