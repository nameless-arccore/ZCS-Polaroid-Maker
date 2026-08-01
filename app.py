ZCS Polaroid Maker v2.14
========================

説明:
画像をポラロイド風に。

【今回の原因】

専用Python 3.11.9のインストール自体は正常に完了していました。

失敗したのは、その直後にPythonのバージョンと実行場所を確認する
「Python probe」です。

v2.13は、PowerShellから次の形式で複数行Pythonコードを渡していました。

python.exe -c <複数行コード>

Windows PowerShell 5.1は、native commandへ引数を渡す際に
コード中の二重引用符を変形または削除することがあります。

その結果、本来Pythonへ渡す予定だった次のコードが、

+ "."

実際には次のように変形されました。

+ .

このため専用Python本体は正常でも、確認コードがSyntaxErrorになり、
「private Python runtime exists but cannot start」と誤判定されていました。

【v2.14の対応】

・Python確認処理から「python.exe -c」を廃止
・確認コードを一時的な.pyファイルへ保存して実行
・確認後は一時ファイルを自動削除
・PillowとTkinterの確認処理も同じ方式へ変更
・verify_release.ps1へ再発検査を追加
・専用Pythonランタイム方式は維持
・登録済みのシステムPythonは変更しない

【重要】

次の内容から、専用Pythonの導入は成功しています。

Private Python installer exit code: 0
python.exe / exists=True
python311.dll / exists=True
Lib / exists=True
DLLs / exists=True
tcl / exists=True

v2.14では既に導入済みの専用Pythonを再利用するため、
通常はPythonをもう一度ダウンロードする必要はありません。

【適用方法】

安全のため、v2.14一式を新しいフォルダへ展開して実行してください。

cd C:\ZCS\ZCS_Polaroid_Maker_v2.14
.\start_windows.bat

v2.13フォルダへ上書きする場合は、最低限次を置き換えます。

setup_windows.ps1
verify_release.ps1

【事前検査】

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\verify_release.ps1

すべてOKになった後、start_windows.batを実行してください。
