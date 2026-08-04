# レイヤーsandbox方式（Photoshop生成塗りつぶし）

隠れた額、後髪、口内などを補完するために生成塗りつぶしを使うときの、GUI側と非GUI側の受け渡し契約です。

## なぜ必要か

`mugi-hiyori-compatible-clean.psd` は全レイヤーが「全キャンバス + レイヤーマスク」で構成されています。原PSDのレイヤーを選んでPhotoshopの生成塗りつぶしを実行すると、選択範囲がマスクではなく2976×4175pxのレイヤー全体になり、全画面へ模様が生成されます。2026-08-04にこれを実行して不合格となりました。原本は無変更で復元済みです。

そのためGUI側には原PSDを渡さず、マスクを焼き込んだ小さなPNGだけを渡します。

## 使い方

```powershell
$env:UV_CACHE_DIR = 'C:\00_PG\40_mugi_live2d\.uv-cache'
uv sync

# 1. レイヤー一覧
uv run python -m pipeline.sandbox list

# 2. sandbox書き出し（顔の例）
uv run python -m pipeline.sandbox export "/顔/顔" `
  --out work/sandbox --id face --grow 40 --margin 24

# 3. CodexがPhotoshopで生成し work/sandbox/face/filled.png を保存

# 4. 検査のみ（何も書き込まない）
uv run python -m pipeline.sandbox qa work/sandbox/face `
  --json work/qa/face-sandbox-qa.json

# 5. 目視レビュー後に元canvasへ戻す
uv run python -m pipeline.sandbox import work/sandbox/face `
  --out work/psd/hiyori/layers-completed/face.png --reviewed-by <名前>
```

`extract` は sandbox を作らずレイヤー単体を透明PNGにします。顔・後髪・前髪・横髪・口内など、どのレイヤーにも同じコマンドを使います。レイヤー不透明度は既定で無視するので、`口中` のように不透明度0で待機しているレイヤーも中身が取り出せます。

## sandboxの中身

| ファイル | 役割 |
| --- | --- |
| `base.png` | Photoshopで開く唯一のファイル。切り出し済みRGBA |
| `editable.png` | 生成してよい範囲。白がその範囲 |
| `locked.png` | 1pxも変えてはいけない範囲 |
| `manifest.json` | tight bbox、余白、戻し座標、canvas、全ファイルのSHA-256、許容値 |
| `filled.png` | Codexが保存する戻り値。`base.png` と同じ画素サイズのRGBA |

`manifest.json` の `sandbox.box` が元canvas上の切り出し矩形、`return.paste_origin` が戻し座標です。`source.psd_sha256` はexport時点の原PSDのハッシュで、importはこれが一致しないと中断します。同じ入力からexportを再実行すると、manifestも各PNGもバイト単位で同一になります（タイムスタンプを記録しないため）。

## 検査項目

| 検査 | 落とすもの |
| --- | --- |
| `inputs_intact` | sandbox入力自体の改変 |
| `return_size` | リサイズ、切り抜き、カンバス変更 |
| `locked_untouched` | 既存の絵の描き替え |
| `silhouette` | 生成範囲外へのはみ出し、既存画素の消去 |
| `colour_match` | 隣接する絵と続かない色 |
| `texture_flatness` | 布地、粒状、筆致などの捏造ディテール |
| `pattern_free` | 織り目のような繰り返し模様 |
| `alpha_solid` | 半透明のにじみ、まだらな透明境界 |

顔sandboxでの実測値です。

| 入力 | 色の外れ率 | Laplacian比 | 周期性 | 判定 |
| --- | --- | --- | --- | --- |
| 正しい端色の延長 | 0% | 1.15 | 0.29 | review_required |
| 布地模様（振幅18） | 0% | 7.73 | 0.80 | rejected |
| 薄い布地模様（振幅4） | 0% | 1.95 | 0.32 | rejected |

布地は平均色を保つので色検査だけでは通ります。`texture_flatness` と `pattern_free` の2つで捕まえます。この2つは合成した布地模様に対する回帰テストで固定しています（`tests/test_sandbox_qa.py` の `FabricRegressionTest`）。

## 自動合格させない

`qa` が返す最良の判定は `review_required` です。`approved` になるのは `import` に `--reviewed-by` で人の名前を渡したときだけで、全検査に通っていても名前がなければ何も書き込みません。検査に落ちた画像は `--reviewed-by` を付けても書き込みません。

閾値は保守的側に倒してあります。正当な生成結果が落ちることはありますが、その場合の代償は再生成であり、通してしまった場合の代償はモデルの作り直しです。閾値の変更はレビュー対象の変更として扱い、実測値を添えて `pipeline/sandbox/manifest.py` の `DEFAULT_TOLERANCES` を書き換えます。

## importの出力

importは原PSDを書き換えず、canvas全面の透明PNGを1枚出力します。それをレイヤーとしてPSDやCubismへ取り込む工程はGUI側の作業です。
