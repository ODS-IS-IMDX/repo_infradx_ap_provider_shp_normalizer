# © 2026 NTT DATA Japan Co., Ltd. & NTT InfraNet All Rights Reserved.

from cx_Freeze import setup, Executable
import sys
import os
from distutils.command.build import build as _build
from distutils.command.bdist import bdist as _bdist

# カレントディレクトリをプロジェクトルートとして取得
project_root = os.getcwd()
src_dir = os.path.join(project_root, "src")
config_dir = os.path.join(project_root, "config")
builds_dir = os.path.join(project_root, "builds")

# buildとbdistコマンドをカスタマイズしてbuilds/フォルダ内にビルド成果物を集約
class build(_build):
    def initialize_options(self):
        super().initialize_options()
        self.build_base = os.path.join(project_root, "builds", "build")

class bdist(_bdist):
    def initialize_options(self):
        super().initialize_options()
        self.bdist_base = os.path.join(project_root, "builds", "build")

# cx_Freezeで直接ビルド（PyInstaller不使用）
build_exe_options = {
    "build_exe": os.path.join(builds_dir, "build", "exe"),
    "packages": [
        "geopandas",
        "pandas",
        "shapely",
        "pyogrio",
        "pyproj",
        "numpy",
        "tkinter",
    ],
    "include_files": [
        (os.path.join(config_dir, "config.json"), "config.json"),
    ],
    "excludes": [
        "matplotlib",
        "scipy",
        "PIL",
        "pygments",
        "unittest",
    ],
}

# MSIオプション
bdist_msi_options = {
    "upgrade_code": "{12345678-1234-1234-1234-123456789013}",
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\ShapefileNormalizerTool",
}

setup(
    name="ShapefileNormalizerTool",
    version="1.0.0",
    description="Shapefile正規化ツール",
    author="NTT DATA Japan Co., Ltd.",
    copyright="© 2026 NTT DATA Japan Co., Ltd. & NTT InfraNet All Rights Reserved.",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
        "egg_info": {
            "egg_base": os.path.join(builds_dir),
        },
    },
    cmdclass={
        "build": build,
        "bdist": bdist,
    },
    executables=[
        Executable(
            os.path.join(src_dir, "shapefile_normalizer_gui.py"),
            base="gui" if sys.platform == "win32" else None,
            target_name="ShapefileNormalizerTool.exe",
            icon=None,
            shortcut_name="Shapefile正規化ツール",
            shortcut_dir="DesktopFolder",  # デスクトップにショートカット作成
        )
    ],
)
