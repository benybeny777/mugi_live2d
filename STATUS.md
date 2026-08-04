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

## キーフォーム転送方式の進捗

- 計画CLI: `python -m pipeline.keyform`（`validate` / `draft-map` / `plan`）
- 手順書: `docs/KEYFORM_TRANSFER.md`、境界は `WORKFLOW.md` 第3節
- キーフォームを絶対座標ではなく、そのメッシュの基準フォームからの変位として転送する。
  基準フォームはパラメータ既定値で特定し、並び順には依存しない。
- 基準フォームの出力はtargetのベース形状とビット単位で一致する（テストで固定）。
- 平行移動・拡大縮小・回転をsourceモデル全体に加えても計画が変わらないことを確認済み。
- 未対応メッシュ、頂点数不一致、三角形リスト不一致、基準フォーム不在、非有限座標、
  既定値の食い違い、範囲外パラメータ、大きすぎる移動量を診断として不合格にする。
- 現在は純粋な計画までで、Cubism GUIへの適用と目視確認は別ゲートのまま未実施。
- ひよりのmanifest抽出（41メッシュ261キーフォーム）と対応表の確定は次工程。

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
- 顔は `face_forehead` 固定領域（顔楕円上部 y<430）をPhotoshopで生成し、42,881pxを検査・承認済み
  - 許可範囲外0px、ロック変更0/70,264px、色距離median/p95ともに0
  - 顔全楕円案は画素QA通過後、全身合成で頬に暗帯が出たため不採用
  - 元の顔レイヤーを置換せず、承認した額下地だけを直下へ追加したPSDプレビューは目視合格
- 未完了: 額下地を含むPSDへの髪・口補完、Cubism再取込

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

0. `face_forehead` は完了。コード・契約・手順をpushする。
1. balanced候補を固定マスクへ分解し、後髪・口内を補完する。
2. v2契約の境界、包含、髪の継ぎ目QAを通す。
3. 合格PSDだけをマスターCMO3へ再インポートする。
4. SDK 5.3/4.2を書き出し、HTML viewerで髪境界、まばたき、口パク、髪揺れを比較する。
5. PicoAgent実アプリで最終目視確認する。

## 注意

- See-through生成は正常終了済み。再実行しない。
- `tools/see-through` の作業ツリーは既存変更を含むため、このリポジトリのcommitへ含めない。
- `work/qa/`、失敗PSD、バックアップPSD、生成途中レイヤーはGitへ追加しない。
