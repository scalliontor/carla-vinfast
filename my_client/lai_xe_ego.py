#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bật autopilot cho xe ego của Scenario Runner
=============================================

VÌ SAO CẦN
    Đây là chỗ dễ hiểu nhầm nhất của Scenario Runner: ở chế độ `--scenario`,
    công cụ CHỈ dựng kịch bản và chấm điểm — nó KHÔNG lái xe ego.

    Xe ego phải do ta cấp người lái. Có ba cách:

        1. `manual_control.py` — người lái bằng bàn phím
        2. `--agent <file>` — nhưng cờ này CHỈ chấp nhận ở chế độ `--route`
        3. autopilot của Traffic Manager — script này

    Nếu không cấp gì, xe đứng yên, điều kiện kết thúc `DriveDistance(ego, 150 m)`
    không bao giờ thoả, và kịch bản chạy tới khi chạm tiêu chí Timeout —
    mặc định 100000 giây. Nhìn bên ngoài giống hệt treo máy.

    (Chế độ `--openscenario2` thì khác: file .osc tự khai báo hành vi cho cả
    xe ego, nên không cần script này.)

CHẠY
    Bật ở cửa sổ khác, SAU khi kịch bản đã in "Running scenario":

        python my_client\lai_xe_ego.py
"""

import argparse
import math
import sys
import time

import carla

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--cho", type=float, default=120.0,
                    help="so giay cho xe ego xuat hien")
    ap.add_argument("--vuot-den-do", action="store_true",
                    help="bo qua den do, de kich ban khong ket thuc giua chung")
    args = ap.parse_args()

    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    tm = client.get_trafficmanager()

    print("Dang cho xe ego (role_name='hero') xuat hien ...")
    hero = None
    t0 = time.time()
    while time.time() - t0 < args.cho:
        for v in world.get_actors().filter("vehicle.*"):
            if v.attributes.get("role_name") == "hero":
                hero = v
                break
        if hero:
            break
        time.sleep(1.0)

    if hero is None:
        raise SystemExit("Khong thay xe ego. Kich ban da chay chua?")

    # Traffic Manager phai cung che do dong bo voi world. Scenario Runner chay
    # o che do BAT DONG BO nen khong can dat gi them; neu ban tu chuyen world
    # sang dong bo thi phai goi tm.set_synchronous_mode(True) o day.
    hero.set_autopilot(True, tm.get_port())
    if args.vuot_den_do:
        tm.ignore_lights_percentage(hero, 100)

    print("Da bat autopilot: %s id=%d" % (hero.type_id, hero.id))

    try:
        # Khi kich ban ket thuc, Scenario Runner huy xe ego. Luc do `is_alive` van
        # tra ve True mot luc va `get_velocity()` tra ve 0 thay vi nem loi, nen
        # phai tu dem so lan doc duoc 0 lien tiep de biet da xong.
        dung_yen = 0
        while True:
            if hero.id not in [a.id for a in world.get_actors().filter("vehicle.*")]:
                break
            v = hero.get_velocity()
            toc_do = 3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)
            print("  toc do %5.1f km/h" % toc_do, flush=True)
            dung_yen = dung_yen + 1 if toc_do < 0.1 else 0
            if dung_yen >= 8:
                break
            time.sleep(1.0)
    except (KeyboardInterrupt, RuntimeError):
        pass
    print("Xe ego khong con — kich ban da ket thuc.")


if __name__ == "__main__":
    main()
