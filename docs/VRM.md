# むぎ VRM 版

## 方針

最初の VRM 版は、一枚絵を透過カードへ貼った「ペラ板 VRM」です。元の絵柄を保ったまま、
VRM 1.0 の読み込み・表示を最小構成で試すためのモデルです。Live2D 版は変更しません。

- 形式: VRM 1.0（GLB コンテナ）
- テクスチャ: `source/mugi-original.png` を最大 2048 px に縮小してモデル内へ格納
- 表示: 両面・Unlit・アルファ透過
- 身長: 1.8 m 相当
- リグ: VRM 1.0 の必須 Humanoid ボーンを T ポーズ階層で収録
- 変形: カード全体を hips にウェイト 1.0 で固定

これは正面絵を 3D 空間に立てる試作です。横・背面の立体形状、表情 BlendShape、髪や服の
物理揺れはありません。フル 3D VRM へ進む場合はモデル本体を差し替えます。

## 生成と検証

リポジトリルートで実行します。

```powershell
uv run python scripts/build_vrm.py
uv run python scripts/validate_vrm.py exports/vrm/mugi.vrm
```

生成スクリプトは元画像から `exports/vrm/mugi.vrm` を再作成します。VRM は Git LFS で管理します。
検証スクリプトは GLB 構造、VRM 1.0 メタデータ、必須 Humanoid ボーン、ボーン階層、埋め込み画像、
カードメッシュとスキンを確認します。

## 利用条件

この試作 VRM のメタデータは、安全側の初期値として次の条件を記録しています。

- アバターとしての利用: 作者本人のみ
- 再配布: 不可
- 改変: 不可
- クレジット: 必須
- 過度な暴力・性的表現、政治・宗教、反社会・ヘイト目的の利用: 不可

条件を変更する場合は `scripts/build_vrm.py` の `VRM_META` とこの節を同じコミットで更新し、
モデルを再生成してください。

## 仕様資料

- [VRM 1.0 specification](https://github.com/vrm-c/vrm-specification/tree/master/specification/VRMC_vrm-1.0)
- [VRM 1.0 Humanoid specification](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/humanoid.md)
- [glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
