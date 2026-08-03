# 制作状況

最終更新: 2026-08-03 14:25 JST

## 保存・出力済み

- Hiyori方式のレイヤー分割PSD: `work/psd/hiyori/mugi-hiyori-compatible-final.psd`
- まばたき・口パク・髪揺れ設定済みCubismモデル: `work/cubism/mugi-hiyori-rigged-final.cmo3`
- SDK 5出力: `exports/sdk5/mugi/`
- SDK 4出力: `exports/sdk4/mugi/`
- HTML動作確認ツール: `viewer/`
- 透明画素のRGBノイズ除去: `scripts/sanitize_export_textures.py` を両SDK出力へ適用済み

## 再起動後の再開位置

1. Cubismでは古いウィンドウを閉じてから `work/cubism/mugi-hiyori-rigged-final.cmo3` を1つだけ開く。
2. HTML viewerで見える髪飾り付近の白い四角・斜線を、該当ArtMeshのメッシュ形状としてCubism上で修正する。
3. SDK 5 / SDK 4を再出力し、透明画素サニタイズ後にHTML viewerで上半身表示、視線、まばたき、口パク、髪揺れを確認する。
4. PicoAgentの `characters/mugi/live2d/` へ両SDKをコピーし、character pack検証と実表示確認を行う。
5. 文書・テストを更新し、最終commit/pushする。

## 注意

- See-through生成は正常終了済み。再実行しない。
- 画面障害時点でCubismモデルは保存済み。GPU温度は65〜67℃で熱スロットリングなし。
- `tools/see-through` サブモジュールの作業ツリーは既存の変更を含むため、無関係にstageしない。
- `work/psd/` の失敗版・バックアップ・QA画像は中間生成物としてstageしない。

## 未完了

- 髪飾り付近のArtMesh表示不良修正
- PicoAgentへの最新SDK 5/4モデル組み込みと実動確認
- 全サンプルキャラクターテンプレートの利用可能化確認
- 最終テスト、文書更新、Git push
