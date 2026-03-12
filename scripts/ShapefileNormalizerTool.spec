# -*- mode: python ; coding: utf-8 -*-
# © 2026 NTT DATA Japan Co., Ltd. & NTT InfraNet All Rights Reserved.

import os
import sys
from pathlib import Path

# スクリプトのディレクトリを取得（.specファイルがあるディレクトリ）
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.dirname(spec_dir)
src_file = os.path.join(project_root, 'src', 'shapefile_normalizer_gui.py')
config_file = os.path.join(project_root, 'config', 'config.json')

# GDALのDLLを含める設定
binaries_list = []
datas_list = [(config_file, '.')]

# pyogrioとGDALのバイナリを含める
try:
    import pyogrio
    pyogrio_path = Path(pyogrio.__file__).parent
    print(f"[INFO] pyogrio found at: {pyogrio_path}")
    
    # pyogrioディレクトリ全体を再帰的に探索
    # DLLファイルを探す（サブディレクトリも含む）
    dll_count = 0
    for dll in pyogrio_path.rglob('*.dll'):
        rel_path = dll.parent.relative_to(pyogrio_path.parent)
        binaries_list.append((str(dll), str(rel_path)))
        dll_count += 1
        print(f"[INFO] Found DLL: {dll.name} -> {rel_path}")
    print(f"[INFO] Total DLLs found: {dll_count}")
    
    # gdal_dataディレクトリを探す
    gdal_data_path = pyogrio_path / 'gdal_data'
    if gdal_data_path.exists():
        datas_list.append((str(gdal_data_path), 'pyogrio/gdal_data'))
        print(f"[INFO] Added gdal_data from: {gdal_data_path}")
    
    # PROJデータも含める
    proj_path = pyogrio_path.parent / 'pyproj' / 'proj_dir' / 'share' / 'proj'
    if proj_path.exists():
        datas_list.append((str(proj_path), 'proj'))
        print(f"[INFO] Added PROJ data from: {proj_path}")
    
    # pyogrio自体もデータとして追加（念のため）
    datas_list.append((str(pyogrio_path), 'pyogrio'))
    print(f"[INFO] Added pyogrio package directory")
    
except ImportError as e:
    print(f"[WARNING] pyogrio not found: {e}")
except Exception as e:
    print(f"[ERROR] Error collecting pyogrio files: {e}")

a = Analysis(
    [src_file],
    pathex=[],
    binaries=binaries_list,
    datas=datas_list,
    hiddenimports=[
        'pyogrio',
        'pyogrio._io',
        'pyogrio._env',
        'pyogrio._ogr',
        'pyogrio.raw',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(spec_dir, 'pyi_rth_gdal.py')],
    excludes=[],
    noarchive=False,
)

print(f"[INFO] Total binaries: {len(a.binaries)}")
print(f"[INFO] Total datas: {len(a.datas)}")
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ShapefileNormalizerTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
