# 制作状況

最終更新: 2026-08-13 JST

## 2026-08-13 VRM手動表示と腕分割の確認

- 自動モーションOFF・neutral時にも`blink=0.15`の自然なまぶたを維持するようにし、実機プレビューで確認した。
- 元解像度2976×4175のPSDをPhotoshopで複製し、腕の肩側だけを平行移動して隙間を隠す候補を実験した。画像拡大や外部送信は行っていない。
- 候補は腕以外の17スプライトが画素一致したが、胴体側の袖と重なって二重の肩形状になったため不採用。リリースVRMと承認済みPSDは変更していない。
- 現在の腕は「肩から手まで一枚の腕」と「袖を含む胴体」の分割自体が制約。次に直す場合は、拡大や単純移動ではなく元解像度での局所描き直し、またはパーツ再分割が必要。

## 2026-08-06 VRM Aプラン

### 最新版

- 見た目が悪化したため、VRM本体・動き・プレビューを`7f575bc`時点の安定版へ戻した。
- 18メッシュ・459頂点・標準17種/カスタム4種Expressionの構成を採用。
- READMEは最新の実機GIF/MP4だけを表示し、旧Phase 1〜6動画を削除。
- 最新GIFの動きと足元固定を検査する視覚品質ゲートは維持。
- Live2D版とPicoAgent実装は変更なし。

### これ以前の改善履歴

- 腕1枚パーツへ不適切に付けていた上腕→前腕の段階ウェイトを廃止し、肩固定の`greet`モーフへ変更。
- 挨拶中に袖と胴体の間へ出ていた黒い隙間を解消し、READMEの実機GIF/MP4とPhase 6動画を更新。
- VRM Expressionは標準17種・カスタム4種。Live2D版は変更なし。
- VRMプレビューのぼやけを修正。4096テクスチャ、透過境界補正、Linear sampling、高密度録画を適用。
- READMEのメインGIFを実ランタイム録画へ更新し、クリック先を高品質MP4へ変更。
- 同一解像度の輪郭指標は435.55から1248.31へ改善。Live2D版は変更なし。
- Phase 6: VRM構造・容量・顔格子・Expression・Spring Bone・タイムライン・Phase動画を一括検査。
- Phase 1基準→Phase 6リリースの全画面順番再生GIF/MP4と品質レポートをREADMEへ追加。
- リリースゲートは18メッシュ、459頂点、Expression 21種、Spring Bone 3チェーン/5可動で合格。
- Phase 5: 外部JSONタイムラインでidle→greet→talkを循環し、頭・胸・左右腕を滑らかに補間。
- 足元固定を維持し、表情・5母音・Spring Boneを動作状態ごとに組み合わせる実機デモへ更新。
- Phase 4→5の全画面順番再生GIF/MP4をREADMEのVRMプレビュー内へ追加。
- Phase 4: 後髪・前髪・星アクセサリーへVRMC_springBone 1.0の3チェーン・5可動ジョイントを追加。
- 髪の反復Expression揺れをSpring Boneへ置換し、頭の動きへ慣性を伴って追従する構成にした。
- three-vrm実機で5 spring jointsの初期化と描画を確認し、Phase 3→4全画面比較動画をREADMEへ追加。
- Phase 3: 目・まつ毛を4×2、口・口内を5×2の格子へ更新し、合計459頂点へ高密度化。
- まばたきを下まぶた側へ閉じる非対称カーブにし、5母音の口角・中央曲率と感情表現を改善。
- READMEのVRMプレビュー内へPhase 1〜3の全画面順番再生GIFを配置し、各GIFからMP4を開けるようにした。
- Phase 2: 胴体・腕・脚・髪・装飾を格子分割し、18メッシュ合計365頂点へ更新。
- 胴体をspine→chest、腕と脚をupper→lowerへ段階ウェイト化し、肘・膝付近の折れを滑らかにした。
- READMEへPhase 1単体動画とPhase 1/2左右比較動画を追加。
- Live2D 版を変更せず、`exports/vrm/mugi.vrm` を独立して追加。
- 完成PSDから18パーツを抽出して個別メッシュにした、1.8 m 相当の多層ペラ板 VRM 1.0。
- VRM 1.0 の必須 Humanoid ボーンと chest / neck を階層で収録し、各カードを対応ボーンへ固定。
- 視線4方向、両目まばたき、5母音、5感情、呼吸、左右アイドルの Expression を追加。
- リポジトリ内検証に合格。Khronos glTF Validator はエラー 0、警告 0。
- `docs/media/mugi-vrm-preview.gif` を README から直接表示し、クリック先を VRM 本体に設定。
- 不自然な全身の横縮み・左右移動を廃止し、足元固定で腕・脚・髪を個別に動かすプレビューへ変更。
- 現段階では横・背面の立体形状と物理シミュレーションは未実装。

## 2026-08-06 最終リリース

- `work/cubism/mugi-hiyori-rigged-final.cmo3` を、PSD再取込済みの49 ArtMesh・29 Parameterモデルへ更新。
- `work/psd/hiyori/mugi-hiyori-compatible-final.psd` を修復済みPSDへ更新。
- 髪の白抜け対策として、既存髪より後ろ・アクセサリーより後ろに描画される専用アンダーレイを追加。
  静止画QAの白抜け率は5.47%から0.36%へ低下し、星の検出画素は2021pxに対して1991pxを維持。
- SDK 5 / SDK 4を8192×8192テクスチャ1枚構成で再出力。両方とも49 Drawable、29 Parameter、
  41実メッシュ、0頂点メッシュなし、EyeBlink / LipSync / 4物理グループを検証済み。
- 完全透明画素の隠れRGBを除去し、両SDKのリリースゲートは合格。
- `docs/media/mugi-cubism-preview.mp4` とGIFを更新し、7秒・28フレームの頭振り、まばたき、髪追従を目視確認。
- 以降の「未完了」「次はexportsの構造回帰」と書かれた旧メモは、この最終リリースで解消済み。

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

## Cubism editorブリッジの進捗

- 動作中のCubism Editor 5.3のJVMへJavaエージェントをアタッチし、GUI操作なしで
  ArtMesh複製・予約UV設定・組み込み用書き出し・メニュー起動・状態ダンプを行う。
  実装は `scripts/cubism_bridge/`、起動は `scripts/*-cubism-*.ps1`。
- 髪の継ぎ目対策として、`CubismDuplicateUnderlayAgentV12` でArtMeshを縮尺と
  描画順オフセット付きで複製する下地メッシュ方式（semantic underlay）を試行中。
- 試行19件のパラメータは `work/cubism/*.cmo3.agent.txt` に記録済み。
  CMO3本体はマスターとこのブリッジから再生成できるためGitへ入れない。
- `scripts/sanitize_export_textures.py` にアトラス側のセマンティック下地塗りを実装済み。
- 未完了: `CubismMocExportAgentV3` による組み込み用書き出しの自動起動。
  `temp/cubism-menu-listeners.txt` にメニュー階層とActionListenerの列挙まで完了し、
  「組み込み用ファイル書き出し」の起動検証で中断している。
- どのunderlay候補が最良かの比較・採否はまだ記録していない。

## 今回のチェックポイント

- Cubism編集モデル: `work/cubism/mugi-hiyori-rigged-final.cmo3`
- Hiyori互換レイヤーPSD: `work/psd/hiyori/mugi-hiyori-compatible-final.psd`
- SDK 5.3出力: `exports/sdk5/mugi/`
- SDK 4.2互換出力: `exports/sdk4/mugi/`
- HTML動作確認ツール: `viewer/`
- 全ArtMeshを「変形度合い（大）」で輪郭に沿うメッシュへ再生成済み
- 上半身表示、目の開閉、SDK 5読込をHTMLで確認済み
- Cubism起動時とHTML viewer起動時にコマンドプロンプトを表示しない構成

## exports/ の構造回帰（最優先）

- `exports/sdk5/mugi/mugi.moc3` と `exports/sdk4/mugi/mugi.moc3` は構造ゲートに落ちる。
  94 drawable中、実メッシュ18、頂点0が27、4頂点の静止板が47、パラメータ28。
  顔の目・口が描画されない。`Part3` の26メッシュが空。
- ディスク上の他のmugi moc3は38個中36個が合格する。作業中の系統は
  drawable 48〜49、実メッシュ41〜42、頂点0は0、4頂点7、パラメータ29で、別物。
  つまり `exports/` に入っているのは作業系統とは無関係の古い壊れたモデル。
- `validate_live2d_exports.py` はテクスチャと物理演算しか見ていなかったため素通りした。
  viewerと同じ構造上限を実装して不合格になるようにした（`fix: gate exports on MOC mesh structure`）。
- 差し替え候補は `temp/semantic-underlay-sdk5-reserved-final/` などディスク上にある。
  ただし候補は8192テクスチャ1枚で、検証は「4096が3枚」を要求する。
  最終的なテクスチャ構成をどちらにするか未決定のため、検証側の期待値は変更していない。
- 候補はmodel3.jsonに `EyeBlink` / `LipSync` のGroupsを持たない。差し替え時に付与が要る。

## 既知の残課題

- HTMLの縮小表示で、左横髪と毛先の境界に細い背景色の線が見える。
- 原因は隣接髪レイヤーが同一境界で接していること。全体膨張は輪郭を荒らすため使用しない。
- `scripts/build_hiyori_psd.py` は後髪へ各髪パーツの内周5pxを重ねる局所下地を生成する。修正版PSDは生成済みだが、Cubismへの再インポートと最終比較は次回工程。
- PicoAgentへの最新SDK 5/4モデル反映、character-pack検証、UI資産同期は完了。実アプリでの最終目視確認は未完了。

## 再開位置

0. `face_forehead` は完了。ブリッジ・アトラス・viewerのコミットとpushも完了。
0b. underlay候補の比較は完了。`reserved-final` が最良で、記録は `docs/progress/README.md`。
0c. 次は `exports/` の構造回帰の解消。テクスチャ構成（8192×1か4096×3か）を決め、
    健全な候補へ差し替え、model3.jsonへGroupsを付け、検証と viewer を通す。
0d. 髪の白い縁の原因は特定済み。被覆不足でステージ背景が透けているだけで、
    アトラスに白は焼き込まれていない。効くのは下地メッシュではなくアトラスの塗り量。
    ただし下地UVが他の12島と重なるため、塗りを濃くすると星のヘアピンとお下げが消える。
    `CubismReservedUvAgent` は予約UVへ移せておらず、`reserved-final` の下地UVは
    `central` と同一。詳細と数値は `docs/progress/README.md`。
    衝突のない `clean2` へ面塗りを当てる迂回策を試した。穴は9.76%から1.65%へ減り
    `r55` を上回ったが、星とお下げは同じように失われた。UV衝突は原因ではない。
    塗りは不透明画素を1つも上書きしておらず（変化229,509画素はすべて元が透明）、
    描画順の遮蔽でもマスクでもないことを実測で確認済み。
    失われているのは絵柄ではなく透明な隙間で、お下げの房間や装飾まわりの隙間まで
    髪色で埋めてしまうため塊になる。塗る範囲を「背景が透ける穴」だけに限定するか、
    `CubismReservedUvAgent` で下地専用UVを確保するのが本筋。
0e. MOCトポロジーのUVから髪の8 drawableを選び、親Part単位・単島単位で膨張するCLIを実装。
    静止headless評価と外周増加指標も追加した。全8島r4/8/12/16と単島8候補を比較し、
    `ArtMesh47` が穴率を5.73%から2.60%へ下げたが、外周・編み込み・額に濃いハローが出た。
    全面・UV島単位・単島の膨張はすべて不採用。詳細は `docs/HAIR_SEAM.md`。
0f. 次は外周側の透明画素を変えず「モデル内側の背景穴」だけを塗るマスク、または承認済みPSDの
    Cubism再取込へ進む。穴率だけで採用せず、外周増加と目視を必須ゲートにする。
1. balanced候補を固定マスクへ分解し、後髪・口内を補完する。
2. v2契約の境界、包含、髪の継ぎ目QAを通す。
3. 合格PSDだけをマスターCMO3へ再インポートする。
4. SDK 5.3/4.2を書き出し、HTML viewerで髪境界、まばたき、口パク、髪揺れを比較する。
5. PicoAgent実アプリで最終目視確認する。

## 注意

- See-through生成は正常終了済み。再実行しない。
- `tools/see-through` の作業ツリーは既存変更を含むため、このリポジトリのcommitへ含めない。
- `work/qa/`、失敗PSD、バックアップPSD、生成途中レイヤーはGitへ追加しない。
