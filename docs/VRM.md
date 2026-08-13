# むぎ VRM 版

## 方針

現在の VRM 版は、Photoshopで高解像度化した同一Tポーズ原画を複数の透過カードへ分けた「多層ペラ板 VRM」です。
元の絵柄を保ちつつ、腕の分離、自然な肩の重なり、表情と視線を実装しています。
Live2D 版は変更しません。

- 形式: VRM 1.0（GLB コンテナ）
- テクスチャ: `work/psd/tpose/mugi-tpose-source-v1-photoshop-pd2-preview.png` から17パーツを抽出して格納
- 表示: 両面・Unlit・アルファ透過
- 身長: 1.8 m 相当
- リグ: VRM 1.0 の必須 Humanoid ボーンと chest / neck を階層で収録
- メッシュ: 17枚・合計347頂点。頭、胴体、腕、肩下地、脚、目、虹彩、まつ毛、口を分割
- 表情: blink / blinkLeft / blinkRight、視線4方向、5母音、happy / angry / sad / relaxed / surprised
- アイドル補助: `breath` / `idleLeft` / `idleRight` / `greet` カスタム Expression
- スキン: 胴体はspine→chest、脚はupper→lowerへ段階ウェイト。腕は上腕ボーン、肩下地はspine、顔パーツはheadへ固定
- 揺れ物: VRMC_springBone 1.0で後髪・前髪・星アクセサリーの3チェーン、5可動ジョイント

これは正面絵を 3D 空間に立て、カードごとのメッシュ変形で顔、呼吸、手足、髪の動きを表現する
試作です。横・背面の立体形状はありません。髪とアクセサリーにはSpring Boneを収録していますが、
正面カードの範囲内で揺れる構成です。フル 3D VRM へ進む場合はモデル本体を差し替えます。

## 動きの扱い

- 対応ビューアが標準 Expression を操作すると、視線、まばたき、5母音の口パク、5感情が動きます。
- `breath` / `idleLeft` / `idleRight` / `greet` はカスタム Expression です。自動再生されるとは限らず、
  ビューア側から値を渡します。
- 後髪・前髪・星アクセサリーはExpressionによる反復揺れをやめ、対応ランタイムが
  `VRMC_springBone`を計算したときだけ頭の動きへ遅れて追従します。
- 実機プレビューは`vrm-viewer/motions/mugi-timeline.json`を読み、idle → greet → talkを
  滑らかなキーフレーム補間で循環します。足・腰の位置は変えず、頭・胸と肩固定の腕モーフだけを動かします。
- Aプランは正面カードのためVRMAは同梱しません。フル3Dモデルへ移行するときに、同じ3状態を
  `VRMC_vrm_animation`へ置き換える方針です。
- README の GIF は足元を固定し、呼吸、手足と髪の微動、視線、左右差のある blink、
  5母音と感情の組み合わせを穏やかに再生します。
- GIF のタイムライン自体は VRM に埋め込んでいません。VRM 1.0 の実際の動きは利用側が制御します。
- 一枚絵由来のため、顔の動きは描き替えではなく各カードの変形です。

実際のVRMランタイムで確認するときは、[VRM実機プレビュー](../vrm-viewer/README.md)を使います。
README用GIFとは別に、VRM本体のExpressionとボーンをthree-vrmで直接再生できます。

## 最新プレビュー

READMEのGIFをクリックすると、同じ最新版の高品質[MP4](media/mugi-vrm-preview.mp4)を開けます。
過去フェーズの比較動画はリポジトリへ残さず、最新版だけを公開します。

## 生成と検証

リポジトリルートで実行します。

```powershell
uv run python -m scripts.build_tpose_vrm_experiment
uv run python -m scripts.validate_vrm exports/vrm/mugi.vrm
uv run python -m scripts.validate_vrm_release
uv run python -m scripts.validate_vrm_visual
uv run python -m scripts.render_vrm_preview
```

多層カードの抽出結果を個別確認するときは、完成 PSD を変更せず `temp/vrm-layers/` へ書き出します。

```powershell
uv run python -m scripts.export_vrm_layers
```

生成スクリプトは完成PSDから `exports/vrm/mugi.vrm` を再作成します。VRM は Git LFS で管理します。
検証スクリプトは GLB 構造、VRM 1.0 メタデータ、必須 Humanoid ボーン、ボーン階層、埋め込み画像、
17カードメッシュ、347頂点、スキン、顔格子8枚、標準17種・カスタム4種の Expression、
Spring Bone 3チェーンと各モーフの結線を確認します。

リリース検証は上記に加えて、17メッシュ・347頂点・顔格子8枚・Expression 21種・
Spring Bone 3チェーン/5可動ジョイント、10 MiB以下の容量、READMEの最新プレビューリンク、
GIF解像度、MP4コンテナ、idle/greet/talkタイムラインを一括確認します。

プレビュー生成は VRM 本体が有効なGLBであることを確認し、モデル生成と同じ決定的なPSDレイヤー抽出を
使って README 用の `docs/media/mugi-vrm-preview.gif` を作ります。

## 利用条件

この試作 VRM のメタデータは、安全側の初期値として次の条件を記録しています。

- アバターとしての利用: 作者本人のみ
- 再配布: 不可
- 改変: 不可
- クレジット: 必須
- 過度な暴力・性的表現、政治・宗教、反社会・ヘイト目的の利用: 不可

条件を変更する場合は `pipeline/vrm_model.py` の `VRM_META` とこの節を同じコミットで更新し、
モデルを再生成してください。

## 仕様資料

- [VRM 1.0 specification](https://github.com/vrm-c/vrm-specification/tree/master/specification/VRMC_vrm-1.0)
- [VRM 1.0 Humanoid specification](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/humanoid.md)
- [glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
