# 作業指示: むぎのテクスチャアトラス再生成

対象エージェント: Codex（Cubism Editor を PC 操作で動かす前提）
作成日: 2026-08-04
関連: [WORKFLOW.md](WORKFLOW.md) の「3. Cubismでリグを適用する」「4. 書き出しと組み込み」、[STATUS.md](STATUS.md)

---

## 1. 何が起きているか

書き出し済みテクスチャアトラスの中身が、シートのほぼ全面が透明という状態になっている。

| ファイル | 不透明率 |
|---|---|
| `exports/sdk5/mugi/mugi.4096/texture_00.png` | 0.11% |
| `exports/sdk5/mugi/mugi.4096/texture_01.png` | 0.79% |
| `exports/sdk5/mugi/mugi.4096/texture_02.png` | **0.00%（完全に空）** |

4096×4096 を 3 枚（計 5,033 万画素）使って、実際に絵がある画素は合計 15 万画素程度しかない。

個々のパーツもテクスチャ上で極端に小さい。

| パーツ | テクスチャ上の実サイズ |
|---|---|
| 顔の肌ベース | **91 × 105 px** |
| 胴体（最大パーツ） | 228 × 787 px |
| 髪の毛束 | 49 × 164 px 程度 |

モデルキャンバスは 2976 × 4175 なので、描画時に各パーツが 4〜7 倍へ引き伸ばされている。これが輪郭の甘さと、髪の縁に出ている赤茶のフリンジの原因。

`sdk4` 側も同じ数値。PicoAgent へ取り込んだものも同一（コピーは正常）。

## 2. 切り分け済み（調べ直さなくてよい）

- **元 PSD は正常**。`work/psd/hiyori/mugi-hiyori-compatible-final.psd` は 2976 × 4175 で、解像度不足ではない。
- **リグ本体は正常**。`moc3` は PicoAgent 側とハッシュ一致。
- **`physics3.json` / `cdi3.json` も正常**（内容は下の 5 章の注意を参照）。
- **PicoAgent への取り込み手順に問題はない**。原本の書き出し時点で既にこの状態。

つまり **Cubism のテクスチャアトラス生成そのものがおかしい**。パーツが極端に縮小された状態でアトラスへ配置されている。

## 3. 現状の計測方法（作業前後で必ず実行する）

PicoAgent に同梱の ImageMagick を使う（別途インストール不要）。

```powershell
$magick = "C:\00_PG\20_PicoAgent\src-tauri\resources\bundled\tools\imagemagick\magick.exe"
$dir = "C:\00_PG\40_mugi_live2d\exports\sdk5\mugi\mugi.4096"

# 各シートの不透明率
Get-ChildItem "$dir\texture_*.png" | ForEach-Object {
  $mean = & $magick $_.FullName -alpha extract -format "%[fx:mean]" info:
  "{0}: 不透明率={1:P2}" -f $_.Name, [double]$mean
}

# パーツごとの実サイズ（大きい順）
& $magick "$dir\texture_00.png" -alpha extract -threshold 5% `
  -define connected-components:verbose=true `
  -define connected-components:area-threshold=200 `
  -connected-components 8 null:
```

`connected-components` の出力は `番号: 幅x高さ+X+Y 重心 面積 色` の形式。`srgb(255,255,255)` の行が実際のパーツ。

## 4. やること

### 4-1. Cubism でアトラスを作り直す

1. Cubism Editor 5.3.03 で `work/cubism/mugi-hiyori-rigged-final.cmo3` を開く。
2. **開いた直後に、ベース表示が元絵と一致することを確認する**（WORKFLOW.md 3-1 と同じ。ここが崩れていたら以降の作業をしない）。
3. `モデリング` → `テクスチャアトラス編集` を開く。
4. 現状の配置を確認する。**パーツが極小で、シートの大部分が空いているはず**。ここが今回の不具合の現物。
5. 設定を次にして自動レイアウトをやり直す。
   - 幅 × 高さ: `4096 × 4096`
   - **倍率: 100%**（ここが今回の主因の可能性が高い。小さい値になっていたら必ず記録してから直す）
   - 余白: `1`〜`2` px
6. 自動レイアウト後、**シートが十分埋まっていることを目視で確認する**。まだスカスカなら倍率設定が効いていないので、パーツ個別の倍率設定を確認する。
7. 3 枚も要らなければシート数を減らす。逆に 4096 に収まらなければ枚数を増やしてよい（枚数より 1 パーツあたりの画素数を優先する）。

### 4-2. 物理演算に髪の設定を足す

現状の `physics3.json` は **「後ろ髪」1 本しか無い**。`ParamHairFront` / `ParamHairSide` / `ParamHairAhoge` が物理演算の対象外で、前髪・横髪・アホ毛が揺れない。

PicoAgent 側では JSON を直接編集して暫定対応済みだが、**このアトラス再書き出しで上書きされて消える**。Cubism の `物理演算・シーン別設定` で同じ内容を入れて、原本側を正とすること。

基準は公式ひよりモデルの同名設定。入力は 4 つとも共通で `ParamAngleX(X, 重み60)` / `ParamAngleZ(Angle, 重み60)` / `ParamBodyAngleX(X, 重み40)` / `ParamBodyAngleZ(Angle, 重み40)`。

| 設定名 | 出力パラメータ | 振り子の長さ | 揺れやすさ | 反応速度 | 揺れの大きさ | 出力倍率 |
|---|---|---|---|---|---|---|
| 後ろ髪（既存・変更不要） | `ParamHairBack` | 15 | 0.95 | 0.8 | 1.5 | 2.132 |
| 前髪（追加） | `ParamHairFront` | 3 | 0.95 | 0.9 | 1.5 | 1.522 |
| 横髪（追加） | `ParamHairSide` | 8 | 0.95 | 0.85 | 1.5 | 1.8 |
| アホ毛（追加） | `ParamHairAhoge` | 5 | 1.0 | 0.5 | 2.0 | 3.0 |

アホ毛だけは入力の重みを `ParamAngle* = 70` / `ParamBodyAngle* = 30` にする（体より頭の動きに強く反応させる）。

### 4-3. 書き出し

WORKFLOW.md 4 章のとおり。

1. SDK 5 向けを `exports/sdk5/` へ書き出す。
2. SDK 4 互換向けを `exports/sdk4/` へ書き出す。
3. `C:\00_PG\30_live\.venv\Scripts\python.exe scripts\sanitize_export_textures.py exports\sdk5 exports\sdk4` を実行する。完全透明画素に残る RGB を消して、WebGL でのアトラス境界漏れを防ぐ。

**アトラスを作り直すと UV が変わるため、`moc3` も必ず再書き出しすること。** PNG だけ差し替えても直らない。

## 5. 受け入れ基準

作業前後で 3 章の計測を実行し、次を満たすこと。

- [ ] `texture_00` / `texture_01` の不透明率が **合計 15% 以上**（現状 0.9%）。
- [ ] **空のシートが 1 枚も無い**（現状 `texture_02` が 0.00%）。使わないシートは書き出さない。
- [ ] **顔の肌ベースがテクスチャ上で高さ 700px 以上**（現状 105px）。`connected-components` の最大級の領域で確認する。
- [ ] `sdk4` / `sdk5` の両方で満たすこと。
- [ ] `model3.json` から参照されるテクスチャ・`moc3`・`physics3.json` に参照切れが無いこと。
- [ ] `physics3.json` の `PhysicsDictionary` に **後ろ髪・前髪・横髪・アホ毛の 4 つ**が入っていること。

### 目視確認（`viewer/` を使う）

`viewer/launch-viewer.vbs` をダブルクリックして、SDK 5 / SDK 4 の両方で確認する。

- [ ] 髪の輪郭に穴・二重像・背景色の細線が出ない（STATUS.md の既知課題）。
- [ ] 前髪・横髪・後髪・アホ毛が**それぞれ別のタイミングで**揺れる（1 本しか揺れていないなら 4-2 が入っていない）。
- [ ] まばたきで白目・瞳が残らない。
- [ ] 口開閉で閉口時に口中が見えない。
- [ ] 拡大表示にしても輪郭が破綻しない（今回の主目的）。

## 6. PicoAgent への組み込み

反映先: `C:\00_PG\20_PicoAgent\characters\mugi\live2d\{sdk4,sdk5}\`

### 上書きしてはいけないもの

`characters/mugi/live2d/{sdk4,sdk5}/motions/mugi_idle.motion3.json` は **PicoAgent 側で作ったファイルで、原本には存在しない**。書き出し結果で消さないこと。

このモーションからは、次の理由で意図的に曲線を除去済み。**再生成・復元しないこと。**

- `ParamEyeLOpen` / `ParamEyeROpen`: 4.7 秒ループ中 t=1.80 / t=3.60 の完全な等間隔まばたきが入っており、機械的だった。まばたきは SDK の `EyeBlink` に任せる。
- `ParamHairAhoge`: ±10 の粗いキーフレームが入っていた。アホ毛は 4-2 の物理演算に任せる。

`model3.json` は原本側に `FileReferences.Motions`（Idle / TapBody）が無いため、書き出し結果をそのまま上書きすると**モーション参照が消える**。PicoAgent 側の `Motions` セクションを維持してマージすること。

### 反映後の確認

```powershell
cd C:\00_PG\20_PicoAgent
cargo xtask dev
```

- [ ] むぎが表示され、拡大表示でも輪郭が破綻しない。
- [ ] 髪 4 種がそれぞれ揺れる。
- [ ] まばたきが等間隔でなく、不規則な間隔で起きる。
- [ ] 読み上げ時に口が動く。

## 7. この PC の環境メモ

**WORKFLOW.md の「作業モニター」の記載は実機と食い違っている。** GUI 操作の座標指定では実測値を使うこと。

実測（DPI 対応プロセスで `EnumDisplayMonitors` / `GetMonitorInfo` を実行した結果）:

```
\\.\DISPLAY1: (0,0)    1920x1200  [PRIMARY]   ← 左。ここで作業する
\\.\DISPLAY5: (1920,0) 2560x1440              ← 右。動画視聴中なので触らない
```

WORKFLOW.md には `(-1920, 0) - (0, 1080)` とあるが、現在の構成では主モニタが左の 1920×1200 で、仮想デスクトップに負の座標は存在しない。**DPI 非対応プロセスから `System.Windows.Forms.Screen` で座標を取ると 1920 ずれた値が返るので使わないこと。**

Cubism・Photoshop・確認用ウィンドウはすべて左（DISPLAY1）に出す。

## 8. 完了時にやること

1. `STATUS.md` の完了項目・未確認項目を更新する。
2. `WORKFLOW.md` のモニター記載を実測値へ直す（7 章）。テクスチャアトラスの倍率設定も手順へ明記する。
3. 目視確認画像は `qa/` に置く（Git 管理外）。作業中の一時ファイルは `temp/` のみ。
4. 変更した Cubism ファイル・書き出し・手順書を同じコミットに含める。
5. PicoAgent 側の反映は別リポジトリなので、そちらでも commit / push する。
