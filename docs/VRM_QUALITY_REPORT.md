# むぎ VRM Aプラン 品質レポート

検証日: 2026-08-13 JST

## 高解像度更新

| 項目 | 結果 |
|---|---:|
| Photoshop PSD | 5952×8350 / 53レイヤー |
| VRMテクスチャ上限 | 8192 |
| VRM容量 | 約9.98 MB |
| メッシュ / 頂点 | 18 / 459 |
| Expression | 標準17 / カスタム4 |
| Spring Bone | 3チェーン / 5可動ジョイント |
| Khronos Validator | error 0 / warning 0 |

同一条件のPNG比較で背景・構図・色を維持し、顔、髪、服の線がわずかに明瞭になった。GIFに見えた背景帯はパレット量子化によるもので、PNGとVRM素材には存在しない。

## 現在の採用版

追加の腕分割・眉分割・強い表情変形を試しましたが、元絵の自然さが低下したため採用しませんでした。
VRM本体、ランタイム動作、READMEプレビューは `7f575bc` 時点の安定版へ戻しています。
READMEには最新版のGIF/MP4だけを掲載します。

Live2D版とPicoAgent実装は検査・変更対象外です。

| 項目 | 結果 |
|---|---:|
| VRM形式 | VRM 1.0 / GLB |
| メッシュ | 18 |
| 頂点 | 459 |
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
