# むぎ Live2D 制作手順

この文書を制作手順の正本とし、工程や出力先を変更したコミットでは必ず同時に更新します。
別キャラクターへ展開するときは `NEW_CHARACTER.md` も参照します。

## このPCの固定環境

- 制作リポジトリ: `C:\00_PG\40_mugi_live2d`
- 自動分割アプリ: `C:\00_PG\30_live`
- 組み込み先: `C:\00_PG\20_PicoAgent`
- Cubism Editor: 5.3.03（SDK 5.3設定）
- 画像修正: `C:\Program Files\Adobe\Adobe Photoshop 2026`
- 作業モニター: 左側サブモニター `(-1920, 0) - (0, 1080)`
- メインモニターは動画視聴を妨げないため、Cubism、Photoshop、PicoAgent確認画面を出さない。
- Python処理は `C:\00_PG\30_live` で `uv run` を使い、必要時は `UV_CACHE_DIR=C:\00_PG\30_live\.uv-cache` を設定する。

## 1. 入力を固定する

1. 権利を持つ正面向き・透過PNGを `source/mugi-original.png` に置く。
2. 解像度、輪郭、左右の目・口・前髪が欠けていないことを確認する。
3. 元画像は直接加工せず、修正は `work/psd/` の複製に行う。

## 2. パーツPSDを作る

1. `tools/see-through` の公式8GB向けblockswapスクリプトで、元画像から塗り足し済みの意味レイヤーPSDを生成する。
2. このPCではRTX 5060 Laptop GPU 8GBのため、LayerDiff 1024・Depth 512・blockswapを標準設定にする。blockswapは埋め込みをCPUでキャッシュしてからテキストエンコーダを解放する。NF4のCPU offload経路は公式コードのデバイス不整合があるため予備扱いとする。
3. 初回だけ `scripts/setup-seethrough.ps1` と `scripts/apply-seethrough-local-fixes.ps1`、生成時は `scripts/run-seethrough.ps1 -Mode blockswap` を実行する。
4. See-through出力を `work/psd/seethrough/` に保存し、元出力を直接上書きしない。
5. Photoshop 2026で各レイヤーを高品質拡大し、ひより基準の2976×4175キャンバスへ戻す。
6. 見えていた表面は元の2976×4175画像をSee-throughマスクで再合成し、See-through生成画は隠れ部分の塗り足しにだけ使う。
7. `C:\00_PG\30_live` の処理で、See-throughの意味レイヤーをひより互換の目・まつげ・口・髪レイヤー名へ変換する。
8. `scripts/build_hiyori_psd.py` で、独立髪パーツの内周だけを後髪へ5px重ねる。隙間対策にレイヤー全体の膨張は使わない。

### ログ確認

- `logs/seethrough-*.stdout.log`: 工程と進捗
- `logs/seethrough-*.stderr.log`: 警告、トレースバック、進捗バー
- `logs/seethrough-*.lifecycle.log`: 開始時刻、モード、終了コード、例外、終了時刻
- `logs/seethrough-monitor.csv`: CPU、GPU、メモリ、出力ファイル数と容量
- プロセスの有無だけで正常判定せず、4種類のログを合わせて確認する。
9. 顔、前髪、横髪、後髪、目、まつげ、眉、口、首、胴体、腕を独立レイヤーにする。
10. 顔レイヤーは目・眉・鼻・口を消した下地にし、輪郭の穴や塗り足しを100%表示で確認する。
11. Photoshopで直した場合も、レイヤー名とキャンバス位置は変えない。
12. 隠れた額・後髪・口内を生成塗りつぶしで補うときは、原PSDを開かず `python -m pipeline.sandbox` のsandboxを使う。原PSDのレイヤーは全キャンバス＋マスク構成のため、直接実行すると全画面へ模様が生成される。手順は `docs/LAYER_SANDBOX.md`。
13. Cubism取込用PSDを `work/psd/hiyori/mugi-hiyori-compatible-final.psd` に保存する。

## 3. Cubismでリグを適用する

1. Cubism 5でPSDを開き、ベース表示が元絵と一致することを先に確認する。
2. 公式ひよりモデルは `reference/` からモデルテンプレートとして参照する。
3. 顔輪郭や胴体を自動対応させず、パーツをAlt+クリックして実ArtMeshを選択し、目・口・髪など必要な対象へパーツ群ごとにテンプレートを適用する。
4. マスク、クリッピング、カラーブレンド、アルファブレンドは引き継がない。
5. パラメータを端まで動かし、少なくとも次を確認する。
   - 左右のまばたきで白目と瞳が残らない
   - 口開閉で口中が閉口時に見えない
   - 前髪・横髪・後髪の揺れで輪郭に穴や二重像が出ない
   - 顔輪郭と胴体が変形して崩れない
6. 全ArtMeshを選択し、必要に応じて「メッシュの自動生成」の変形度合い（大）を適用する。パラメータ設定後は形状が変わるため、必ず全キー値を再確認する。
7. 編集ファイルを `work/cubism/mugi-hiyori-rigged-final.cmo3` に保存する。

### キーフォーム転送の境界

ひよりの変形をむぎのArtMeshへ移すときは、キーフォームの頂点座標を直接コピーしない。絶対座標のコピーは髪の浮き・頭頂部の白抜け・口の消失として実際に失敗している。手順とスキーマは `docs/KEYFORM_TRANSFER.md` を正本とする。

| 工程 | 担当 | 合否 |
| --- | --- | --- |
| manifest検査・対応表検証・フレーム推定・変位転送・計画生成 | `python -m pipeline.keyform`（自動・テスト済み） | 終了コード0かつ `status == "ready"` |
| Cubismからのmanifest抽出 | Cubism GUI（手作業） | `keyform validate` が通ること |
| 計画のCubismへの適用 | Cubism GUIブリッジ（**別ゲート**） | 適用後に再抽出し `target_invariants` が一致すること |
| まばたき・口パク・髪揺れの端値確認、viewer、PicoAgent | 目視（**別ゲート**） | 第3節5項と第4節の確認項目 |

計画が `ready` でも見た目の合格ではない。純粋な計画側が通っただけであり、GUI適用と目視確認は必ず別工程として実施する。対応表 `pipeline/keyform-map.*.json` はレビュー済みデータとして扱い、実行を通すために書き換えない。

## 4. 書き出しと組み込み

1. Cubism 5向けを `exports/sdk5/` に書き出す。
2. Cubism 4互換向けを `exports/sdk4/` に書き出す。
3. テクスチャ、model3.json、moc3、物理演算、モーションの参照切れがないことを確認する。
4. `C:\00_PG\30_live\.venv\Scripts\python.exe scripts\sanitize_export_textures.py exports\sdk5 exports\sdk4` を実行し、完全透明画素に残るRGBを消してWebGLのアトラス境界漏れを防ぐ。
5. PicoAgentでは上半身表示、透過背景、常時アイドル、まばたき、音声連動口パクを確認する。
6. 起動時にコンソールが表示されず、ウィンドウが指定モニターへ出ることを確認する。

### HTMLローカル動作確認ツール

1. 初回だけ `viewer/setup-runtime.ps1` を実行し、このPCのPicoAgentからLive2Dランタイムをコピーする。ランタイムはGitへ追加しない。
2. `viewer/launch-viewer.vbs` をダブルクリックする。`pythonw.exe`を使うためコマンドプロンプトは表示されない。
3. SDK 5とSDK 4を切り替え、それぞれの`model3.json`が読めることを確認する。
4. 上半身表示、視線追従、自動・手動まばたき、口スライダー、髪揺れ、倍率・上下位置を確認する。
5. 読込失敗時は診断欄のエラーを記録し、`model3.json`内の参照ファイルとCore互換性を確認する。

## 5. 完了記録

1. `STATUS.md` の完了項目と未確認項目を更新する。
2. 目視確認画像を必要に応じて `qa/` に置く（画像自体はGit管理外）。
3. 変更したPSD/Cubismファイルと手順書を同じGitコミットに含める。
