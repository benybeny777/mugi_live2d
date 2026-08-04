# 制作状況

最終更新: 2026-08-04 JST

## A方式（固定トポロジー）の進捗

- 固定契約: `pipeline/topology.mugi-hiyori-v2.json`
- 計測・校正・正規化CLI: `python -m pipeline.fixedtopo`
- 3候補（compact / balanced / close）を同一入力から決定的に生成可能
- balancedの顔・目・口アンカー残差: 最大0.003px未満
- 23ユニットテスト、Ruff、CLI起動: 合格
- README動画と `viewer/` は保護・回帰確認済み
- 現在は合成画像の正規化まで。固定レイヤーPNG/PSD生成とCubism適用は未完了

## レイヤーsandbox方式の進捗

- PSDレイヤー抽出・sandbox書き出し・検査・戻し: `python -m pipeline.sandbox`
- 手順書: `docs/LAYER_SANDBOX.md`
- 原PSDへの生成塗りつぶしは全画面へ模様が出るため実行しない。原本は無変更。
- `work/sandbox/face` を書き出し済み。額の補完が対象
  - 切り出し: 元canvas `(1256, 216) - (1714, 881)`、458×665px、戻し座標 `(1256, 216)`
  - 生成可能133,379px、変更禁止70,264px
  - 元PSD SHA-256先頭: `8f2b7cb50bc828cb`
- `後ろ髪`・`前髪`・`前髪左`・`前髪右`・`口中` も同じCLIで抽出可能なことを実機確認済み
  （`口中` は不透明度0で待機中だが58×31pxの中身を取り出せる）
- 原PSDに対する往復リハーサルを実施。レビュー名なしでは書き込まれず、
  名前を付けると2976×4175pxのPNGが出力され、顔のalpha bboxが
  `(1295, 414, 1673, 845)` から `(1280, 240, 1690, 857)` へ額方向に伸びることを確認
- 布地模様の回帰テストを含む21件のsandboxテストを追加。全69件とRuffは合格
- 未完了: Codexによる実際の生成、その結果の検査と取り込み

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

0. `work/sandbox/face` をPhotoshopで生成し、`qa` と `import` を通す。
1. balanced候補を固定マスクへ分解し、隠れた額・後髪・口内を補完する。
2. v2契約の境界、包含、髪の継ぎ目QAを通す。
3. 合格PSDだけをマスターCMO3へ再インポートする。
4. SDK 5.3/4.2を書き出し、HTML viewerで髪境界、まばたき、口パク、髪揺れを比較する。
5. PicoAgent実アプリで最終目視確認する。

## 注意

- See-through生成は正常終了済み。再実行しない。
- `tools/see-through` の作業ツリーは既存変更を含むため、このリポジトリのcommitへ含めない。
- `work/qa/`、失敗PSD、バックアップPSD、生成途中レイヤーはGitへ追加しない。
