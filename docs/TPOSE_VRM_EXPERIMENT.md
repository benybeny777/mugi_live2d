# Tポーズ VRM 制作記録

腕と表情を自然に動かせる平面VRMとして、同一のTポーズ原画だけから17パーツを決定的に抽出します。既存のLive2D、VRM、PicoAgentパーツは再利用しません。

## 入力と拡大

- 原画: `work/psd/tpose/mugi-tpose-source-v1.png`
- 高解像度化: デスクトップ版 Photoshop の「ディテールを保持 2.0」のみ
- 作業PSD: `work/psd/tpose/mugi-tpose-source-v1-photoshop-pd2.psd`
- 寸法: 730 x 1024 から 2920 x 4096

生成AI、ブラウザー、Pillow、ImageMagick、OS APIによる拡大は使用しません。

## 分割方針

`pipeline/tpose_vrm_layers.py` が高解像度原画から頭、胴体、左右の腕、左右の肩下地、左右の脚、左右の白目・虹彩・まつ毛、口と口内を抽出します。白背景は連結領域と白マット補正で除去し、切り出し座標は2920 x 4096の基準キャンバスに対する比率で管理します。

肩は同じ原画から抽出した丸い下地を胴体固定で腕の背面へ置き、腕側と胴体側にも隠し重なりを持たせます。顔は元の目と口を局所補完した下地の上へ、同じ原画から抽出した可動パーツを重ねます。これにより腕を下げても肩に穴が開かず、自動モーションを切っても目が二重になりません。

## 再生成と確認

```powershell
uv run python -m scripts.build_tpose_vrm_experiment
uv run python -m scripts.validate_vrm exports/vrm/mugi.vrm
uv run python -m scripts.validate_vrm_release
uv run pytest -q
```

ローカル表示は `http://127.0.0.1:8765/vrm-viewer/index.html` を使います。`?model=tpose` は正式版を更新する前の一時確認用です。

## 現在の判定

腕の分離と肩下地方式は、約60度まで腕を下げた実機表示で穴、白縁、二重輪郭がないことを確認しました。まばたき、左右独立まばたき、視線4方向、5母音、happy / angry / sad / relaxed / surprised、カスタム4表情も全て空でないモーフへ接続し、正式版 `exports/vrm/mugi.vrm` へ昇格しました。
