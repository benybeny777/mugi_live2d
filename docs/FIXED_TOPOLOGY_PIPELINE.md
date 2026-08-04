# 固定トポロジー方式（A方式）

目的は、1体をGUI操作で無理に直すことではなく、品質確認済みのマスターリグへ同じ構造の絵を繰り返し適用できるようにすることです。

## 契約

- キャンバスは 2976×4175 px 固定です。
- レイヤー名、左右、描画順、目のクリッピング先を `pipeline/topology.mugi-hiyori-v1.json` で固定します。
- 生成AIや分割器の出力を直接Cubismへ渡しません。必ず固定トポロジーQAを通します。
- 顔、目、口、前髪、横髪、後髪の境界をマスター用マスクへ合わせます。絵柄の変更は許容しますが、パーツ境界は変更しません。
- Cubismでは、検証済みマスターCMO3へのPSD再インポート、テクスチャアトラス再配置、MOC3書き出しだけを決定的な最終工程にします。

## QA

```powershell
$python = 'C:\Users\benyb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python scripts/fixed_topology_qa.py work/psd/hiyori/layers `
  --json work/qa/fixed-topology-report.json `
  --html work/qa/fixed-topology-report.html
```

終了コード0だけを合格とします。現在の旧分割結果は、空の目・まつ毛・口レイヤーと小さすぎる顔が検出されるため不合格です。これはA方式の入力として再利用しません。

合格後は `viewer/` でSDK 5/4の実動作を確認します。READMEの動画は書き出したモデルをキャラクター単体で録画した回帰確認資料です。

## 再現手順

1. マスターリグと同じ正面姿勢・輪郭でキャラクター画像を生成または描画する。
2. 固定マスクで各PNGを作る。境界修正はマスク側へ反映し、個別のCubism頂点修正に逃がさない。
3. `fixed_topology_qa.py` を実行し、欠落、空レイヤー、最小寸法、包含、髪と首の重なりを検査する。
4. 合格PNGからPSDを生成する。
5. マスターCMO3へPSDを再インポートし、100%倍率・1〜2px余白でアトラスを再生成する。
6. MOC3を書き出し、`viewer/?demo=1` とパラメータQAで動作を確認する。

最初の3候補で毎回パーツ境界の手修正が必要なら、固定トポロジーに適合する画像生成条件が成立していないと判断し、See-through + Cubism AIの半自動方式へ切り替えます。
