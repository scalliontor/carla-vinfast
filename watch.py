"""
Camera bam theo xe trong kich ban - de NHIN THAY kich ban dang dien ra.

Dung (cua so rieng, chay TRUOC khi bat kich ban):
    .venv-sr\Scripts\python.exe watch.py

Vi sao can script nay:
  Cua so CARLA mo bang co -game la mot SERVER, khong phai game de choi.
  Trong do khong co dieu khien nao ca - khong lai duoc, khong bay camera duoc.
  Goc nhin trong cua so do la "spectator", va cach duy nhat de di chuyen no
  la qua Python API: world.get_spectator().set_transform(...)

  Script nay lam dung mot viec: moi vong lap, tim xe ego roi dat spectator
  ra phia sau + ben tren no, nhin theo huong xe chay.
"""
import time

import carla

HOST, PORT = "127.0.0.1", 2000
DIST_BEHIND = 8.0   # met, lui ve phia sau xe
HEIGHT = 4.0        # met, nang len cao
PITCH = -15.0       # do, chuc xuong


def pick_ego(world):
    """Chon xe de bam theo: uu tien role_name hero/ego, roi den Tesla Model 3."""
    vehicles = list(world.get_actors().filter("vehicle.*"))
    if not vehicles:
        return None
    for v in vehicles:
        if v.attributes.get("role_name") in ("hero", "ego_vehicle"):
            return v
    for v in vehicles:
        if "model3" in v.type_id:
            return v
    return vehicles[0]


def main():
    client = carla.Client(HOST, PORT)
    client.set_timeout(30.0)
    world = client.get_world()
    spectator = world.get_spectator()

    print(f"Da noi toi {HOST}:{PORT} | map = {world.get_map().name}")
    print("Dang cho kich ban spawn xe... (Ctrl+C de dung)")

    current_id = None
    waiting_printed = False

    while True:
        ego = pick_ego(world)

        if ego is None:
            if not waiting_printed:
                print("  ... chua co xe nao trong the gioi")
                waiting_printed = True
            current_id = None
            time.sleep(0.5)
            continue

        if ego.id != current_id:
            current_id = ego.id
            waiting_printed = False
            print(f"  -> bam theo {ego.type_id} (id={ego.id}, "
                  f"role_name={ego.attributes.get('role_name')!r})")

        try:
            tf = ego.get_transform()
        except RuntimeError:
            # Xe vua bi huy giua chung -> quay lai vong lap tim xe khac
            current_id = None
            continue

        fwd = tf.get_forward_vector()
        loc = carla.Location(
            x=tf.location.x - fwd.x * DIST_BEHIND,
            y=tf.location.y - fwd.y * DIST_BEHIND,
            z=tf.location.z + HEIGHT,
        )
        rot = carla.Rotation(pitch=PITCH, yaw=tf.rotation.yaw, roll=0.0)
        spectator.set_transform(carla.Transform(loc, rot))

        time.sleep(0.03)   # ~30 lan/giay, du muot


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDa dung.")
