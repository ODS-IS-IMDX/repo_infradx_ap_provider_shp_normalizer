@echo off
REM © 2026 NTT DATA Japan Co., Ltd. & NTT InfraNet All Rights Reserved.

chcp 65001 >nul

REM このスクリプトのディレクトリに移動
cd /d "%~dp0"

echo ========================================
echo Shapefile変換ツール - cx_Freeze MSI Build
echo パターン2-MSI: cx_Freezeのみ（MSIインストーラー）
echo ========================================
echo.

echo [Step 1/3] 依存ライブラリのインストール...
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ../requirements.txt
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org cx_Freeze
echo.

echo [Step 2/3] ビルドディレクトリのクリーンアップ...
if exist ..\\builds\\build rmdir /s /q ..\\builds\\build
if exist ..\\builds\\dist rmdir /s /q ..\\builds\\dist
if exist ..\\builds\\ShapefileNormalizerTool.egg-info rmdir /s /q ..\\builds\\ShapefileNormalizerTool.egg-info
if exist ..\\src\\ShapefileNormalizerTool.egg-info rmdir /s /q ..\\src\\ShapefileNormalizerTool.egg-info
if exist ..\\build rmdir /s /q ..\\build
if exist build rmdir /s /q build
if exist ShapefileNormalizerTool.egg-info rmdir /s /q ShapefileNormalizerTool.egg-info
echo.

echo [Step 3/3] cx_FreezeでMSIをビルド中...
cd ..
python scripts\setup_cx_only.py bdist_msi --dist-dir=builds\dist
set BUILD_ERROR=%errorlevel%

REM egg-infoとbuildフォルダをbuildsフォルダに移動（念のため）
if exist build (
    if not exist builds\build mkdir builds\build
    xcopy /E /I /Y build builds\build_temp >nul 2>&1
    rmdir /s /q build
)
if exist ShapefileNormalizerTool.egg-info (
    if not exist builds mkdir builds
    move ShapefileNormalizerTool.egg-info builds\ >nul 2>&1
)
if exist src\ShapefileNormalizerTool.egg-info (
    if not exist builds mkdir builds
    move src\ShapefileNormalizerTool.egg-info builds\ >nul 2>&1
)

cd scripts

echo.
if %BUILD_ERROR% neq 0 goto :build_failed

echo ========================================
echo ビルド完了！
echo ========================================
echo.
echo インストーラー: ..\builds\dist\ShapefileNormalizerTool-1.0.0-win64.msi
echo.
echo このMSIには以下が含まれています:
echo   [*] ShapefileNormalizerTool.exe
echo   [*] python314.dll
echo   [*] 必要なライブラリDLL群
echo   [*] config.json (ビルド前に設定した内容)
echo.
echo 配布方法: MSIファイルを配布してインストール
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
