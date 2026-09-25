@echo off
REM ============================================================================
REM  Khoi dong CARLA server tu ban build SOURCE (khong phai ban release)
REM ----------------------------------------------------------------------------
REM  Tai lieu SR muc "Running a scenario" noi:
REM     - ban source : cd ~/carla && make launch  -> roi bam Play trong UE Editor
REM     - ban release: ./CarlaUE4.sh
REM
REM  May nay la ban SOURCE nhung KHONG co `make`. Doc Makefile thi `make launch`
REM  chi la wrapper goi UE4Editor.exe voi file .uproject. Nen ta goi thang, va
REM  them co `-game` de vao thang che do server - khong phai mo editor roi bam
REM  Play bang tay.
REM
REM  Co dung o day:
REM     -game              chay nhu game/server, bo qua giao dien editor
REM     -quality-level=Low giam tai GPU (may dung chung, desktop da chiem ~9GB)
REM     -carla-rpc-port    cong RPC. CARLA con dung 2001 (streaming) + 2002
REM     -nosound           bo am thanh
REM
REM  KHONG dung -RenderOffScreen o day: Task #1 can NHIN THAY kich ban de quay
REM  lam bang chung. Khi thu du lieu cam bien (Task #2) thi them co do vao cho
REM  nhe GPU - camera van render binh thuong vi UE render vao texture.
REM ============================================================================

set "CARLA_ROOT=D:\Hunganh\carla_tuan"
set "UE4=%CARLA_ROOT%\UnrealEngine_4.26\Engine\Binaries\Win64\UE4Editor.exe"

echo Starting CARLA server (RPC port 2000)...
echo Doi 1-3 phut cho den khi cua so hien ban do.
pushd "%CARLA_ROOT%\Unreal\CarlaUE4"
"%UE4%" "%CARLA_ROOT%\Unreal\CarlaUE4\CarlaUE4.uproject" -game -nosound -quality-level=Low -carla-rpc-port=2000
popd
