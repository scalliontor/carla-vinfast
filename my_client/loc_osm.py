#!/usr/bin/env python
"""
Lọc file OSM trước khi đưa vào Digital Twin Tool
=================================================

VÌ SAO CẦN
    Widget Digital Twin gọi osm2odr với THAM SỐ MẶC ĐỊNH và không cho ta chỉnh
    danh sách loại đường. Với dữ liệu đô thị dày (Hoàn Kiếm, phố cổ), nó gặp
    làn đường suy biến rồi sập Editor:

        EXCEPTION_ACCESS_VIOLATION reading address 0xfffffffffffffff0
        std::vector<NWWriter_OpenDrive::LanePoint>::back()
        NWWriter_OpenDrive::writeNetwork()
        osm2odr::ConvertOSMToOpenDRIVE()

    Địa chỉ 0xffff...f0 là dấu hiệu gọi .back() trên vector RỖNG — osm2odr
    thiếu kiểm tra rỗng. Đây là lỗi của CARLA, không phải của dữ liệu:
    cùng file đó, gọi carla.Osm2Odr.convert() từ Python (có khai báo rõ
    set_osm_way_types) thì chạy tốt cả ba mức chi tiết.

    Không sửa được widget thì sửa đầu vào: bỏ hẳn các loại đường không lái xe
    được ra khỏi file .osm. Chúng vốn không dùng để dựng đường, chỉ gây rủi ro.

GIỮ LẠI
    - way có thẻ `highway` thuộc danh sách lái xe được
    - way có thẻ `building` (để Digital Twin dựng nhà)
    - node được các way đó tham chiếu, cộng node có tên/thẻ đáng giữ

BỎ ĐI
    footway, path, steps, pedestrian, cycleway, track, corridor, bridleway...
    và các way không liên quan (waterway, barrier rời...)

CHẠY
    .venv-sr\\Scripts\\python.exe my_client\\loc_osm.py osm\\ho_guom.osm osm\\ho_guom_clean.osm
"""

import sys
import xml.etree.ElementTree as ET
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


# Dung danh sach GIU LAI (allowlist) thay vi danh sach loai bo, vi OSM co hang
# tram gia tri `highway=` khac nhau — liet ke cai xau khong bao gio du.
GIU_HIGHWAY = {
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service",
}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    src, dst = sys.argv[1], sys.argv[2]

    tree = ET.parse(src)
    root = tree.getroot()

    ways = root.findall("way")
    nodes = root.findall("node")
    rels = root.findall("relation")
    print("Dau vao : %d node, %d way, %d relation" % (len(nodes), len(ways), len(rels)))

    giu_way, bo_way = [], []
    bo_theo_loai = Counter()

    for w in ways:
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        if "highway" in tags:
            if tags["highway"] in GIU_HIGHWAY:
                giu_way.append(w)
            else:
                bo_way.append(w)
                bo_theo_loai[tags["highway"]] += 1
        elif "building" in tags:
            giu_way.append(w)          # giu de Digital Twin dung nha
        else:
            bo_way.append(w)
            bo_theo_loai["(khong phai duong/nha)"] += 1

    # Tap node can giu: moi node ma cac way duoc giu tham chieu toi
    can_giu = set()
    for w in giu_way:
        for nd in w.findall("nd"):
            can_giu.add(nd.get("ref"))

    giu_node = [n for n in nodes if n.get("id") in can_giu]

    # Xoa khoi cay XML nhung thu khong giu.
    # Quan he (relation) bi bo het: chung tham chieu cheo toi way da xoa, de lai
    # se thanh tham chieu hong.
    for w in bo_way:
        root.remove(w)
    for n in nodes:
        if n.get("id") not in can_giu:
            root.remove(n)
    for r in rels:
        root.remove(r)

    tree.write(dst, encoding="utf-8", xml_declaration=True)

    print("Giu lai : %d node, %d way" % (len(giu_node), len(giu_way)))
    print("Da bo   : %d way, %d node, %d relation"
          % (len(bo_way), len(nodes) - len(giu_node), len(rels)))
    print()
    print("Loai duong da bo (10 nhieu nhat):")
    for k, v in bo_theo_loai.most_common(10):
        print("   %-26s %d" % (k, v))
    print()
    print("Da ghi:", dst)


if __name__ == "__main__":
    main()
