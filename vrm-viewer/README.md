# むぎ VRM 実機プレビュー

`exports/vrm/mugi.vrm` をthree.jsとthree-vrmで直接読み込む、ローカル専用WebGLビューアです。
既存のLive2D viewerは変更しません。

## セットアップ

```powershell
& .\vrm-viewer\setup-runtime.ps1
```

three.js `0.180.0` と `@pixiv/three-vrm` `3.5.3` を、Git管理外の
`vrm-viewer/vendor/`へインストールします。外部CDNは使いません。

## 起動

既存のローカルサーバーを使います。

```powershell
uv run python viewer/server.py
```

ブラウザで `http://127.0.0.1:8765/vrm-viewer/index.html` を開きます。

- 実際のVRM Expressionを操作
- 自動呼吸、視線、左右差のある自然なまばたき
- 5母音の滑らかな自動口パクと感情デモ、手動の感情切替
- ローカル音声ファイルの周波数帯から母音を推定する口パク
- 独立した眉・まぶた・笑い線による表情と `sleepy`
- 上腕・前腕・手の3分割による肩・肘・手首の連鎖変形
- 髪・顔・アクセサリーの微小な奥行き視差
- 後髪・前髪・星アクセサリーのSpring Boneをthree-vrmで直接計算
- `motions/mugi-timeline.json`のidle・greet・talkを滑らかに循環
- Canvasから5秒WebMを直接録画

動画はブラウザ内で生成され、外部へ送信されません。
