#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Chụp ảnh và quay video map do Digital Twin Tool sinh ra — KHÔNG cần mở Editor
=============================================================================

VÌ SAO LÀM THẾ NÀY
    Map Digital Twin nằm trong Content/CustomMaps/<ten>/. Cách thông thường là
    mở Unreal Editor rồi tự bay camera quanh — chậm, phải thao tác tay, và ảnh
    chụp ra dính cả giao diện Editor.

    Server CARLA nạp được map đó: nó có mặt trong client.get_available_maps().
    Vậy thì gắn camera vào mô phỏng rồi chụp bằng lệnh — hình sạch, lặp lại được.

BA CÁI BẪY ĐÃ VẤP, MỖI CÁI TỐN MỘT LẦN SẬP SERVER

  1. Đo khung bao map phải dựa vào MẠNG LƯỚI ĐƯỜNG, không phải vị trí actor.
     Actor có thể nằm ở toạ độ rất xa, kéo khung bao phình ra và đẩy camera lên
     quá cao. Lần thử đầu camera bay lên 881 m, cả map lọt vào khung nhìn, server
     treo hàng render 60 giây rồi sập.

  2. KHÔNG được thả camera tự do trong map Digital Twin.
     Map này là Large Map (chia tile). ALargeMapManager thấy actor nằm xa xe hero
     thì chuyển nó sang trạng thái ngủ, và CARLA sập ngay ở đó:

         EXCEPTION_ACCESS_VIOLATION reading address 0x0000000000000008
         carla::streaming::detail::token_type::operator carla::streaming::Token()
         ASensor::EndPlay()                          Sensor.cpp:129
         FActorRegistry::PutActorToSleep()           ActorRegistry.cpp:198
         ALargeMapManager::ConvertActiveToDormantActors()

     Mã xử lý ngủ đông không lường trường hợp actor là CẢM BIẾN.
     Cách vòng: gắn camera vào một xe đặt role_name='hero'. Actor hero không bị
     cho ngủ, và còn kéo theo việc nạp tile quanh nó — thứ ta cần để thấy nhà cửa.

  3. KHÔNG được dịch chuyển xe hero ra xa.

         Assertion failed: Tile    LargeMapManager.cpp:672

     Số tile công cụ sinh ra KHÔNG phủ hết vùng dữ liệu: đo được 1222x1327 m dữ
     liệu nhưng chỉ có 2x1 tile phủ 1000x500 m. Đưa xe ra ngoài vùng có tile là sập.

     Cách vòng: xe đứng yên, chỉ đổi transform TƯƠNG ĐỐI của camera gắn trên xe.

CHẠY
    REM  Khoi dong server THANG voi map nay, dung load_world (do ton bo nho hon):
    UE4Editor.exe CarlaUE4.uproject "/Game/CustomMaps/VinUniCampus/VinUniCampus" ^
        -game -nosound -quality-level=Low -carla-rpc-port=2000

    python my_client\\quay_map_digitaltwin.py --map VinUniCampus ^
        --thu-muc-ra "...\\Duong Digital Twin" --video "...\\video.mp4"
"""

import argparse
import math
import os
import sys
import time
from queue import Queue, Empty

import carla
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

W, H = 1280, 720


def tao_xe_hero(world):
    """Spawn một xe đánh dấu hero — thứ neo việc nạp tile của Large Map."""
    bp = world.get_blueprint_library().filter("vehicle.tesla.model3")[0]
    bp.set_attribute("role_name", "hero")

    diem = world.get_map().get_spawn_points()
    if not diem:
        raise SystemExit("Map khong co diem spawn nao.")

    # Dat xe vao GIUA mang luoi duong, khong phai o goc toa do.
    #
    # Goc toa do (0, 0) la GOC cua tile dau tien, nen dat xe o do thi nua khung
    # hinh la khoang trong ngoai ria map. Lay tam cua mang luoi duong thi chac
    # chan nam trong vung co tile — da do duoc mang luoi trai 802 x 448 m, vua
    # gon trong 2x1 tile phu 1000 x 500 m.
    wp = world.get_map().generate_waypoints(10.0)
    if wp:
        cx = sum(w.transform.location.x for w in wp) / len(wp)
        cy = sum(w.transform.location.y for w in wp) / len(wp)
    else:
        cx = cy = 0.0
    gan_tam = sorted(diem, key=lambda d: (d.location.x - cx) ** 2 + (d.location.y - cy) ** 2)
    for sp in gan_tam:
        try:
            return world.spawn_actor(bp, sp), diem
        except RuntimeError:
            continue
    raise SystemExit("Khong spawn duoc xe o bat ky diem nao.")


def pham_vi_duong(world):
    """Khung bao của mạng lưới đường — xem bẫy số 1 ở đầu file."""
    xs, ys = [], []
    for wp in world.get_map().generate_waypoints(10.0):
        l = wp.transform.location
        xs.append(l.x)
        ys.append(l.y)
    if len(xs) < 10:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def gan_camera(world, xe, tf, fov=90):
    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(W))
    bp.set_attribute("image_size_y", str(H))
    bp.set_attribute("fov", str(fov))
    return world.spawn_actor(bp, tf, attach_to=xe)


def lay_anh(q, bo_qua=8, cho=15.0):
    """Bỏ vài frame đầu: ngay sau khi gắn, texture còn ở mức phân giải thấp."""
    anh = None
    t0 = time.time()
    n = 0
    while time.time() - t0 < cho:
        try:
            anh = q.get(timeout=cho)
        except Empty:
            break
        n += 1
        if n >= bo_qua:
            break
    return anh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--thu-muc-ra", required=True)
    ap.add_argument("--video", default=None)
    ap.add_argument("--vong-giay", type=float, default=26.0)
    ap.add_argument("--fps", type=int, default=15)
    args = ap.parse_args()

    os.makedirs(args.thu_muc_ra, exist_ok=True)

    client = carla.Client("127.0.0.1", 2000)
    client.set_timeout(300.0)
    world = client.get_world()
    ten_map = world.get_map().name
    print("[1/4] Map dang chay tren server:", ten_map, flush=True)
    if args.map.lower() not in ten_map.lower():
        print("      CANH BAO: khong khop ten map mong doi (%s)" % args.map, flush=True)

    pv = pham_vi_duong(world)
    if pv:
        x0, x1, y0, y1 = pv
        print("[2/4] Mang luoi duong trai %.0f x %.0f m" % (x1 - x0, y1 - y0), flush=True)
    print("      so diem spawn: %d" % len(world.get_map().get_spawn_points()), flush=True)

    xe, diem = tao_xe_hero(world)
    vt = xe.get_location()
    print("      xe hero: %s id=%d tai x=%.0f y=%.0f z=%.0f"
          % (xe.type_id, xe.id, vt.x, vt.y, vt.z), flush=True)
    time.sleep(8.0)          # cho tile quanh xe nap xong

    print("[3/4] Chup anh tinh", flush=True)
    goc = [
        ("Map nhin tu tren xuong.png",
         carla.Transform(carla.Location(x=0, z=230), carla.Rotation(pitch=-90))),
        ("Map nhin xien tu tren cao.png",
         carla.Transform(carla.Location(x=-115, z=95), carla.Rotation(pitch=-30))),
        ("Khuon vien nhin tu huong khac.png",
         carla.Transform(carla.Location(y=-115, z=95), carla.Rotation(pitch=-30, yaw=90))),
        ("Nha va duong nhin gan.png",
         carla.Transform(carla.Location(x=-16, z=7), carla.Rotation(pitch=-11))),
        ("Duong trong map nhin ngang.png",
         carla.Transform(carla.Location(x=-6.5, z=2.6), carla.Rotation(pitch=-5))),
    ]
    for ten, tf in goc:
        cam = gan_camera(world, xe, tf)
        q = Queue()
        cam.listen(q.put)
        anh = lay_anh(q)
        if anh is not None:
            anh.save_to_disk(os.path.join(args.thu_muc_ra, ten))
            print("   %-36s OK" % ten, flush=True)
        else:
            print("   %-36s khong nhan duoc anh" % ten, flush=True)
        cam.stop()
        cam.destroy()
        time.sleep(1.5)

    if args.video:
        print("[4/4] Quay video bay mot vong quanh khu vuc", flush=True)
        import cv2
        os.makedirs(os.path.dirname(args.video), exist_ok=True)
        vw = cv2.VideoWriter(args.video, cv2.VideoWriter_fourcc(*"mp4v"),
                             args.fps, (W, H))
        cam = gan_camera(world, xe, carla.Transform(
            carla.Location(x=-150, z=85), carla.Rotation(pitch=-34)))
        q = Queue()
        cam.listen(q.put)

        # Xe hero DUNG YEN (xem bay so 3). Chi doi transform TUONG DOI cua camera:
        # voi actor da gan, set_transform() dat vi tri tuong doi so voi vat cha,
        # nen camera bay vong quanh xe ma xe khong he nhuc nhich.
        tong = int(args.vong_giay * args.fps)
        try:
            for i in range(tong):
                t = i / max(tong - 1, 1)
                goc_quay = 2 * math.pi * t
                # Ban kinh va do cao giam dan: mo dau nhin bao quat, ket thuc ha
                # xuong gan ngang tam duong.
                r = 150.0 - 118.0 * t
                z = 85.0 - 74.0 * t
                pitch = -34.0 + 26.0 * t
                cam.set_transform(carla.Transform(
                    carla.Location(x=-r * math.cos(goc_quay),
                                   y=-r * math.sin(goc_quay), z=z),
                    carla.Rotation(pitch=pitch, yaw=math.degrees(goc_quay))))
                world.wait_for_tick()
                try:
                    img = q.get(timeout=5.0)
                except Empty:
                    continue
                arr = np.frombuffer(img.raw_data, dtype=np.uint8).reshape((H, W, 4))
                fr = arr[:, :, :3].copy()
                cv2.rectangle(fr, (0, 0), (W, 44), (0, 0, 0), -1)
                cv2.putText(fr, "Map %s - sinh bang Digital Twin Tool tu OpenStreetMap"
                            % args.map, (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                            (255, 255, 255), 2, cv2.LINE_AA)
                vw.write(fr)
                if i % 60 == 0:
                    print("   ...%d/%d" % (i, tong), flush=True)
        finally:
            cam.stop()
            cam.destroy()
            vw.release()
        print("   da ghi: %s (%.1f MB)"
              % (args.video, os.path.getsize(args.video) / 1e6), flush=True)

    try:
        xe.destroy()
    except Exception:
        pass
    print("Xong.", flush=True)


if __name__ == "__main__":
    main()
