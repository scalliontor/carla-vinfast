@echo off
REM ============================================================================
REM  Bien moi truong cho Scenario Runner - CHI co hieu luc trong phien shell nay
REM  Dung:  call env.bat
REM ----------------------------------------------------------------------------
REM  Tai lieu chinh thuc (muc "Set environment variables"):
REM  https://scenario-runner.readthedocs.io/en/latest/getting_scenariorunner/
REM ============================================================================

set "CARLA_ROOT=D:\Hunganh\carla_tuan"
set "SCENARIO_RUNNER_ROOT=D:\Hunganh\carla-scenario\scenario_runner"

REM Tai lieu yeu cau 2 duong dan tren PYTHONPATH:
REM
REM   1) %CARLA_ROOT%\PythonAPI\carla\dist\carla-<VERSION>.egg
REM      -> BO QUA o day. Thu muc dist\ trong ban build source nay dang TRONG
REM         (chua chay BuildPythonAPI.bat de sinh wheel/egg).
REM         Thay vao do module `carla` da duoc cai bang pip (carla==0.9.16)
REM         vao .venv-sr, nen Python tim thay `import carla` tu site-packages.
REM         Ket qua giong nhau; egg chi la mot cach dong goi khac.
REM
REM   2) %CARLA_ROOT%\PythonAPI\carla
REM      -> BAT BUOC phai co. Scenario Runner import `agents.navigation.*`
REM         (BasicAgent, LocalPlanner, GlobalRoutePlanner). Package `agents`
REM         KHONG nam trong wheel carla tren PyPI, no chi nam trong source tree
REM         cua CARLA. Thieu dong nay se bao: ModuleNotFoundError: No module
REM         named 'agents'

set "PYTHONPATH=%PYTHONPATH%;%CARLA_ROOT%\PythonAPI\carla"

REM Python cua venv rieng cho Scenario Runner.
REM Venv rieng vi requirements.txt cua SR ghim numpy==1.24.4, py-trees==0.8.3,
REM networkx==3.4.2 - cai de vao .venv chinh se ha cap va pha moi truong client.
set "SR_PYTHON=D:\Hunganh\carla-scenario\.venv-sr\Scripts\python.exe"

echo [env] CARLA_ROOT           = %CARLA_ROOT%
echo [env] SCENARIO_RUNNER_ROOT = %SCENARIO_RUNNER_ROOT%
echo [env] SR_PYTHON            = %SR_PYTHON%
