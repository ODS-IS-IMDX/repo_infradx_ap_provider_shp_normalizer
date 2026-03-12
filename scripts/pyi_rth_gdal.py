# -*- coding: utf-8 -*-
# © 2026 NTT DATA Japan Co., Ltd. & NTT InfraNet All Rights Reserved.
# PyInstaller runtime hook for GDAL/pyogrio

import os
import sys

# 実行時のディレクトリをPATHに追加
if hasattr(sys, '_MEIPASS'):
    meipass = sys._MEIPASS
    
    # 複数のパスをPATHに追加
    paths_to_add = [
        meipass,
        os.path.join(meipass, 'pyogrio'),
        os.path.join(meipass, 'pyogrio', '.libs'),
    ]
    
    for path in paths_to_add:
        if os.path.exists(path):
            os.environ['PATH'] = path + os.pathsep + os.environ.get('PATH', '')
    
    # GDAL_DATAの設定（複数の場所を試す）
    gdal_data_locations = [
        os.path.join(meipass, 'pyogrio', 'gdal_data'),
        os.path.join(meipass, 'gdal_data'),
    ]
    
    for gdal_data_path in gdal_data_locations:
        if os.path.exists(gdal_data_path):
            os.environ['GDAL_DATA'] = gdal_data_path
            break
    
    # PROJ_LIBの設定
    proj_lib = os.path.join(meipass, 'proj')
    if os.path.exists(proj_lib):
        os.environ['PROJ_LIB'] = proj_lib
    
    # pyogrioのDLLロードパスを設定
    try:
        if hasattr(os, 'add_dll_directory'):
            # Windows 10以降
            for path in paths_to_add:
                if os.path.exists(path):
                    os.add_dll_directory(path)
    except Exception:
        pass
