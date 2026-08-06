# むぎ VRM 版

## 方針

最初の VRM 版は、完成PSDのパーツを複数の透過カードへ貼った「多層ペラ板 VRM」です。
元の絵柄を保ったまま、VRM 1.0 の読み込み・表示とパーツ単位の動きを試すモデルです。
Live2D 版は変更しません。

- 形式: VRM 1.0（GLB コンテナ）
- テクスチャ: `work/psd/hiyori/mugi-hiyori-compatible-final.psd` から18パーツを抽出して格納
- 表示: 両面・Unlit・アルファ透過
- 身長: 1.8 m 相当
- リグ: VRM 1.0 の必須 Humanoid ボーンと chest / neck を階層で収録
- メッシュ: 18枚・合計365頂点。胴体、腕、脚、髪、装飾は格子分割
- 表情: blink / blinkLeft / blinkRight、視線4方向、5母音、happy / angry / sad / relaxed / surprised
- アイドル補助: `breath` / `idleLeft` / `idleRight` カスタム Expression
- スキン: 胴体はspine→chest、手足はupper→lowerへ段階ウェイト。顔パーツはheadへ固定

これは正面絵を 3D 空間に立て、カードごとのメッシュ変形で顔、呼吸、手足、髪の動きを表現する
試作です。横・背面の立体形状と物理シミュレーションはありません。フル 3D VRM へ進む場合は
モデル本体を差し替えます。

## 動きの扱い

- 対応ビューアが標準 Expression を操作すると、視線、まばたき、5母音の口パク、5感情が動きます。
- `breath` / `idleLeft` / `idleRight` はカスタム Expression です。自動再生されるとは限らず、
  ビューア側から値を渡します。
- README の GIF は足元を固定し、呼吸、手足と髪の微動、視線、両目の blink、`aa` を穏やかに再生します。
- GIF のタイムライン自体は VRM に埋め込んでいません。VRM 1.0 の実際の動きは利用側が制御します。
- 一枚絵由来のため、顔の動きは描き替えではなく各カードの変形です。

実際のVRMランタイムで確認するときは、[VRM実機プレビュー](../vrm-viewer/README.md)を使います。
README用GIFとは別に、VRM本体のExpressionとボーンをthree-vrmで直接再生できます。

## フェーズ比較動画

各品質改善フェーズは同じ正面構図で録画し、前段階との差を確認できるようにします。

| フェーズ | 主な確認内容 | 動画 |
|---|---|---|
| Phase 1 | three-vrmで実際のVRM本体を読み込んだ基準映像 | [MP4](media/vrm-phase1-runtime.mp4) |
| Phase 2 | 4頂点カードと多分割・段階ウェイト版の左右比較 | [MP4](media/vrm-phase2-deformable-mesh.mp4) |

## 生成と検証

リポジトリルートで実行します。

```powershell
uv run python -m scripts.build_vrm
uv run python -m scripts.validate_vrm exports/vrm/mugi.vrm
uv run python -m scripts.render_vrm_preview
```

多層カードの抽出結果を個別確認するときは、完成 PSD を変更せず `temp/vrm-layers/` へ書き出します。

```powershell
uv run python -m scripts.export_vrm_layers
```

生成スクリプトは完成PSDから `exports/vrm/mugi.vrm` を再作成します。VRM は Git LFS で管理します。
検証スクリプトは GLB 構造、VRM 1.0 メタデータ、必須 Humanoid ボーン、ボーン階層、埋め込み画像、
18カードメッシュ、スキン、標準17種・カスタム3種の Expression と各モーフの結線を確認します。

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
