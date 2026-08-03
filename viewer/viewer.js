"use strict";

const runtimeScripts = ["vendor/live2dcubismcore.min.js", "vendor/pixi.min.js", "vendor/cubism4.min.js"];
const parameterIds = {
  eyeL: ["ParamEyeLOpen", "PARAM_EYE_L_OPEN"], eyeR: ["ParamEyeROpen", "PARAM_EYE_R_OPEN"],
  mouth: ["ParamMouthOpenY", "PARAM_MOUTH_OPEN_Y"], hairFront: ["ParamHairFront", "PARAM_HAIR_FRONT"],
  hairSide: ["ParamHairSide", "PARAM_HAIR_FLUFFY"], hairBack: ["ParamHairBack", "PARAM_HAIR_BACK"],
};
let app, model, runtimeReady;
let baseScale = 1, autoBlink = true, hairMotion = true, blinkUntil = 0;
const $ = id => document.getElementById(id);
const log = message => {
  const stamp = new Date().toLocaleTimeString("ja-JP", { hour12: false });
  $("log").textContent = `[${stamp}] ${message}\n${$("log").textContent}`.slice(0, 5000);
};

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script"); script.src = src; script.onload = resolve;
    script.onerror = () => reject(new Error(`${src} を読み込めません`)); document.head.appendChild(script);
  });
}
async function ensureRuntime() {
  if (window.PIXI?.live2d?.Live2DModel) return;
  runtimeReady ||= (async () => { for (const script of runtimeScripts) await loadScript(script); PIXI.live2d.config.sound = false; })();
  await runtimeReady;
}
function resizeStage() {
  if (!app) return;
  const stage = $("stage"); app.renderer.resize(stage.clientWidth, stage.clientHeight);
  if (!model) return;
  const width = model.internalModel.originalWidth, height = model.internalModel.originalHeight;
  baseScale = Math.min(stage.clientWidth / (width * 1.05), stage.clientHeight / (height * 0.58));
  model.scale.set(baseScale * Number($("zoom").value)); model.anchor.set(0.5, 0);
  model.position.set(stage.clientWidth / 2, Number($("offset").value) - height * baseScale * 0.015);
}
function setParameter(ids, value) {
  if (!model) return;
  for (const id of ids) { try { model.internalModel.coreModel.setParameterValueById(id, value); } catch (_) { /* compatibility alias */ } }
}
function parameterCount() {
  const core = model?.internalModel?.coreModel;
  return core?.parameters?.count ?? core?._model?.parameters?.count ?? "確認不可";
}
async function loadModel() {
  $("status").className = "status waiting"; $("status").textContent = "読込中";
  try {
    await ensureRuntime();
    if (model) { app.stage.removeChild(model); model.destroy(); }
    if (!app) {
      app = new PIXI.Application({ width: $("stage").clientWidth, height: $("stage").clientHeight, backgroundAlpha: 0, antialias: true, resolution: window.devicePixelRatio || 1, autoDensity: true });
      $("stage").appendChild(app.view); app.ticker.add(updateParameters);
    }
    const path = $("modelPath").value.trim();
    model = await PIXI.live2d.Live2DModel.from(path, { autoInteract: false }); app.stage.addChild(model); resizeStage();
    $("loadedFormat").textContent = $("sdk").value.toUpperCase();
    $("dimensions").textContent = `${model.internalModel.originalWidth} × ${model.internalModel.originalHeight}`;
    $("parameterCount").textContent = parameterCount(); $("status").className = "status ready"; $("status").textContent = "正常";
    log(`読込成功: ${path}`);
  } catch (error) {
    $("status").className = "status error"; $("status").textContent = "失敗"; log(`読込失敗: ${error.message || error}`);
  }
}
function updateParameters() {
  if (!model) return;
  const now = performance.now(), cycle = now % 4200, automaticClose = autoBlink && cycle > 3650 && cycle < 3810;
  const eyes = (automaticClose || now < blinkUntil) ? 0 : 1;
  setParameter(parameterIds.eyeL, eyes); setParameter(parameterIds.eyeR, eyes); setParameter(parameterIds.mouth, Number($("mouth").value));
  if (hairMotion) {
    const seconds = now / 1000;
    setParameter(parameterIds.hairFront, Math.sin(seconds * 1.25) * 0.45);
    setParameter(parameterIds.hairSide, Math.sin(seconds * 1.05 + 1.1) * 0.5);
    setParameter(parameterIds.hairBack, Math.sin(seconds * 0.9 + 2.0) * 0.4);
  }
}

$("sdk").addEventListener("change", event => { $("modelPath").value = `/exports/${event.target.value}/mugi/mugi.model3.json`; });
$("load").addEventListener("click", loadModel); $("blink").addEventListener("click", () => { blinkUntil = performance.now() + 220; });
$("blinkAuto").addEventListener("click", event => { autoBlink = !autoBlink; event.target.classList.toggle("active", autoBlink); event.target.textContent = `自動まばたき ${autoBlink ? "ON" : "OFF"}`; });
$("hair").addEventListener("click", event => { hairMotion = !hairMotion; event.target.classList.toggle("active", hairMotion); event.target.textContent = `髪揺れ ${hairMotion ? "ON" : "OFF"}`; });
$("reset").addEventListener("click", () => {
  $("mouth").value = 0; $("zoom").value = 1; $("offset").value = 0; $("mouthValue").value = "0.00"; $("zoomValue").value = "1.00"; $("offsetValue").value = "0"; resizeStage();
});
for (const id of ["mouth", "zoom", "offset"]) {
  $(id).addEventListener("input", event => { const value = Number(event.target.value); $(`${id}Value`).value = id === "offset" ? String(value) : value.toFixed(2); if (id !== "mouth") resizeStage(); });
}
$("stage").addEventListener("pointermove", event => { if (!model) return; const rect = $("stage").getBoundingClientRect(); model.focus(event.clientX - rect.left, event.clientY - rect.top); });
window.addEventListener("resize", resizeStage); loadModel();
