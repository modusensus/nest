#!/usr/bin/env python3
"""PyInstaller 打包入口：让 FastAPI 后端 + 前端静态文件打包为单个 .exe。
在 electron/ 目录下运行：
  1. 先构建前端：cd ../frontend && npm run build
  2. 然后打包后端：cd ../electron && python build_backend.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
ELECTRON = ROOT / "electron"
OUTPUT = ELECTRON / "backend-dist"

# 确保前端已构建
if not (FRONTEND_DIST / "index.html").exists():
    print("[错误] 前端未构建，请先运行: cd frontend && npm run build")
    sys.exit(1)

# 确保后端 .env 存在
env_example = BACKEND / ".env.example"
env_file = BACKEND / ".env"
if not env_file.exists() and env_example.exists():
    import shutil
    shutil.copy(env_example, env_file)
    print(f"[初始化] 已创建 {env_file}，请编辑后重新运行")
    sys.exit(0)

# 创建临时 spec 文件
spec = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, r'{BACKEND}')
a = Analysis(
    [r'{BACKEND / 'app' / 'main.py'}'],
    pathex=[r'{BACKEND}'],
    binaries=[],
    datas=[
        (r'{FRONTEND_DIST}', 'frontend/dist'),
        (r'{BACKEND / '.env'}', '.'),
    ],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ai-workbench',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""

spec_path = ELECTRON / "ai-workbench.spec"
spec_path.write_text(spec, encoding="utf-8")
print(f"[PyInstaller] 已生成 spec 文件: {spec_path}")

# 运行 PyInstaller
OUTPUT.mkdir(parents=True, exist_ok=True)
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--distpath", str(OUTPUT),
    "--workpath", str(ELECTRON / "build-temp"),
    "--clean",
    "--noconfirm",
    str(spec_path),
]
print(f"[PyInstaller] 正在打包...")
subprocess.run(cmd, check=True)

exe_path = OUTPUT / "ai-workbench.exe"
if exe_path.exists():
    print(f"[成功] 后端打包完成: {exe_path}")
else:
    print(f"[错误] 打包失败，未找到 {exe_path}")
    sys.exit(1)