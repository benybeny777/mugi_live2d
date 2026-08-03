# 制作状況

最終更新: 2026-08-03 18:15 JST

## 今回のチェックポイント

- Cubism編集モデル: `work/cubism/mugi-hiyori-rigged-final.cmo3`
- Hiyori互換レイヤーPSD: `work/psd/hiyori/mugi-hiyori-compatible-final.psd`
- SDK 5.3出力: `exports/sdk5/mugi/`
- SDK 4.2互換出力: `exports/sdk4/mugi/`
- HTML動作確認ツール: `viewer/`
- 全ArtMeshを「変形度合い（大）」で輪郭に沿うメッシュへ再生成済み
- 上半身表示、目の開閉、SDK 5読込をHTMLで確認済み
- Cubism起動時とHTML viewer起動時にコマンドプロンプトを表示しない構成

## 既知の残課題

- HTMLの縮小表示で、左横髪と毛先の境界に細い背景色の線が見える。
- 原因は隣接髪レイヤーが同一境界で接していること。全体膨張は輪郭を荒らすため使用しない。
- `scripts/build_hiyori_psd.py` は後髪へ各髪パーツの内周5pxを重ねる局所下地を生成する。修正版PSDは生成済みだが、Cubismへの再インポートと最終比較は次回工程。
- PicoAgentへの最新SDK 5/4モデル反映、character-pack検証、UI資産同期は完了。実アプリでの最終目視確認は未完了。

## 再開位置

1. Cubismを1つだけ起動し、`mugi-hiyori-rigged-final.cmo3` を開く。
2. `mugi-hiyori-compatible-final.psd` を既存モデルへ「追加・差し替え」で再インポートする。
3. SDK 5.3とSDK 4.2を再出力し、HTML viewerで髪境界、まばたき、口パク、髪揺れを比較する。
4. PicoAgent実アプリでSDK 5優先読込、SDK 4フォールバック、まばたき、口パクを最終目視確認する。
5. 手順と状況を更新して最終commit/pushする。

## 注意

- See-through生成は正常終了済み。再実行しない。
- `tools/see-through` の作業ツリーは既存変更を含むため、このリポジトリのcommitへ含めない。
- `work/qa/`、失敗PSD、バックアップPSD、生成途中レイヤーはGitへ追加しない。
