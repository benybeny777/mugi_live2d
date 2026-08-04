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
  --out work/sandbox --id face --region face_oval --grow 12 --margin 24

# 3. CodexがPhotoshopで生成し work/sandbox/face/filled.png を保存

# 4. 検査のみ（何も書き込まない）
uv run python -m pipeline.sandbox qa work/sandbox/face `
  --json work/qa/face-sandbox-qa.json

# 5. 目視レビュー後に元canvasへ戻す
uv run python -m pipeline.sandbox import work/sandbox/face `
  --out work/psd/hiyori/layers-completed/face.png --reviewed-by <名前>
```

`extract` は sandbox を作らずレイヤー単体を透明PNGにします。顔・後髪・前髪・横髪・口内など、どのレイヤーにも同じコマンドを使います。レイヤー不透明度は既定で無視するので、`口中` のように不透明度0で待機しているレイヤーも中身が取り出せます。

## 2種類の埋め方（fill_mode）

manifestの `sandbox.fill_mode` が、その sandbox がどちらの作業かを宣言します。検査のうち `colour_match` だけがこれを読みます。

| mode | 生成範囲 | 色の基準 | 使う場面 |
| --- | --- | --- | --- |
| `extend` | 既存シルエットの外側 `grow` px のリング | 隣接している既存の絵の色 | 輪郭を少し伸ばす |
| `underlay` | 固定形状のうちレイヤーが未到達の部分＋その隙間が必要とする外側の縫い代 | レイヤーのベース色（`sandbox.base_colour`） | 既存の絵の**下**に下地を敷く |

顔は `underlay` です。前髪に隠れて額が存在しないので、既存の縁から何px広げてもそこには届きません。`--region face_oval` で固定トポロジー契約の顔楕円を境界にします。

境界は `pipeline/topology.mugi-hiyori-v2.json` の `calibration.face_oval_source`（= `[1302, 282, 1669, 838]`）から読みます。同ファイルの `frame.face_oval` はリターゲット後のcanvas座標なので、現行の `mugi-hiyori-compatible-clean.psd` に当てるとcalibration倍率ぶんずれます。使いません。

`--region` を付けない場合は従来どおり `extend` です。

## GUI側の手順（underlay / 顔）

`manifest.json` の `rules` に同じことが英語で入っています。数値はすべて再export後の実測値です。

1. `work/sandbox/face/base.png` と `work/sandbox/face/editable.png` の2枚だけを開きます。原PSDは開きません。
2. `base.png` をアクティブにして「選択範囲 > 選択範囲を読み込む」、ソース書類に `editable.png` を選びます。これが生成可能な全範囲です（80155px）。
3. 既存レイヤーの**下**に新規レイヤーを作ります。
4. 選択範囲を `sandbox.base_colour` の色で塗りつぶします（`#FEEFDB`）。1色のみで、輪郭線・縁の陰・グラデーション・ハイライトは描きません。縁取りは上のレイヤーに既にあります。
5. 楕円を描き足したり、選択範囲を広げたり、「見栄えのために」形を大きくしたりはしません。選択範囲の外に出た画素はすべて `silhouette` で落ちます。
6. `filled.png` としてPNG書き出し（透明度あり、100%、437×627px）。書き出し時のflattenは想定内です。`base.png` は上書きしません。

`--region face_oval` を使うと、生成範囲は「顔楕円のうちレイヤーが未到達の部分」＋「その隙間が楕円の外側で必要とする縫い代 `--grow` px」だけになります。既に描き上がっている輪郭にはリングが付かないので、シルエットが外側へ育つことはありません。

## sandboxの中身

| ファイル | 役割 |
| --- | --- |
| `base.png` | Photoshopで開く唯一のファイル。切り出し済みRGBA |
| `editable.png` | 生成してよい範囲。白がその範囲 |
| `locked.png` | 1pxも変えてはいけない範囲 |
| `manifest.json` | tight bbox、余白、戻し座標、canvas、全ファイルのSHA-256、許容値 |
| `filled.png` | Codexが保存する戻り値。`base.png` と同じ画素サイズのRGBA |

`manifest.json` の `sandbox.box` が元canvas上の切り出し矩形、`return.paste_origin` が戻し座標です。`sandbox.region.box` と `sandbox.base_colour` は **sandbox内のローカル座標と色** なので、GUI側はcanvas座標へ換算する必要がありません。`source.psd_sha256` はexport時点の原PSDのハッシュで、importはこれが一致しないと中断します。同じ入力からexportを再実行すると、manifestも各PNGもバイト単位で同一になります（タイムスタンプを記録しないため）。

## 検査項目

| 検査 | 落とすもの |
| --- | --- |
| `inputs_intact` | sandbox入力自体の改変 |
| `return_size` | リサイズ、切り抜き、カンバス変更 |
| `locked_untouched` | 既存の絵の描き替え |
| `silhouette` | 生成範囲外へのはみ出し、既存画素の消去 |
| `colour_match` | `extend` は隣接する絵と続かない色、`underlay` はレイヤーのベース色から外れた色 |
| `texture_flatness` | 布地、粒状、筆致などの捏造ディテール |
| `pattern_free` | 織り目のような繰り返し模様 |
| `alpha_solid` | 半透明のにじみ、まだらな透明境界 |

顔sandbox（`extend`読み）での実測値です。

| 入力 | 色の外れ率 | Laplacian比 | 周期性 | 判定 |
| --- | --- | --- | --- | --- |
| 正しい端色の延長 | 0% | 1.15 | 0.29 | review_required |
| 布地模様（振幅18） | 0% | 7.73 | 0.80 | rejected |
| 薄い布地模様（振幅4） | 0% | 1.95 | 0.32 | rejected |

布地は平均色を保つので色検査だけでは通ります。`texture_flatness` と `pattern_free` の2つで捕まえます。この2つは合成した布地模様に対する回帰テストで固定しています（`tests/test_sandbox_qa.py` の `FabricRegressionTest`）。

## underlayでcolour_matchが誤判定していた件（2026-08-04）

Photoshopで既存FaceBaseの**下**に肌色 `#FAEBD7` の楕円を敷いた戻り値が、色は正しいのに `colour_match` で落ちました。`fill_rgb` も `art_rgb` も `[250, 235, 215]` なのに `distance_median=74.148`、外れ率97.6%です。

演算ではなく比較対象の問題でした。`colour_match` は各生成画素を**最も近い不透明な既存画素**と比べます。顔レイヤーは全周が絵として描かれた髪色の縁取りで、深さ20px前後あります。肌を正しく延長した下地はその縁取りに四方で接するので、絵の側の中央値ではなく縁の色（最近傍色の中央値は `[237, 187, 160]`、p95距離235）と比較され、**通すべき唯一の色を落としていた**ことになります。レポートの `art_rgb` はレイヤー全体の中央値だったため、数字が矛盾して見えていました。

`underlay` ではレイヤーのベース色と比べます。ベース色は不透明画素を16px内側へ侵食した位置の中央値で、縁取りも透明画素もアンチエイリアス画素も入りません。`extend` は従来どおり最近傍色のままです（単一基準色にすると、髪色の顔縁を正しく延長した結果が200単位の誤差として落ちます）。

同じ画像・同じPSDでの実測です。

| | 旧 `extend` 読み | 新 `underlay` 読み |
| --- | --- | --- |
| `colour_match` | rejected | ok |
| `distance_median` | 74.148 | 6.928 |
| `distance_p95` | 234.139 | 6.928 |
| 外れ率 | 97.6% | 0.0% |
| `art_rgb` | `[250, 235, 215]`（レイヤー中央値・実際の比較相手ではない） | `[254, 239, 219]`（ベース色・実際の比較相手） |

## 2026-08-04の戻り値の判定

再exportした顔sandboxで再検査した結果は **rejected（`silhouette`のみ）** です。`review_required` にはしません。

| | 値 |
| --- | --- |
| 契約の顔楕円（sandboxローカル） | `(35, 36, 402, 592)` |
| 実際に描かれた楕円 | `(13, 0, 423, 611)` |
| はみ出し 左/上/右/下 | 22 / 36以上 / 21 / 19 px |
| `silhouette` spill | 22636 px |
| `locked_untouched` | 0 / 70264 変更 |
| `colour_match` | ok（上表） |

色・平坦さ・周期性・アルファはすべて合格で、落ちているのは形だけです。楕円が契約の顔楕円より全周で約20px大きく、上辺は40px以上高い位置にあります。生成物ではなく手描きの楕円なので、選択範囲どおりに描き直せば通ります。

石材状・布地状の生成結果は引き続き拒否します。`UnderlayTest` に、下地としての石材色（`colour_match`）と織り目（`texture_flatness` + `pattern_free`）の両方を固定しています。

## 自動合格させない

`qa` が返す最良の判定は `review_required` です。`approved` になるのは `import` に `--reviewed-by` で人の名前を渡したときだけで、全検査に通っていても名前がなければ何も書き込みません。検査に落ちた画像は `--reviewed-by` を付けても書き込みません。

閾値は保守的側に倒してあります。正当な生成結果が落ちることはありますが、その場合の代償は再生成であり、通してしまった場合の代償はモデルの作り直しです。閾値の変更はレビュー対象の変更として扱い、実測値を添えて `pipeline/sandbox/manifest.py` の `DEFAULT_TOLERANCES` を書き換えます。

## importの出力

importは原PSDを書き換えず、canvas全面の透明PNGを1枚出力します。それをレイヤーとしてPSDやCubismへ取り込む工程はGUI側の作業です。
