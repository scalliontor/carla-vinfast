"""
Chay hang loat kich ban OpenSCENARIO 2 bang Scenario Runner, gom ket qua thanh bang.

Dung:
    .venv-sr\Scripts\python.exe run_batch.py                  # chay bo mac dinh
    .venv-sr\Scripts\python.exe run_batch.py a.osc b.osc      # chay danh sach tu chon

Vi sao can script nay thay vi go tay tung lenh:
  1. PYTHONIOENCODING=utf-8  -> console Windows mac dinh cp1252 khong ma hoa noi
     ky tu ke bang Unicode cua bang ket qua -> UnicodeEncodeError.
  2. --outputDir bi bug: scenario_runner ghep thang duong dan file .osc vao ten file
     ket qua (scenario_runner.py:279), sinh ra thu muc con khong ton tai.
     -> phai tao truoc <outdir>/srunner/examples/
  3. --timeout phai lon: ban build tu source nap map lan dau mat ~370s (bien dich shader).
"""
import json
import os
import pathlib
import subprocess
import sys

# Console Windows mac dinh cp1252 -> khong in noi ky tu ke bang Unicode cua
# bang ket qua. Phai ep ca tien trinh NAY sang utf-8, khong chi tien trinh con.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

ROOT = pathlib.Path(__file__).resolve().parent
SR = ROOT / "scenario_runner"
# Trong Docker hai bien nay do image dat san; tren Windows dung mac dinh cu.
PY = pathlib.Path(os.environ.get("SR_PYTHON", ROOT / ".venv-sr" / "Scripts" / "python.exe"))
CARLA_ROOT = pathlib.Path(os.environ.get("CARLA_ROOT", r"D:\Hunganh\carla_tuan"))
OUTDIR = ROOT / "evidence" / "task1"

# Mac dinh: 5 kich ban khac nhau ve hanh vi, TAT CA deu dung Town04
# (tranh doi map -> moi map moi phai bien dich shader lai tu dau).
DEFAULT = [
    "keep_lane.osc",              # giu lan - khong co tinh huong nguy hiem
    "acceleration.osc",           # tang toc
    "change_lane.osc",            # chuyen lan
    "overtake1.osc",              # vuot
    "one_of.osc",                 # toan tu chon ngau nhien mot nhanh
    "cut_in_and_slow_range.osc",  # cat dau + giam toc (bai test kho)
]


def run_one(name: str) -> dict:
    rel = f"srunner/examples/{name}"
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(CARLA_ROOT / "PythonAPI" / "carla"),
        "CARLA_ROOT": str(CARLA_ROOT),
        "SCENARIO_RUNNER_ROOT": str(SR),
    }
    cmd = [
        str(PY), "-u", "scenario_runner.py",
        "--sync", "--timeout", "600",
        "--openscenario2", rel,
        "--output", "--file", "--json",
        "--outputDir", str(OUTDIR),
    ]
    print(f"\n{'='*70}\n  {name}\n{'='*70}", flush=True)
    p = subprocess.run(cmd, cwd=SR, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    out = p.stdout or ""
    for line in out.splitlines():
        if line.startswith(("WARNING: ", "INFO: ")):
            continue
        print(line, flush=True)
    if p.returncode != 0 and p.stderr:
        print("--- stderr ---", flush=True)
        print(p.stderr[-2000:], flush=True)
    return {"scenario": name, "returncode": p.returncode, "stdout": out}


def latest_json(name: str):
    """Doc file .json moi nhat ma scenario_runner vua ghi cho kich ban nay."""
    d = OUTDIR / "srunner" / "examples"
    files = sorted(d.glob(f"{name}*.json"), key=lambda f: f.stat().st_mtime)
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def main():
    names = sys.argv[1:] or DEFAULT
    # Va bug --outputDir: tao truoc cay thu muc ma scenario_runner se ghi vao.
    (OUTDIR / "srunner" / "examples").mkdir(parents=True, exist_ok=True)

    rows = []
    for n in names:
        if not (SR / "srunner" / "examples" / n).is_file():
            rows.append((n, "KHONG CO FILE", "", ""))
            continue
        run_one(n)
        j = latest_json(n)
        if j is None:
            rows.append((n, "KHONG CO KET QUA", "", ""))
            continue
        coll = next((c for c in j["criteria"] if c["name"] == "CollisionTest"), None)
        dur = next((c for c in j["criteria"] if c["name"] == "Duration"), None)
        rows.append((
            n,
            "SUCCESS" if j["success"] else "FAILURE",
            f"{coll['actual']}" if coll else "-",
            f"{dur['actual']:.1f}s" if dur else "-",
        ))

    print(f"\n\n{'='*74}")
    print("  TONG KET")
    print(f"{'='*74}")
    print(f"  {'Kich ban':<38} {'Ket qua':<9} {'Va cham':<8} {'Game time'}")
    print(f"  {'-'*38} {'-'*9} {'-'*8} {'-'*10}")
    for n, res, coll, dur in rows:
        print(f"  {n:<38} {res:<9} {coll:<8} {dur}")
    print(f"{'='*74}")
    print(f"  Ket qua chi tiet: {OUTDIR / 'srunner' / 'examples'}")


if __name__ == "__main__":
    main()
