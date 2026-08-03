# むぎ Live2D モデル

HTMLベースのローカル動作確認ツールは `viewer/README.md` を参照してください。SDK 5/4の読込、上半身表示、視線追従、まばたき、口パク、髪揺れをブラウザで確認できます。

むぎ専用のモデル制作・書き出し管理ディレクトリです。

- `source/`: 権利を持つ元画像
- `work/psd/`: パーツ分割PSD
- `work/cubism/`: Cubism編集ファイル
- `exports/sdk5/`: Cubism SDK 5向け書き出し
- `exports/sdk4/`: Cubism SDK 4互換向け書き出し
- `reference/`: テンプレートや確認画像（再配布条件を確認して使用）

自動生成処理の実装は `C:\00_PG\30_live` に残し、完成モデルと制作素材だけをここで管理します。

制作手順の正本は `WORKFLOW.md`、現在の進捗は `STATUS.md` です。工程変更時は両方を同じGit変更内で更新します。別キャラクターを新規作成するときは `NEW_CHARACTER.md` を使います。
