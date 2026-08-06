# むぎ VRM Aプラン 品質レポート

検証日: 2026-08-06 JST

## 最新版の改善内容

- 左右の腕を上腕・前腕・手へ3分割し、肩・肘・手首を連鎖変形
- 眉を独立メッシュ化し、happy / angry / sad / relaxed / surprised を描き分け
- 目尻の笑い線と sleepy 表情を追加
- 5母音を滑らかに補間し、ローカル音声ファイルの周波数帯から口形を推定
- 後髪・顔・前髪・星アクセサリーへ微小な奥行き視差を追加
- greet の腕振りを強めつつ、足元は固定
- READMEプレビューを最新版のGIF/MP4だけに整理

Live2D版とPicoAgent実装は検査・変更対象外です。

| 項目 | 結果 |
|---|---:|
| VRM形式 | VRM 1.0 / GLB |
| メッシュ | 26 |
| 頂点 | 543 |
| 顔格子メッシュ | 12 |
| 標準 / カスタムExpression | 17 / 5 |
| 腕分割 | 左右各3、合計6 |
| Spring Bone | 3チェーン / 5可動ジョイント |
| モーション状態 | idle / greet / talk |
| README動画 | 最新GIF / MP4のみ |

## 自動検証

```powershell
uv run python -m scripts.validate_vrm_release
uv run python -m scripts.validate_vrm_visual
uv run pytest -q
uv run ruff check .
node --check vrm-viewer/viewer.js
```

`validate_vrm_release`はVRM構造、Expression、Spring Bone、容量、READMEの最新版リンクを検査します。
`validate_vrm_visual`は最新版GIFの解像度、フレーム数、目視可能な動き、足元の固定、腕6分割、眉2分割を検査します。

## 目視確認

- three-vrm 3.5.3で22 Expressionと5 Spring Jointを初期化
- happy / angry / surprised / sleepy の表情と眉・まぶたの連動を確認
- greetで肩・肘・手首の継ぎ目が開かないことを確認
- 足元を固定したまま、呼吸・視線・まばたき・口形・髪の遅れを確認
