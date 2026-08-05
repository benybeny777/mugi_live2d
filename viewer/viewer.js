"use strict";

const runtimeScripts = ["vendor/live2dcubismcore.min.js", "vendor/pixi.min.js", "vendor/cubism4.min.js"];
const viewerVersion = "27";
const pageOptions = new URLSearchParams(location.search);
const demoMode = pageOptions.get("demo") === "1";
const noMaskDiagnostic = pageOptions.get("nomask") === "1";
const irisOnlyDiagnostic = pageOptions.get("iris") === "1";
const parameterIds = {
  eyeL: ["ParamEyeLOpen", "PARAM_EYE_L_OPEN"], eyeR: ["ParamEyeROpen", "PARAM_EYE_R_OPEN"],
  mouth: ["ParamMouthOpenY", "PARAM_MOUTH_OPEN_Y"], hairFront: ["ParamHairFront", "PARAM_HAIR_FRONT"],
  hairSide: ["ParamHairSide", "PARAM_HAIR_FLUFFY"], hairBack: ["ParamHairBack", "PARAM_HAIR_BACK"],
  hairAhoge: ["ParamHairAhoge"],
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
  runtimeReady ||= (async () => {
    for (const script of runtimeScripts) await loadScript(script);
    PIXI.settings.SCALE_MODE = PIXI.SCALE_MODES.LINEAR;
    PIXI.settings.MIPMAP_TEXTURES = PIXI.MIPMAP_MODES.OFF;
    PIXI.live2d.config.sound = false;
  })();
  await runtimeReady;
}
function resizeStage() {
  if (!app) return;
  const stage = $("stage"); app.renderer.resize(stage.clientWidth, stage.clientHeight);
  if (!model) return;
  const width = model.internalModel.originalWidth, height = model.internalModel.originalHeight;
  baseScale = stage.clientHeight / (height * 0.40);
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
function drawableDiagnostics() {
  const core = model?.internalModel?.coreModel;
  const drawables = core?.drawables ?? core?._model?.drawables;
  const parts = core?.parts ?? core?._model?.parts;
  const counts = Array.from(drawables?.vertexCounts ?? []);
  const ids = Array.from(drawables?.ids ?? []);
  const textureIndices = Array.from(drawables?.textureIndices ?? []);
  const renderOrders = Array.from(core?._model?.renderOrders ?? core?.renderOrders ?? []);
  const drawOrders = Array.from(drawables?.drawOrders ?? []);
  const opacities = Array.from(drawables?.opacities ?? []);
  const maskCounts = Array.from(drawables?.maskCounts ?? []);
  const constantFlags = Array.from(drawables?.constantFlags ?? []);
  const dynamicFlags = Array.from(drawables?.dynamicFlags ?? []);
  const parentPartIndices = Array.from(drawables?.parentPartIndices ?? []);
  const partIds = Array.from(parts?.ids ?? []);
  const bounds = values => {
    const xs = [], ys = [];
    for (let offset = 0; offset + 1 < values.length; offset += 2) {
      xs.push(values[offset]); ys.push(values[offset + 1]);
    }
    return xs.length ? {
      minX: Math.min(...xs), minY: Math.min(...ys),
      maxX: Math.max(...xs), maxY: Math.max(...ys),
    } : null;
  };
  const entries = counts.map((vertexCount, index) => ({
    index,
    id: String(ids[index] ?? `#${index}`),
    vertexCount,
    textureIndex: textureIndices[index] ?? null,
    renderOrder: renderOrders[index] ?? null,
    drawOrder: drawOrders[index] ?? null,
    opacity: opacities[index] ?? null,
    maskCount: maskCounts[index] ?? 0,
    masks: Array.from(drawables?.masks?.[index] ?? []),
    constantFlag: constantFlags[index] ?? 0,
    dynamicFlag: dynamicFlags[index] ?? 0,
    parentPartIndex: parentPartIndices[index] ?? null,
    parentPartId: partIds[parentPartIndices[index]] ? String(partIds[parentPartIndices[index]]) : null,
    positionBounds: bounds(Array.from(drawables?.vertexPositions?.[index] ?? [])),
    uvBounds: bounds(Array.from(drawables?.vertexUvs?.[index] ?? [])),
  }));
  return {
    total: drawables?.count ?? counts.length,
    empty: counts.filter(count => count === 0).length,
    flat: counts.filter(count => count === 4).length,
    entries,
  };
}

function affineTriangle(source, target) {
  const [s0, s1, s2] = source, [d0, d1, d2] = target;
  const denominator = s0.x * (s1.y - s2.y) + s1.x * (s2.y - s0.y) + s2.x * (s0.y - s1.y);
  if (Math.abs(denominator) < 1e-9) return null;
  const solve = key => ({
    x: (d0[key] * (s1.y - s2.y) + d1[key] * (s2.y - s0.y) + d2[key] * (s0.y - s1.y)) / denominator,
    y: (d0[key] * (s2.x - s1.x) + d1[key] * (s0.x - s2.x) + d2[key] * (s1.x - s0.x)) / denominator,
    c: (d0[key] * (s1.x * s2.y - s2.x * s1.y) + d1[key] * (s2.x * s0.y - s0.x * s2.y) + d2[key] * (s0.x * s1.y - s1.x * s0.y)) / denominator,
  });
  const horizontal = solve("x"), vertical = solve("y");
  return [horizontal.x, vertical.x, horizontal.y, vertical.y, horizontal.c, vertical.c];
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image(); image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`部位PNGを読み込めません: ${url}`)); image.src = url;
  });
}

function alphaBounds(image, crop) {
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", {willReadFrequently: true});
  context.drawImage(image, 0, 0);
  const [x0, y0, x1, y1] = crop.map(Math.round);
  const pixels = context.getImageData(x0, y0, x1 - x0, y1 - y0);
  let minX = x1, minY = y1, maxX = x0, maxY = y0;
  for (let y = 0; y < pixels.height; y += 1) {
    for (let x = 0; x < pixels.width; x += 1) {
      if (pixels.data[(y * pixels.width + x) * 4 + 3] <= 8) continue;
      minX = Math.min(minX, x0 + x); minY = Math.min(minY, y0 + y);
      maxX = Math.max(maxX, x0 + x + 1); maxY = Math.max(maxY, y0 + y + 1);
    }
  }
  return maxX > minX && maxY > minY ? [minX, minY, maxX, maxY] : null;
}

async function buildFixedAtlas() {
  if (!model) throw new Error("先にHiyori原本MOCを読み込んでください");
  const manifestUrl = $("partsManifest").value.trim();
  const response = await fetch(manifestUrl);
  if (!response.ok) throw new Error(`manifestの読込に失敗しました: HTTP ${response.status}`);
  const manifest = await response.json();
  const base = new URL(".", new URL(manifestUrl, location.href));
  const images = {};
  for (const [partId, item] of Object.entries(manifest.parts)) images[partId] = await loadImage(new URL(item.file, base).href);
  const referenceTexture = await loadImage($("referenceTexture").value.trim());

  const core = model.internalModel.coreModel;
  const drawables = core.drawables ?? core._model.drawables;
  const parts = core.parts ?? core._model.parts;
  const partIds = Array.from(parts.ids ?? []);
  const size = 2048, width = manifest.canvas.width, height = manifest.canvas.height;
  const pixelsPerUnit = width, centerX = width * 0.5, centerY = height * 0.5;
  const modelPoint = (positions, index) => ({
    x: centerX + positions[index * 2] * pixelsPerUnit,
    y: centerY - positions[index * 2 + 1] * pixelsPerUnit,
  });
  // Body and facial plates must be fitted to the corresponding master-rig
  // envelope. Hair is deliberately not scaled to Hiyori's long-hair bounds:
  // keeping Mugi's bob silhouette is part of the character identity.
  const fittedParts = new Set([
    "PartBrow", "PartNose", "PartFace", "PartEar", "PartNeck", "PartBody", "PartArmA",
  ]);
  const topAlignedParts = new Set(["PartHairBack", "PartHairSide", "PartHairFront"]);
  const referenceParts = new Set(["PartCheek", "PartEyeBall", "PartEye", "PartMouth"]);
  const targetBounds = {};
  const drawableBounds = {};
  for (let drawableIndex = 0; drawableIndex < drawables.count; drawableIndex += 1) {
    const partId = String(partIds[drawables.parentPartIndices[drawableIndex]] ?? "");
    const positions = drawables.vertexPositions[drawableIndex];
    for (let vertexIndex = 0; vertexIndex < positions.length / 2; vertexIndex += 1) {
      const point = modelPoint(positions, vertexIndex);
      const bounds = targetBounds[partId] ||= {minX: point.x, minY: point.y, maxX: point.x, maxY: point.y};
      bounds.minX = Math.min(bounds.minX, point.x); bounds.minY = Math.min(bounds.minY, point.y);
      bounds.maxX = Math.max(bounds.maxX, point.x); bounds.maxY = Math.max(bounds.maxY, point.y);
      const drawableId = String(drawables.ids[drawableIndex]);
      const drawableBox = drawableBounds[drawableId] ||= {minX: point.x, minY: point.y, maxX: point.x, maxY: point.y};
      drawableBox.minX = Math.min(drawableBox.minX, point.x); drawableBox.minY = Math.min(drawableBox.minY, point.y);
      drawableBox.maxX = Math.max(drawableBox.maxX, point.x); drawableBox.maxY = Math.max(drawableBox.maxY, point.y);
    }
  }
  const hairSourceBox = manifest.parts.PartHairBack?.bbox;
  const hairTargetBox = targetBounds.PartHairBack;
  const hairSourceCenterX = hairSourceBox ? (hairSourceBox[0] + hairSourceBox[2]) * 0.5 : 0;
  const hairTargetCenterX = hairTargetBox ? (hairTargetBox.minX + hairTargetBox.maxX) * 0.5 : 0;
  const bodySourceBox = manifest.parts.PartBody?.bbox;
  const lowerBodyStart = bodySourceBox ? bodySourceBox[1] + (bodySourceBox[3] - bodySourceBox[1]) * 0.46 : 0;
  const lowerBodyGroups = [
    {ids: new Set(["ArtMesh69", "ArtMesh70", "ArtMesh74"]), side: [0, manifest.canvas.width * 0.5]},
    {ids: new Set(["ArtMesh71", "ArtMesh72", "ArtMesh73"]), side: [manifest.canvas.width * 0.5, manifest.canvas.width]},
  ].map(group => {
    const boxes = [...group.ids].map(id => drawableBounds[id]).filter(Boolean);
    return {
      ...group,
      source: alphaBounds(images.PartBody, [group.side[0], lowerBodyStart, group.side[1], manifest.canvas.height]),
      target: boxes.length ? {
        minX: Math.min(...boxes.map(box => box.minX)), minY: Math.min(...boxes.map(box => box.minY)),
        maxX: Math.max(...boxes.map(box => box.maxX)), maxY: Math.max(...boxes.map(box => box.maxY)),
      } : null,
    };
  });
  const canvas = document.createElement("canvas"); canvas.width = size; canvas.height = size;
  const context = canvas.getContext("2d"); context.clearRect(0, 0, size, size);
  context.drawImage(referenceTexture, 0, 0, size, size);

  let triangles = 0, skipped = 0;
  for (let drawableIndex = 0; drawableIndex < drawables.count; drawableIndex += 1) {
    const parentIndex = drawables.parentPartIndices[drawableIndex];
    const partId = String(partIds[parentIndex] ?? "");
    const drawableId = String(drawables.ids[drawableIndex]);
    const sourceImage = images[partId];
    const sourceBounds = manifest.parts[partId]?.bbox;
    const targetBox = targetBounds[partId];
    if (referenceParts.has(partId)) { skipped += 1; continue; }
    if (!sourceImage || !sourceBounds || !targetBox) { skipped += 1; continue; }
    const positions = drawables.vertexPositions[drawableIndex];
    const uvs = drawables.vertexUvs[drawableIndex];
    const indices = drawables.indices[drawableIndex];
    for (let offset = 0; offset + 2 < indices.length; offset += 3) {
      const vertexIds = [indices[offset], indices[offset + 1], indices[offset + 2]];
      const source = vertexIds.map(index => {
        const targetPoint = modelPoint(positions, index);
        const lowerBody = lowerBodyGroups.find(group => group.ids.has(drawableId));
        if (lowerBody?.source && lowerBody.target) {
          return {
            x: lowerBody.source[0] + (targetPoint.x - lowerBody.target.minX) * (lowerBody.source[2] - lowerBody.source[0]) / (lowerBody.target.maxX - lowerBody.target.minX),
            y: lowerBody.source[1] + (targetPoint.y - lowerBody.target.minY) * (lowerBody.source[3] - lowerBody.source[1]) / (lowerBody.target.maxY - lowerBody.target.minY),
          };
        }
        if (fittedParts.has(partId)) {
          return {
            x: sourceBounds[0] + (targetPoint.x - targetBox.minX) * (sourceBounds[2] - sourceBounds[0]) / (targetBox.maxX - targetBox.minX),
            y: sourceBounds[1] + (targetPoint.y - targetBox.minY) * (sourceBounds[3] - sourceBounds[1]) / (targetBox.maxY - targetBox.minY),
          };
        }
        if (topAlignedParts.has(partId)) {
          // All hair plates share one rigid transform. Independent alignment
          // would break the authored overlaps and expose white seams.
          return {
            x: targetPoint.x + hairSourceCenterX - hairTargetCenterX,
            y: targetPoint.y + hairSourceBox[1] - hairTargetBox.minY,
          };
        }
        return targetPoint;
      });
      // Cubism UV uses a bottom-left V origin while PNG/canvas uses top-left.
      const target = vertexIds.map(index => ({x: uvs[index * 2] * size, y: (1 - uvs[index * 2 + 1]) * size}));
      const transform = affineTriangle(source, target);
      if (!transform) continue;
      context.save(); context.beginPath(); context.moveTo(target[0].x, target[0].y);
      context.lineTo(target[1].x, target[1].y); context.lineTo(target[2].x, target[2].y); context.closePath(); context.clip();
      // Hair plates are intentionally sparse. Preserve Hiyori's authored fill
      // beneath transparent Mugi pixels so the larger fixed mesh never becomes
      // a white/skin-coloured hole while it deforms.
      if (!topAlignedParts.has(partId)) context.clearRect(0, 0, size, size);
      context.setTransform(...transform); context.drawImage(sourceImage, 0, 0); context.restore(); triangles += 1;
    }
  }
  // Hiyori's preserved eye islands are blue. Shift only blue-dominant pixels
  // toward Mugi's emerald palette; Mugi-projected outfit/hair pixels remain intact.
  const pixels = context.getImageData(0, 0, size, size);
  for (let offset = 0; offset < pixels.data.length; offset += 4) {
    const red = pixels.data[offset], green = pixels.data[offset + 1], blue = pixels.data[offset + 2];
    if (blue > 70 && blue > red * 1.15 && blue > green * 1.08) {
      pixels.data[offset] = Math.round(red * 0.55);
      pixels.data[offset + 1] = Math.min(255, Math.round(blue * 0.9 + green * 0.35));
      pixels.data[offset + 2] = Math.round(green * 0.7);
    }
  }
  context.putImageData(pixels, 0, 0);
  const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
  const objectUrl = URL.createObjectURL(blob);
  const link = $("atlasDownload"); link.href = objectUrl; link.hidden = false;
  const preview = $("atlasPreview"); preview.src = objectUrl; preview.hidden = false;
  link.click();
  return {triangles, skipped, bytes: blob.size};
}
async function loadModel() {
  $("status").className = "status waiting"; $("status").textContent = "読込中";
  try {
    await ensureRuntime();
    if (model) { app.stage.removeChild(model); model.destroy({children: true, texture: true, baseTexture: true}); model = undefined; }
    PIXI.utils.clearTextureCache();
    if (!app) {
      const canvas = document.createElement("canvas");
      // Let PIXI own the WebGL context. Cubism's renderer maintains a separate
      // framebuffer for clipping masks and must receive PIXI's managed context.
      app = new PIXI.Application({ view: canvas, width: $("stage").clientWidth, height: $("stage").clientHeight, transparent: true, useContextAlpha: true, backgroundAlpha: 0, antialias: true, resolution: 1, autoDensity: false });
      $("stage").appendChild(app.view);
      // Apply QA/demo controls after the model motion and physics update.
      // The default ticker priority ran first, so the Live2D update overwrote
      // eye-open values and made even the official Hiyori model look blank.
      app.ticker.add(updateParameters, null, PIXI.UPDATE_PRIORITY.LOW);
    }
    const path = $("modelPath").value.trim();
    model = await PIXI.live2d.Live2DModel.from(path, { autoInteract: false }); app.stage.addChild(model); resizeStage();
    if (noMaskDiagnostic) {
      const contexts = model.internalModel.renderer?._clippingManager?._clippingContextListForDraw;
      if (contexts) contexts.fill(null);
    }
    $("loadedFormat").textContent = $("sdk").value.toUpperCase();
    $("dimensions").textContent = `${model.internalModel.originalWidth} × ${model.internalModel.originalHeight}`;
    const topology = drawableDiagnostics();
    $("parameterCount").textContent = parameterCount();
    $("drawableCount").textContent = String(topology.total);
    $("emptyMeshCount").textContent = String(topology.empty);
    $("flatMeshCount").textContent = String(topology.flat);
    $("diagnosticJson").textContent = JSON.stringify({
      model: path,
      parameterCount: parameterCount(),
      total: topology.total,
      empty: topology.empty,
      flat4: topology.flat,
      drawables: topology.entries,
    }, null, 2);
    const topologyOk = topology.empty <= 5 && topology.flat <= 20;
    $("status").className = topologyOk ? "status ready" : "status error";
    $("status").textContent = topologyOk ? "正常" : "構造NG";
    log(`読込成功: ${path} (viewer ${viewerVersion})`);
    if (!topologyOk) log(`構造NG: 頂点0=${topology.empty}, 4頂点=${topology.flat}`);
  } catch (error) {
    $("status").className = "status error"; $("status").textContent = "失敗"; log(`読込失敗: ${error.message || error}`);
  }
}
function updateParameters() {
  if (!model) return;
  const now = performance.now(), cycle = now % 4200, automaticClose = autoBlink && cycle > 3650 && cycle < 3810;
  const eyes = (automaticClose || now < blinkUntil) ? 0 : 1;
  const demoSeconds = now / 1000;
  const mouth = demoMode ? Math.max(0, Math.sin(demoSeconds * 2.2)) * 0.65 : Number($("mouth").value);
  setParameter(parameterIds.eyeL, eyes); setParameter(parameterIds.eyeR, eyes); setParameter(parameterIds.mouth, mouth);
  if (demoMode) {
    const stage = $("stage");
    model.focus(
      stage.clientWidth * (0.5 + Math.sin(demoSeconds * 0.72) * 0.28),
      stage.clientHeight * (0.42 + Math.sin(demoSeconds * 0.51 + 0.8) * 0.18),
    );
  }
  if (hairMotion) {
    const seconds = now / 1000;
    setParameter(parameterIds.hairFront, Math.sin(seconds * 1.25) * 0.45);
    setParameter(parameterIds.hairSide, Math.sin(seconds * 1.05 + 1.1) * 0.5);
    setParameter(parameterIds.hairBack, Math.sin(seconds * 0.9 + 2.0) * 0.4);
    setParameter(parameterIds.hairAhoge, Math.sin(seconds * 1.5 + 0.6) * 0.55);
  }
  if (irisOnlyDiagnostic) {
    const core = model.internalModel.coreModel;
    const drawables = core.drawables ?? core._model.drawables;
    for (let index = 0; index < drawables.count; index += 1) {
      if (!["ArtMesh7", "ArtMesh8", "ArtMesh9", "ArtMesh10"].includes(String(drawables.ids[index]))) drawables.opacities[index] = 0;
    }
  }
}

$("sdk").addEventListener("change", event => { $("modelPath").value = `/exports/${event.target.value}/mugi/mugi.model3.json`; });
$("load").addEventListener("click", loadModel); $("blink").addEventListener("click", () => { blinkUntil = performance.now() + 220; });
$("buildAtlas").addEventListener("click", async () => {
  $("atlasStatus").textContent = "投影中…";
  try {
    const result = await buildFixedAtlas();
    $("atlasStatus").textContent = `完了: ${result.triangles}三角形 / ${result.bytes} bytes（未割当 ${result.skipped} ArtMesh）`;
  } catch (error) { $("atlasStatus").textContent = `失敗: ${error.message || error}`; }
});
$("blinkAuto").addEventListener("click", event => { autoBlink = !autoBlink; event.target.classList.toggle("active", autoBlink); event.target.textContent = `自動まばたき ${autoBlink ? "ON" : "OFF"}`; });
$("hair").addEventListener("click", event => { hairMotion = !hairMotion; event.target.classList.toggle("active", hairMotion); event.target.textContent = `髪揺れ ${hairMotion ? "ON" : "OFF"}`; });
$("reset").addEventListener("click", () => {
  $("mouth").value = 0; $("zoom").value = 1; $("offset").value = 0; $("mouthValue").value = "0.00"; $("zoomValue").value = "1.00"; $("offsetValue").value = "0"; resizeStage();
});
for (const id of ["mouth", "zoom", "offset"]) {
  $(id).addEventListener("input", event => { const value = Number(event.target.value); $(`${id}Value`).value = id === "offset" ? String(value) : value.toFixed(2); if (id !== "mouth") resizeStage(); });
}
$("stage").addEventListener("pointermove", event => { if (!model) return; const rect = $("stage").getBoundingClientRect(); model.focus(event.clientX - rect.left, event.clientY - rect.top); });
if (demoMode) document.body.classList.add("demo-mode");
const initialModel = pageOptions.get("model");
if (initialModel) $("modelPath").value = initialModel;
window.addEventListener("resize", resizeStage); loadModel();
