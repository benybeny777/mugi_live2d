# 制作状況

最終更新: 2026-08-03

## 完了

- 専用ディレクトリと管理構成を作成
- 元画像を `source/mugi-original.png` に固定
- ひより互換名の目・まつげ・口・髪パーツを含むPSDを作成
- 右まつげ7までのレイヤー名を追加
- 胴体の誤テンプレート変形を確認し、適用対象から外す方針を確定
- See-through blockswap生成を詳細ログ付きで正常完了
- 髪の半透明ノイズと顔補完の暗い帯を修正
- 修正版ひより互換PSDを `work/psd/hiyori/mugi-hiyori-compatible-final.psd` に保存
- 修正版基礎CMO3を `work/cubism/mugi-hiyori-compatible-final.cmo3` に保存
- まばたき・口パク・髪揺れを設定した中間モデルを `work/cubism/mugi-hiyori-rigged-final.cmo3` に保存
- まばたき、口パク、髪揺れの端値をCubism上で目視確認
- SDK 5/4対応のHTMLローカル動作確認ツールを `viewer/` に実装
- HTMLビューアの構文、ローカルHTTP配信、画面表示、コンソール非表示起動経路を確認

## 作業中

- 3ページ構成のテクスチャアトラスを作成し、SDK 5 / SDK 4互換へ書き出す

## 未完了

- SDK 5 / SDK 4互換書き出し
- HTML動作確認ツールでSDK 5 / SDK 4の実モデル読込と各パラメータ操作を確認
- PicoAgentでの上半身表示と動作確認

## 中間チェックポイント

この時点のGit版は、再開可能なPSD、CMO3、HTML確認ツール、制作手順を保存するための中間版です。SDK出力とPicoAgent実機確認が終わるまでは完成版として扱いません。
