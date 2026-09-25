#!/usr/bin/env python
"""
Khảo sát chất lượng dữ liệu OSM trước khi dựng map
===================================================

VÌ SAO CẦN CÔNG CỤ NÀY
    Chất lượng map Digital Twin phụ thuộc HOÀN TOÀN vào độ đầy đủ của dữ liệu
    OSM, không phụ thuộc công cụ. Dựng thử một vùng mất 8-10 phút sinh mesh
    cộng hơn một giờ lưu map — quá đắt để thử sai.

    Script này đọc file .osm và chấm điểm trong vài giây, cho biết trước vùng
    đó có đáng dựng hay không.

BA CHỈ SỐ QUAN TRỌNG NHẤT

    1. building:levels  — QUYẾT ĐỊNH SỐ NHÀ DỰNG ĐƯỢC
       Digital Twin chỉ đùn khối được cho toà nhà biết chiều cao. Không có
       `height` hay `building:levels` thì bỏ qua. Đo trên khu VinUni: chỉ
       30/206 toà có thẻ này -> map dựng ra thưa.

    2. lanes            — QUYẾT ĐỊNH ĐƯỜNG CÓ ĐÚNG SỐ LÀN
       Thiếu thẻ này thì mọi đường bị gán cùng một độ rộng làn mặc định,
       nên đường lớn và ngõ nhỏ trông giống hệt nhau.

    3. Tỉ lệ đường có tên — chỉ báo mức độ "đã được ai đó chăm sóc kỹ"
       Vùng được cộng đồng map kỹ thường đầy đủ cả ba.

CHẠY
    .venv-sr\\Scripts\\python.exe my_client\\khao_sat_osm.py osm\\*.osm
"""

import sys
import glob
import math
import xml.etree.ElementTree as ET
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


# Loại đường mà osm2odr / Digital Twin thực sự đưa vào map.
DRIVABLE = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential",
}


def do_dai_met(pts):
    """Độ dài một đường, tính bằng mét (xấp xỉ phẳng, đủ dùng ở quy mô km)."""
    tong = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(pts, pts[1:]):
        dx = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
        dy = (lat2 - lat1) * 110540
        tong += math.hypot(dx, dy)
    return tong


def khao_sat(path):
    root = ET.parse(path).getroot()
    nodes = {n.get("id"): (float(n.get("lon")), float(n.get("lat")))
             for n in root.findall("node")}

    b = root.find("bounds")
    dien_tich = None
    if b is not None:
        la0, la1 = float(b.get("minlat")), float(b.get("maxlat"))
        lo0, lo1 = float(b.get("minlon")), float(b.get("maxlon"))
        rong = (lo1 - lo0) * 111320 * math.cos(math.radians((la0 + la1) / 2))
        cao = (la1 - la0) * 110540
        dien_tich = rong * cao / 1e6          # km2

    n_road = n_drivable = 0
    dai_drivable = 0.0
    road_co_ten = road_co_lanes = road_co_toc_do = 0
    loai_duong = Counter()

    n_build = build_co_cao = build_co_ten = 0
    loai_nha = Counter()

    for w in root.findall("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        pts = [nodes[nd.get("ref")] for nd in w.findall("nd") if nd.get("ref") in nodes]

        if "highway" in tags:
            n_road += 1
            hw = tags["highway"]
            loai_duong[hw] += 1
            if hw in DRIVABLE:
                n_drivable += 1
                if len(pts) >= 2:
                    dai_drivable += do_dai_met(pts)
                if "name" in tags:
                    road_co_ten += 1
                if "lanes" in tags:
                    road_co_lanes += 1
                if "maxspeed" in tags:
                    road_co_toc_do += 1

        elif "building" in tags:
            n_build += 1
            loai_nha[tags["building"]] += 1
            # Digital Twin can MOT TRONG HAI the nay de biet chieu cao
            if "height" in tags or "building:levels" in tags:
                build_co_cao += 1
            if "name" in tags:
                build_co_ten += 1

    return {
        "file": path.split("\\")[-1].split("/")[-1],
        "dien_tich_km2": dien_tich,
        "n_road": n_road,
        "n_drivable": n_drivable,
        "km_duong": dai_drivable / 1000.0,
        "road_ten": road_co_ten,
        "road_lanes": road_co_lanes,
        "road_toc_do": road_co_toc_do,
        "n_build": n_build,
        "build_cao": build_co_cao,
        "build_ten": build_co_ten,
        "loai_duong": loai_duong,
        "loai_nha": loai_nha,
    }


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def in_ket_qua(k):
    print("\n" + "=" * 68)
    print("  " + k["file"])
    print("=" * 68)
    if k["dien_tich_km2"]:
        print("  Dien tich vung        : %.2f km2" % k["dien_tich_km2"])

    print("\n  DUONG")
    print("    tong so way highway : %d" % k["n_road"])
    print("    trong do chay xe duoc: %d  (%.1f km)" % (k["n_drivable"], k["km_duong"]))
    print("    co ten              : %4d  (%.0f%%)" % (k["road_ten"], pct(k["road_ten"], k["n_drivable"])))
    print("    co so lan `lanes`   : %4d  (%.0f%%)   <- quyet dinh do rong dung/sai"
          % (k["road_lanes"], pct(k["road_lanes"], k["n_drivable"])))
    print("    co `maxspeed`       : %4d  (%.0f%%)" % (k["road_toc_do"], pct(k["road_toc_do"], k["n_drivable"])))
    top = ", ".join("%s=%d" % (a, b) for a, b in k["loai_duong"].most_common(5))
    print("    pho bien nhat       : %s" % top)

    print("\n  NHA")
    print("    tong footprint      : %d" % k["n_build"])
    print("    CO CHIEU CAO        : %4d  (%.0f%%)   <- SO NHA DUNG DUOC"
          % (k["build_cao"], pct(k["build_cao"], k["n_build"])))
    print("    co ten              : %4d  (%.0f%%)" % (k["build_ten"], pct(k["build_ten"], k["n_build"])))

    # Cham diem tong hop
    diem = 0
    diem += 40 * min(1.0, pct(k["build_cao"], k["n_build"]) / 50.0)   # 50% la rat tot
    diem += 30 * min(1.0, pct(k["road_lanes"], k["n_drivable"]) / 50.0)
    diem += 20 * min(1.0, pct(k["road_ten"], k["n_drivable"]) / 80.0)
    diem += 10 * min(1.0, k["km_duong"] / 30.0)
    if diem >= 70:
        danh_gia = "RAT TOT - nen dung vung nay"
    elif diem >= 45:
        danh_gia = "KHA - dung duoc, map se hoi thua"
    elif diem >= 25:
        danh_gia = "YEU - map se rat thua nha"
    else:
        danh_gia = "KEM - khong nen dung"
    print("\n  DIEM TONG HOP: %.0f/100  ->  %s" % (diem, danh_gia))


def main():
    args = sys.argv[1:]
    paths = []
    for a in args:
        paths.extend(glob.glob(a))
    if not paths:
        print("Khong tim thay file .osm nao. Vi du:")
        print("   python my_client\\khao_sat_osm.py osm\\*.osm")
        return

    ket_qua = []
    for p in sorted(set(paths)):
        try:
            k = khao_sat(p)
            in_ket_qua(k)
            ket_qua.append(k)
        except Exception as e:
            print("\n[loi] %s -> %s" % (p, e))

    if len(ket_qua) > 1:
        print("\n" + "=" * 68)
        print("  SO SANH")
        print("=" * 68)
        print("  %-26s %7s %7s %8s %8s" % ("vung", "km duong", "nha", "co cao", "co lanes"))
        print("  " + "-" * 62)
        for k in ket_qua:
            print("  %-26s %7.1f %7d %7.0f%% %7.0f%%" % (
                k["file"][:26], k["km_duong"], k["n_build"],
                pct(k["build_cao"], k["n_build"]),
                pct(k["road_lanes"], k["n_drivable"])))


if __name__ == "__main__":
    main()
