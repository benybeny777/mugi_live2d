# むぎ VRM Aプラン 品質レポート

検証日: 2026-08-06 JST

## リリース判定

Phase 6の品質ゲートに合格しています。Live2D版とPicoAgent実装は検査・変更対象外です。

| 項目 | 結果 |
|---|---:|
| VRM形式 | VRM 1.0 / GLB |
| メッシュ | 18 |
| 頂点 | 459 |
| 顔格子メッシュ | 8 |
| 標準 / カスタムExpression | 17 / 3 |
| Spring Bone | 3チェーン / 5可動ジョイント |
| モーション状態 | idle / greet / talk |
| READMEフェーズ動画 | Phase 1〜6 |
| 内部VRM検証 | 合格 |
| Khronos glTF Validator | エラー0 / 警告0 |

## 自動検証

リポジトリルートで次を実行します。

```powershell
uv run python -m scripts.validate_vrm_release
uv run pytest -q
uv run ruff check .
node --check vrm-viewer/viewer.js
```

`validate_vrm_release`はVRM本体だけでなく、READMEからPhase 1〜6のGIF/MP4を開けること、
GIFの表示解像度、MP4コンテナ、タイムラインの状態順も検査します。

## 目視確認

- three-vrm 3.5.3で実VRMを読み込み、20 Expressionと5 Spring Jointの初期化を確認。
- 自然なまばたき、5母音、感情、idle/greet/talk、髪と星アクセサリーの遅れ揺れを確認。
- 足元は固定され、旧プレビューにあった全身の横滑り・周期的な不自然な揺れはありません。
- README動画は横並びを使わず、前段階から現段階を全画面で順番再生します。
