v2.14
- 専用Python確認コードがWindows PowerShell 5.1で変形される問題を修正
- Python確認処理からpython.exe -cを廃止
- バージョン確認を一時.pyファイル実行方式へ変更
- Pillow／Tkinter確認も一時.pyファイル実行方式へ変更
- 確認用一時ファイルの自動削除を追加
- verify_release.ps1へpython -c再混入検査を追加
- 専用PythonランタイムとシステムPython非変更方針を維持

v2.13
- Windows PowerShell 5.1でsetup_windows.ps1が解析できない問題を修正
- 行頭に置かれた文字列連結演算子を全件撤去
- 文字列組み立てを-f演算子へ変更
- start_windows.batへPowerShellネイティブパーサーによる事前検査を追加
- verify_release.ps1を追加
- 専用Pythonランタイム方式とシステムPython非変更方針を維持

v2.12
- 壊れた既存Python 3.12へ依存しない構成へ変更
- ZCS専用の隔離Python 3.11.9自動導入を追加
- 専用Pythonを%LOCALAPPDATA%\ZCS配下へ設置
- PATH、Launcher、関連付け、既存Pythonを変更しない構成
- Python実行失敗時の終了コードとエラー出力をログ化
- private_python_installer.logを追加
- 診断スクリプトへ専用ランタイム検査を追加
- WinGetと既存Python修復への依存を廃止

v2.11
- Pythonインストール済みだが検出できない問題を修正
- PEP 514準拠で全Company／Tagのレジストリを列挙
- App Paths、アンインストール情報、標準外フォルダを検出対象へ追加
- Python Launcherの既知設置先を追加
- インストール後にPATHを再読込
- WinGet既存パッケージへwinget repairを実行
- Python公式インストーラーの/repairフォールバックを追加
- python_installer.logとpython_installer_repair.logを追加
- 診断スクリプトのPEP 514表示を強化

v2.10
- setup_windows.ps1のPowerShell解析エラーを修正
- $wingetHex: を書式演算子による安全な文字列生成へ変更
- 変数直後のコロンを全スクリプトから静的検査
- Python自動インストール、公式フォールバック、ログ機能は維持

v2.9
- WinGet失敗時に成功扱いされるPowerShell戻り値混入を修正
- 0x8A15002B発生時にpython.org公式インストーラーへ確実に切替
- Python検出へレジストリとwhere.exeを追加
- Python公式版の設置先を明示
- start_windows.batの空欄終了コードを修正
- setup_windows.logを追加
- diagnose_windows.ps1を強化

v2.8
- 起動スクリプトへPython 3.12の自動インストールを統合
- WinGetによるユーザー単位の無人インストールに対応
- WinGet失敗時のpython.org公式インストーラーフォールバックを追加
- Python公式インストーラーのAuthenticode署名検証を追加
- AMD64／ARM64の公式インストーラーを自動選択
- Python導入後に自動再検出し、.venv作成と依存導入を継続
- start_windows.batの案内と終了コードを改善

v2.7
- setup_windows.ps1のpyランチャー必須問題を修正
- Python 3.11／3.12を複数経路から自動検出
- Microsoft StoreのWindowsApps実行エイリアスを除外
- 壊れた・別PC由来の.venvを自動再作成
- start_windows.batのエラー処理を改善
- EXE／ポータブル／インストーラー作成処理を改善
- diagnose_windows.ps1を追加
- セットアップ表示の古い2.0表記を修正

v2.6
- 複数画像の外周保護の初期値を標準へ変更
- v2.5の「なし」既定値を一度だけ標準へ移行
- 旧プロジェクトの不足値と不明値も標準へ統一

v2.5
- 画像編集画面の状態テキストを削除
- プレビュー下部の操作説明を削除
- 複数画像の外周保護の初期値を「なし」へ変更
- 旧版の標準初期値を一度だけ「なし」へ移行
- プロジェクト保存の重複キーを整理

v2.4
- 複数画像印刷時の上下見切れ対策を追加
- 複数画像の外周保護プリセットを追加
- 画像間の隙間0を維持したまま集合全体を安全領域へ縮小
- プリンター補正とは加算せず大きい補正値を採用
- プレビュー・保存・印刷診断へ外周保護を反映
- 0mm補正が1pxになる境界条件を修正

v2.3
- 複数選択プレビューとページ変換結果が一致しない不具合を修正
- 現在ページ変換で選択画像・自動レイアウト・隙間0を反映
- 全ページ変換で選択画像を最大4枚ずつページ分割
- 変換開始時の設定スナップショット化で処理中の選択変更を遮断

v2.2
- 写真一覧の複数選択プレビューと直接編集に対応
- 複数画像プレビュー時の隙間を0に変更
- 複数選択中も個別画像をクリックして編集可能

ZCS Polaroid Maker Change Log

v2.1
- 位置設定と写真加工を別セクションへ分離
- 横位置・縦位置インジケーターを追加
- 位置／加工／両方のデフォルト復元ボタンを追加
- ケラレ量・範囲・ぼかしを追加
- ケラレ視覚インジケーターを追加
- 旧プロジェクト読込互換性を改善

v2.0
- Print Studio機能一式
