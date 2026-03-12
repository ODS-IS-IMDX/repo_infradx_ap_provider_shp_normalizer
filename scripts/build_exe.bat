@echo off
REM © 2026 NTT DATA Japan Co., Ltd. & NTT InfraNet All Rights Reserved.

chcp 65001 >nul

REM このスクリプトのディレクトリに移動
cd /d "%~dp0"

echo ========================================
echo Shapefile変換ツール - EXE Build
echo パターン1: PyInstallerのみ（単一EXE）
echo ========================================
echo.

echo [Step 1/2] 依存ライブラリのインストール...
echo.
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ../requirements.txt
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pyinstaller
echo.
echo [pyogrio] バイナリホイールをインストール中...
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --only-binary :all: pyogrio
echo.

echo [Step 2/2] EXEファイルをビルド中...
echo （この処理には数分かかります）
echo.
python -m PyInstaller --distpath ../builds/dist --workpath ../builds/build ShapefileNormalizerTool.spec

echo.
if %errorlevel% neq 0 goto :build_failed

echo ========================================
echo ビルド完了！
echo ========================================
echo.
echo 実行ファイル: ..\builds\dist\ShapefileNormalizerTool.exe
echo.
echo このEXEファイルは:
echo   [*] 他のPCでもそのまま実行可能
echo   [*] Pythonのインストール不要
echo   [*] ライブラリのインストール不要
echo.
pause
exit /b 0

:build_failed
echo ========================================
echo エラー: ビルドに失敗しました
echo ========================================
echo.
pause
exit /b 1
