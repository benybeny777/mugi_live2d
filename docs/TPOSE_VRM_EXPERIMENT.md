# Tポーズ VRM 分割実験

腕を自然に動かせる平面VRMを検証するため、同一のTポーズ原画だけから6パーツを決定的に抽出する実験です。既存のLive2D、VRM、PicoAgentパーツは再利用しません。

## 入力と拡大

- 原画: `work/psd/tpose/mugi-tpose-source-v1.png`
- 高解像度化: デスクトップ版 Photoshop の「ディテールを保持 2.0」のみ
- 作業PSD: `work/psd/tpose/mugi-tpose-source-v1-photoshop-pd2.psd`
- 寸法: 730 x 1024 から 2920 x 4096

生成AI、ブラウザー、Pillow、ImageMagick、OS APIによる拡大は使用しません。

## 分割方針

`pipeline/tpose_vrm_layers.py` が高解像度原画から頭、胴体、左右の腕、左右の脚を抽出します。白背景は連結領域と白マット補正で除去し、切り出し座標は2920 x 4096の基準キャンバスに対する比率で管理します。

肩は腕側と胴体側に隠し重なりを持たせ、腕を胴体の背面へ配置します。これにより腕を下げても肩に穴が開かず、外側に二重の袖輪郭を作りません。パーツ画像には透明余白を追加し、テクスチャ端のクランプも避けます。

## 再生成と確認

```powershell
uv run python -m scripts.build_tpose_vrm_experiment
uv run python -m scripts.validate_vrm temp/mugi-tpose-experiment.vrm
uv run pytest -q tests/test_tpose_vrm_layers.py tests/test_vrm_viewer.py
```

ローカル表示は `http://127.0.0.1:8765/vrm-viewer/index.html?model=tpose` を使います。Tポーズだけでなく、腕を下げた検査姿勢でも肩の穴、背景縁、二重線を確認します。

## 現在の判定

腕の分離と肩の重なり方式は採用候補です。現在の実験VRMは6メッシュで、顔の表情用パーツはまだ分割していません。正式版 `exports/vrm/mugi.vrm` は置き換えていません。
