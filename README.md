# むぎ Live2D / VRM モデル

## VRM プレビュー

[![むぎのVRMプレビュー](docs/media/mugi-vrm-preview.gif)](docs/media/mugi-vrm-preview.mp4)

完成PSDを26枚の透過メッシュへ分けた VRM 1.0 の A プラン（多層ペラ板 VRM）です。髪、顔、目、眉、
口、胴体、腕、脚を個別メッシュにし、足元を固定した呼吸・視線・まばたき・口パクを再生しています。
左右の腕は上腕・前腕・手へ3分割し、肩・肘・手首を連鎖変形させて継ぎ目が開かないようにしています。
最新プレビューでは自動モーションと happy・surprised・sleepy の表情変化を確認できます。
画像をクリックすると高品質MP4を開けます。VRM本体は [`mugi.vrm`](exports/vrm/mugi.vrm) です。
仕様、利用条件、再生成・検証方法は [VRM 制作資料](docs/VRM.md)を参照してください。

最終構造と動画リンクの検査結果は[VRM品質レポート](docs/VRM_QUALITY_REPORT.md)にまとめています。

## Live2D 動作プレビュー

[![むぎのLive2D動作プレビュー](docs/media/mugi-cubism-preview.gif)](docs/media/mugi-cubism-preview.mp4)

SDK 5モデルを直接描画したキャラクター単体のプレビューです。視線・顔向き、まばたき、口の開閉、髪揺れを自動再生します。画像をクリックするとMP4版を開けます。

HTMLベースのローカル動作確認ツールは `viewer/README.md` を参照してください。SDK 5/4の読込、上半身表示、視線追従、まばたき、口パク、髪揺れをブラウザで確認できます。

むぎ専用のモデル制作・書き出し管理ディレクトリです。

- `source/`: 権利を持つ元画像
- `work/psd/`: パーツ分割PSD
- `work/cubism/`: Cubism編集ファイル
- `exports/sdk5/`: Cubism SDK 5向け書き出し
- `exports/sdk4/`: Cubism SDK 4互換向け書き出し
- `exports/vrm/`: VRM 1.0 書き出し
- `reference/`: テンプレートや確認画像（再配布条件を確認して使用）

自動生成処理の実装は `C:\00_PG\30_live` に残し、完成モデルと制作素材だけをここで管理します。

Live2D 制作手順の正本は `WORKFLOW.md`、VRM 制作手順は `docs/VRM.md`、現在の進捗は
`STATUS.md` です。工程変更時は該当する手順書と進捗を同じ Git 変更内で更新します。
別キャラクターを新規作成するときは `NEW_CHARACTER.md` を使います。

再現可能なモデル生成は、固定済みの高品質リグへ同一トポロジーの画像を適用する[A方式](docs/FIXED_TOPOLOGY_PIPELINE.md)を優先します。入力画像はCubismへ入れる前に境界QAを通します。

隠れた額・後髪・口内をPhotoshopの生成塗りつぶしで補完するときは、原PSDを開かず[レイヤーsandbox方式](docs/LAYER_SANDBOX.md)を使います。

ひよりのリグの変形をむぎのArtMeshへ移すときは、頂点座標をコピーせず[キーフォーム転送方式](docs/KEYFORM_TRANSFER.md)で変位として転送します。
