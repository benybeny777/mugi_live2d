# むぎ VRM Aプラン 品質レポート

検証日: 2026-08-14 JST

## 現在の採用版

Photoshopで高解像度化した同一Tポーズ原画から、腕、肩下地、顔の可動パーツを再分割しました。
肩は約60度下げた状態で穴、白縁、二重輪郭がないことを実機確認し、正式版へ採用しました。
自動モーションを無効にした中立状態でも元絵どおりの目を維持し、まばたき、視線、口、感情表現を確認しています。
追加の実機確認で、白目・虹彩を潰さずまつ毛だけを閉じるまばたき、縮小した口パク、胴体固定の連続したスカート裾、白背景マット除去、約70度の下向き腕へ調整しました。

Live2D版とPicoAgent実装は検査・変更対象外です。

| 項目 | 結果 |
|---|---:|
| VRM形式 | VRM 1.0 / GLB |
| メッシュ | 17 |
| 頂点 | 347 |
| 顔格子メッシュ | 8 |
| 標準 / カスタムExpression | 17 / 4 |
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
`validate_vrm_visual`は最新版GIFの解像度、フレーム数、目視可能な動き、足元の固定を検査します。
