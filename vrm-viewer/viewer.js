import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMMetaLoaderPlugin } from "@pixiv/three-vrm";

const canvas = document.querySelector("#stage");
const stage = document.querySelector(".stage-panel");
const loading = document.querySelector("#loading");
const status = document.querySelector("#status");
const autoMotion = document.querySelector("#auto-motion");
const emotion = document.querySelector("#emotion");
const mouth = document.querySelector("#mouth");
const lookX = document.querySelector("#look-x");
const lookY = document.querySelector("#look-y");
const blinkButton = document.querySelector("#blink");
const recordButton = document.querySelector("#record");

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
const camera = new THREE.OrthographicCamera(-0.78, 0.78, 1.0, -1.0, 0.1, 10);
camera.position.set(0, 0.9, 3);
camera.lookAt(0, 0.9, 0);
scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2));

const clock = new THREE.Clock();
const licenseUrl = "https://github.com/benybeny777/mugi_live2d/blob/main/docs/VRM.md#%E5%88%A9%E7%94%A8%E6%9D%A1%E4%BB%B6";
let vrm = null;
let blinkUntil = 0;
let elapsed = 0;
const boneRest = new Map();

const loader = new GLTFLoader();
loader.register(
  (parser) => new VRMLoaderPlugin(parser, {
    metaPlugin: new VRMMetaLoaderPlugin(parser, { acceptLicenseUrls: [licenseUrl] }),
  }),
);
loader.load(
  "../exports/vrm/mugi.vrm",
  (gltf) => {
    vrm = gltf.userData.vrm;
    scene.add(vrm.scene);
    [
      "chest",
      "leftUpperArm",
      "leftLowerArm",
      "rightUpperArm",
      "rightLowerArm",
      "leftUpperLeg",
      "leftLowerLeg",
      "rightUpperLeg",
      "rightLowerLeg",
    ].forEach((name) => {
      const bone = vrm.humanoid?.getNormalizedBoneNode(name);
      if (bone) boneRest.set(name, { bone, quaternion: bone.quaternion.clone() });
    });
    loading.hidden = true;
    const expressionCount = Object.keys(vrm.expressionManager?.expressionMap ?? {}).length;
    status.textContent = `読込成功・${expressionCount} expressions・実VRM描画中`;
  },
  (progress) => {
    if (progress.total > 0) loading.textContent = `VRM読込 ${Math.round(progress.loaded / progress.total * 100)}%`;
  },
  (error) => {
    console.error(error);
    loading.textContent = "VRMの読み込みに失敗しました。setup-runtime.ps1を確認してください。";
    status.textContent = "読込失敗";
  },
);

function setExpression(name, value) {
  vrm?.expressionManager?.setValue(name, THREE.MathUtils.clamp(value, 0, 1));
}

function clearGroup(names) {
  names.forEach((name) => setExpression(name, 0));
}

function updateControls() {
  document.querySelector("#mouth-value").value = Number(mouth.value).toFixed(2);
  document.querySelector("#look-x-value").value = Number(lookX.value).toFixed(2);
  document.querySelector("#look-y-value").value = Number(lookY.value).toFixed(2);
}

function applyExpressions(now) {
  if (!vrm) return;
  clearGroup(["happy", "angry", "sad", "relaxed", "surprised"]);
  if (emotion.value) setExpression(emotion.value, 1);

  let mouthValue = Number(mouth.value);
  let horizontal = Number(lookX.value);
  let vertical = Number(lookY.value);
  if (autoMotion.checked) {
    mouthValue = Math.max(mouthValue, Math.max(0, Math.sin(elapsed * 4.2)) * 0.42);
    horizontal = Math.sin(elapsed * 0.55) * 0.7;
    vertical = Math.sin(elapsed * 0.31) * 0.25;
  }
  setExpression("aa", mouthValue);
  setExpression("blink", now < blinkUntil ? 1 : 0);
  setExpression("lookLeft", Math.max(0, horizontal));
  setExpression("lookRight", Math.max(0, -horizontal));
  setExpression("lookUp", Math.max(0, vertical));
  setExpression("lookDown", Math.max(0, -vertical));

  const idle = Math.sin(elapsed * 0.8);
  setExpression("idleLeft", autoMotion.checked ? Math.max(0, idle) : 0);
  setExpression("idleRight", autoMotion.checked ? Math.max(0, -idle) : 0);
  setExpression("breath", autoMotion.checked ? 0.5 - 0.5 * Math.cos(elapsed * 1.25) : 0);
  if (autoMotion.checked && Math.sin(elapsed * 1.7) > 0.992) blinkUntil = now + 115;
}

function applyBoneMotion() {
  const sway = autoMotion.checked ? Math.sin(elapsed * 0.8) : 0;
  const delayed = autoMotion.checked ? Math.sin(elapsed * 0.8 - 0.45) : 0;
  const rotations = {
    chest: 0.012 * sway,
    leftUpperArm: 0.028 * sway,
    leftLowerArm: 0.035 * delayed,
    rightUpperArm: -0.028 * sway,
    rightLowerArm: -0.035 * delayed,
    leftUpperLeg: 0.007 * sway,
    leftLowerLeg: -0.009 * delayed,
    rightUpperLeg: -0.007 * sway,
    rightLowerLeg: 0.009 * delayed,
  };
  boneRest.forEach(({ bone, quaternion }, name) => {
    bone.quaternion.copy(quaternion);
    bone.rotateZ(rotations[name] ?? 0);
  });
}

function resize() {
  const width = stage.clientWidth;
  const height = stage.clientHeight;
  renderer.setSize(width, height, false);
  const aspect = width / Math.max(height, 1);
  camera.left = -aspect;
  camera.right = aspect;
  camera.top = 1;
  camera.bottom = -1;
  camera.updateProjectionMatrix();
}

function animate(now) {
  const delta = Math.min(clock.getDelta(), 1 / 15);
  elapsed += delta;
  resize();
  applyExpressions(now);
  applyBoneMotion();
  vrm?.update(delta);
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

[mouth, lookX, lookY].forEach((control) => control.addEventListener("input", updateControls));
blinkButton.addEventListener("click", () => { blinkUntil = performance.now() + 140; });
recordButton.addEventListener("click", () => {
  const stream = canvas.captureStream(30);
  const recorder = new MediaRecorder(stream, { mimeType: "video/webm;codecs=vp9" });
  const chunks = [];
  recorder.addEventListener("dataavailable", (event) => { if (event.data.size) chunks.push(event.data); });
  recorder.addEventListener("stop", () => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob(chunks, { type: "video/webm" }));
    link.download = "mugi-vrm-runtime-preview.webm";
    link.click();
    URL.revokeObjectURL(link.href);
    recordButton.disabled = false;
    recordButton.textContent = "5秒録画";
  });
  recordButton.disabled = true;
  recordButton.textContent = "録画中…";
  recorder.start();
  window.setTimeout(() => recorder.stop(), 5000);
});

updateControls();
requestAnimationFrame(animate);
