# © 2026 NTT DATA Japan Co., Ltd. & NTT InfraNet All Rights Reserved.

# __pycache__ の生成を抑制
import sys
sys.dont_write_bytecode = True

"""
Shapefile正規化ツール - GUIアプリケーション

このモジュールは、Shapefileのジオメトリチェック、座標系変換、
カラムマッピングを行うGUIアプリケーションを提供します。

主な機能:
    - 複数Shapefileの統合
    - ジオメトリの検証と修正
    - EPSG座標系の変換
    - 文字コード変換
    - カラムマッピング（7種類の変換方式）
    - マッピング定義の保存・読み込み

使用方法:
    python shapefile_normalizer_gui.py

必要なライブラリ:
    - tkinter: GUI
    - geopandas: GISデータ処理
    - shapely: ジオメトリ操作
    - pandas: データフレーム操作
    - numpy: 数値計算
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import os
import sys
import json
import numpy as np
import pandas as pd
import random
import zipfile
import tempfile
import shutil
import threading
import time

# 同梱されたライブラリのパス追加（EXE配布用）
# PyInstallerでビルドする際、libsフォルダを一緒にパッケージングすることで
# geopandas等の依存ライブラリを同梱できます
libs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libs')
if os.path.exists(libs_path):
    sys.path.insert(0, libs_path)

# GIS関連ライブラリのインポートとエラーハンドリング
try:
    import geopandas as gpd
    from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon
    from shapely import validation
    from shapely.validation import make_valid
    
    # GDAL設定: 破損した.shxファイルの自動修復を有効化
    # .shxファイルはShapefileのインデックスファイルで、破損することがあります
    # この設定により、GDALが自動的に.shxを再構築します
    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    
    # GDALモジュールが利用可能な場合、直接設定も行う
    try:
        from osgeo import gdal
        gdal.SetConfigOption('SHAPE_RESTORE_SHX', 'YES')
    except ImportError:
        # GDALがインポートできない場合は環境変数のみで動作
        pass
    
except ImportError as e:
    # 必要なライブラリがインストールされていない場合のエラーメッセージ
    root = tk.Tk()
    root.withdraw()
    error_msg = "必要なライブラリがインストールされていません。\n\n"
    if 'geopandas' in str(e) or 'shapely' in str(e):
        error_msg += "GeoPandasがインストールされていません。\n\n"
    error_msg += "開発者の方へ：\n  pip install -r requirements.txt\n\nまたは、配布用EXEファイルをご利用ください。"
    messagebox.showerror("エラー", error_msg)
    sys.exit(1)


class ShapefileNormalizerApp:
    """
    Shapefile正規化ツールのメインアプリケーションクラス
    
    このクラスは、GUIの構築、ファイル管理、データ処理、
    マッピング定義の管理を担当します。
    
    Attributes:
        root (tk.Tk): Tkinterルートウィンドウ
        config_file (str): 設定ファイルのパス
        input_files (list): 入力ファイルのリスト
        output_dir (str): 出力ディレクトリパス
        column_mappings (dict): カラムマッピング定義の辞書
        current_mapping_name (str): 現在選択中のマッピング定義名
    
    Constants:
        DEFAULT_WINDOW_SIZE (str): デフォルトのウィンドウサイズ
        MAPPING_TYPES (list): 利用可能なマッピング方式のリスト
        SUPPORTED_ENCODINGS (list): サポートされる文字エンコーディング
        COMMON_EPSG_CODES (list): よく使用されるEPSGコード
    """
    
    # ウィンドウ設定
    DEFAULT_WINDOW_SIZE = "1000x850"
    
    # マッピング方式の定義
    MAPPING_TYPES = [
        "カラム代入", 
        "カラム四則演算", 
        "複数カラム四則演算", 
        "複数カラム抽出",
        "固定値", 
        "ファイル名",
        "ランダム値", 
        "シーケンス値", 
        "条件分岐", 
        "None"
    ]
    
    # サポートされる文字エンコーディング
    SUPPORTED_ENCODINGS = [
        'UTF-8', 'Shift_JIS', 'EUC-JP', 'ISO-2022-JP', 
        'CP932', 'latin1', 'ascii'
    ]
    
    # よく使用されるEPSGコード（日本国内）
    COMMON_EPSG_CODES = [
        '4326',   # WGS84（世界測地系）
        '6668',   # JGD2011（日本測地系2011）
        '6669',   # JGD2011 / Japan Plane Rectangular CS I
        '6670',   # JGD2011 / Japan Plane Rectangular CS II
        '6671',   # JGD2011 / Japan Plane Rectangular CS III
        '6672',   # JGD2011 / Japan Plane Rectangular CS IV
        '6673',   # JGD2011 / Japan Plane Rectangular CS V
        '6674',   # JGD2011 / Japan Plane Rectangular CS VI
        '6675',   # JGD2011 / Japan Plane Rectangular CS VII
        '6676',   # JGD2011 / Japan Plane Rectangular CS VIII
        '6677',   # JGD2011 / Japan Plane Rectangular CS IX
        '3857',   # Web Mercator
    ]
    
    # ログレベルの色設定
    LOG_COLORS = {
        'INFO': 'black',
        'DEBUG': 'blue',
        'WARNING': 'orange',
        'ERROR': 'red'
    }
    
    def __init__(self, root):
        """
        アプリケーションの初期化
        
        Args:
            root (tk.Tk): Tkinterのルートウィンドウ
        """
        self.root = root
        self.root.title("Shapefile正規化ツール")
        self.root.geometry(self.DEFAULT_WINDOW_SIZE)
        
        # 設定ファイルのパス（EXE/スクリプト実行で自動判定）
        if getattr(sys, 'frozen', False):
            # EXEとして実行されている場合
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # Pythonスクリプトとして実行されている場合
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(base_dir, 'config.json')
        
        # データ処理用の変数
        self.input_file = None         # 単一ファイル処理用（後方互換性のため保持）
        self.output_file = None        # 出力ファイルパス
        self.gdf = None                # 現在読み込まれているGeoDataFrame
        self.invalid_records = []      # 無効なレコードのリスト
        
        # マルチファイル処理用の変数
        self.input_files = []                    # 選択された入力ファイルのリスト
        self.output_dir = None                   # 出力ディレクトリパス
        self.file_mapping = {}                   # {ファイルパス: マッピング定義名}
        self.file_mapping_widgets = {}           # ファイルマッピングUIのウィジェット辞書
        self.file_specific_settings = {}         # {ファイルパス: {source_epsg, source_encoding}}
        self.file_name_mapping_definitions = {}  # {ファイル名: マッピング定義名} ※自動復元用
        
        # 出力カラムテンプレート（線設備/点設備/電柱）
        # UI表示用（和名）
        self.output_columns_templates = {
            "線設備": [
                "シーケンス番号", "設備キー", "入力ファイル名", "設置年", "データ更新日時",
                "XY座標の精度", "設備種別", "管の外径", "管の外径の精度", "管の内径",
                "管の厚み", "管種", "始点土被り", "終点土被り", "土被りの精度",
                "延長", "条数", "段数", "占用許可年月日", "残置区分",
                "離隔", "Type"
            ],
            "点設備": [
                "シーケンス番号", "設備キー", "入力ファイル名", "設置年", "データ更新日時",
                "XY座標の精度", "設備種別", "数量", "土被り", "土被りの精度",
                "高さ", "横幅", "奥行", "占用許可年月日", "残置区分"
            ],
            "電柱": [
                "シーケンス番号", "設備キー", "入力ファイル名", "設置年", "データ更新日時",
                "XY座標の精度", "設備種別", "数量", "埋設深さ", "電柱の高さ",
                "電柱の横幅", "占用許可年月日"
            ]
        }

        # 和名→英名マッピング（Shapefile出力用）
        self.column_name_mapping = {
            "シーケンス番号": "seq_no",
            "設備キー": "fac_key",
            "入力ファイル名": "file_name",
            "設置年": "inst_year",
            "データ更新日時": "org_update",
            "XY座標の精度": "xy_prec",
            "設備種別": "fac_type",
            "管の外径": "out_diam",
            "管の外径の精度": "out_d_prec",
            "管の内径": "in_diam",
            "管の厚み": "thickness",
            "管種": "pipe_mat",
            "始点土被り": "str_depth",
            "終点土被り": "end_depth",
            "土被りの精度": "depth_prec",
            "延長": "ex_length",
            "条数": "row_num",
            "段数": "column_num",
            "占用許可年月日": "occ_perm",
            "残置区分": "ret_type",
            "離隔": "clearance",
            "Type": "pipe_type",
            "数量": "qty",
            "土被り": "org_depth",
            "高さ": "fac_size_h",
            "横幅": "fac_size_w",
            "奥行": "fac_size_d",
            "埋設深さ": "bury_depth",
            "電柱の高さ": "pole_hgt",
            "電柱の横幅": "pole_wd"
        }
        self.output_columns = self.output_columns_templates["線設備"]  # 現在の出力カラムリスト
        
        # カラムマッピング定義の管理
        self.column_mappings = {"デフォルト": {}}              # {定義名: {カラム名: {type, value, ...}}}
        self.column_mappings_meta = {"デフォルト": {"type": "線設備"}}  # {定義名: {type: "線設備"/"点設備"/"電柱"}}
        self.current_mapping_name = "デフォルト"               # 現在編集中の定義名
        self.current_mapping_type = "線設備"                   # 現在編集中の定義のタイプ
        self.current_mapping_widgets = {}                      # 現在表示中のウィジェット
        self.input_columns = []                                # 入力ファイルから読み込んだカラムリスト
        self.sample_file = None                                # サンプルファイルパス（カラム自動取得用）
        self.sample_shp_filename = None                        # サンプルファイルのshpファイル名（拡張子あり）
        self.last_selected_facility_type = "線設備"            # 最後に選択した設備タイプを記憶
        
        # UIで使用するデフォルト値
        self.min_distance = tk.DoubleVar(value=0.01)           # 短い辺のチェック閾値（m）
        self.source_epsg = tk.StringVar(value="6669")          # 入力座標系（デフォルト: JGD2000系9）
        self.target_epsg = tk.StringVar(value="6677")          # 出力座標系（デフォルト: JGD2011系9）
        self.source_encoding = tk.StringVar(value="UTF-8")     # 入力文字コード
        
        # GUIの構築
        self.create_widgets()
        
        # 保存された設定の読み込み
        self.load_config()
    
    def create_widgets(self):
        """
        メインウィンドウのGUIコンポーネントを構築
        
        タブごとにファイルマッピング、カラムマッピング、実行画面を作成します。
        """
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タブコントロールを一番上に作成
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # タブ1: 実行タブ
        execute_tab = ttk.Frame(self.notebook)
        self.notebook.add(execute_tab, text="実行")
        self.create_execute_tab(execute_tab)
        
        # タブ2: 設定タブ
        config_tab = ttk.Frame(self.notebook)
        self.notebook.add(config_tab, text="設定")
        self.create_config_tab(config_tab)
        
        # タブ3: カラム設定タブ
        column_tab = ttk.Frame(self.notebook)
        self.notebook.add(column_tab, text="カラム設定")
        self.create_column_mapping_tab(column_tab)
        
        # ステータスバー
        self.status_label = ttk.Label(self.root, text="準備完了", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # グリッドの設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
    
    def create_execute_tab(self, parent):
        """
        実行タブのUIを作成
        
        ファイルマッピングテーブル、出力先選択、実行ボタンを配置します。
        
        Args:
            parent (ttk.Frame): 親フレーム
        """
        # ファイル選択フレーム
        file_frame = ttk.LabelFrame(parent, text="ファイル選択", padding="10")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 入力ファイル（複数選択対応）
        ttk.Label(file_frame, text="入力ファイル（.shp/.zip）:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_label = ttk.Label(file_frame, text="未選択", foreground="gray")
        self.input_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        self.select_input_btn = ttk.Button(file_frame, text="複数選択", command=self.select_input_files)
        self.select_input_btn.grid(row=0, column=2, padx=5)

        # 出力ディレクトリ
        ttk.Label(file_frame, text="出力先ディレクトリ:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_label = ttk.Label(file_frame, text="未選択", foreground="gray")
        self.output_label.grid(row=1, column=1, sticky=tk.W, padx=5)
        self.select_output_btn = ttk.Button(file_frame, text="参照", command=self.select_output_dir)
        self.select_output_btn.grid(row=1, column=2, padx=5)
        
        # ファイルマッピングフレーム
        self.mapping_frame = ttk.LabelFrame(parent, text="ファイルマッピング", padding="10")
        self.mapping_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 操作ボタンフレーム（上部）
        mapping_btn_frame = ttk.Frame(self.mapping_frame)
        mapping_btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        ttk.Label(mapping_btn_frame, text="マッピング定義の保存/削除:").pack(side=tk.LEFT, padx=5)
        self.save_all_mapping_btn = ttk.Button(mapping_btn_frame, text="現在の設定を保存", 
                                               command=self.save_all_file_mappings)
        self.save_all_mapping_btn.pack(side=tk.LEFT, padx=5)
        
        self.delete_all_mapping_btn = ttk.Button(mapping_btn_frame, text="保存済み定義を削除", 
                                                 command=self.delete_all_file_mappings)
        self.delete_all_mapping_btn.pack(side=tk.LEFT, padx=5)
        
        # 内部にスクロール可能なフレームを作成
        self.mapping_canvas = tk.Canvas(self.mapping_frame, height=150,
                                        bg='SystemButtonFace', highlightthickness=0)
        mapping_scrollbar = ttk.Scrollbar(self.mapping_frame, orient="vertical", command=self.mapping_canvas.yview)
        self.mapping_scrollable_frame = ttk.Frame(self.mapping_canvas)

        self.mapping_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.mapping_canvas.configure(scrollregion=self.mapping_canvas.bbox("all"))
        )

        self.mapping_canvas.create_window((0, 0), window=self.mapping_scrollable_frame, anchor="nw")
        self.mapping_canvas.configure(yscrollcommand=mapping_scrollbar.set)

        self.mapping_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mapping_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # マウスホイールでスクロール
        def _on_mapping_mousewheel(event):
            # スクロール可能な範囲があるかチェック（コンテンツがCanvas高さより大きい場合のみスクロール）
            if self.mapping_canvas.winfo_height() < self.mapping_scrollable_frame.winfo_reqheight():
                self.mapping_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        # ハンドラをインスタンス変数として保存
        self._on_mapping_mousewheel = _on_mapping_mousewheel

        # Canvasとscrollable_frame内の全てのウィジェットにバインド
        self.mapping_canvas.bind("<MouseWheel>", _on_mapping_mousewheel)
        self.bind_mousewheel_to_widget(self.mapping_scrollable_frame, _on_mapping_mousewheel)
        
        # 初期メッセージ
        self.mapping_info_label = ttk.Label(self.mapping_scrollable_frame, 
                                           text="ファイルを選択すると、ここにマッピング設定が表示されます",
                                           foreground="gray")
        self.mapping_info_label.pack(pady=20)
        
        # ログ表示エリア
        log_frame = ttk.LabelFrame(parent, text="処理ログ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=100, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 実行ボタン
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.execute_button = ttk.Button(button_frame, text="実行", command=self.execute_cleaning, state=tk.DISABLED)
        self.execute_button.pack(side=tk.LEFT, padx=5)

        self.log_clear_btn = ttk.Button(button_frame, text="ログクリア", command=self.clear_log)
        self.log_clear_btn.pack(side=tk.LEFT, padx=5)
    
    def create_config_tab(self, parent):
        """
        設定タブのUIを作成
        
        サンプルファイル選択、座標系設定、文字コード設定などの
        全体設定を行うUIを配置します。
        
        Args:
            parent (ttk.Frame): 親フレーム
        """
        """設定タブを作成（処理設定のみ）"""
        # 説明ラベル
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(info_frame, text="処理設定を行います。設定はconfig.jsonに保存されます。", 
                 foreground="blue").pack(anchor=tk.W)
        
        # 設定ファイル情報
        file_info_frame = ttk.LabelFrame(parent, text="設定ファイル", padding="5")
        file_info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(file_info_frame, text=f"保存先: {self.config_file}").pack(anchor=tk.W, pady=2)
        
        button_frame = ttk.Frame(file_info_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="設定を読み込み", command=self.load_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="設定を保存", command=self.save_config).pack(side=tk.LEFT, padx=5)
        
        # 処理設定フレーム
        process_frame = ttk.LabelFrame(parent, text="処理設定（デフォルト値）", padding="5")
        process_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 説明ラベル
        info_label = ttk.Label(process_frame, 
                              text="※ ファイルマッピングタブで各ファイルごとに個別のEPSG・文字コードを設定できます", 
                              foreground="blue", font=('', 8))
        info_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0,10))
        
        # 頂点間距離の閾値
        ttk.Label(process_frame, text="最小頂点間距離（これ以下を削除）:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(process_frame, textvariable=self.min_distance, width=15).grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(process_frame, text="メートル").grid(row=1, column=2, sticky=tk.W)
        
        # 座標系変換
        ttk.Label(process_frame, text="変換元EPSG（デフォルト）:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(process_frame, textvariable=self.source_epsg, width=15).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(process_frame, text="（例: 6669 = JGD2000平面直角9系）").grid(row=2, column=2, sticky=tk.W)
        
        ttk.Label(process_frame, text="変換先EPSG:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(process_frame, textvariable=self.target_epsg, width=15).grid(row=3, column=1, sticky=tk.W, padx=5)
        ttk.Label(process_frame, text="（例: 6677 = JGD2011平面直角9系）").grid(row=3, column=2, sticky=tk.W)
        
        # 文字コード
        ttk.Label(process_frame, text="文字コード（デフォルト）:").grid(row=4, column=0, sticky=tk.W, pady=5)
        encoding_combo = ttk.Combobox(process_frame, textvariable=self.source_encoding, width=13, state='readonly')
        encoding_combo['values'] = ('UTF-8', 'Shift_JIS', 'CP932', 'EUC-JP', 'ISO-2022-JP')
        encoding_combo.grid(row=4, column=1, sticky=tk.W, padx=5)
        self.bind_combobox_wheel(encoding_combo)  # マウスホイールイベント制御
        ttk.Label(process_frame, text="(.cpgがあれば自動設定)").grid(row=4, column=2, sticky=tk.W)
    
    def create_column_mapping_tab(self, parent):
        """
        カラムマッピングタブのUIを作成
        
        マッピング定義の管理、出力カラムごとのマッピング方式設定を行います。
        
        Args:
            parent (ttk.Frame): 親フレーム
        """
        """カラム設定タブを作成（複数定義管理対応）"""
        # 説明ラベル
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        info_text = (
            "カラムマッピング定義を管理します。複数の定義を作成し、ファイルごとに適用できます。\n"
            "サンプルファイルを読み込んでカラム情報を取得し、マッピング設定を作成してください。"
        )
        ttk.Label(info_frame, text=info_text, foreground="blue", wraplength=900, justify=tk.LEFT).pack(anchor=tk.W)
        
        # 設定ファイル情報
        file_info_frame = ttk.LabelFrame(parent, text="設定ファイル", padding="5")
        file_info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(file_info_frame, text=f"保存先: {self.config_file}").pack(anchor=tk.W, pady=2)
        
        button_frame = ttk.Frame(file_info_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="設定を読み込み", command=self.load_config).pack(side=tk.LEFT, padx=5)
        
        # マッピング定義管理フレーム
        definition_frame = ttk.LabelFrame(parent, text="マッピング定義管理", padding="5")
        definition_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 定義選択と管理ボタン
        def_control_frame = ttk.Frame(definition_frame)
        def_control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(def_control_frame, text="定義名:").pack(side=tk.LEFT, padx=5)
        
        self.mapping_def_combo = ttk.Combobox(def_control_frame, width=20, state="readonly")
        self.mapping_def_combo.pack(side=tk.LEFT, padx=5)
        self.bind_combobox_wheel(self.mapping_def_combo)  # マウスホイールイベント制御
        self.mapping_def_combo.bind("<<ComboboxSelected>>", self.on_mapping_definition_changed)
        
        ttk.Button(def_control_frame, text="新規作成", command=self.create_new_mapping_definition).pack(side=tk.LEFT, padx=2)
        ttk.Button(def_control_frame, text="名称変更", command=self.rename_mapping_definition).pack(side=tk.LEFT, padx=2)
        ttk.Button(def_control_frame, text="複製", command=self.duplicate_mapping_definition).pack(side=tk.LEFT, padx=2)
        ttk.Button(def_control_frame, text="削除", command=self.delete_mapping_definition).pack(side=tk.LEFT, padx=2)
        
        # タイプ表示フレーム（読み取り専用）
        type_control_frame = ttk.Frame(definition_frame)
        type_control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(type_control_frame, text="設備タイプ:").pack(side=tk.LEFT, padx=5)
        
        self.mapping_type_var = tk.StringVar(value="線設備")
        type_label = ttk.Label(type_control_frame, textvariable=self.mapping_type_var, 
                              font=('', 9, 'bold'), foreground="blue")
        type_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(type_control_frame, text="（新規作成時に選択、変更不可）", 
                 foreground="gray", font=('', 8)).pack(side=tk.LEFT, padx=5)
        
        # サンプルファイル選択フレーム
        sample_frame = ttk.LabelFrame(parent, text="サンプルファイル選択（カラム情報取得用） - まずここから開始", padding="5")
        sample_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 説明
        sample_info = ttk.Label(sample_frame, 
                               text="① サンプルファイル（.shp/.zip）を選択 → ② カラム情報を読込 → ③ 下のマッピング設定でカラムを選択",
                               foreground="darkgreen")
        sample_info.pack(anchor=tk.W, padx=5, pady=2)
        
        sample_control_frame = ttk.Frame(sample_frame)
        sample_control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(sample_control_frame, text="サンプルファイル:").pack(side=tk.LEFT, padx=5)
        
        self.sample_file_label = ttk.Label(sample_control_frame, text="未選択", foreground="gray")
        self.sample_file_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(sample_control_frame, text="ファイル選択", command=self.select_sample_file).pack(side=tk.LEFT, padx=5)
        
        # 文字コード選択
        ttk.Label(sample_control_frame, text="文字コード:").pack(side=tk.LEFT, padx=(15, 5))
        self.sample_encoding = tk.StringVar(value=self.source_encoding.get())
        self.sample_encoding_combo = ttk.Combobox(sample_control_frame, textvariable=self.sample_encoding,
                                                  values=('UTF-8', 'Shift_JIS', 'CP932', 'EUC-JP', 'ISO-2022-JP'),
                                                  width=12, state="readonly")
        self.sample_encoding_combo.pack(side=tk.LEFT, padx=5)
        self.bind_combobox_wheel(self.sample_encoding_combo)  # マウスホイールイベント制御
        
        ttk.Button(sample_control_frame, text="カラム情報を読込", command=self.load_sample_columns).pack(side=tk.LEFT, padx=5)
        
        # カラム情報表示
        self.sample_columns_label = ttk.Label(sample_frame, text="カラム情報: 未読み込み", foreground="gray")
        self.sample_columns_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # 保存ボタンフレーム（下部に固定）
        save_button_frame = ttk.Frame(parent)
        save_button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=10)
        
        ttk.Button(save_button_frame, text="設定を保存", command=self.save_config, 
                  width=20).pack(side=tk.RIGHT, padx=5)
        
        # カラムマッピング設定フレーム
        config_frame = ttk.LabelFrame(parent, text="カラムマッピング設定", padding="5")
        config_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # スクロール可能なフレーム
        self.column_canvas = tk.Canvas(config_frame, height=400, width=900, 
                                       bg='SystemButtonFace', highlightthickness=0)
        column_scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=self.column_canvas.yview)
        self.column_scrollable_frame = ttk.Frame(self.column_canvas)
        
        self.column_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.column_canvas.configure(scrollregion=self.column_canvas.bbox("all"))
        )
        
        self.column_canvas.create_window((0, 0), window=self.column_scrollable_frame, anchor="nw")
        self.column_canvas.configure(yscrollcommand=column_scrollbar.set)
        
        # Combobox上でのマウスホイール処理
        def _on_combobox_mousewheel(event):
            """Combobox上でもCanvas全体をスクロールし、Comboboxのドロップダウンへの伝播を防ぐ"""
            # スクロール可能な範囲があるかチェック（コンテンツがCanvas高さより大きい場合のみスクロール）
            if self.column_canvas.winfo_height() < self.column_scrollable_frame.winfo_reqheight():
                self.column_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"

        self._on_combobox_mousewheel = _on_combobox_mousewheel

        # マウスホイールでスクロール
        def _on_mousewheel(event):
            # スクロール可能な範囲があるかチェック（コンテンツがCanvas高さより大きい場合のみスクロール）
            if self.column_canvas.winfo_height() < self.column_scrollable_frame.winfo_reqheight():
                self.column_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        # ハンドラをインスタンス変数として保存
        self._on_column_mousewheel = _on_mousewheel

        # Canvasとscrollable_frame内の全てのウィジェットにバインド
        self.column_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.bind_mousewheel_to_widget(self.column_scrollable_frame, _on_mousewheel)
        
        self.column_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        column_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # カラムマッピングUIを初期化
        self.init_column_mapping_ui()
    
    def init_column_mapping_ui(self):
        """
        カラムマッピングUIを初期化

        現在選択されているマッピング定義に基づいて、
        各出力カラムのマッピング方式選択UIを動的に生成します。

        Note:
            マッピングタイプ（線設備/点設備）が変更された際にも呼び出されます。
        """
        # 既存のウィジェットをクリア
        for widget in self.column_scrollable_frame.winfo_children():
            widget.destroy()

        # スクロール位置を先頭にリセット
        self.column_canvas.yview_moveto(0)

        self.current_mapping_widgets = {}
        
        # 定義コンボボックスを更新
        self.update_mapping_definition_list()
        
        # ヘッダー
        header_frame = ttk.Frame(self.column_scrollable_frame)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(header_frame, text="出力カラム", font=('', 8, 'bold'), width=20).grid(row=0, column=0, padx=5)
        ttk.Label(header_frame, text="設定", font=('', 8, 'bold'), width=21 ).grid(row=0, column=1, padx=7)
        ttk.Label(header_frame, text="値/インポートカラム", font=('', 8, 'bold'), width=50).grid(row=0, column=2, padx=5)
        
        # 各出力カラムのマッピング設定
        for idx, out_col in enumerate(self.output_columns, start=1):
            row_frame = ttk.Frame(self.column_scrollable_frame)
            row_frame.grid(row=idx, column=0, sticky=(tk.W, tk.E), pady=2)
            
            # 出力カラム名
            ttk.Label(row_frame, text=out_col, width=20).grid(row=0, column=0, padx=5, sticky=tk.W)
            
            # 設定タイプ選択
            type_var = tk.StringVar(value="None")
            type_combo = ttk.Combobox(row_frame, textvariable=type_var,
                                     values=["カラム代入", "カラム四則演算", "複数カラム四則演算", "複数カラム抽出",
                                             "固定値", "ファイル名", "ランダム値", "シーケンス値", "条件分岐", "ファイル名分岐", "None"],
                                     width=18, state="readonly")
            type_combo.grid(row=0, column=1, padx=5)
            type_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)
            # 値入力欄フレーム（幅制限を削除して自動調整）
            value_widget_frame = ttk.Frame(row_frame)
            value_widget_frame.grid(row=0, column=2, padx=5, sticky=(tk.W, tk.E))
            
            # === パターン1: カラム代入 ===
            assign_frame = ttk.Frame(value_widget_frame)
            assign_combo = ttk.Combobox(assign_frame, values=self.input_columns if self.input_columns else [],
                                       width=18, state="readonly")
            assign_combo.pack(side=tk.LEFT, padx=5)
            assign_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            # 補完設定（同じ行）
            ttk.Label(assign_frame, text="補完:").pack(side=tk.LEFT, padx=(28, 5))
            assign_fallback_type_var = tk.StringVar()
            assign_fallback_type = ttk.Combobox(assign_frame, textvariable=assign_fallback_type_var,
                                               values=["固定値", "他カラム", "ファイル名"],
                                               width=8, state="readonly")
            assign_fallback_type.pack(side=tk.LEFT, padx=5)
            assign_fallback_type.bind("<MouseWheel>", self._on_combobox_mousewheel)
            
            # 補完値入力用ウィジェット（ヘルパー関数で作成）
            fallback_widgets = self.create_fallback_widgets(assign_frame, entry_width=15, mapping_name="カラム代入")
            
            # 保存/ロード処理用にエイリアスを展開
            assign_fallback_container = fallback_widgets['container']
            assign_fallback_entry = fallback_widgets['entry']
            assign_fallback_combo = fallback_widgets['combo']
            assign_fallback_fixed = fallback_widgets['fixed']
            assign_fallback_column = fallback_widgets['column']
            assign_fallback_filename = fallback_widgets['filename']
            
            # イベントハンドラをバインド
            on_assign_fallback_type_change = self.create_fallback_type_change_handler(
                fallback_widgets, mapping_name="カラム代入"
            )
            assign_fallback_type.bind("<<ComboboxSelected>>", on_assign_fallback_type_change)

            # === パターン2: カラム四則演算 ===
            calc_frame = ttk.Frame(value_widget_frame)
            calc_col_combo = ttk.Combobox(calc_frame, values=self.input_columns if self.input_columns else [],
                                         width=18, state="readonly")
            calc_col_combo.pack(side=tk.LEFT, padx=5)
            calc_col_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            calc_op_combo = ttk.Combobox(calc_frame, values=["+", "-", "*", "/"], width=5, state="readonly")
            calc_op_combo.pack(side=tk.LEFT, padx=5)
            calc_op_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            # 数値入力欄（半角数字のみ）
            vcmd = (self.root.register(self.validate_number_input), '%P')
            calc_num_entry = ttk.Entry(calc_frame, width=20, validate='key', validatecommand=vcmd)
            calc_num_entry.pack(side=tk.LEFT, padx=5)

            # 補完設定（同じ行）
            ttk.Label(calc_frame, text="補完:").pack(side=tk.LEFT, padx=(32, 5))
            calc_fallback_type_var = tk.StringVar()
            calc_fallback_type = ttk.Combobox(calc_frame, textvariable=calc_fallback_type_var,
                                             values=["固定値", "他カラム", "ファイル名"],
                                             width=8, state="readonly")
            calc_fallback_type.pack(side=tk.LEFT, padx=5)
            calc_fallback_type.bind("<MouseWheel>", self._on_combobox_mousewheel)
            
            # 補完値入力用ウィジェット（ヘルパー関数で作成）
            fallback_widgets = self.create_fallback_widgets(calc_frame, entry_width=15, mapping_name="カラム四則演算")
            
            # 保存/ロード処理用にエイリアスを展開
            calc_fallback_container = fallback_widgets['container']
            calc_fallback_entry = fallback_widgets['entry']
            calc_fallback_combo = fallback_widgets['combo']
            calc_fallback_fixed = fallback_widgets['fixed']
            calc_fallback_column = fallback_widgets['column']
            calc_fallback_filename = fallback_widgets['filename']
            
            # イベントハンドラをバインド
            on_calc_fallback_type_change = self.create_fallback_type_change_handler(
                fallback_widgets, mapping_name="カラム四則演算"
            )
            calc_fallback_type.bind("<<ComboboxSelected>>", on_calc_fallback_type_change)
            
            # === パターン3: 複数カラム四則演算 ===
            multi_calc_frame = ttk.Frame(value_widget_frame)
            multi_col1_combo = ttk.Combobox(multi_calc_frame, values=self.input_columns if self.input_columns else [],
                                           width=18, state="readonly")
            multi_col1_combo.pack(side=tk.LEFT, padx=5)
            multi_col1_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            multi_op_combo = ttk.Combobox(multi_calc_frame, values=["+", "-", "*", "/"], width=5, state="readonly")
            multi_op_combo.pack(side=tk.LEFT, padx=5)
            multi_op_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            multi_col2_combo = ttk.Combobox(multi_calc_frame, values=self.input_columns if self.input_columns else [],
                                           width=18, state="readonly")
            multi_col2_combo.pack(side=tk.LEFT, padx=5)
            multi_col2_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            # 補完設定（同じ行）
            ttk.Label(multi_calc_frame, text="補完:").pack(side=tk.LEFT, padx=(27, 5))
            multi_calc_fallback_type_var = tk.StringVar()
            multi_calc_fallback_type = ttk.Combobox(multi_calc_frame, textvariable=multi_calc_fallback_type_var,
                                                   values=["固定値", "他カラム", "ファイル名"],
                                                   width=8, state="readonly")
            multi_calc_fallback_type.pack(side=tk.LEFT, padx=5)
            multi_calc_fallback_type.bind("<MouseWheel>", self._on_combobox_mousewheel)
            
            # 補完値入力用ウィジェット（ヘルパー関数で作成）
            fallback_widgets = self.create_fallback_widgets(multi_calc_frame, entry_width=15, mapping_name="複数カラム四則演算")
            
            # 保存/ロード処理用にエイリアスを展開
            multi_calc_fallback_container = fallback_widgets['container']
            multi_calc_fallback_entry = fallback_widgets['entry']
            multi_calc_fallback_combo = fallback_widgets['combo']
            multi_calc_fallback_fixed = fallback_widgets['fixed']
            multi_calc_fallback_column = fallback_widgets['column']
            multi_calc_fallback_filename = fallback_widgets['filename']
            
            # イベントハンドラをバインド
            on_multi_calc_fallback_type_change = self.create_fallback_type_change_handler(
                fallback_widgets, mapping_name="複数カラム四則演算"
            )
            multi_calc_fallback_type.bind("<<ComboboxSelected>>", on_multi_calc_fallback_type_change)
            
            # === パターン4: 複数カラム抽出 ===
            multi_extract_frame = ttk.Frame(value_widget_frame)

            # 最大/最小選択
            ttk.Label(multi_extract_frame, text="条件:").pack(side=tk.LEFT, padx=5)
            extract_mode_combo = ttk.Combobox(multi_extract_frame, values=["MAX", "MIN"],
                                               width=6, state="readonly")
            extract_mode_combo.pack(side=tk.LEFT, padx=5)
            extract_mode_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            # カラム選択（ポップアップ方式）
            ttk.Label(multi_extract_frame, text="カラム:").pack(side=tk.LEFT, padx=5)

            # 読み取り専用の入力欄（選択されたカラムをカンマ区切りで表示）
            extract_columns_entry = ttk.Entry(multi_extract_frame, width=22, state="readonly")
            extract_columns_entry.pack(side=tk.LEFT, padx=5)

            # カラム選択ボタン
            def on_select_columns(out_col=out_col):
                selected = self.show_column_selector_dialog(
                    current_selection=self.current_mapping_widgets[out_col]['extract_columns_entry'].get()
                )
                if selected is not None:
                    # 読み取り専用を一時解除して値を設定
                    entry = self.current_mapping_widgets[out_col]['extract_columns_entry']
                    entry.config(state="normal")
                    entry.delete(0, tk.END)
                    entry.insert(0, ", ".join(selected))
                    entry.config(state="readonly")

            extract_select_btn = ttk.Button(multi_extract_frame, text="選択",
                                           command=on_select_columns, width=6)
            extract_select_btn.pack(side=tk.LEFT, padx=5)

            # 補完設定（同じ行）- ラベル2つ分を考慮
            ttk.Label(multi_extract_frame, text="補完:").pack(side=tk.LEFT, padx=(15, 5))
            extract_fallback_type_var = tk.StringVar()
            extract_fallback_type = ttk.Combobox(multi_extract_frame, textvariable=extract_fallback_type_var,
                                                values=["固定値", "他カラム", "ファイル名"],
                                                width=8, state="readonly")
            extract_fallback_type.pack(side=tk.LEFT, padx=5)
            extract_fallback_type.bind("<MouseWheel>", self._on_combobox_mousewheel)
            
            # 補完値入力用ウィジェット（ヘルパー関数で作成）
            fallback_widgets = self.create_fallback_widgets(multi_extract_frame, entry_width=15, mapping_name="複数カラム抽出")
            
            # 保存/ロード処理用にエイリアスを展開
            extract_fallback_container = fallback_widgets['container']
            extract_fallback_entry = fallback_widgets['entry']
            extract_fallback_combo = fallback_widgets['combo']
            extract_fallback_fixed = fallback_widgets['fixed']
            extract_fallback_column = fallback_widgets['column']
            extract_fallback_filename = fallback_widgets['filename']
            
            # イベントハンドラをバインド
            on_extract_fallback_type_change = self.create_fallback_type_change_handler(
                fallback_widgets, mapping_name="複数カラム抽出"
            )
            extract_fallback_type.bind("<<ComboboxSelected>>", on_extract_fallback_type_change)
            
            # === パターン5: 固定値 ===
            fixed_frame = ttk.Frame(value_widget_frame)
            fixed_entry = ttk.Entry(fixed_frame, width=45)
            fixed_entry.pack(side=tk.LEFT, padx=5)


            # === パターン6: ファイル名 ===
            filename_frame = ttk.Frame(value_widget_frame)
            # ファイル名は自動設定されるため表示不要（空のフレームのみ）

            # === パターン7: ランダム値 ===
            random_frame = ttk.Frame(value_widget_frame)
            ttk.Label(random_frame, text="最小:").pack(side=tk.LEFT, padx=5)
            vcmd_rand = (self.root.register(self.validate_number_input), '%P')
            random_min_entry = ttk.Entry(random_frame, width=15, validate='key', validatecommand=vcmd_rand)
            random_min_entry.pack(side=tk.LEFT, padx=5)
            ttk.Label(random_frame, text="最大:").pack(side=tk.LEFT, padx=5)
            random_max_entry = ttk.Entry(random_frame, width=15, validate='key', validatecommand=vcmd_rand)
            random_max_entry.pack(side=tk.LEFT, padx=5)

            # === パターン8: シーケンス値 ===
            seq_frame = ttk.Frame(value_widget_frame)
            ttk.Label(seq_frame, text="開始値:").pack(side=tk.LEFT, padx=5)
            vcmd_seq = (self.root.register(self.validate_number_input), '%P')
            seq_start_entry = ttk.Entry(seq_frame, width=15, validate='key', validatecommand=vcmd_seq)
            seq_start_entry.pack(side=tk.LEFT, padx=5)
            ttk.Label(seq_frame, text="ステップ:").pack(side=tk.LEFT, padx=5)
            seq_step_entry = ttk.Entry(seq_frame, width=15, validate='key', validatecommand=vcmd_seq)
            seq_step_entry.pack(side=tk.LEFT, padx=5)
            
            # === パターン9: 条件分岐 ===
            condition_frame = ttk.Frame(value_widget_frame)

            ttk.Label(condition_frame, text="カラム:").pack(side=tk.LEFT, padx=5)
            condition_col_combo = ttk.Combobox(condition_frame,
                                               values=self.input_columns if self.input_columns else [],
                                               width=18, state="readonly")
            condition_col_combo.pack(side=tk.LEFT, padx=5)
            condition_col_combo.bind("<MouseWheel>", self._on_combobox_mousewheel)

            ttk.Label(condition_frame, text="条件 (入力値=出力値,...):").pack(side=tk.LEFT, padx=5)
            condition_entry = ttk.Entry(condition_frame, width=30)
            condition_entry.pack(side=tk.LEFT, padx=5)

            ttk.Label(condition_frame, text="デフォルト:").pack(side=tk.LEFT, padx=5)
            condition_default_entry = ttk.Entry(condition_frame, width=15)
            condition_default_entry.pack(side=tk.LEFT, padx=5)

            # === パターン10: ファイル名分岐 ===
            filename_branch_frame = ttk.Frame(value_widget_frame)

            ttk.Label(filename_branch_frame, text="条件 (ファイル名=出力値,...):").pack(side=tk.LEFT, padx=5)
            filename_branch_entry = ttk.Entry(filename_branch_frame, width=35)
            filename_branch_entry.pack(side=tk.LEFT, padx=5)

            ttk.Label(filename_branch_frame, text="デフォルト:").pack(side=tk.LEFT, padx=5)
            filename_branch_default_entry = ttk.Entry(filename_branch_frame, width=15)
            filename_branch_default_entry.pack(side=tk.LEFT, padx=5)

            # 初期状態では全て非表示
            assign_frame.grid(row=0, column=0)
            assign_frame.grid_remove()
            calc_frame.grid(row=0, column=0)
            calc_frame.grid_remove()
            multi_calc_frame.grid(row=0, column=0)
            multi_calc_frame.grid_remove()
            multi_extract_frame.grid(row=0, column=0)
            multi_extract_frame.grid_remove()
            fixed_frame.grid(row=0, column=0)
            fixed_frame.grid_remove()
            filename_frame.grid(row=0, column=0)
            filename_frame.grid_remove()
            random_frame.grid(row=0, column=0)
            random_frame.grid_remove()
            seq_frame.grid(row=0, column=0)
            seq_frame.grid_remove()
            condition_frame.grid(row=0, column=0)
            condition_frame.grid_remove()
            filename_branch_frame.grid(row=0, column=0)
            filename_branch_frame.grid_remove()

            # タイプが変更されたときの処理
            def on_type_change(event, t_var=type_var, out_col=out_col,
                             a_frame=assign_frame, c_frame=calc_frame, mc_frame=multi_calc_frame,
                             me_frame=multi_extract_frame,
                             f_frame=fixed_frame, fn_frame=filename_frame, r_frame=random_frame, s_frame=seq_frame,
                             cond_frame=condition_frame, fnb_frame=filename_branch_frame):
                selected_type = t_var.get()
                
                # 全て非表示
                a_frame.grid_remove()
                c_frame.grid_remove()
                mc_frame.grid_remove()
                me_frame.grid_remove()
                f_frame.grid_remove()
                r_frame.grid_remove()
                s_frame.grid_remove()
                fn_frame.grid_remove()
                cond_frame.grid_remove()
                fnb_frame.grid_remove()

                # 選択されたタイプに応じて表示
                if selected_type == "カラム代入":
                    a_frame.grid()
                    a_frame.update_idletasks()
                elif selected_type == "カラム四則演算":
                    c_frame.grid()
                    c_frame.update_idletasks()
                elif t_var.get() == "複数カラム四則演算":
                    mc_frame.grid()
                    mc_frame.update_idletasks()
                elif t_var.get() == "複数カラム抽出":
                    me_frame.grid()
                    me_frame.update_idletasks()
                elif t_var.get() == "固定値":
                    f_frame.grid()
                elif t_var.get() == "ランダム値":
                    r_frame.grid()
                elif t_var.get() == "ファイル名":
                    fn_frame.grid()
                    # ファイル名は自動設定されるため何も表示しない
                elif t_var.get() == "シーケンス値":
                    s_frame.grid()
                elif t_var.get() == "条件分岐":
                    cond_frame.grid()
                elif t_var.get() == "ファイル名分岐":
                    fnb_frame.grid()

            type_combo.bind("<<ComboboxSelected>>", on_type_change)
            
            # マッピング情報を保存（現在の定義用）
            self.current_mapping_widgets[out_col] = {
                'type_var': type_var,
                'assign_combo': assign_combo,
                'assign_fallback_type': assign_fallback_type,
                'assign_fallback_fixed': assign_fallback_fixed,
                'assign_fallback_column': assign_fallback_column,
                'assign_fallback_filename': assign_fallback_filename,
                'calc_col_combo': calc_col_combo,
                'calc_op_combo': calc_op_combo,
                'calc_num_entry': calc_num_entry,
                'calc_fallback_type': calc_fallback_type,
                'calc_fallback_fixed': calc_fallback_fixed,
                'calc_fallback_column': calc_fallback_column,
                'calc_fallback_filename': calc_fallback_filename,
                'multi_col1_combo': multi_col1_combo,
                'multi_op_combo': multi_op_combo,
                'multi_col2_combo': multi_col2_combo,
                'multi_calc_fallback_type': multi_calc_fallback_type,
                'multi_calc_fallback_fixed': multi_calc_fallback_fixed,
                'multi_calc_fallback_column': multi_calc_fallback_column,
                'multi_calc_fallback_filename': multi_calc_fallback_filename,
                'extract_mode_combo': extract_mode_combo,
                'extract_columns_entry': extract_columns_entry,
                'extract_fallback_type': extract_fallback_type,
                'extract_fallback_fixed': extract_fallback_fixed,
                'extract_fallback_column': extract_fallback_column,
                'extract_fallback_filename': extract_fallback_filename,
                'fixed_entry': fixed_entry,
                'filename_frame': filename_frame,
                'random_min_entry': random_min_entry,
                'random_max_entry': random_max_entry,
                'seq_start_entry': seq_start_entry,
                'seq_step_entry': seq_step_entry,
                'condition_col_combo': condition_col_combo,
                'condition_entry': condition_entry,
                'condition_default_entry': condition_default_entry,
                'filename_branch_entry': filename_branch_entry,
                'filename_branch_default_entry': filename_branch_default_entry
            }

        # UIが更新されたので、全てのウィジェットにマウスホイールをバインド
        if hasattr(self, '_on_column_mousewheel'):
            self.bind_mousewheel_to_widget(self.column_scrollable_frame, self._on_column_mousewheel)

    # ===== ユーティリティメソッド =====

    def validate_number_input(self, new_value):
        """数値入力のバリデーション（半角数字、小数点、マイナスのみ許可）
        
        Args:
            new_value: 入力された新しい値
            
        Returns:
            bool: 入力を許可する場合True、拒否する場合False
        """
        # 空文字列は許可（削除操作のため）
        if new_value == "":
            return True
        
        # マイナス記号は先頭のみ許可
        if new_value == "-":
            return True
        
        # 半角数字、小数点、マイナスのみを含むか確認
        # マイナスは先頭のみ、小数点は1つまで
        import re
        # 正規表現: 先頭に0または1個のマイナス、その後に数字と小数点（小数点は最大1個）
        pattern = r'^-?\d*\.?\d*$'
        
        if re.match(pattern, new_value):
            # 小数点が複数ないか確認
            if new_value.count('.') > 1:
                return False
            return True
        
        return False
    
    def create_fallback_widgets(self, parent_frame, entry_width=18, mapping_name=""):
        """補完処理用のウィジェット群を作成（Entry + Combobox の2ウィジェット方式）
        
        Args:
            parent_frame: 親フレーム（補完値を配置するフレーム）
            entry_width: 入力欄の幅（デフォルト: 18）
            mapping_name: マッピング名（ログ用、デフォルト: ""）
            
        Returns:
            dict: 作成されたウィジェットの辞書
                {
                    'container': コンテナフレーム,
                    'entry': Entry（手入力用）,
                    'combo': Combobox（他カラム用、readonly）,
                    'fixed': 固定値用ウィジェット（Entryのエイリアス）,
                    'column': 他カラム用ウィジェット（Comboboxのエイリアス）,
                    'filename': ファイル名用ウィジェット（Entryのエイリアス）
                }
        """
        # コンテナフレーム作成
        container = ttk.Frame(parent_frame)
        container.pack(side=tk.LEFT, padx=5)
        
        # 手入力用Entry（固定値・ファイル名用）
        entry = ttk.Entry(container, width=entry_width)
        entry.grid(row=0, column=0, sticky="w")
        
        # ドロップダウン選択用Combobox（他カラム用 - readonly）
        combo = ttk.Combobox(container, width=entry_width, state="readonly")
        combo.bind("<MouseWheel>", self._on_combobox_mousewheel)
        # 初期状態ではgridしない（後で必要に応じて表示）
        
        # 保存/ロード処理用のエイリアス（各補完タイプで使用するウィジェットを指定）
        return {
            'container': container,
            'entry': entry,
            'combo': combo,
            'fixed': entry,      # 固定値用
            'column': combo,     # 他カラム用
            'filename': entry    # ファイル名用
        }
    
    def create_fallback_type_change_handler(self, widgets, mapping_name=""):
        """補完タイプ変更時のイベントハンドラを生成
        
        Args:
            widgets: create_fallback_widgets()が返したウィジェット辞書
            mapping_name: マッピング名（ログ用、デフォルト: ""）
            
        Returns:
            function: イベントハンドラ関数
        """
        entry = widgets['entry']
        combo = widgets['combo']
        
        def handler(event):
            try:
                selected_type = event.widget.get()
                
                # 選択されたタイプに応じてウィジェットを切り替え（gridで同じ位置を使用）
                if selected_type == "固定値":
                    # Comboboxを非表示、Entryを表示
                    combo.grid_forget()
                    entry.delete(0, tk.END)
                    entry.grid(row=0, column=0, sticky="w")
                    entry.focus()
                    
                elif selected_type == "他カラム":
                    # Entryを非表示、Comboboxを表示
                    entry.grid_forget()
                    cols = self.input_columns if self.input_columns else []
                    combo['values'] = cols
                    combo.set('')
                    combo.grid(row=0, column=0, sticky="w")
                    combo.focus()
                    
                elif selected_type == "ファイル名":
                    # Comboboxを非表示、Entryを表示
                    combo.grid_forget()
                    entry.delete(0, tk.END)
                    entry.grid(row=0, column=0, sticky="w")
                    entry.focus()
                
            except Exception as e:
                self.log(f"補完設定の変更中にエラーが発生しました: {e}", "ERROR")
        
        return handler
    
    def bind_combobox_wheel(self, combobox):
        """コンボボックスのマウスホイールイベントを制御して、下のスクロールを防ぐ
        
        コンボボックス上でのマウスホイールイベントが親に伝播しないようにします。
        Canvasのイベントハンドラ側でCombobox上のイベントをフィルタリングするため、
        このメソッドではCombobox自体にイベントを確実に届けるための設定のみを行います。
        """
        def on_wheel(event):
            # イベントの伝播を停止（Canvasのハンドラに届く前にブロック）
            return "break"
        
        # すべてのプラットフォームのマウスホイールイベントをバインド
        combobox.bind("<MouseWheel>", on_wheel)  # Windows, MacOS
        combobox.bind("<Button-4>", on_wheel)     # Linux scroll up
        combobox.bind("<Button-5>", on_wheel)     # Linux scroll down

    def bind_mousewheel_to_widget(self, widget, handler):
        """
        ウィジェットとその全ての子孫に再帰的にマウスホイールイベントをバインド
        Comboboxの場合は選択内容が変わらないように特別な処理を行う

        Args:
            widget: バインドするウィジェット
            handler: マウスホイールイベントハンドラ
        """
        # Comboboxの場合、選択内容が変わらないようにする
        if isinstance(widget, ttk.Combobox):
            def combobox_handler(event):
                handler(event)  # Canvasをスクロール
                return "break"  # Comboboxの選択内容は変更しない
            widget.bind("<MouseWheel>", combobox_handler)
        else:
            widget.bind("<MouseWheel>", handler)

        for child in widget.winfo_children():
            self.bind_mousewheel_to_widget(child, handler)

    def log(self, message, level="INFO"):
        """
        ログメッセージを出力（スレッドセーフ）

        Args:
            message (str): ログメッセージ
            level (str): ログレベル（INFO, DEBUG, WARNING, ERROR）
        """
        def _log_internal():
            self.log_text.insert(tk.END, f"[{level}] {message}\n")
            self.log_text.see(tk.END)

        # メインスレッドから呼ばれているかチェック
        if threading.current_thread() == threading.main_thread():
            _log_internal()
            self.root.update()
        else:
            # バックグラウンドスレッドからの場合はメインスレッドで実行
            self.root.after(0, _log_internal)

    def _progress_monitor(self, stop_event, message_prefix, interval=3):
        """
        長時間処理の進捗を定期的にログ出力（バックグラウンドスレッド用）

        Args:
            stop_event: 停止イベント（threading.Event）
            message_prefix: ログメッセージのプレフィックス
            interval: ログ出力間隔（秒）
        """
        start_time = time.time()
        while not stop_event.is_set():
            elapsed = int(time.time() - start_time)
            self.log(f"      {message_prefix}... (経過時間: {elapsed}秒)", "INFO")
            time.sleep(interval)

    def clear_log(self):
        """ログをクリア"""
        self.log_text.delete(1.0, tk.END)
    
    def show_column_selector_dialog(self, current_selection=""):
        """カラム選択ダイアログを表示（1～4つのカラムを選択可能）
        
        Args:
            current_selection: 現在選択されているカラムのカンマ区切り文字列
            
        Returns:
            list: 選択されたカラムのリスト、キャンセル時はNone
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("カラム選択")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 現在の選択を解析
        current_cols = [col.strip() for col in current_selection.split(',') if col.strip()]
        
        # 説明ラベル
        ttk.Label(dialog, text="最低1つ、最大4つのカラムを選択してください", 
                 wraplength=380).pack(pady=10, padx=10)
        
        # スクロール可能なチェックボックスリスト
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # チェックボックスの状態を管理
        check_vars = {}
        for col in (self.input_columns if self.input_columns else []):
            var = tk.BooleanVar(value=(col in current_cols))
            check_vars[col] = var
            ttk.Checkbutton(scrollable_frame, text=col, variable=var).pack(anchor='w', padx=20, pady=2)
        
        result = [None]  # クロージャで結果を格納
        
        def on_ok():
            selected = [col for col, var in check_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("選択エラー", "最低1つのカラムを選択してください。")
                return
            if len(selected) > 4:
                messagebox.showwarning("選択エラー", "選択できるカラムは最大4つです。")
                return
            result[0] = selected
            dialog.destroy()
        
        def on_cancel():
            result[0] = None
            dialog.destroy()
        
        # ボタンフレーム
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="OK", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="キャンセル", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # ダイアログが閉じるまで待機
        dialog.wait_window()
        
        return result[0]
    
    # ===== マッピング定義管理メソッド =====
    
    def update_mapping_definition_list(self):
        """マッピング定義リストを更新"""
        definition_names = list(self.column_mappings.keys())
        self.mapping_def_combo['values'] = definition_names
        if self.current_mapping_name in definition_names:
            self.mapping_def_combo.set(self.current_mapping_name)
        elif definition_names:
            self.mapping_def_combo.set(definition_names[0])
            self.current_mapping_name = definition_names[0]
        
        # ファイルマッピングUIのコンボボックスも更新
        self.update_file_mapping_combo_values()
    
    def update_file_mapping_combo_values(self):
        """ファイルマッピングUIのコンボボックスの選択肢を更新"""
        if not hasattr(self, 'file_mapping_widgets'):
            return
        
        definition_names = list(self.column_mappings.keys())
        
        for file_path, widgets in self.file_mapping_widgets.items():
            if 'combo' in widgets:
                combo = widgets['combo']
                current_value = combo.get()
                
                # 選択肢を更新
                combo['values'] = definition_names
                
                # 現在選択されている値が削除された場合はデフォルトに戻す
                if current_value not in definition_names:
                    combo.set("デフォルト")
                    self.file_mapping[file_path] = "デフォルト"
                    self.log(f"ファイル '{os.path.basename(file_path)}' のマッピングをデフォルトに設定（定義が削除されたため）", "INFO")
    
    def on_mapping_definition_changed(self, event=None):
        """マッピング定義が変更された時の処理"""
        # 現在のUIの設定を保存
        self.save_current_mapping_to_definition()
        
        # 新しい定義を選択
        new_name = self.mapping_def_combo.get()
        if new_name and new_name in self.column_mappings:
            self.current_mapping_name = new_name
            
            # タイプを復元
            if new_name in self.column_mappings_meta:
                self.current_mapping_type = self.column_mappings_meta[new_name].get("type", "線設備")
            else:
                self.current_mapping_type = "線設備"
            self.mapping_type_var.set(self.current_mapping_type)
            
            # 出力カラムを切り替え
            self.output_columns = self.output_columns_templates[self.current_mapping_type]
            
            # UIを再描画
            self.init_column_mapping_ui()
            # 保存された設定を復元
            self.load_mapping_definition_to_ui(new_name)
            self.log(f"マッピング定義を切り替えました: {new_name} ({self.current_mapping_type})")
    
    def on_mapping_type_changed(self, event=None):
        """設備タイプが変更された時の処理"""
        # 現在のUIの設定を保存
        self.save_current_mapping_to_definition()
        
        # 新しいタイプを適用
        new_type = self.mapping_type_var.get()
        self.current_mapping_type = new_type
        
        # メタ情報を更新
        if self.current_mapping_name not in self.column_mappings_meta:
            self.column_mappings_meta[self.current_mapping_name] = {}
        self.column_mappings_meta[self.current_mapping_name]["type"] = new_type
        
        # 出力カラムを切り替え
        self.output_columns = self.output_columns_templates[new_type]
        
        # UIを再描画
        self.init_column_mapping_ui()
        
        # 保存されていた設定があれば復元（新しいカラムに対応する設定のみ）
        self.load_mapping_definition_to_ui(self.current_mapping_name)
        
        self.log(f"設備タイプを変更しました: {new_type} (カラム数: {len(self.output_columns)})")
    
    def save_current_mapping_to_definition(self):
        """
        現在のUIの設定をマッピング定義に保存
        
        各出力カラムのマッピング方式とパラメータを
        内部辞書（self.column_mappings）に保存します。
        """
        if not self.current_mapping_widgets:
            return
        
        mapping_data = {}
        for out_col, widgets in self.current_mapping_widgets.items():
            mapping_type = widgets['type_var'].get()
            mapping_data[out_col] = {'type': mapping_type}
            
            if mapping_type == "カラム代入":
                mapping_data[out_col]['column'] = widgets['assign_combo'].get()
                # 補完処理を保存（fallback_typeに値があれば有効）
                fallback_type = widgets['assign_fallback_type'].get()
                if fallback_type:
                    mapping_data[out_col]['fallback'] = {
                        'type': fallback_type,
                        'fixed_value': widgets['assign_fallback_fixed'].get(),
                        'column': widgets['assign_fallback_column'].get(),
                        'filename_mapping': widgets['assign_fallback_filename'].get()
                    }
            elif mapping_type == "カラム四則演算":
                mapping_data[out_col]['column'] = widgets['calc_col_combo'].get()
                mapping_data[out_col]['operator'] = widgets['calc_op_combo'].get()
                mapping_data[out_col]['value'] = widgets['calc_num_entry'].get()
                # 補完処理を保存（fallback_typeに値があれば有効）
                fallback_type = widgets['calc_fallback_type'].get()
                if fallback_type:
                    mapping_data[out_col]['fallback'] = {
                        'type': fallback_type,
                        'fixed_value': widgets['calc_fallback_fixed'].get(),
                        'column': widgets['calc_fallback_column'].get(),
                        'filename_mapping': widgets['calc_fallback_filename'].get()
                    }
            elif mapping_type == "複数カラム四則演算":
                mapping_data[out_col]['column1'] = widgets['multi_col1_combo'].get()
                mapping_data[out_col]['operator'] = widgets['multi_op_combo'].get()
                mapping_data[out_col]['column2'] = widgets['multi_col2_combo'].get()
                # 補完処理を保存（fallback_typeに値があれば有効）
                fallback_type = widgets['multi_calc_fallback_type'].get()
                if fallback_type:
                    mapping_data[out_col]['fallback'] = {
                        'type': fallback_type,
                        'fixed_value': widgets['multi_calc_fallback_fixed'].get(),
                        'column': widgets['multi_calc_fallback_column'].get(),
                        'filename_mapping': widgets['multi_calc_fallback_filename'].get()
                    }
            elif mapping_type == "複数カラム抽出":
                mapping_data[out_col]['mode'] = widgets['extract_mode_combo'].get()
                # カンマ区切り文字列から配列に変換
                columns_str = widgets['extract_columns_entry'].get().strip()
                if columns_str:
                    columns = [col.strip() for col in columns_str.split(',')]
                else:
                    columns = []
                mapping_data[out_col]['columns'] = columns
                # 補完処理を保存（fallback_typeに値があれば有効）
                fallback_type = widgets['extract_fallback_type'].get()
                if fallback_type:
                    mapping_data[out_col]['fallback'] = {
                        'type': fallback_type,
                        'fixed_value': widgets['extract_fallback_fixed'].get(),
                        'column': widgets['extract_fallback_column'].get(),
                        'filename_mapping': widgets['extract_fallback_filename'].get()
                    }
            elif mapping_type == "固定値":
                mapping_data[out_col]['value'] = widgets['fixed_entry'].get()
            elif mapping_type == "ファイル名":
                # ファイル名は実行時に自動設定されるため、valueは保存不要（互換性のため空文字列）
                mapping_data[out_col]['value'] = ''
            elif mapping_type == "ランダム値":
                mapping_data[out_col]['min'] = widgets['random_min_entry'].get()
                mapping_data[out_col]['max'] = widgets['random_max_entry'].get()
            elif mapping_type == "シーケンス値":
                mapping_data[out_col]['start'] = widgets['seq_start_entry'].get()
                mapping_data[out_col]['step'] = widgets['seq_step_entry'].get()
            elif mapping_type == "条件分岐":
                mapping_data[out_col]['column'] = widgets['condition_col_combo'].get()
                # 条件文字列を解析して保存
                condition_str = widgets['condition_entry'].get().strip()
                conditions = []
                if condition_str:
                    # カンマで分割して各条件を解析
                    for item in condition_str.split(','):
                        item = item.strip()
                        if '=' in item:
                            parts = item.split('=', 1)
                            input_val = parts[0].strip()
                            output_val = parts[1].strip()
                            if input_val:  # 入力値が空でない場合のみ保存
                                conditions.append({'input': input_val, 'output': output_val})
                mapping_data[out_col]['conditions'] = conditions
                mapping_data[out_col]['default'] = widgets['condition_default_entry'].get()
            elif mapping_type == "ファイル名分岐":
                # 条件文字列を解析して保存
                condition_str = widgets['filename_branch_entry'].get().strip()
                conditions = []
                if condition_str:
                    # カンマで分割して各条件を解析
                    for item in condition_str.split(','):
                        item = item.strip()
                        if '=' in item:
                            parts = item.split('=', 1)
                            filename_val = parts[0].strip()
                            output_val = parts[1].strip()
                            if filename_val:  # ファイル名が空でない場合のみ保存
                                conditions.append({'filename': filename_val, 'output': output_val})
                mapping_data[out_col]['conditions'] = conditions
                mapping_data[out_col]['default'] = widgets['filename_branch_default_entry'].get()

        self.column_mappings[self.current_mapping_name] = mapping_data
    
    def load_mapping_definition_to_ui(self, definition_name):
        """
        保存されたマッピング定義をUIに復元
        
        指定された定義名のマッピング設定を読み込み、
        UIウィジェットに値を設定します。
        
        Args:
            definition_name (str): 読み込むマッピング定義名
        """
        if definition_name not in self.column_mappings:
            return
        
        # メタ情報からタイプを復元（UIの再構築が必要な場合のみ）
        need_rebuild = False
        if definition_name in self.column_mappings_meta:
            mapping_type = self.column_mappings_meta[definition_name].get('type', '線設備')
            if self.current_mapping_type != mapping_type:
                self.current_mapping_type = mapping_type
                self.mapping_type_var.set(mapping_type)
                self.output_columns = self.output_columns_templates[mapping_type]
                need_rebuild = True
        
        # UIを再構築（タイプが変わった場合のみ）
        if need_rebuild:
            self.init_column_mapping_ui()
        
        saved_mapping = self.column_mappings[definition_name]
        
        for out_col, saved_data in saved_mapping.items():
            if out_col not in self.current_mapping_widgets:
                continue
            
            widgets = self.current_mapping_widgets[out_col]
            mapping_type = saved_data.get('type', 'None')
            widgets['type_var'].set(mapping_type)
            
            # 各タイプに応じて値を復元
            if mapping_type == "カラム代入":
                widgets['assign_combo'].set(saved_data.get('column', ''))
                # 補完処理を復元
                fallback = saved_data.get('fallback', {})
                if fallback:
                    fallback_type = fallback.get('type', '')
                    widgets['assign_fallback_type'].set(fallback_type)
                    # タイプに応じて適切なウィジェットを表示
                    if fallback_type == "固定値":
                        widgets['assign_fallback_column'].grid_forget()
                        widgets['assign_fallback_fixed'].delete(0, tk.END)
                        widgets['assign_fallback_fixed'].insert(0, fallback.get('fixed_value', ''))
                        widgets['assign_fallback_fixed'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "他カラム":
                        widgets['assign_fallback_fixed'].grid_forget()
                        widgets['assign_fallback_column']['values'] = self.input_columns if self.input_columns else []
                        widgets['assign_fallback_column'].set(fallback.get('column', ''))
                        widgets['assign_fallback_column'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "ファイル名":
                        widgets['assign_fallback_column'].grid_forget()
                        widgets['assign_fallback_filename'].delete(0, tk.END)
                        widgets['assign_fallback_filename'].insert(0, fallback.get('filename_mapping', ''))
                        widgets['assign_fallback_filename'].grid(row=0, column=0, sticky="w")
            elif mapping_type == "カラム四則演算":
                widgets['calc_col_combo'].set(saved_data.get('column', ''))
                widgets['calc_op_combo'].set(saved_data.get('operator', ''))
                widgets['calc_num_entry'].delete(0, tk.END)
                widgets['calc_num_entry'].insert(0, saved_data.get('value', ''))
                # 補完処理を復元
                fallback = saved_data.get('fallback', {})
                if fallback:
                    fallback_type = fallback.get('type', '')
                    widgets['calc_fallback_type'].set(fallback_type)
                    if fallback_type == "固定値":
                        widgets['calc_fallback_column'].grid_forget()
                        widgets['calc_fallback_fixed'].delete(0, tk.END)
                        widgets['calc_fallback_fixed'].insert(0, fallback.get('fixed_value', ''))
                        widgets['calc_fallback_fixed'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "他カラム":
                        widgets['calc_fallback_fixed'].grid_forget()
                        widgets['calc_fallback_column']['values'] = self.input_columns if self.input_columns else []
                        widgets['calc_fallback_column'].set(fallback.get('column', ''))
                        widgets['calc_fallback_column'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "ファイル名":
                        widgets['calc_fallback_column'].grid_forget()
                        widgets['calc_fallback_filename'].delete(0, tk.END)
                        widgets['calc_fallback_filename'].insert(0, fallback.get('filename_mapping', ''))
                        widgets['calc_fallback_filename'].grid(row=0, column=0, sticky="w")
            elif mapping_type == "複数カラム四則演算":
                widgets['multi_col1_combo'].set(saved_data.get('column1', ''))
                widgets['multi_op_combo'].set(saved_data.get('operator', ''))
                widgets['multi_col2_combo'].set(saved_data.get('column2', ''))
                # 補完処理を復元
                fallback = saved_data.get('fallback', {})
                if fallback:
                    fallback_type = fallback.get('type', '')
                    widgets['multi_calc_fallback_type'].set(fallback_type)
                    if fallback_type == "固定値":
                        widgets['multi_calc_fallback_column'].grid_forget()
                        widgets['multi_calc_fallback_fixed'].delete(0, tk.END)
                        widgets['multi_calc_fallback_fixed'].insert(0, fallback.get('fixed_value', ''))
                        widgets['multi_calc_fallback_fixed'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "他カラム":
                        widgets['multi_calc_fallback_fixed'].grid_forget()
                        widgets['multi_calc_fallback_column']['values'] = self.input_columns if self.input_columns else []
                        widgets['multi_calc_fallback_column'].set(fallback.get('column', ''))
                        widgets['multi_calc_fallback_column'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "ファイル名":
                        widgets['multi_calc_fallback_column'].grid_forget()
                        widgets['multi_calc_fallback_filename'].delete(0, tk.END)
                        widgets['multi_calc_fallback_filename'].insert(0, fallback.get('filename_mapping', ''))
                        widgets['multi_calc_fallback_filename'].grid(row=0, column=0, sticky="w")
            elif mapping_type == "複数カラム抽出":
                widgets['extract_mode_combo'].set(saved_data.get('mode', ''))
                columns = saved_data.get('columns', [])
                # 配列をカンマ区切り文字列に変換して表示
                columns_filtered = [col for col in columns if col and col != 'None']
                entry = widgets['extract_columns_entry']
                entry.config(state="normal")
                entry.delete(0, tk.END)
                if columns_filtered:
                    entry.insert(0, ", ".join(columns_filtered))
                entry.config(state="readonly")
                # 補完処理を復元
                fallback = saved_data.get('fallback', {})
                if fallback:
                    fallback_type = fallback.get('type', '')
                    widgets['extract_fallback_type'].set(fallback_type)
                    if fallback_type == "固定値":
                        widgets['extract_fallback_column'].grid_forget()
                        widgets['extract_fallback_fixed'].delete(0, tk.END)
                        widgets['extract_fallback_fixed'].insert(0, fallback.get('fixed_value', ''))
                        widgets['extract_fallback_fixed'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "他カラム":
                        widgets['extract_fallback_fixed'].grid_forget()
                        widgets['extract_fallback_column']['values'] = self.input_columns if self.input_columns else []
                        widgets['extract_fallback_column'].set(fallback.get('column', ''))
                        widgets['extract_fallback_column'].grid(row=0, column=0, sticky="w")
                    elif fallback_type == "ファイル名":
                        widgets['extract_fallback_column'].grid_forget()
                        widgets['extract_fallback_filename'].delete(0, tk.END)
                        widgets['extract_fallback_filename'].insert(0, fallback.get('filename_mapping', ''))
                        widgets['extract_fallback_filename'].grid(row=0, column=0, sticky="w")
            elif mapping_type == "固定値":
                widgets['fixed_entry'].delete(0, tk.END)
                widgets['fixed_entry'].insert(0, saved_data.get('value', ''))
            elif mapping_type == "ファイル名":
                # ファイル名は自動設定されるため復元処理不要
                pass
            elif mapping_type == "ランダム値":
                widgets['random_min_entry'].delete(0, tk.END)
                widgets['random_min_entry'].insert(0, saved_data.get('min', ''))
                widgets['random_max_entry'].delete(0, tk.END)
                widgets['random_max_entry'].insert(0, saved_data.get('max', ''))
            elif mapping_type == "シーケンス値":
                widgets['seq_start_entry'].delete(0, tk.END)
                widgets['seq_start_entry'].insert(0, saved_data.get('start', '1'))
                widgets['seq_step_entry'].delete(0, tk.END)
                widgets['seq_step_entry'].insert(0, saved_data.get('step', '1'))
            elif mapping_type == "条件分岐":
                widgets['condition_col_combo'].set(saved_data.get('column', ''))
                # 条件配列を文字列に変換して復元
                conditions = saved_data.get('conditions', [])
                condition_str = ','.join([f"{c.get('input', '')}={c.get('output', '')}" for c in conditions])
                widgets['condition_entry'].delete(0, tk.END)
                widgets['condition_entry'].insert(0, condition_str)
                # デフォルト値を復元
                widgets['condition_default_entry'].delete(0, tk.END)
                widgets['condition_default_entry'].insert(0, saved_data.get('default', ''))
            elif mapping_type == "ファイル名分岐":
                # 条件配列を文字列に変換して復元
                conditions = saved_data.get('conditions', [])
                condition_str = ','.join([f"{c.get('filename', '')}={c.get('output', '')}" for c in conditions])
                widgets['filename_branch_entry'].delete(0, tk.END)
                widgets['filename_branch_entry'].insert(0, condition_str)
                # デフォルト値を復元
                widgets['filename_branch_default_entry'].delete(0, tk.END)
                widgets['filename_branch_default_entry'].insert(0, saved_data.get('default', ''))

            # UIを更新（対応するフレームを表示）
            widgets['assign_combo'].master.grid_remove()
            widgets['calc_col_combo'].master.grid_remove()
            widgets['multi_col1_combo'].master.grid_remove()
            widgets['extract_mode_combo'].master.grid_remove()
            widgets['fixed_entry'].master.grid_remove()
            widgets['filename_frame'].grid_remove()
            widgets['random_min_entry'].master.grid_remove()
            widgets['seq_start_entry'].master.grid_remove()
            widgets['condition_col_combo'].master.grid_remove()
            widgets['filename_branch_entry'].master.grid_remove()

            if mapping_type == "カラム代入":
                widgets['assign_combo'].master.grid()
            elif mapping_type == "カラム四則演算":
                widgets['calc_col_combo'].master.grid()
            elif mapping_type == "複数カラム四則演算":
                widgets['multi_col1_combo'].master.grid()
            elif mapping_type == "複数カラム抽出":
                widgets['extract_mode_combo'].master.grid()
            elif mapping_type == "固定値":
                widgets['fixed_entry'].master.grid()
            elif mapping_type == "ファイル名":
                widgets['filename_frame'].grid()
            elif mapping_type == "ランダム値":
                widgets['random_min_entry'].master.grid()
            elif mapping_type == "シーケンス値":
                widgets['seq_start_entry'].master.grid()
            elif mapping_type == "条件分岐":
                widgets['condition_col_combo'].master.grid()
            elif mapping_type == "ファイル名分岐":
                widgets['filename_branch_entry'].master.grid()
    
    def show_create_definition_dialog(self):
        """新規定義作成用のカスタムダイアログ"""
        dialog = tk.Toplevel(self.root)
        dialog.title("新規マッピング定義作成")
        dialog.geometry("550x180")
        dialog.resizable(False, False)
        
        # 中央に配置
        dialog.transient(self.root)
        dialog.grab_set()
        
        result = [None, None]  # [定義名, 設備タイプ]
        
        # 定義名入力
        name_frame = ttk.Frame(dialog, padding="10")
        name_frame.pack(fill=tk.X)
        ttk.Label(name_frame, text="定義名:").pack(side=tk.LEFT, padx=5)
        name_entry = ttk.Entry(name_frame, width=30)
        name_entry.pack(side=tk.LEFT, padx=5)
        name_entry.focus()
        
        # 設備タイプ選択
        type_frame = ttk.Frame(dialog, padding="10")
        type_frame.pack(fill=tk.X)
        ttk.Label(type_frame, text="設備タイプ:").pack(side=tk.LEFT, padx=5)
        
        type_var = tk.StringVar(value=self.last_selected_facility_type)
        ttk.Radiobutton(type_frame, text="線設備 (22カラム)", variable=type_var,
                       value="線設備").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(type_frame, text="点設備 (15カラム)", variable=type_var,
                       value="点設備").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(type_frame, text="電柱 (12カラム)", variable=type_var,
                       value="電柱").pack(side=tk.LEFT, padx=10)
        
        # 注意書き
        note_frame = ttk.Frame(dialog, padding="5")
        note_frame.pack(fill=tk.X)
        ttk.Label(note_frame, text="※設備タイプは後から変更できません", 
                 foreground="red", font=('', 8)).pack()
        
        # ボタン
        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)
        
        def on_ok():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("警告", "定義名を入力してください。", parent=dialog)
                return
            result[0] = name
            result[1] = type_var.get()
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(button_frame, text="OK", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # Enterキーで確定
        name_entry.bind('<Return>', lambda e: on_ok())
        
        dialog.wait_window()
        return tuple(result) if result[0] else None
    
    def create_new_mapping_definition(self):
        """新しいマッピング定義を作成"""
        # カスタムダイアログで定義名と設備タイプを入力
        result = self.show_create_definition_dialog()
        if not result:
            return
        
        new_name, facility_type = result
        
        if new_name in self.column_mappings:
            messagebox.showwarning("警告", f"定義名 '{new_name}' は既に存在します。")
            return
        
        # 現在の設定を保存
        self.save_current_mapping_to_definition()
        
        # 新しい定義を作成（空）
        self.column_mappings[new_name] = {}
        # 選択されたタイプでメタ情報を作成
        self.column_mappings_meta[new_name] = {"type": facility_type}
        self.last_selected_facility_type = facility_type  # 次回のデフォルト値として保存
        self.current_mapping_name = new_name
        
        # タイプを更新
        self.current_mapping_type = facility_type
        self.mapping_type_var.set(facility_type)  # UI表示を更新
        self.output_columns = self.output_columns_templates[facility_type]
        
        # UIを更新（ファイルマッピングのコンボボックスも更新される）
        self.update_mapping_definition_list()
        self.init_column_mapping_ui()
        
        self.log(f"新しいマッピング定義を作成しました: {new_name} ({facility_type})")
    
    def rename_mapping_definition(self):
        """マッピング定義の名称を変更"""
        if self.current_mapping_name == "デフォルト":
            messagebox.showwarning("警告", "'デフォルト'定義は名称変更できません。")
            return
        
        new_name = tk.simpledialog.askstring("名称変更", 
                                            f"'{self.current_mapping_name}' の新しい名前を入力してください:",
                                            initialvalue=self.current_mapping_name)
        if not new_name or new_name == self.current_mapping_name:
            return
        
        if new_name in self.column_mappings:
            messagebox.showwarning("警告", f"定義名 '{new_name}' は既に存在します。")
            return
        
        # 現在の設定を保存
        self.save_current_mapping_to_definition()
        
        # 名称変更
        self.column_mappings[new_name] = self.column_mappings.pop(self.current_mapping_name)
        # メタ情報も移動
        if self.current_mapping_name in self.column_mappings_meta:
            self.column_mappings_meta[new_name] = self.column_mappings_meta.pop(self.current_mapping_name)
        
        # ファイルマッピングも更新
        for file_path in self.file_mapping:
            if self.file_mapping[file_path] == self.current_mapping_name:
                self.file_mapping[file_path] = new_name
        
        # ファイル名マッピングも更新
        for file_name in self.file_name_mapping_definitions:
            if self.file_name_mapping_definitions[file_name] == self.current_mapping_name:
                self.file_name_mapping_definitions[file_name] = new_name
        
        old_name = self.current_mapping_name
        self.current_mapping_name = new_name
        
        # UIを更新（ファイルマッピングのコンボボックスも更新される）
        self.update_mapping_definition_list()
        
        # ファイルマッピングUIの表示も更新
        for file_path, widgets in self.file_mapping_widgets.items():
            if widgets['var'].get() == old_name:
                widgets['var'].set(new_name)
        
        # 設定を保存
        self.save_config()
        
        self.log(f"定義名を変更しました: {old_name} → {new_name}")
    
    def duplicate_mapping_definition(self):
        """マッピング定義を複製"""
        new_name = tk.simpledialog.askstring("複製", 
                                            f"'{self.current_mapping_name}' の複製名を入力してください:",
                                            initialvalue=f"{self.current_mapping_name}_コピー")
        if not new_name:
            return
        
        if new_name in self.column_mappings:
            messagebox.showwarning("警告", f"定義名 '{new_name}' は既に存在します。")
            return
        
        # 現在の設定を保存
        self.save_current_mapping_to_definition()
        
        # 複製を作成
        import copy
        self.column_mappings[new_name] = copy.deepcopy(self.column_mappings[self.current_mapping_name])
        # メタ情報も複製
        if self.current_mapping_name in self.column_mappings_meta:
            self.column_mappings_meta[new_name] = copy.deepcopy(self.column_mappings_meta[self.current_mapping_name])
        else:
            self.column_mappings_meta[new_name] = {"type": self.current_mapping_type}
        
        # UIを更新（ファイルマッピングのコンボボックスも更新される）
        self.update_mapping_definition_list()

        # 複製した定義に切り替え
        self.current_mapping_name = new_name
        self.mapping_def_combo.set(new_name)

        # 複製したタイプを設定
        if new_name in self.column_mappings_meta:
            self.current_mapping_type = self.column_mappings_meta[new_name]["type"]
            self.mapping_type_var.set(self.current_mapping_type)  # UI表示を更新
            self.output_columns = self.output_columns_templates[self.current_mapping_type]

        # UIを再初期化して複製した定義の内容を表示
        self.init_column_mapping_ui()

        self.load_mapping_definition_to_ui(new_name)
        self.log(f"定義を複製しました: {self.current_mapping_name} → {new_name}")
    
    def delete_mapping_definition(self):
        """マッピング定義を削除"""
        if self.current_mapping_name == "デフォルト":
            messagebox.showwarning("警告", "'デフォルト'定義は削除できません。")
            return
        
        if len(self.column_mappings) <= 1:
            messagebox.showwarning("警告", "最後の定義は削除できません。")
            return
        
        if not messagebox.askyesno("確認", f"定義 '{self.current_mapping_name}' を削除しますか？"):
            return
        
        deleted_name = self.current_mapping_name
        
        # ファイルマッピングから削除（デフォルトに戻す）
        files_to_update = [fp for fp, mn in self.file_mapping.items() if mn == deleted_name]
        for file_path in files_to_update:
            self.file_mapping[file_path] = "デフォルト"
        
        # ファイル名マッピングからも削除
        files_to_remove = [fn for fn, mn in self.file_name_mapping_definitions.items() if mn == deleted_name]
        for file_name in files_to_remove:
            del self.file_name_mapping_definitions[file_name]
        
        # 定義を削除
        del self.column_mappings[deleted_name]
        if deleted_name in self.column_mappings_meta:
            del self.column_mappings_meta[deleted_name]
        
        # デフォルトに切り替え
        self.current_mapping_name = "デフォルト"
        
        # UIを更新（ファイルマッピングのコンボボックスも更新される）
        self.update_mapping_definition_list()
        self.init_column_mapping_ui()
        self.load_mapping_definition_to_ui(self.current_mapping_name)
        
        # ファイルマッピングUIの表示も更新
        for file_path in files_to_update:
            if file_path in self.file_mapping_widgets:
                self.file_mapping_widgets[file_path]['var'].set("デフォルト")
        
        # 設定を保存
        self.save_config()
        
        self.log(f"定義を削除しました: {deleted_name}")
        if files_to_update:
            self.log(f"  影響を受けたファイル {len(files_to_update)}件 をデフォルトに戻しました", "INFO")
    
    # ===== サンプルファイル選択・カラム読み込み関連メソッド =====
    
    def select_sample_file(self):
        """カラム設定用のサンプルファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="サンプルファイルを選択（.shpまたは.zip）",
            filetypes=[("対応ファイル", "*.shp *.zip"), ("Shapeファイル", "*.shp"), ("ZIPファイル", "*.zip"), ("すべてのファイル", "*.*")]
        )
        if file_path:
            self.sample_file = file_path
            file_name = os.path.basename(file_path)
            self.sample_file_label.config(text=file_name, foreground="black")
            self.log(f"サンプルファイルを選択: {file_name}")
            
            # shpファイル名を設定（ZIP対応）
            if file_path.lower().endswith('.zip'):
                # ZIPの場合、shpファイル名は未設定（load_sample_columns()で取得）
                self.sample_shp_filename = None
            else:
                # 直接.shpファイルの場合
                # ファイル名を取得（Unicodeとして確実に扱う）
                self.sample_shp_filename = str(os.path.basename(file_path))
                self.log(f"shpファイル名を設定: {self.sample_shp_filename}")
                # 「ファイル名」方式が選択されている全てのEntryに自動反映
                self._update_filename_entries()
            
            # .cpgファイルから文字コードを自動検出
            detected = self.detect_file_settings(file_path)
            if detected['source_encoding']:
                self.sample_encoding.set(detected['source_encoding'])
                self.log(f"サンプルファイルの文字コードを自動検出: {detected['source_encoding']}")
            else:
                # デフォルト値を設定
                self.sample_encoding.set(self.source_encoding.get())
                self.log(f"サンプルファイルの文字コードはデフォルト値を使用: {self.source_encoding.get()}")
            
            # カラム情報表示をリセット
            self.sample_columns_label.config(text="カラム情報: 未読み込み（「カラム情報を読込」ボタンをクリック）", foreground="orange")
    
    
    def _update_filename_entries(self):
        """「ファイル名」方式が選択されている場合の処理（実行時に自動設定されるため何もしない）"""
        # ファイル名は実行時に各ファイルの実際のファイル名が自動設定されるため、UI更新は不要
        pass
    
    def _extract_zip_with_utf8_fix(self, zip_path, extract_to):
        """
        ZIPファイルを複数のエンコーディング候補から適切なものを自動検出して展開します。

        日本語環境で作成されたZIPファイルは多くの場合Shift_JISまたはCP932でエンコードされています。
        このメソッドは複数のエンコーディングを順番に試行し、最初に成功したものを使用します。

        試行順序:
        1. UTF-8: 国際標準、最近のツールで作成されたZIP
        2. Shift_JIS: 日本語Windows環境で一般的
        3. CP932: Shift_JISの拡張（Windowsコードページ932）
        4. EUC-JP: UNIX系環境での日本語
        5. GBK: 中国語環境（念のため）
        6. CP437: ZIPデフォルト（フォールバック）

        Args:
            zip_path (str): 展開するZIPファイルのパス
            extract_to (str): 展開先ディレクトリ

        Raises:
            Exception: 全てのエンコーディングで展開に失敗した場合
        """
        import zipfile

        encodings_to_try = ['utf-8', 'shift_jis', 'cp932', 'euc-jp', 'gbk']

        for encoding in encodings_to_try:
            try:
                success = self._try_extract_with_encoding(zip_path, extract_to, encoding)
                if success:
                    self.log(f"  ✓ ZIP展開成功（エンコーディング: {encoding}）", "DEBUG")
                    return
            except Exception as e:
                self.log(f"  × {encoding}での展開試行失敗: {e}", "DEBUG")
                continue

        # 全てのエンコーディングで失敗した場合、CP437でフォールバック
        self.log("  ⚠ 全てのエンコーディング検出に失敗、CP437でフォールバック", "WARNING")
        try:
            with zipfile.ZipFile(zip_path, 'r', metadata_encoding='cp437') as zf:
                file_list = zf.infolist()
                total_files = len(file_list)
                total_bytes = sum(info.file_size for info in file_list)
                total_mb = total_bytes / (1024 * 1024)

                self.log(f"  ZIP展開開始: {total_files}個のファイル ({total_mb:.1f} MB)を展開中...", "INFO")

                extracted_bytes = 0
                last_reported_percent = -1

                for idx, info in enumerate(file_list, 1):
                    zf.extract(info, extract_to)
                    extracted_bytes += info.file_size

                    if total_bytes > 0:
                        percent = int((extracted_bytes / total_bytes) * 100)
                        if percent >= last_reported_percent + 10 or idx == total_files:
                            extracted_mb = extracted_bytes / (1024 * 1024)
                            self.log(f"  展開中... {percent}% ({extracted_mb:.1f}/{total_mb:.1f} MB)", "INFO")
                            last_reported_percent = percent

                self.log(f"  ZIP展開完了: {total_files}個のファイル ({total_mb:.1f} MB)を展開しました", "INFO")
        except Exception as e:
            raise Exception(f"ZIPファイルの展開に失敗しました: {e}")


    def _try_extract_with_encoding(self, zip_path, extract_to, encoding):
        """
        指定されたエンコーディングでZIPファイルの展開を試行します。

        展開後、ファイル名に制御文字（U+0000-U+001F、タブ/改行/CR除く）が含まれていないことを検証します。
        制御文字が含まれる場合、エンコーディングが正しくない可能性が高いと判断します。

        Args:
            zip_path (str): 展開するZIPファイルのパス
            extract_to (str): 展開先ディレクトリ
            encoding (str): 使用するエンコーディング名（例: 'shift_jis', 'utf-8'）

        Returns:
            bool: 展開と検証に成功した場合True、失敗した場合False
        """
        import zipfile

        try:
            with zipfile.ZipFile(zip_path, 'r', metadata_encoding=encoding) as zf:
                file_list = zf.infolist()
                total_files = len(file_list)

                # ファイル名検証: 制御文字が含まれていないかチェック
                for info in file_list:
                    filename = info.filename
                    # タブ(\t=0x09)、改行(\n=0x0A)、CR(\r=0x0D)以外の制御文字を検出
                    if any(ord(c) < 32 and c not in '\t\n\r' for c in filename):
                        self.log(f"  ✗ {encoding}: ファイル名に不正な制御文字を検出: {repr(filename)}", "DEBUG")
                        return False

                # 検証成功、展開実行（進捗表示付き）
                # 総バイト数を計算
                total_bytes = sum(info.file_size for info in file_list)
                total_mb = total_bytes / (1024 * 1024)

                self.log(f"  ZIP展開開始: {total_files}個のファイル ({total_mb:.1f} MB)を展開中...", "INFO")

                extracted_bytes = 0
                last_reported_percent = -1

                for idx, info in enumerate(file_list, 1):
                    zf.extract(info, extract_to)
                    extracted_bytes += info.file_size

                    # 10%ごとに進捗を表示
                    if total_bytes > 0:
                        percent = int((extracted_bytes / total_bytes) * 100)
                        if percent >= last_reported_percent + 10 or idx == total_files:
                            extracted_mb = extracted_bytes / (1024 * 1024)
                            self.log(f"  展開中... {percent}% ({extracted_mb:.1f}/{total_mb:.1f} MB)", "INFO")
                            last_reported_percent = percent

                self.log(f"  ZIP展開完了: {total_files}個のファイル ({total_mb:.1f} MB)を展開しました", "INFO")
                return True

        except (UnicodeDecodeError, UnicodeEncodeError, LookupError) as e:
            # エンコーディングエラー: このエンコーディングは不適切
            self.log(f"  ✗ {encoding}: エンコーディングエラー: {e}", "DEBUG")
            return False
        except Exception as e:
            # その他のエラー: 展開失敗
            self.log(f"  ✗ {encoding}: 展開エラー: {e}", "DEBUG")
            return False

    def load_sample_columns(self):
        """サンプルファイルからカラム情報を読み込み"""
        if not self.sample_file:
            messagebox.showwarning("警告", "サンプルファイルを選択してください")
            return
        
        temp_dir = None
        try:
            temp_gdf = None
            
            # UIで選択された文字コードを使用
            encoding = self.sample_encoding.get()
            self.log(f"サンプルファイルを読み込み中（文字コード: {encoding}）...")
            
            # ZIPファイルの場合は展開して.shpを探す
            if self.sample_file.lower().endswith('.zip'):
                self.log("サンプルファイル（ZIP）を展開中...")
                temp_dir = tempfile.mkdtemp()
                try:
                    # UTF-8ファイル名対応でZIP展開
                    self._extract_zip_with_utf8_fix(self.sample_file, temp_dir)
                    # .shpファイルを探す
                    self.log("カラム情報を読み込み中...")
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.lower().endswith('.shp'):
                                shp_path = os.path.join(root, file)
                                # カラム情報のみ取得（全データは読み込まない）
                                temp_gdf = gpd.read_file(shp_path, encoding=encoding, rows=1)
                                self.log(f".shpファイル検出: {file}")
                                # ファイル名を取得（Unicodeとして確実に扱う）
                                self.sample_shp_filename = str(file)
                                break
                        if temp_gdf is not None:
                            break
                finally:
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)

                if temp_gdf is None:
                    messagebox.showerror("エラー", "ZIP内に.shpファイルが見つかりません")
                    return
            else:
                self.log("カラム情報を読み込み中...")
                # カラム情報のみ取得（全データは読み込まない）
                temp_gdf = gpd.read_file(self.sample_file, encoding=encoding, rows=1)
            
            if temp_gdf is not None:
                # カラム情報を読み込んで表示
                self.load_columns(temp_gdf)
                
                # カラム情報表示を更新
                column_count = len(self.input_columns)
                columns_preview = ", ".join(self.input_columns[:5])
                if column_count > 5:
                    columns_preview += f" ... (他{column_count - 5}個)"
                
                self.sample_columns_label.config(
                    text=f"カラム情報: {column_count}個読み込み済み（{columns_preview}）", 
                    foreground="green"
                )
                
                self.log(f"サンプルファイルのカラム情報を読み込みました: {column_count}個")
                
                # shpファイル名を使って「ファイル名」方式のEntryに自動反映
                if self.sample_shp_filename:
                    self.log(f"shpファイル名: {self.sample_shp_filename}")
                    self._update_filename_entries()
                
                messagebox.showinfo("完了", f"カラム情報を読み込みました。\n\nカラム数: {column_count}\n\nマッピング設定のコンボボックスに反映されました。")
                
        except Exception as e:
            error_msg = f"サンプルファイルの読み込みに失敗: {str(e)}"
            self.log(f"エラー: {error_msg}", "ERROR")
            messagebox.showerror("エラー", error_msg)
            
            # .shxエラーの場合は追加情報を表示
            if 'shx' in str(e).lower() or 'SHX' in str(e):
                self.log("  → .shxファイルが破損または欠落しています", "WARNING")
                self.log("  → GDAL設定により自動修復を試行します", "INFO")
        
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    # ===== ファイル選択・マッピング関連メソッド =====
    
    def select_input_files(self):
        file_paths = filedialog.askopenfilenames(
            title="ファイルを選択（.shpまたは.zip）",
            filetypes=[("対応ファイル", "*.shp *.zip"), ("Shapeファイル", "*.shp"), ("ZIPファイル", "*.zip"), ("すべてのファイル", "*.*")]
        )
        if file_paths:
            self.input_files = list(file_paths)
            file_count = len(self.input_files)
            self.input_label.config(text=f"{file_count}個のファイルを選択", foreground="black")
            self.log(f"{file_count}個のファイルを選択しました")
            
            # 選択されたファイルの設定をクリア（再検出させるため）
            for file_path in self.input_files:
                if file_path in self.file_specific_settings:
                    del self.file_specific_settings[file_path]
                    self.log(f"ファイル '{os.path.basename(file_path)}' の設定をクリアして再検出します", "INFO")
            
            # ファイル名に対応する保存済みマッピング定義を自動適用
            for file_path in self.input_files:
                file_name = os.path.basename(file_path)
                if file_name in self.file_name_mapping_definitions:
                    # 保存済みのマッピング定義を適用
                    saved_mapping = self.file_name_mapping_definitions[file_name]
                    if saved_mapping in self.column_mappings:
                        self.file_mapping[file_path] = saved_mapping
                        self.log(f"ファイル '{file_name}' に保存済みマッピング定義 '{saved_mapping}' を自動適用しました", "INFO")
                    else:
                        self.log(f"警告: 保存済みマッピング定義 '{saved_mapping}' が見つかりません。デフォルトを使用します", "WARNING")
                        self.file_mapping[file_path] = "デフォルト"
                else:
                    # 新規ファイルの場合はデフォルトを設定
                    self.file_mapping[file_path] = "デフォルト"
                    self.log(f"ファイル '{file_name}' は新規です。デフォルトのマッピング定義が選択されています", "INFO")
            
            # ファイル情報の読み込み完了通知
            self.log("ファイル情報の読み込みが完了しました")
            self.log("※ カラムマッピングは「カラム設定」タブでサンプルファイルから作成してください", "INFO")
            
            # ファイルマッピングUIを更新（各ファイルの.cpg/.prjを検出）
            self.update_file_mapping_ui()
            
            self.update_execute_button_state()
    
    def detect_file_settings(self, file_path):
        """ファイルからEPSGと文字コードを自動検出"""
        settings = {'source_epsg': '', 'source_encoding': '', 'shp_filename': ''}

        try:
            # ZIPファイルの場合は展開
            actual_shp_file = file_path
            temp_dir = None

            if file_path.lower().endswith('.zip'):
                self.log(f"  ZIPファイルを検出、設定ファイル（.cpg/.prj）を取得するため展開します...", "INFO")
                temp_dir = tempfile.mkdtemp()
                try:
                    # UTF-8ファイル名対応でZIP展開
                    self._extract_zip_with_utf8_fix(file_path, temp_dir)
                    # .shpファイルを探す
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.lower().endswith('.shp'):
                                actual_shp_file = os.path.join(root, file)
                                settings['shp_filename'] = file  # .shpファイル名を保存
                                self.log(f"  .shpファイルを検出: {file}", "INFO")
                                break
                        if actual_shp_file != file_path:
                            break
                except:
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    return settings
            else:
                # 直接.shpファイルの場合もファイル名を保存
                settings['shp_filename'] = os.path.basename(file_path)

            # .cpgファイルから文字コードを検出
            self.log(f"  設定ファイル（.cpg/.prj）を読み込み中...", "INFO")
            cpg_path = actual_shp_file.replace('.shp', '.cpg')
            if os.path.exists(cpg_path):
                try:
                    with open(cpg_path, 'r', encoding='ascii') as f:
                        encoding = f.read().strip()
                    
                    # エンコーディング名を変換
                    encoding_map = {
                        'UTF-8': 'UTF-8', 'UTF8': 'UTF-8',
                        'SHIFT_JIS': 'Shift_JIS', 'SHIFT-JIS': 'Shift_JIS', 'SJIS': 'Shift_JIS',
                        'CP932': 'CP932',
                        'EUC-JP': 'EUC-JP', 'EUCJP': 'EUC-JP',
                        'ISO-2022-JP': 'ISO-2022-JP',
                    }
                    encoding_upper = encoding.upper()
                    if encoding_upper in encoding_map:
                        settings['source_encoding'] = encoding_map[encoding_upper]
                        self.log(f"  文字コード検出: {settings['source_encoding']}", "INFO")
                except Exception as e:
                    self.log(f"  文字コード検出失敗: {str(e)}", "DEBUG")
                    pass
            
            # .prjファイルからEPSGを検出
            prj_path = actual_shp_file.replace('.shp', '.prj')
            if os.path.exists(prj_path):
                try:
                    from pyproj import CRS
                    with open(prj_path, 'r', encoding='utf-8') as f:
                        prj_content = f.read()
                    # WKT文字列からCRSオブジェクトを作成
                    crs = CRS.from_wkt(prj_content)
                    if crs.to_epsg() is not None:
                        settings['source_epsg'] = str(crs.to_epsg())
                        self.log(f"  EPSG検出: {settings['source_epsg']}", "INFO")
                except Exception as e:
                    self.log(f"  EPSG検出失敗: {str(e)}", "DEBUG")
                    pass
            
            # 一時ディレクトリのクリーンアップ
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            pass
        
        return settings
    
    def detect_encoding_from_cpg(self, shapefile_path):
        """.cpgファイルから文字コードを検出して自動設定"""
        try:
            # .shpファイルから.cpgファイルのパスを生成
            cpg_path = shapefile_path.replace('.shp', '.cpg')
            
            if os.path.exists(cpg_path):
                # .cpgファイルを読み取り
                with open(cpg_path, 'r', encoding='ascii') as f:
                    encoding = f.read().strip()
                
                # よくあるエンコーディング名を変換
                encoding_map = {
                    'UTF-8': 'UTF-8',
                    'UTF8': 'UTF-8',
                    'SHIFT_JIS': 'Shift_JIS',
                    'SHIFT-JIS': 'Shift_JIS',
                    'SJIS': 'Shift_JIS',
                    'CP932': 'CP932',
                    'EUC-JP': 'EUC-JP',
                    'EUCJP': 'EUC-JP',
                    'ISO-2022-JP': 'ISO-2022-JP',
                }
                
                # 大文字小文字を無視してマッピング
                encoding_upper = encoding.upper()
                if encoding_upper in encoding_map:
                    detected_encoding = encoding_map[encoding_upper]
                    self.source_encoding.set(detected_encoding)
                    self.log(f"文字コードを自動設定: {detected_encoding} (.cpgファイルより)")
                else:
                    self.log(f".cpgファイル検出: {encoding} (未対応のため手動選択してください)", "WARNING")
            else:
                self.log("警告: .cpgファイルが見つかりません。文字コードを手動で選択してください", "WARNING")
        except Exception as e:
            self.log(f"警告: .cpgファイルの読み込みに失敗: {str(e)}", "WARNING")
    
    def load_columns(self, gdf):
        """カラム情報を読み込んでコンボボックスを更新"""
        # インポートカラムを取得
        self.input_columns = [col for col in gdf.columns if col != 'geometry']
        
        # 既存のコンボボックスにカラムリストを設定
        if self.current_mapping_widgets:
            for out_col, widgets in self.current_mapping_widgets.items():
                # 各種カラム選択コンボボックスを更新
                widgets['assign_combo']['values'] = self.input_columns
                widgets['assign_fallback_column']['values'] = self.input_columns
                widgets['calc_col_combo']['values'] = self.input_columns
                widgets['calc_fallback_column']['values'] = self.input_columns
                widgets['multi_col1_combo']['values'] = self.input_columns
                widgets['multi_col2_combo']['values'] = self.input_columns
                widgets['multi_calc_fallback_column']['values'] = self.input_columns
                # 複数カラム抽出はポップアップ選択式のためComboboxの更新は不要
                widgets['extract_fallback_column']['values'] = self.input_columns
                widgets['condition_col_combo']['values'] = self.input_columns
        
        self.log(f"インポート可能なカラム数: {len(self.input_columns)}")
    
    def select_output_dir(self):
        dir_path = filedialog.askdirectory(
            title="出力先ディレクトリを選択"
        )
        if dir_path:
            self.output_dir = dir_path
            self.output_label.config(text=dir_path, foreground="black")
            self.update_execute_button_state()
    
    def update_file_mapping_ui(self):
        """ファイルマッピングUIを更新"""
        # 既存のウィジェットをクリア
        for widget in self.mapping_scrollable_frame.winfo_children():
            widget.destroy()

        # スクロール位置を先頭にリセット
        self.mapping_canvas.yview_moveto(0)

        self.file_mapping_widgets = {}
        
        if not self.input_files:
            # ファイルが選択されていない場合
            self.mapping_info_label = ttk.Label(self.mapping_scrollable_frame, 
                                               text="ファイルを選択すると、ここにマッピング設定が表示されます",
                                               foreground="gray")
            self.mapping_info_label.pack(pady=20)
            return
        
        # ヘッダー（固定幅のFrameを使用して確実に揃える）
        header_frame = ttk.Frame(self.mapping_scrollable_frame)
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 各列を固定幅のFrameで配置
        col0_frame = tk.Frame(header_frame, width=280, height=25)
        col0_frame.pack(side=tk.LEFT, padx=2)
        col0_frame.pack_propagate(False)
        ttk.Label(col0_frame, text="ファイル名", font=('', 9, 'bold')).pack(side=tk.LEFT, padx=3, anchor=tk.W)
        
        col1_frame = tk.Frame(header_frame, width=150, height=25)
        col1_frame.pack(side=tk.LEFT, padx=2)
        col1_frame.pack_propagate(False)
        ttk.Label(col1_frame, text="マッピング定義", font=('', 9, 'bold')).pack(side=tk.LEFT, padx=3, anchor=tk.W)
        
        col2_frame = tk.Frame(header_frame, width=100, height=25)
        col2_frame.pack(side=tk.LEFT, padx=2)
        col2_frame.pack_propagate(False)
        ttk.Label(col2_frame, text="変換元EPSG", font=('', 9, 'bold')).pack(side=tk.LEFT, padx=3, anchor=tk.W)
        
        col3_frame = tk.Frame(header_frame, width=120, height=25)
        col3_frame.pack(side=tk.LEFT, padx=2)
        col3_frame.pack_propagate(False)
        ttk.Label(col3_frame, text="文字コード", font=('', 9, 'bold')).pack(side=tk.LEFT, padx=3, anchor=tk.W)
        
        # マッピング定義のリストを取得
        definition_names = list(self.column_mappings.keys())
        encoding_choices = ('UTF-8', 'Shift_JIS', 'CP932', 'EUC-JP', 'ISO-2022-JP')
        
        # 各ファイルのマッピング設定
        total_files = len(self.input_files)
        for idx, file_path in enumerate(self.input_files, 1):
            file_name = os.path.basename(file_path)

            # 進捗表示
            self.log(f"ファイル設定を読み込み中... ({idx}/{total_files}): {file_name}", "INFO")

            row_frame = ttk.Frame(self.mapping_scrollable_frame)
            row_frame.pack(fill=tk.X, padx=5, pady=2)

            # 各列を固定幅のFrameで配置（ヘッダーと同じ幅）
            # ファイル名列
            col0_frame = tk.Frame(row_frame, width=280, height=30)
            col0_frame.pack(side=tk.LEFT, padx=2)
            col0_frame.pack_propagate(False)
            file_label = ttk.Label(col0_frame, text=file_name, anchor=tk.W)
            file_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)

            # マッピング定義列
            col1_frame = tk.Frame(row_frame, width=150, height=30)
            col1_frame.pack(side=tk.LEFT, padx=2)
            col1_frame.pack_propagate(False)

            # マッピング定義選択
            if file_path not in self.file_mapping:
                self.file_mapping[file_path] = "デフォルト"

            mapping_var = tk.StringVar(value=self.file_mapping[file_path])
            mapping_combo = ttk.Combobox(col1_frame, textvariable=mapping_var,
                                        values=definition_names, state="readonly")
            mapping_combo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            self.bind_combobox_wheel(mapping_combo)  # マウスホイールイベント制御

            # ファイル固有の設定を取得または初期化
            if file_path not in self.file_specific_settings:
                # .cpg/.prjファイルから自動検出を試行
                detected = self.detect_file_settings(file_path)
                
                # EPSGが検出されなかった場合、デフォルト値を使用
                if not detected['source_epsg']:
                    detected['source_epsg'] = self.source_epsg.get()
                    self.log(f"ファイル '{file_name}' はCRS情報なし。デフォルトEPSGを適用: {detected['source_epsg']}", "INFO")
                else:
                    self.log(f"ファイル '{file_name}' のEPSGを自動検出: {detected['source_epsg']}")
                
                # 文字コードが検出されなかった場合、デフォルト値を使用
                if not detected['source_encoding']:
                    detected['source_encoding'] = self.source_encoding.get()
                    self.log(f"ファイル '{file_name}' は.cpgなし。デフォルト文字コードを適用: {detected['source_encoding']}", "INFO")
                else:
                    self.log(f"ファイル '{file_name}' の文字コードを自動検出: {detected['source_encoding']}")
                
                self.file_specific_settings[file_path] = detected
            
            # 変換元EPSG列
            col2_frame = tk.Frame(row_frame, width=100, height=30)
            col2_frame.pack(side=tk.LEFT, padx=2)
            col2_frame.pack_propagate(False)
            epsg_var = tk.StringVar(value=self.file_specific_settings[file_path]['source_epsg'])
            epsg_entry = ttk.Entry(col2_frame, textvariable=epsg_var)
            epsg_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            
            # 文字コード列
            col3_frame = tk.Frame(row_frame, width=120, height=30)
            col3_frame.pack(side=tk.LEFT, padx=2)
            col3_frame.pack_propagate(False)
            encoding_var = tk.StringVar(value=self.file_specific_settings[file_path]['source_encoding'])
            encoding_combo = ttk.Combobox(col3_frame, textvariable=encoding_var,
                                         values=encoding_choices, state="readonly")
            encoding_combo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            self.bind_combobox_wheel(encoding_combo)  # マウスホイールイベント制御
            
            # コンボボックスの値が変更されたときにfile_mappingを更新
            def on_mapping_change(fp=file_path, mv=mapping_var):
                self.file_mapping[fp] = mv.get()
                self.log(f"ファイル '{os.path.basename(fp)}' のマッピングを '{mv.get()}' に設定")
            
            def on_epsg_change(fp=file_path, ev=epsg_var, *args):
                self.file_specific_settings[fp]['source_epsg'] = ev.get().strip()
                if ev.get().strip():
                    self.log(f"ファイル '{os.path.basename(fp)}' のEPSGを '{ev.get()}' に設定")
            
            def on_encoding_change(fp=file_path, encv=encoding_var):
                enc_value = encv.get()
                self.file_specific_settings[fp]['source_encoding'] = enc_value
                self.log(f"ファイル '{os.path.basename(fp)}' の文字コードを '{enc_value}' に設定")
            
            mapping_combo.bind("<<ComboboxSelected>>", lambda e, fp=file_path, mv=mapping_var: on_mapping_change(fp, mv))
            epsg_var.trace_add('write', on_epsg_change)
            encoding_combo.bind("<<ComboboxSelected>>", lambda e, fp=file_path, encv=encoding_var: on_encoding_change(fp, encv))
            
            self.file_mapping_widgets[file_path] = {
                'label': file_label,
                'mapping_combo': mapping_combo,
                'mapping_var': mapping_var,
                'epsg_entry': epsg_entry,
                'epsg_var': epsg_var,
                'encoding_combo': encoding_combo,
                'encoding_var': encoding_var
            }

        # UIが更新されたので、全てのウィジェットにマウスホイールをバインド
        if hasattr(self, '_on_mapping_mousewheel'):
            self.bind_mousewheel_to_widget(self.mapping_scrollable_frame, self._on_mapping_mousewheel)

        # 全ファイルの設定読み込み完了
        self.log(f"全ファイルの設定読み込みが完了しました ({total_files}個)", "INFO")

    def update_execute_button_state(self):
        if self.input_files and self.output_dir:
            self.execute_button.config(state=tk.NORMAL)
        else:
            self.execute_button.config(state=tk.DISABLED)
    
    def save_all_file_mappings(self):
        """全ファイルの現在のマッピング定義を保存"""
        if not self.input_files:
            messagebox.showwarning("警告", "ファイルが選択されていません。")
            return
        
        saved_count = 0
        for file_path in self.input_files:
            file_name = os.path.basename(file_path)
            mapping_name = self.file_mapping.get(file_path, "デフォルト")
            
            # マッピング定義が存在するか確認
            if mapping_name in self.column_mappings:
                self.file_name_mapping_definitions[file_name] = mapping_name
                saved_count += 1
                self.log(f"ファイル '{file_name}' のマッピング定義 '{mapping_name}' を保存しました", "INFO")
        
        # config.jsonに保存
        self.save_config()
        messagebox.showinfo("保存完了", f"{saved_count}個のファイルのマッピング定義を保存しました。")
    
    def delete_all_file_mappings(self):
        """選択中のファイルの保存済みマッピング定義を削除"""
        if not self.input_files:
            messagebox.showwarning("警告", "ファイルが選択されていません。")
            return
        
        # 削除対象のファイルを確認
        files_to_delete = []
        for file_path in self.input_files:
            file_name = os.path.basename(file_path)
            if file_name in self.file_name_mapping_definitions:
                files_to_delete.append(file_name)
        
        if not files_to_delete:
            messagebox.showinfo("情報", "選択中のファイルに保存済みマッピング定義はありません。")
            return
        
        # 確認ダイアログを表示
        files_list = "\n".join([f"  ・{fn}" for fn in files_to_delete])
        result = messagebox.askyesno("確認", 
                                     f"以下のファイルの保存済みマッピング定義を削除しますか？\n\n{files_list}\n\n({len(files_to_delete)}個)")
        
        if result:
            # 削除
            for file_name in files_to_delete:
                del self.file_name_mapping_definitions[file_name]
                self.log(f"ファイル '{file_name}' の保存済みマッピング定義を削除しました", "INFO")
                
                # 該当するファイルをデフォルトに戻す
                for file_path in self.input_files:
                    if os.path.basename(file_path) == file_name:
                        self.file_mapping[file_path] = "デフォルト"
            
            # config.jsonに保存
            self.save_config()
            messagebox.showinfo("削除完了", f"{len(files_to_delete)}個のファイルのマッピング定義を削除しました。")
            
            # UIを更新
            self.update_file_mapping_ui()
    
    def save_config(self):
        """
        現在の設定をJSONファイルに保存
        
        保存される情報:
            - 基本設定（EPSG、文字コード、短い辺閾値）
            - カラムマッピング定義（複数）
            - ファイルごとのマッピング割り当て
            - ファイルごとの座標系/文字コード設定
        
        Note:
            - config.jsonという名前で保存されます
            - EXE実行時は実行ファイルと同じディレクトリに保存されます
        """
        try:
            # 現在のUIの設定を保存
            self.save_current_mapping_to_definition()
            
            config = {
                'min_distance': self.min_distance.get(),
                'source_epsg': self.source_epsg.get(),
                'target_epsg': self.target_epsg.get(),
                'source_encoding': self.source_encoding.get(),
                'column_mappings': self.column_mappings,  # 複数のマッピング定義
                'column_mappings_meta': self.column_mappings_meta,  # メタ情報（タイプなど）
                'file_mapping': self.file_mapping,  # ファイルごとのマッピング割り当て
                'file_specific_settings': self.file_specific_settings,  # ファイルごとのEPSG・文字コード設定
                'current_mapping_name': self.current_mapping_name,  # 現在選択中の定義
                'file_mappings': self.file_name_mapping_definitions  # ファイル名ベースのマッピング定義保存
            }
            
            # JSONファイルに書き込み
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("保存完了", f"設定を保存しました:\n{self.config_file}")
            self.log(f"設定を保存しました: {self.config_file}")
            
        except Exception as e:
            messagebox.showerror("保存エラー", f"設定の保存に失敗しました:\n{str(e)}")
    
    def load_config(self):
        """
        保存された設定をJSONファイルから読み込み
        
        読み込まれる情報:
            - 基本設定（EPSG、文字コード、短い辺閾値）
            - カラムマッピング定義（複数）
            - ファイルごとのマッピング割り当て
        
        Note:
            - 設定ファイルが存在しない場合はデフォルト設定が使用されます
            - 不正なJSON形式の場合はエラーメッセージが表示されます
        """
        try:
            if not os.path.exists(self.config_file):
                self.log(f"設定ファイルが見つかりません: {self.config_file}")
                self.log("デフォルト設定を使用します")
                # デフォルト設定をファイルに保存
                try:
                    # 設定ファイルのディレクトリが存在しない場合は作成
                    config_dir = os.path.dirname(self.config_file)
                    if not os.path.exists(config_dir):
                        os.makedirs(config_dir, exist_ok=True)
                    
                    default_config = {
                        'min_distance': self.min_distance.get(),
                        'source_epsg': self.source_epsg.get(),
                        'target_epsg': self.target_epsg.get(),
                        'source_encoding': self.source_encoding.get(),
                        'column_mappings': {"デフォルト": {}},
                        'file_mapping': {},
                        'current_mapping_name': "デフォルト"
                    }
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        json.dump(default_config, f, ensure_ascii=False, indent=2)
                    self.log(f"デフォルト設定ファイルを作成しました: {self.config_file}")
                except Exception as e:
                    self.log(f"警告: デフォルト設定ファイルの作成に失敗: {str(e)}", "WARNING")
                return
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 処理設定を読み込み
            if 'min_distance' in config:
                self.min_distance.set(config['min_distance'])
            if 'source_epsg' in config:
                self.source_epsg.set(config['source_epsg'])
            if 'target_epsg' in config:
                self.target_epsg.set(config['target_epsg'])
            if 'source_encoding' in config:
                self.source_encoding.set(config['source_encoding'])
            
            # 複数マッピング定義に対応（旧形式との互換性あり）
            if 'column_mappings' in config:
                # 新形式
                self.column_mappings = config['column_mappings']
            elif 'column_mapping' in config:
                # 旧形式（単一マッピング）を新形式に変換
                self.column_mappings = {"デフォルト": config['column_mapping']}
                self.log("旧形式の設定を新形式に変換しました", "INFO")
            
            # メタ情報を読み込み（タイプなど）
            if 'column_mappings_meta' in config:
                self.column_mappings_meta = config['column_mappings_meta']
            else:
                # メタ情報がない場合はデフォルト（線設備）で初期化
                self.column_mappings_meta = {name: {"type": "線設備"} for name in self.column_mappings.keys()}
            
            # ファイルマッピングを読み込み
            if 'file_mapping' in config:
                self.file_mapping = config['file_mapping']
            
            # ファイル固有の設定を読み込み（EPSG・文字コード）
            if 'file_specific_settings' in config:
                self.file_specific_settings = config['file_specific_settings']
            
            # ファイル名ベースのマッピング定義を読み込み
            if 'file_mappings' in config:
                self.file_name_mapping_definitions = config['file_mappings']
                if hasattr(self, 'log_text') and self.file_name_mapping_definitions:
                    self.log(f"ファイル名マッピング定義を読み込みました ({len(self.file_name_mapping_definitions)}件)", "INFO")
            
            # 現在選択中の定義を読み込み
            if 'current_mapping_name' in config and config['current_mapping_name'] in self.column_mappings:
                self.current_mapping_name = config['current_mapping_name']
            elif self.column_mappings:
                self.current_mapping_name = list(self.column_mappings.keys())[0]
            
            # UIを更新
            self.update_mapping_definition_list()
            if self.current_mapping_widgets:
                self.load_mapping_definition_to_ui(self.current_mapping_name)
            
            self.log(f"設定を読み込みました: {self.config_file}")
            
        except Exception as e:
            self.log(f"設定の読み込みに失敗: {str(e)}", "WARNING")
    
    def reset_config(self):
        """設定をデフォルト値にリセット（複数マッピング定義対応）"""
        if messagebox.askyesno("確認", "設定をデフォルト値にリセットしますか？"):
            self.min_distance.set(0.01)
            self.source_epsg.set("6669")
            self.target_epsg.set("6677")
            
            # すべてのマッピング定義をクリア
            self.column_mappings = {"デフォルト": {}}
            self.current_mapping_name = "デフォルト"
            self.file_mapping = {}
            
            # UIをリセット
            if self.current_mapping_widgets:
                for out_col, widgets in self.current_mapping_widgets.items():
                    widgets['type_var'].set("None")
                    # 全ての入力欄をクリア
                    widgets['assign_combo'].set('')
                    widgets['calc_col_combo'].set('')
                    widgets['calc_op_combo'].set('')
                    widgets['calc_num_entry'].delete(0, tk.END)
                    widgets['multi_col1_combo'].set('')
                    widgets['multi_op_combo'].set('')
                    widgets['multi_col2_combo'].set('')
                    widgets['fixed_entry'].delete(0, tk.END)
                    widgets['random_min_entry'].delete(0, tk.END)
                    widgets['random_max_entry'].delete(0, tk.END)
                    widgets['seq_start_entry'].delete(0, tk.END)
                    widgets['seq_step_entry'].delete(0, tk.END)
                    # 全フレームを非表示
                    widgets['assign_combo'].master.grid_remove()
                    widgets['calc_col_combo'].master.grid_remove()
                    widgets['multi_col1_combo'].master.grid_remove()
                    widgets['fixed_entry'].master.grid_remove()
                    widgets['random_min_entry'].master.grid_remove()
                    widgets['seq_start_entry'].master.grid_remove()
            
            # ファイルマッピングUIもリセット
            self.update_mapping_definition_list()
            self.update_file_mapping_ui()
            
            self.log("設定をリセットしました")
    
    def check_invalid_geometry(self, geom):
        """
        ジオメトリの無効性をチェック
        
        以下の条件で無効と判定します:
        - ジオメトリがNoneまたはempty
        - 座標にNaNまたはInfが含まれる
        
        Args:
            geom: Shapelyジオメトリオブジェクト
        
        Returns:
            tuple: (is_invalid: bool, reason: str or None)
                - is_invalid: 無効な場合True
                - reason: 無効な理由（有効な場合はNone）
        """
        if geom is None or geom.is_empty:
            return True, "null/empty geometry"
        
        # 座標にNaN/Infが含まれているかチェック
        coords = np.array(geom.coords if hasattr(geom, 'coords') else list(geom.exterior.coords) if hasattr(geom, 'exterior') else [])
        if coords.size > 0 and (np.isnan(coords).any() or np.isinf(coords).any()):
            return True, "NaN/Inf in coordinates"
        
        return False, None
    
    def try_fix_geometry(self, geom):
        """
        無効なジオメトリの修正を試みる
        
        Shapelyのmake_valid()を使用してジオメトリの修正を試みます。
        修正後も無効な場合や、buffer(0)でも修正できない場合はNoneを返します。
        
        Args:
            geom: Shapelyジオメトリオブジェクト
        
        Returns:
            修正後のジオメトリまたはNone
        """
        if geom is None or geom.is_empty:
            return None
        
        # 座標にNaN/Infが含まれている場合は修正不可
        try:
            coords = np.array(geom.coords if hasattr(geom, 'coords') else list(geom.exterior.coords) if hasattr(geom, 'exterior') else [])
            if coords.size > 0 and (np.isnan(coords).any() or np.isinf(coords).any()):
                return None
        except Exception:
            pass
        
        # is_validチェックで例外が発生する場合を処理
        try:
            if geom.is_valid:
                return geom  # 既に有効
        except Exception as e:
            # is_validチェック自体がエラーの場合、修正を試みる
            self.log(f"      ジオメトリチェック中にエラー: {str(e)}")
        
        # make_validで修正を試みる
        try:
            fixed_geom = make_valid(geom)
            if fixed_geom and not fixed_geom.is_empty and fixed_geom.is_valid:
                return fixed_geom
        except Exception as e:
            self.log(f"      make_valid失敗: {str(e)}")
        
        # buffer(0)で修正を試みる
        try:
            fixed_geom = geom.buffer(0)
            if fixed_geom and not fixed_geom.is_empty and fixed_geom.is_valid:
                return fixed_geom
        except Exception as e:
            self.log(f"      buffer(0)失敗: {str(e)}")
        
        # 座標を再構築して修正を試みる（最後の手段）
        try:
            if geom.geom_type == 'Polygon':
                coords = list(geom.exterior.coords)
                if len(coords) >= 4:  # ポリゴンには最低4点必要（始点と終点が同じ）
                    fixed_geom = Polygon(coords)
                    if fixed_geom.is_valid:
                        return fixed_geom
            elif geom.geom_type == 'LineString':
                coords = list(geom.coords)
                if len(coords) >= 2:
                    fixed_geom = LineString(coords)
                    if fixed_geom.is_valid:
                        return fixed_geom
        except Exception as e:
            self.log(f"      座標再構築失敗: {str(e)}")
        
        return None  # 修正不可
    
    def check_short_edges(self, geom, min_dist):
        """
        ジオメトリに短すぎる辺が含まれるかチェック
        
        LineStringやPolygonの連続する点間の距離が、
        指定された閾値より短い場合にTrueを返します。
        
        Args:
            geom: Shapelyジオメトリオブジェクト
            min_dist (float): 最小距離（メートル）
        
        Returns:
            bool: 短すぎる辺が存在する場合True
        """
        """短い辺があるかチェック"""
        if not isinstance(geom, (LineString, Polygon, MultiLineString, MultiPolygon)):
            return False, None
        
        def check_line(line):
            coords = list(line.coords)
            for i in range(len(coords) - 1):
                p1 = Point(coords[i])
                p2 = Point(coords[i + 1])
                dist = p1.distance(p2)
                if 0 < dist <= min_dist:
                    return True, f"short edge: {dist:.6f}m"
            return False, None
        
        if isinstance(geom, LineString):
            return check_line(geom)
        elif isinstance(geom, Polygon):
            result, msg = check_line(geom.exterior)
            if result:
                return result, msg
            for interior in geom.interiors:
                result, msg = check_line(interior)
                if result:
                    return result, msg
        elif isinstance(geom, (MultiLineString, MultiPolygon)):
            for sub_geom in geom.geoms:
                result, msg = self.check_short_edges(sub_geom, min_dist)
                if result:
                    return result, msg
        
        return False, None
    
    def check_polygon_validity(self, geom):
        """
        Polygonの妥当性をチェック
        
        Shapelyのis_validプロパティを使用して、
        Polygonのジオメトリが有効かどうかを確認します。
        
        Args:
            geom: Shapelyジオメトリオブジェクト
        
        Returns:
            bool: 無効なPolygonの場合True
        """
        """Polygonの妥当性チェック"""
        if not isinstance(geom, (Polygon, MultiPolygon)):
            return False, None
        
        try:
            if isinstance(geom, Polygon):
                if not geom.is_valid:
                    reason = validation.explain_validity(geom)
                    return True, f"invalid polygon: {reason}"
            elif isinstance(geom, MultiPolygon):
                for poly in geom.geoms:
                    if not poly.is_valid:
                        reason = validation.explain_validity(poly)
                        return True, f"invalid polygon: {reason}"
        except Exception as e:
            # is_validチェック自体がエラーの場合
            return True, f"polygon check error: {str(e)}"
        
        return False, None
    
    def explode_multi_geometries(self, gdf):
        """MultiジオメトリをSingleに展開"""
        self.log("⑤ MultiジオメトリをSingleに展開中...")
        
        original_count = len(gdf)
        
        # GeoPandasの組み込みexplode()メソッドを使用
        result_gdf = gdf.explode(index_parts=False).reset_index(drop=True)
        
        self.log(f"   展開前: {original_count} レコード → 展開後: {len(result_gdf)} レコード")
        return result_gdf
    
    def execute_cleaning(self):
        """
        複数のShapefileを一括処理（スレッド起動）

        バックグラウンドスレッドで処理を実行し、UIがフリーズしないようにします。
        """
        # 処理中の場合は何もしない
        if hasattr(self, '_processing_thread') and self._processing_thread.is_alive():
            messagebox.showwarning("警告", "処理実行中です。しばらくお待ちください。")
            return

        self.clear_log()
        self.status_label.config(text="処理中...")
        self.execute_button.config(state=tk.DISABLED)

        # バックグラウンドスレッドで処理実行
        self._processing_thread = threading.Thread(target=self._execute_cleaning_thread, daemon=True)
        self._processing_thread.start()

    def _execute_cleaning_thread(self):
        """
        複数のShapefileを一括処理（スレッド実行）

        選択された全ての入力ファイルに対して以下の処理を実行します：
        1. ファイルの読み込み（ZIP展開対応）
        2. ジオメトリチェックと修正
        3. 座標系変換（EPSG）
        4. カラムマッピングの適用
        5. 出力ファイルの保存

        処理の進捗とエラーはログに出力されます。

        Note:
            - 各ファイルに設定されたマッピング定義とEPSG/エンコーディングが適用されます
            - エラーが発生したファイルはスキップされ、処理は継続されます
            - 全ファイル処理後に成功/失敗の集計が表示されます
        """
        try:
            
            total_files = len(self.input_files)
            success_count = 0
            error_files = []
            
            self.log("=" * 60)
            self.log(f"バッチ処理開始: {total_files} ファイル")
            self.log("=" * 60)
            
            for file_idx, input_file in enumerate(self.input_files, 1):
                self.log(f"\n[{file_idx}/{total_files}] 処理中: {os.path.basename(input_file)}")
                self.log("-" * 60)
                
                try:
                    # 単一ファイルの処理
                    result = self.process_single_file(input_file, file_idx)
                    if result:
                        success_count += 1
                    else:
                        error_files.append(os.path.basename(input_file))
                except Exception as e:
                    self.log(f"   エラー: {str(e)}", "ERROR")
                    error_files.append(os.path.basename(input_file))
                
            # 全体のサマリー
            self.log("\n" + "=" * 60)
            self.log("全体処理サマリー")
            self.log("=" * 60)
            self.log(f"処理ファイル数: {total_files}")
            self.log(f"成功: {success_count}")
            self.log(f"失敗: {len(error_files)}")
            if error_files:
                self.log(f"\n失敗したファイル:")
                for err_file in error_files:
                    self.log(f"  - {err_file}")
            self.log("=" * 60)

            # メインスレッドでUI更新
            def update_ui_on_success():
                self.status_label.config(text=f"完了: {success_count}/{total_files} ファイル処理成功")
                self.execute_button.config(state=tk.NORMAL)

                if error_files:
                    messagebox.showwarning("処理完了（一部エラー）",
                                          f"処理が完了しました。\n\n"
                                          f"成功: {success_count} ファイル\n"
                                          f"失敗: {len(error_files)} ファイル\n\n"
                                          f"詳細はログを確認してください。")
                else:
                    messagebox.showinfo("処理完了",
                                      f"すべてのファイルの処理が完了しました。\n\n"
                                      f"処理数: {total_files} ファイル")

            self.root.after(0, update_ui_on_success)

        except Exception as e:
            self.log(f"\nエラー: {str(e)}", "ERROR")

            # メインスレッドでUI更新
            def update_ui_on_error():
                self.status_label.config(text="エラー")
                self.execute_button.config(state=tk.NORMAL)
                messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{str(e)}")

            self.root.after(0, update_ui_on_error)
    
    def process_single_file(self, input_file, file_num):
        """
        単一Shapefileの変換処理
        
        以下の処理を順次実行します：
        1. ZIPファイルの場合は一時ディレクトリに展開
        2. Shapefileの読み込み（文字コード変換）
        3. 座標系変換（EPSG）
        4. ジオメトリの検証と修正
           - 無効なジオメトリのチェック
           - 短い辺のチェック
           - Polygon妥当性チェック
        5. カラムマッピングの適用（7種類の変換方式に対応）
        6. 出力ファイルの保存
        
        Args:
            input_file (str): 入力ファイルのパス（.shpまたは.zip）
            file_num (int): ファイル番号（ログ出力用）
        
        Returns:
            bool: 処理が成功した場合True、エラーが発生した場合False
        
        Note:
            - 処理中エラーが発生しても一時ファイルは自動的にクリーンアップされます
            - 5000件ごとに進捗ログが出力されます
        """
        temp_dir = None
        
        try:
            # このファイルに割り当てられたマッピング定義を取得
            mapping_name = self.file_mapping.get(input_file, "デフォルト")
            if mapping_name not in self.column_mappings:
                self.log(f"   警告: マッピング定義 '{mapping_name}' が見つかりません。デフォルトを使用します", "WARNING")
                mapping_name = "デフォルト"
            
            self.log(f"   適用するマッピング定義: {mapping_name}")
            column_mapping_definition = self.column_mappings[mapping_name]
            
            # マッピング定義のタイプを取得して対応する出力カラムを設定
            if mapping_name in self.column_mappings_meta:
                mapping_type = self.column_mappings_meta[mapping_name].get('type', '線設備')
            else:
                mapping_type = '線設備'
            output_columns = self.output_columns_templates[mapping_type]
            self.log(f"   設備タイプ: {mapping_type} ({len(output_columns)}カラム)")
            
            # ZIPファイルの場合は展開
            actual_shp_file = input_file
            if input_file.lower().endswith('.zip'):
                self.log("   ZIP展開中...")
                temp_dir = tempfile.mkdtemp()
                # UTF-8ファイル名対応でZIP展開
                self._extract_zip_with_utf8_fix(input_file, temp_dir)
                
                # .shpファイルを探す
                shp_found = False
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.lower().endswith('.shp'):
                            actual_shp_file = os.path.join(root, file)
                            shp_found = True
                            break
                    if shp_found:
                        break
                
                if not shp_found:
                    self.log("   エラー: ZIP内に.shpファイルが見つかりません", "ERROR")
                    return False
                
                self.log(f"   .shpファイル検出: {os.path.basename(actual_shp_file)}")

            # ファイル固有の設定を取得（なければデフォルト値を使用）
            file_settings = self.file_specific_settings.get(input_file, {})
            source_epsg = file_settings.get('source_epsg', '').strip() or self.source_epsg.get()
            source_encoding = file_settings.get('source_encoding', '').strip() or self.source_encoding.get()

            # 実際のファイル名を取得（カラムマッピングで使用）
            # ファイル選択時に保存された.shpファイル名を優先、なければ実際のパスから取得
            current_processing_filename = file_settings.get('shp_filename', '') or os.path.basename(actual_shp_file)

            self.log(f"   使用するEPSG: {source_epsg}")
            self.log(f"   使用する文字コード: {source_encoding}")
            
            # ① Shapeファイル読み込み
            self.log("   ① Shapeファイル読み込み中...")
            self.log(f"      ファイルパス: {actual_shp_file}")
            self.log(f"      文字コード: {source_encoding}")

            # ファイルサイズを取得
            try:
                file_size_bytes = os.path.getsize(actual_shp_file)
                file_size_mb = file_size_bytes / (1024 * 1024)
                self.log(f"      ファイルサイズ: {file_size_mb:.1f} MB")
            except:
                pass

            self.log(f"      データ読み込み中...")

            # 進捗モニター開始
            stop_event = threading.Event()
            monitor_thread = threading.Thread(
                target=self._progress_monitor,
                args=(stop_event, "読み込み中", 3),
                daemon=True
            )
            monitor_thread.start()

            try:
                # 選択された文字コードでShapefileを読み込み
                self.gdf = gpd.read_file(actual_shp_file, encoding=source_encoding)
            finally:
                # 進捗モニター停止
                stop_event.set()
                monitor_thread.join(timeout=1)

            self.log(f"      読み込み完了: {len(self.gdf)} レコード")
            self.log(f"      ジオメトリタイプ: {self.gdf.geometry.geom_type.unique()}")
            self.log(f"      座標系: {self.gdf.crs}")
            self.log(f"      元のカラム: {list(self.gdf.columns)}")
            
            original_count = len(self.gdf)
            to_remove = []
            
            # ② 無効なジオメトリのチェックと修正
            self.log("   ② 無効なジオメトリのチェックと修正...")
            fixed_count = 0
            geom_type_changed_count = 0
            geom_type_changed_details = []  # ジオメトリタイプ変換の詳細
            
            total_records = len(self.gdf)
            processed_count = 0
            log_interval = 5000  # 5000件ごとに進捗を表示
            
            for idx, row in self.gdf.iterrows():
                processed_count += 1
                
                # 進捗ログ
                if processed_count % log_interval == 0 or processed_count == total_records:
                    self.log(f"      進捗: {processed_count}/{total_records} 件処理中...")
                
                try:
                    original_geom_type = row.geometry.geom_type if row.geometry is not None else None
                    
                    # まず修正を試みる
                    fixed_geom = self.try_fix_geometry(row.geometry)
                    
                    if fixed_geom is not None:
                        # ジオメトリタイプが変わった場合は削除対象
                        if fixed_geom.geom_type != original_geom_type:
                            to_remove.append((idx, f"ジオメトリタイプ変換: {original_geom_type} → {fixed_geom.geom_type}"))
                            geom_type_changed_count += 1
                            geom_type_changed_details.append(f"Index {idx}: {original_geom_type} → {fixed_geom.geom_type}")
                        elif fixed_geom != row.geometry:
                            # タイプが同じで修正された場合
                            self.gdf.at[idx, 'geometry'] = fixed_geom
                            fixed_count += 1
                    else:
                        # 修正不可の場合は削除リストに追加
                        is_invalid, reason = self.check_invalid_geometry(row.geometry)
                        if is_invalid:
                            to_remove.append((idx, reason))
                except Exception as e:
                    # 処理中にエラーが発生したレコードは削除
                    to_remove.append((idx, f"処理エラー: {str(e)}"))
            
            if fixed_count > 0:
                self.log(f"      {fixed_count} 件のジオメトリを修正")
            
            # ジオメトリタイプ変換の警告
            if geom_type_changed_count > 0:
                self.log(f"      警告: {geom_type_changed_count} 件のジオメトリタイプが変換されました（削除対象）", "WARNING")
                for detail in geom_type_changed_details[:5]:  # 最大5件まで表示
                    self.log(f"        {detail}", "WARNING")
                if len(geom_type_changed_details) > 5:
                    self.log(f"        ...他 {len(geom_type_changed_details) - 5} 件", "WARNING")
            
            if to_remove:
                indices_to_remove = [idx for idx, _ in to_remove]
                self.gdf = self.gdf.drop(indices_to_remove)
                self.log(f"      {len(to_remove)} 件の無効なレコードを削除")
            
            if fixed_count == 0 and len(to_remove) == 0:
                self.log("      無効なジオメトリなし")
            
            # ③ 短い辺のチェック
            self.log("   ③ 短い辺のチェック...")
            min_dist = self.min_distance.get()
            to_remove = []
            
            total_records = len(self.gdf)
            processed_count = 0
            log_interval = 5000
            
            for idx, row in self.gdf.iterrows():
                processed_count += 1
                
                # 進捗ログ
                if processed_count % log_interval == 0 or processed_count == total_records:
                    self.log(f"      進捗: {processed_count}/{total_records} 件処理中...")
                
                has_short_edge, reason = self.check_short_edges(row.geometry, min_dist)
                if has_short_edge:
                    to_remove.append((idx, reason))
            
            if to_remove:
                indices_to_remove = [idx for idx, _ in to_remove]
                self.gdf = self.gdf.drop(indices_to_remove)
                self.log(f"      {len(to_remove)} 件の短辺レコードを削除")
            else:
                self.log("      短い辺なし")
            
            # ④ Polygon妥当性チェック
            self.log("   ④ Polygon妥当性チェック...")
            to_remove = []
            
            total_records = len(self.gdf)
            processed_count = 0
            log_interval = 5000
            
            for idx, row in self.gdf.iterrows():
                processed_count += 1
                
                # 進捗ログ
                if processed_count % log_interval == 0 or processed_count == total_records:
                    self.log(f"      進捗: {processed_count}/{total_records} 件処理中...")
                
                is_invalid, reason = self.check_polygon_validity(row.geometry)
                if is_invalid:
                    to_remove.append((idx, reason))
            
            if to_remove:
                indices_to_remove = [idx for idx, _ in to_remove]
                self.gdf = self.gdf.drop(indices_to_remove)
                self.log(f"      {len(to_remove)} 件の不正Polygonを削除")
            else:
                self.log("      不正なPolygonなし")
            
            # ⑤ MultiをSingleに展開
            self.log("   ⑤ MultiジオメトリをSingleに展開...")
            self.gdf = self.explode_multi_geometries(self.gdf)
            
            # ⑥ 測地系変換
            self.log("   ⑥ 測地系変換...")
            # ファイル固有のEPSG設定を使用（既にsource_epsg変数に設定済み）
            target_epsg = self.target_epsg.get()
            
            if source_epsg and target_epsg:
                if self.gdf.crs is not None:
                    current_epsg = self.gdf.crs.to_epsg()
                    self.log(f"      変換前CRS: EPSG:{current_epsg}")
                else:
                    self.gdf.set_crs(epsg=int(source_epsg), inplace=True)
                    self.log(f"      元座標系を設定: EPSG:{source_epsg}")

                self.log(f"      座標変換実行中: EPSG:{source_epsg} → EPSG:{target_epsg}")

                # 進捗モニター開始
                stop_event = threading.Event()
                monitor_thread = threading.Thread(
                    target=self._progress_monitor,
                    args=(stop_event, "座標変換中", 3),
                    daemon=True
                )
                monitor_thread.start()

                try:
                    self.gdf = self.gdf.to_crs(epsg=int(target_epsg))
                finally:
                    # 進捗モニター停止
                    stop_event.set()
                    monitor_thread.join(timeout=1)

                result_epsg = self.gdf.crs.to_epsg()
                self.log(f"      変換後CRS: EPSG:{result_epsg}")
                
                if result_epsg != int(target_epsg):
                    self.log(f"      警告: 目標EPSG({target_epsg})と結果EPSG({result_epsg})が異なります", "WARNING")
                else:
                    self.log(f"      座標系変換完了")
            else:
                self.log("      座標系変換はスキップ")
            
            # ⑦ カラムマッピング
            self.log("   ⑦ カラムマッピング...")
            new_data = {}
            
            # マッピング定義からデータを作成
            for out_col in output_columns:  # self.output_columnsではなくoutput_columnsを使用
                if out_col not in column_mapping_definition:
                    new_data[out_col] = None
                    self.log(f"      {out_col}: 未設定 → None", "DEBUG")
                    continue
                
                mapping_config = column_mapping_definition[out_col]
                map_type = mapping_config.get('type', 'None')
                
                if map_type == "カラム代入":
                    col_name = mapping_config.get('column', '').strip()
                    if col_name and col_name in self.gdf.columns:
                        new_data[out_col] = self.gdf[col_name].copy()
                        self.log(f"      {out_col}: カラム代入 '{col_name}' → 成功", "DEBUG")
                        
                        # 補完処理の適用
                        fallback = mapping_config.get('fallback', {})
                        if fallback:
                            mask = new_data[out_col].isna() | (new_data[out_col] == '') | (new_data[out_col] == 'None')
                            if mask.any():
                                fallback_type = fallback.get('type', '')
                                if fallback_type == "固定値":
                                    fallback_value = fallback.get('fixed_value', '')
                                    new_data[out_col] = new_data[out_col].fillna(fallback_value)
                                    new_data[out_col] = new_data[out_col].replace(['', 'None'], fallback_value)
                                elif fallback_type == "他カラム":
                                    fallback_col = fallback.get('column', '')
                                    if fallback_col in self.gdf.columns:
                                        new_data[out_col][mask] = self.gdf[fallback_col][mask]
                                elif fallback_type == "ファイル名":
                                    filename_mapping = fallback.get('filename_mapping', '')
                                    if filename_mapping:
                                        # ファイル名=出力値 形式をパース
                                        mapping_dict = {}
                                        for pair in filename_mapping.split(','):
                                            if '=' in pair:
                                                key, val = pair.split('=', 1)
                                                mapping_dict[key.strip()] = val.strip()
                                        
                                        # 現在のファイル名を取得（実行中のファイル）
                                        current_filename = current_processing_filename
                                        current_filename_noext = os.path.splitext(current_filename)[0]
                                        
                                        # ファイル名に一致する値を取得
                                        fallback_value = None
                                        if current_filename in mapping_dict:
                                            fallback_value = mapping_dict[current_filename]
                                        elif current_filename_noext in mapping_dict:
                                            fallback_value = mapping_dict[current_filename_noext]
                                        
                                        if fallback_value:
                                            new_data[out_col] = new_data[out_col].fillna(fallback_value)
                                            new_data[out_col] = new_data[out_col].replace(['', 'None'], fallback_value)
                    else:
                        new_data[out_col] = None
                        if col_name:
                            self.log(f"      {out_col}: カラム '{col_name}' が見つかりません → None", "WARNING")
                        else:
                            self.log(f"      {out_col}: カラム名未指定 → None", "WARNING")
                
                elif map_type == "カラム四則演算":
                    col_name = mapping_config.get('column', '').strip()
                    operator = mapping_config.get('operator', '').strip()
                    value_str = mapping_config.get('value', '').strip() if isinstance(mapping_config.get('value'), str) else str(mapping_config.get('value', ''))
                    
                    if col_name and col_name in self.gdf.columns and operator and value_str:
                        try:
                            value = float(value_str)
                            col_data = pd.to_numeric(self.gdf[col_name], errors='coerce')
                            
                            if operator == '+':
                                new_data[out_col] = col_data + value
                            elif operator == '-':
                                new_data[out_col] = col_data - value
                            elif operator == '*':
                                new_data[out_col] = col_data * value
                            elif operator == '/':
                                new_data[out_col] = col_data / value
                            self.log(f"      {out_col}: 四則演算 '{col_name}' {operator} {value} → 成功", "DEBUG")
                            
                            # 補完処理の適用
                            fallback = mapping_config.get('fallback', {})
                            if fallback:
                                mask = new_data[out_col].isna()
                                if mask.any():
                                    fallback_type = fallback.get('type', '')
                                    if fallback_type == "固定値":
                                        fallback_value = fallback.get('fixed_value', '')
                                        new_data[out_col] = new_data[out_col].fillna(fallback_value)
                                    elif fallback_type == "他カラム":
                                        fallback_col = fallback.get('column', '')
                                        if fallback_col in self.gdf.columns:
                                            new_data[out_col][mask] = self.gdf[fallback_col][mask]
                                    elif fallback_type == "ファイル名":
                                        filename_mapping = fallback.get('filename_mapping', '')
                                        if filename_mapping:
                                            # ファイル名=出力値 形式をパース
                                            mapping_dict = {}
                                            for pair in filename_mapping.split(','):
                                                if '=' in pair:
                                                    key, val = pair.split('=', 1)
                                                    mapping_dict[key.strip()] = val.strip()
                                            
                                            # 現在のファイル名を取得
                                            current_filename = self.sample_shp_filename if self.sample_shp_filename else ''
                                            current_filename_noext = os.path.splitext(current_filename)[0]
                                            
                                            # ファイル名に一致する値を取得
                                            fallback_value = None
                                            if current_filename in mapping_dict:
                                                fallback_value = mapping_dict[current_filename]
                                            elif current_filename_noext in mapping_dict:
                                                fallback_value = mapping_dict[current_filename_noext]
                                            
                                            if fallback_value:
                                                new_data[out_col] = new_data[out_col].fillna(fallback_value)
                        except Exception as e:
                            new_data[out_col] = None
                            self.log(f"      {out_col}: 四則演算エラー → None ({str(e)})", "WARNING")
                    else:
                        new_data[out_col] = None
                
                elif map_type == "複数カラム四則演算":
                    col1_name = mapping_config.get('column1', '').strip()
                    operator = mapping_config.get('operator', '').strip()
                    col2_name = mapping_config.get('column2', '').strip()
                    
                    if (col1_name and col1_name in self.gdf.columns and 
                        col2_name and col2_name in self.gdf.columns and operator):
                        try:
                            col1_data = pd.to_numeric(self.gdf[col1_name], errors='coerce')
                            col2_data = pd.to_numeric(self.gdf[col2_name], errors='coerce')
                            
                            if operator == '+':
                                new_data[out_col] = col1_data + col2_data
                            elif operator == '-':
                                new_data[out_col] = col1_data - col2_data
                            elif operator == '*':
                                new_data[out_col] = col1_data * col2_data
                            elif operator == '/':
                                new_data[out_col] = col1_data / col2_data
                            self.log(f"      {out_col}: 複数カラム演算 '{col1_name}' {operator} '{col2_name}' → 成功", "DEBUG")
                            
                            # 補完処理の適用
                            fallback = mapping_config.get('fallback', {})
                            if fallback:
                                mask = new_data[out_col].isna()
                                if mask.any():
                                    fallback_type = fallback.get('type', '')
                                    if fallback_type == "固定値":
                                        fallback_value = fallback.get('fixed_value', '')
                                        new_data[out_col] = new_data[out_col].fillna(fallback_value)
                                    elif fallback_type == "他カラム":
                                        fallback_col = fallback.get('column', '')
                                        if fallback_col in self.gdf.columns:
                                            new_data[out_col][mask] = self.gdf[fallback_col][mask]
                                    elif fallback_type == "ファイル名":
                                        filename_mapping = fallback.get('filename_mapping', '')
                                        if filename_mapping:
                                            # ファイル名=出力値 形式をパース
                                            mapping_dict = {}
                                            for pair in filename_mapping.split(','):
                                                if '=' in pair:
                                                    key, val = pair.split('=', 1)
                                                    mapping_dict[key.strip()] = val.strip()
                                            
                                            # 現在のファイル名を取得
                                            current_filename = self.sample_shp_filename if self.sample_shp_filename else ''
                                            current_filename_noext = os.path.splitext(current_filename)[0]
                                            
                                            # ファイル名に一致する値を取得
                                            fallback_value = None
                                            if current_filename in mapping_dict:
                                                fallback_value = mapping_dict[current_filename]
                                            elif current_filename_noext in mapping_dict:
                                                fallback_value = mapping_dict[current_filename_noext]
                                            
                                            if fallback_value:
                                                new_data[out_col] = new_data[out_col].fillna(fallback_value)
                        except Exception as e:
                            new_data[out_col] = None
                            self.log(f"      {out_col}: 複数カラム演算エラー → None ({str(e)})", "WARNING")
                    else:
                        new_data[out_col] = None
                
                elif map_type == "複数カラム抽出":
                    mode = mapping_config.get('mode', '').strip()
                    columns = mapping_config.get('columns', [])
                    
                    # 空でないカラム名で、"None"以外のものをフィルタ
                    valid_columns = [col.strip() for col in columns if col and col.strip() and col.strip() != "None"]
                    
                    # 有効なカラムが存在するか確認
                    existing_columns = [col for col in valid_columns if col in self.gdf.columns]
                    
                    if existing_columns and mode in ["最大値", "最小値"]:
                        try:
                            # 数値に変換
                            col_data_list = [pd.to_numeric(self.gdf[col], errors='coerce') 
                                           for col in existing_columns]
                            
                            # DataFrameに統合
                            combined_df = pd.concat(col_data_list, axis=1)
                            
                            if mode == "最大値":
                                new_data[out_col] = combined_df.max(axis=1)
                            else:  # 最小値
                                new_data[out_col] = combined_df.min(axis=1)
                            
                            self.log(f"      {out_col}: 複数カラム抽出 {mode} {existing_columns} → 成功", "DEBUG")
                            
                            # 補完処理の適用
                            fallback = mapping_config.get('fallback', {})
                            if fallback:
                                mask = new_data[out_col].isna()
                                if mask.any():
                                    fallback_type = fallback.get('type', '')
                                    if fallback_type == "固定値":
                                        fallback_value = fallback.get('fixed_value', '')
                                        new_data[out_col] = new_data[out_col].fillna(fallback_value)
                                    elif fallback_type == "他カラム":
                                        fallback_col = fallback.get('column', '')
                                        if fallback_col in self.gdf.columns:
                                            new_data[out_col][mask] = self.gdf[fallback_col][mask]
                                    elif fallback_type == "ファイル名":
                                        filename_mapping = fallback.get('filename_mapping', '')
                                        if filename_mapping:
                                            # ファイル名=出力値 形式をパース
                                            mapping_dict = {}
                                            for pair in filename_mapping.split(','):
                                                if '=' in pair:
                                                    key, val = pair.split('=', 1)
                                                    mapping_dict[key.strip()] = val.strip()
                                            
                                            # 現在のファイル名を取得
                                            current_filename = self.sample_shp_filename if self.sample_shp_filename else ''
                                            current_filename_noext = os.path.splitext(current_filename)[0]
                                            
                                            # ファイル名に一致する値を取得
                                            fallback_value = None
                                            if current_filename in mapping_dict:
                                                fallback_value = mapping_dict[current_filename]
                                            elif current_filename_noext in mapping_dict:
                                                fallback_value = mapping_dict[current_filename_noext]
                                            
                                            if fallback_value:
                                                new_data[out_col] = new_data[out_col].fillna(fallback_value)
                        except Exception as e:
                            new_data[out_col] = None
                            self.log(f"      {out_col}: 複数カラム抽出エラー → None ({str(e)})", "WARNING")
                    else:
                        new_data[out_col] = None
                        if not mode:
                            self.log(f"      {out_col}: 抽出モード未指定 → None", "WARNING")
                        elif not existing_columns:
                            self.log(f"      {out_col}: 有効なカラムが見つかりません → None", "WARNING")
                
                elif map_type == "固定値":
                    value = mapping_config.get('value', '').strip() if isinstance(mapping_config.get('value'), str) else str(mapping_config.get('value', ''))
                    new_data[out_col] = value if value else None
                    self.log(f"      {out_col}: 固定値 '{value}' → 設定", "DEBUG")
                
                elif map_type == "ファイル名":
                    # 実行中のファイル名を使用（.shp拡張子付き）
                    # ZIPの場合でも展開後の.shpファイル名が取得される
                    value = current_processing_filename
                    new_data[out_col] = value if value else None
                    self.log(f"      {out_col}: ファイル名 '{value}' → 設定", "DEBUG")
                
                elif map_type == "ランダム値":
                    min_str = str(mapping_config.get('min', '')).strip()
                    max_str = str(mapping_config.get('max', '')).strip()
                    
                    if min_str and max_str:
                        try:
                            min_val = float(min_str)
                            max_val = float(max_str)
                            random_values = [random.uniform(min_val, max_val) for _ in range(len(self.gdf))]
                            new_data[out_col] = random_values
                            self.log(f"      {out_col}: ランダム値 [{min_val}, {max_val}] → 生成", "DEBUG")
                        except Exception as e:
                            new_data[out_col] = None
                            self.log(f"      {out_col}: ランダム値エラー → None ({str(e)})", "WARNING")
                    else:
                        new_data[out_col] = None
                
                elif map_type == "シーケンス値":
                    start_str = str(mapping_config.get('start', '1')).strip()
                    step_str = str(mapping_config.get('step', '1')).strip()
                    
                    if start_str and step_str:
                        try:
                            start_val = int(start_str)
                            step_val = int(step_str)
                            seq_values = [start_val + (i * step_val) for i in range(len(self.gdf))]
                            new_data[out_col] = seq_values
                            self.log(f"      {out_col}: シーケンス値 開始={start_val} ステップ={step_val} → 生成", "DEBUG")
                        except Exception as e:
                            new_data[out_col] = None
                            self.log(f"      {out_col}: シーケンス値エラー → None ({str(e)})", "WARNING")
                    else:
                        new_data[out_col] = None
                
                elif map_type == "条件分岐":
                    col_name = mapping_config.get('column', '').strip()
                    conditions = mapping_config.get('conditions', [])
                    default_value = mapping_config.get('default', '')
                    
                    if col_name and col_name in self.gdf.columns and conditions:
                        try:
                            # 条件マッピング辞書を作成
                            condition_map = {cond['input']: cond['output'] for cond in conditions}
                            
                            # データを変換（文字列として比較）
                            def apply_condition(value):
                                value_str = str(value) if value is not None else ''
                                return condition_map.get(value_str, default_value if default_value else value)
                            
                            new_data[out_col] = self.gdf[col_name].apply(apply_condition)
                            self.log(f"      {out_col}: 条件分岐 '{col_name}' ({len(conditions)}件の条件) → 成功", "DEBUG")
                        except Exception as e:
                            new_data[out_col] = None
                            self.log(f"      {out_col}: 条件分岐エラー → None ({str(e)})", "WARNING")
                    else:
                        new_data[out_col] = None
                        if not col_name:
                            self.log(f"      {out_col}: カラム名未指定 → None", "WARNING")
                        elif col_name not in self.gdf.columns:
                            self.log(f"      {out_col}: カラム '{col_name}' が見つかりません → None", "WARNING")
                        elif not conditions:
                            self.log(f"      {out_col}: 条件が設定されていません → None", "WARNING")

                elif map_type == "ファイル名分岐":
                    conditions = mapping_config.get('conditions', [])
                    default_value = mapping_config.get('default', '')

                    if conditions:
                        try:
                            # 現在のファイル名を取得（実行中のファイル）
                            current_filename = current_processing_filename
                            # 拡張子なしのファイル名も取得
                            current_filename_noext = os.path.splitext(current_filename)[0]

                            # 条件マッピング辞書を作成
                            condition_map = {cond['filename']: cond['output'] for cond in conditions}

                            # ファイル名に一致する値を取得（拡張子あり→拡張子なしの順で試す）
                            if current_filename in condition_map:
                                output_value = condition_map[current_filename]
                            elif current_filename_noext in condition_map:
                                output_value = condition_map[current_filename_noext]
                            else:
                                output_value = default_value

                            new_data[out_col] = output_value if output_value else None
                            self.log(f"      {out_col}: ファイル名分岐 '{current_filename}' → '{output_value}'", "DEBUG")
                        except Exception as e:
                            new_data[out_col] = None
                            self.log(f"      {out_col}: ファイル名分岐エラー → None ({str(e)})", "WARNING")
                    else:
                        new_data[out_col] = None
                        self.log(f"      {out_col}: 条件が設定されていません → None", "WARNING")

                else:  # None
                    new_data[out_col] = None
                    self.log(f"      {out_col}: タイプ=None → None", "DEBUG")
            
            new_data['geometry'] = self.gdf['geometry']

            # 和名カラム→英名カラムに変換（Shapefile出力用）
            new_data_english = {}
            for jp_col_name, value in new_data.items():
                if jp_col_name == 'geometry':
                    new_data_english['geometry'] = value
                elif jp_col_name in self.column_name_mapping:
                    eng_col_name = self.column_name_mapping[jp_col_name]
                    new_data_english[eng_col_name] = value
                else:
                    # マッピングにない場合はそのまま使用
                    new_data_english[jp_col_name] = value

            self.gdf = gpd.GeoDataFrame(new_data_english, geometry='geometry', crs=self.gdf.crs)
            self.log(f"      カラムマッピング完了: {len(output_columns)} カラム")
            
            # ⑧ 出力
            self.log("   ⑧ Shapeファイル出力中...")

            # 出力ファイル名を生成
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_file = os.path.join(self.output_dir, f"{base_name}_cleaned.shp")

            output_record_count = len(self.gdf)
            self.log(f"      出力レコード数: {output_record_count}件")
            self.log(f"      ファイル書き込み中...")

            # 進捗モニター開始
            stop_event = threading.Event()
            monitor_thread = threading.Thread(
                target=self._progress_monitor,
                args=(stop_event, "書き込み中", 3),
                daemon=True
            )
            monitor_thread.start()

            try:
                self.gdf.to_file(output_file, encoding='utf-8')
            finally:
                # 進捗モニター停止
                stop_event.set()
                monitor_thread.join(timeout=1)

            self.log(f"      出力完了: {output_file}")
            self.log(f"      入力レコード: {original_count}, 出力レコード: {output_record_count}, 削除: {original_count - output_record_count}")
            
            return True
            
        except Exception as e:
            self.log(f"   処理エラー: {str(e)}", "ERROR")
            return False
        
        finally:
            # 一時ディレクトリをクリーンアップ
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """
    アプリケーションのエントリーポイント
    
    Tkinterルートウィンドウを作成し、ShapefileCleanerAppを初期化して
    メインイベントループを開始します。
    """
    root = tk.Tk()
    app = ShapefileNormalizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    # スクリプトが直接実行された場合のみmain関数を呼び出す
    # モジュールとしてインポートされた場合は実行されません
    main()
