# むぎ Live2D HTML動作確認ツール

このPC専用のローカルHTML/WebGL viewerです。画像やモデルを外部へ送信せず、`127.0.0.1` だけで配信します。

## 初回セットアップ

PowerShellで次を1回実行します。

```powershell
& 'C:\00_PG\40_mugi_live2d\viewer\setup-runtime.ps1'
```

Live2D Cubism Core、PixiJS、pixi-live2d-displayを、このPCのPicoAgentから `viewer\vendor` へコピーします。Live2Dランタイムはライセンス上Gitへ追加しません。

## 起動

`launch-viewer.vbs` をダブルクリックします。`pythonw.exe`で起動するため、コマンドプロンプトは表示されません。

- SDK 5: `exports\sdk5\mugi\mugi.model3.json`
- SDK 4: `exports\sdk4\mugi\mugi.model3.json`
- URL: `http://127.0.0.1:8765/viewer/index.html`

SDK切替、上半身表示、視線追従、自動・手動まばたき、口の開き、髪揺れ、倍率、上下位置を確認できます。読込失敗時は画面の診断欄とブラウザコンソールを確認してください。

## 終了

ブラウザを閉じてもローカルサーバーは残ります。タスクマネージャーで、このファイルを実行している `pythonw.exe` を終了してください。PC再起動でも終了します。
