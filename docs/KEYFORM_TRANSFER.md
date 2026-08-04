# キーフォーム転送方式（ひより変形 → むぎのArtMesh）

ひよりのリグが持つ変形を、むぎの各ArtMeshのベース形状を保ったまま移すための、非GUI側とCubism GUI側の受け渡し契約です。

## なぜ必要か

キーフォームの頂点座標をインデックス順にそのままコピーすると、むぎのメッシュがひよりの**絶対キャンバス座標**に置き換わります。実際にこれを行い、髪が頭から浮く、頭頂部に白い穴が空く、口が消える、という結果になりました。コピー処理そのものには「値が入った」以外の判定基準がなく、壊れたことを検出できませんでした。

そこでキーフォームを座標ではなく、**そのメッシュ自身の基準フォームからの変位**として扱います。

## 転送の式

対応する1組（source mesh S、target mesh T）について、キーフォーム `k` ごとに

```
frame  = Frame(S_reference → T_reference)          # 相似変換（既定）または アフィン
T_k    = T_reference + frame.linear · (S_k − S_reference)
```

- 変位は2点の差なので、平行移動は式の中で必ず打ち消されます。
- 拡大縮小と回転は `frame.linear` が担います。むぎの目がひよりの半分の大きさなら、まばたきの移動量も半分になります。
- `k` が基準フォーム自身のとき変位は厳密に0で、出力は `T_reference` とビット単位で一致します。**むぎのベース形状は転送で変わりません。**
- ソースの絶対座標は式のどこにも残りません。

`frame` の既定は `similarity`（一様スケール＋回転＋平行移動）です。ベース形状の縦横比が本質的に違う組だけ、`affine`（異方スケール＋シアーを許可）を対応表側で個別指定します。どちらも閉形式の最小二乗なので、同じ入力からは常に同じ結果になります。

## 3つの文書

| schema | 役割 | 生成者 |
| --- | --- | --- |
| `mugi-live2d/keyform-manifest@1` | 1モデル分のArtMesh・固定トポロジー・全キーフォーム | Cubism側の抽出 |
| `mugi-live2d/keyform-map@1` | どのsource meshがどのtarget meshを駆動するか、どれを対象外にするか | 人間のレビュー |
| `mugi-live2d/keyform-transfer-plan@1` | GUIブリッジが適用する転送計画 | `python -m pipeline.keyform plan` |

### manifest

```json
{
  "schema": "mugi-live2d/keyform-manifest@1",
  "model": {"id": "mugi", "role": "target", "canvas": {"width": 2976, "height": 4175}},
  "parameters": [
    {"id": "ParamEyeLOpen", "name": "左目 開閉", "minimum": 0.0, "maximum": 1.0, "default": 1.0}
  ],
  "meshes": [
    {
      "id": "ArtMesh_EyeL",
      "vertex_count": 4,
      "parameters": ["ParamEyeLOpen"],
      "triangles": [[0, 1, 2], [0, 2, 3]],
      "uvs": [[0, 0], [1, 0], [1, 1], [0, 1]],
      "draw_order": 520,
      "clipped_by": ["ArtMesh_EyeLMask"],
      "opacity": 1.0,
      "forms": [
        {"coordinate": {"ParamEyeLOpen": 0.0}, "vertices": [[1280, 900], [1320, 900], [1320, 900], [1280, 900]]},
        {"coordinate": {"ParamEyeLOpen": 1.0}, "vertices": [[1280, 880], [1320, 880], [1320, 920], [1280, 920]]}
      ]
    }
  ]
}
```

要点は2つです。

- **すべてのキーフォームが自分のパラメータ座標を持ちます。** source と target のフォームは並び順ではなく座標の一致で対応付けます。
- **すべてのパラメータが `default` を宣言します。** 基準フォームは「全パラメータが既定値の座標にあるフォーム」であり、`forms[0]` ではありません。並び順は基準フォームの証拠になりません。該当が0個でも2個でも、そのメッシュは不合格になります。

`triangles` は必須です。これがないと「頂点インデックスが両モデルで同じ意味を持つ」ことを確認できません。

### map（対応表）

```json
{
  "schema": "mugi-live2d/keyform-map@1",
  "id": "mugi-hiyori-v1",
  "frame": "similarity",
  "limits": {"max_displacement_px": 400},
  "pairs": [{"target": "ArtMesh_EyeL", "source": "Hiyori_EyeL", "frame": "affine"}],
  "excluded": [{"target": "ArtMesh_Accessory", "reason": "むぎ固有の小物でひより側に対応部位がない"}]
}
```

対応表はレビュー済みデータです。plan時に推測はしません。targetのArtMeshは `pairs` か `excluded` のどちらかに必ず現れる必要があり、どちらにも無いメッシュがあればその実行は不合格です（黙って変形なしのまま通しません）。`excluded` には必ず文章の理由を書きます。

`limits.max_displacement_px` は転送後の最大移動量の上限です。絶対座標コピーが起きると移動量が桁違いに大きくなるため、この上限が直接の検出手段になります。

### plan（転送計画）

`meshes[].forms[]` に、target座標系の頂点列・パラメータ座標・`create` / `replace` の別・移動量が入ります。UV、三角形、描画順、クリッピング、不透明度、IDは**計画に一切含めません**。代わりに `target_invariants` にArtMesh数と各メッシュのダイジェストを記録するので、適用後に再抽出して不変を証明できます。

`status` が `ready` の計画だけを適用します。`rejected` の計画も（41メッシュ分の問題を一度に直せるように）出力されますが、GUIブリッジは適用してはいけません。

## 検証一覧

manifest自体が読めない場合は `ManifestError` / `MeshMapError` で終了コード2になります（スキーマ不一致、ID重複、宣言頂点数との不一致、非有限座標、範囲外のパラメータ値、範囲外の三角形インデックス、UV数の不一致、同一座標の重複フォームなど）。

2つの文書の**あいだ**の問題は診断として集約され、終了コード1になります。

| code | 内容 |
| --- | --- |
| `role_mismatch` | source/target の役割が manifest の宣言と違う |
| `unmapped_target` | 対応表に載っていないtarget ArtMesh |
| `unknown_target` / `unknown_source` | 対応表がモデルに存在しないメッシュを指している |
| `vertex_count_mismatch` | 頂点数が一致しない（頂点ごとの変位が定義できない） |
| `topology_mismatch` | 頂点数は同じだが三角形リストが違う |
| `reference_form` | 既定値にあるフォームが0個または2個 |
| `degenerate_frame` | ベース形状の大きさが0、または一直線でフレームが決まらない |
| `unknown_target_parameter` | sourceの変形パラメータをtargetモデルが持たない |
| `default_mismatch` | 同じパラメータの既定値が両モデルで違う（基準ポーズが別物） |
| `parameter_range` | sourceのキーフォーム座標がtargetの可動範囲外 |
| `non_finite_result` | 転送結果が非有限 |
| `displacement_over_limit` | 転送後の移動量がレビュー済み上限を超えた |

## 使い方

```powershell
$env:UV_CACHE_DIR = 'C:\00_PG\40_mugi_live2d\.uv-cache'
uv sync

# 1. 抽出したmanifestを単体で検査する
uv run python -m pipeline.keyform validate work/keyform/hiyori-source.json
uv run python -m pipeline.keyform validate work/keyform/mugi-target.json

# 2. 固定トポロジーから対応表の下書きを作る（提案のみ。人間が確定させる）
uv run python -m pipeline.keyform draft-map `
  --source work/keyform/hiyori-source.json `
  --target work/keyform/mugi-target.json `
  --out work/keyform/map-draft.json

# 3. 転送計画を出す。status が ready のときだけ終了コード0
uv run python -m pipeline.keyform plan `
  --source work/keyform/hiyori-source.json `
  --target work/keyform/mugi-target.json `
  --map pipeline/keyform-map.mugi-hiyori-v1.json `
  --max-displacement 400 `
  --out work/keyform/transfer-plan.json
```

`draft-map` は、頂点数と三角形リストのダイジェストが**1対1で一致する**組だけを `pairs` に提案し、候補が複数ある組（左右の目のように形が同じもの）は `unassigned` に残します。`unassigned` は読み込み時に無視されるため、下書きのまま `plan` を実行しても `unmapped_target` で不合格になります。人間が部位として確認し、`pairs` に移すか理由付きで `excluded` に移すまで先に進みません。

## 自動化される範囲と、別ゲートのままの範囲

| 工程 | 扱い |
| --- | --- |
| manifestの検査、対応表の検証、フレーム推定、変位転送、計画の生成 | **自動・テスト済み**。`pipeline/keyform/` は純粋関数で、同じ入力から同じ計画を返す |
| Cubismからのmanifest抽出 | GUI側の手作業。抽出結果は `validate` を通す |
| 計画のCubismへの適用（GUIブリッジ） | **別ゲート**。`status == "ready"` 以外は適用しない。適用後に再抽出し `target_invariants` の一致を確認する |
| まばたき・口パク・髪揺れの端値確認、HTML viewer、PicoAgentでの目視 | **別ゲート**。計画が通ったことは見た目が正しいことの証拠にならない |

計画が `ready` になっても、それは「数値の整合と保存則が守られている」という意味だけです。完成判定は `WORKFLOW.md` の第3節・第4節の目視確認で行います。
