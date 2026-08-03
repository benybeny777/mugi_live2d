# むぎ Live2D HTML動作確認ツール

このPC専用のHTML/WebGLビューアです。画像・モデルを外部へ送信せず、`127.0.0.1` だけで配信します。

## 初回セットアップ

PowerShellで次を1回実行します。

```powershell
& 'C:\00_PG\40_mugi_live2d\viewer\setup-runtime.ps1'
```

Live2D Cubism Core、PixiJS、pixi-live2d-displayを、このPCのPicoAgentから `viewer\vendor` へコピーします。Live2Dランタイムはライセンス上Gitへ追加しません。

## 起動

`launch-viewer.vbs` をダブルクリックします。コマンドプロンプトは表示されません。

既定のモデル位置は次の通りです。

- SDK 5: `exports\sdk5\mugi\mugi.model3.json`
- SDK 4: `exports\sdk4\mugi\mugi.model3.json`

モデル読込、上半身表示、視線追従、まばたき、口の開閉、髪揺れ、倍率・上下位置を確認できます。診断欄に読込エラーとモデル情報を表示します。

SDKモデル未出力の中間チェックポイントでは、HTML画面自体は起動できますがモデル読込は失敗表示になります。`exports`へSDKモデルを書き出した後に実モデル確認を行います。

## 終了

ブラウザを閉じてもローカルサーバーは残ります。タスクマネージャーで、このファイルを実行している `pythonw.exe` を終了してください。PC再起動でも終了します。
