import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMMetaLoaderPlugin } from "@pixiv/three-vrm";

const canvas = document.querySelector("#stage");
const stage = document.querySelector(".stage-panel");
const loading = document.querySelector("#loading");
const status = document.querySelector("#status");
const motionState = document.querySelector("#motion-state");
const autoMotion = document.querySelector("#auto-motion");
const emotion = document.querySelector("#emotion");
const audioFile = document.querySelector("#audio-file");
const audioStatus = document.querySelector("#audio-status");
const mouth = document.querySelector("#mouth");
const lookX = document.querySelector("#look-x");
const lookY = document.querySelector("#look-y");
const blinkButton = document.querySelector("#blink");
const recordButton = document.querySelector("#record");

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
const defaultPixelRatio = Math.min(window.devicePixelRatio, 2);
renderer.setPixelRatio(defaultPixelRatio);
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
let blinkStartedAt = Number.NEGATIVE_INFINITY;
let nextBlinkAt = 1400;
const blinkDuration = 190;
let elapsed = 0;
let motionTimeline = null;
const boneRest = new Map();
const parallaxRest = new Map();
let parallaxLookX = 0;
let parallaxLookY = 0;
let smoothedMouth = 0;
let audioContext = null;
let audioAnalyser = null;
let audioSource = null;
let audioFrequencyData = null;

fetch("./motions/mugi-timeline.json")
  .then((response) => {
    if (!response.ok) throw new Error(`motion timeline HTTP ${response.status}`);
    return response.json();
  })
  .then((timeline) => {
    motionTimeline = timeline;
    stage.dataset.motionTimeline = timeline.name;
  })
  .catch((error) => {
    console.warn("Motion timeline fallback:", error);
    motionState.textContent = "motion: fallback idle";
  });

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
      "head",
      "leftUpperLeg",
      "leftLowerLeg",
      "rightUpperLeg",
      "rightLowerLeg",
    ].forEach((name) => {
      const bone = vrm.humanoid?.getNormalizedBoneNode(name);
      if (bone) boneRest.set(name, { bone, quaternion: bone.quaternion.clone() });
    });
    ["back_hair", "face", "front_hair", "accessory"].forEach((name) => {
      const node = vrm.scene.getObjectByName(name);
      if (node) parallaxRest.set(name, { node, position: node.position.clone() });
    });
    loading.hidden = true;
    const expressionCount = Object.keys(vrm.expressionManager?.expressionMap ?? {}).length;
    const springJointCount = vrm.springBoneManager?.joints.size ?? 0;
    stage.dataset.springJoints = String(springJointCount);
    status.textContent = `読込成功・${expressionCount} expressions・${springJointCount} spring joints`;
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

function startBlink(now) {
  blinkStartedAt = now;
  nextBlinkAt = now + 2600 + 550 * (0.5 + 0.5 * Math.sin(elapsed * 1.37));
}

function blinkCurve(now, delay = 0) {
  const progress = (now - blinkStartedAt - delay) / blinkDuration;
  if (progress <= 0 || progress >= 1) return 0;
  return Math.sin(Math.PI * progress) ** 1.45;
}

function updateControls() {
  document.querySelector("#mouth-value").value = Number(mouth.value).toFixed(2);
  document.querySelector("#look-x-value").value = Number(lookX.value).toFixed(2);
  document.querySelector("#look-y-value").value = Number(lookY.value).toFixed(2);
}

function analysedVowels() {
  if (!audioAnalyser || !audioFrequencyData || !audioContext) return null;
  audioAnalyser.getByteFrequencyData(audioFrequencyData);
  const nyquist = audioContext.sampleRate / 2;
  const band = (low, high) => {
    const start = Math.max(0, Math.floor(low / nyquist * audioFrequencyData.length));
    const end = Math.min(audioFrequencyData.length, Math.ceil(high / nyquist * audioFrequencyData.length));
    if (end <= start) return 0;
    let sum = 0;
    for (let index = start; index < end; index += 1) sum += audioFrequencyData[index];
    return sum / (end - start) / 255;
  };
  const low = band(120, 700);
  const middle = band(700, 1800);
  const high = band(1800, 3800);
  const raw = {
    aa: low * 0.55 + middle * 0.45,
    ih: middle * 0.35 + high * 0.65,
    ou: low * 0.75 + middle * 0.25,
    ee: middle * 0.55 + high * 0.45,
    oh: low * 0.62 + middle * 0.38,
  };
  const peak = Math.max(...Object.values(raw), 0.001);
  const strength = THREE.MathUtils.clamp((low + middle + high) * 0.72, 0, 1);
  return Object.fromEntries(Object.entries(raw).map(([name, value]) => [name, value / peak * strength]));
}

function scriptedVowels(strength) {
  const vowels = ["aa", "ih", "ou", "ee", "oh"];
  const position = elapsed / 0.46;
  const index = Math.floor(position) % vowels.length;
  const linear = position - Math.floor(position);
  const mix = linear * linear * (3 - 2 * linear);
  return {
    [vowels[index]]: strength * (1 - mix),
    [vowels[(index + 1) % vowels.length]]: strength * mix,
  };
}

function applyExpressions(now) {
  if (!vrm) return;
  clearGroup(["happy", "angry", "sad", "relaxed", "surprised", "sleepy"]);
  const motion = currentMotion();
  const activeEmotion = emotion.value || (autoMotion.checked ? motion.emotion : "");
  if (activeEmotion) setExpression(activeEmotion, activeEmotion === "surprised" ? 0.72 : 0.82);

  let mouthValue = Number(mouth.value);
  let horizontal = Number(lookX.value);
  let vertical = Number(lookY.value);
  if (autoMotion.checked) {
    const speechStrength = motion.name === "talk" ? 0.52 : motion.name === "greet" ? 0.18 : 0.05;
    mouthValue = Math.max(
      mouthValue,
      Math.max(0, Math.sin(elapsed * 6.05)) * speechStrength,
    );
    horizontal = Math.sin(elapsed * 0.55) * 0.7;
    vertical = Math.sin(elapsed * 0.31) * 0.25;
  }
  clearGroup(["aa", "ih", "ou", "ee", "oh", "blink"]);
  smoothedMouth += (mouthValue - smoothedMouth) * 0.24;
  const vowelWeights = analysedVowels() ?? scriptedVowels(smoothedMouth);
  Object.entries(vowelWeights).forEach(([name, value]) => setExpression(name, value));
  setExpression("blinkLeft", blinkCurve(now));
  setExpression("blinkRight", blinkCurve(now, 18));
  setExpression("lookLeft", Math.max(0, horizontal));
  setExpression("lookRight", Math.max(0, -horizontal));
  setExpression("lookUp", Math.max(0, vertical));
  setExpression("lookDown", Math.max(0, -vertical));
  parallaxLookX = horizontal;
  parallaxLookY = vertical;

  const idle = Math.sin(elapsed * 0.8);
  setExpression("idleLeft", autoMotion.checked ? Math.max(0, idle) : 0);
  setExpression("idleRight", autoMotion.checked ? Math.max(0, -idle) : 0);
  setExpression("greet", autoMotion.checked ? sampleMotionTrack("greet") : 0);
  setExpression("breath", autoMotion.checked ? 0.5 - 0.5 * Math.cos(elapsed * 1.25) : 0);
  if (autoMotion.checked && now >= nextBlinkAt) startBlink(now);
}

function applyLayerParallax() {
  const sway = autoMotion.checked ? Math.sin(elapsed * 0.8) : 0;
  const offsets = {
    back_hair: [-0.0012, -0.0005],
    face: [0.0006, 0.0004],
    front_hair: [0.0020, 0.0010],
    accessory: [0.0028, 0.0014],
  };
  parallaxRest.forEach(({ node, position }, name) => {
    const [factorX, factorY] = offsets[name] ?? [0, 0];
    node.position.copy(position);
    node.position.x += factorX * (parallaxLookX + sway * 0.22);
    node.position.y += factorY * parallaxLookY;
  });
}

function currentMotion() {
  if (!motionTimeline) return { name: "idle", emotion: "relaxed" };
  const time = elapsed % motionTimeline.duration;
  return motionTimeline.segments.find((segment) => time >= segment.start && time < segment.end)
    ?? motionTimeline.segments[0];
}

function sampleMotionTrack(name) {
  const keyframes = motionTimeline?.tracks?.[name];
  if (!keyframes?.length) return 0;
  const time = elapsed % motionTimeline.duration;
  for (let index = 0; index < keyframes.length - 1; index += 1) {
    const [startTime, startValue] = keyframes[index];
    const [endTime, endValue] = keyframes[index + 1];
    if (time < startTime || time > endTime) continue;
    const linear = (time - startTime) / Math.max(endTime - startTime, 1e-6);
    const eased = linear * linear * (3 - 2 * linear);
    return THREE.MathUtils.lerp(startValue, endValue, eased);
  }
  return keyframes[keyframes.length - 1][1];
}

function applyBoneMotion() {
  const sway = autoMotion.checked ? Math.sin(elapsed * 0.8) : 0;
  const delayed = autoMotion.checked ? Math.sin(elapsed * 0.8 - 0.45) : 0;
  const rotations = {
    chest: 0.007 * sway,
    head: 0.01 * delayed,
    leftUpperLeg: 0.007 * sway,
    leftLowerLeg: -0.009 * delayed,
    rightUpperLeg: -0.007 * sway,
    rightLowerLeg: 0.009 * delayed,
  };
  boneRest.forEach(({ bone, quaternion }, name) => {
    bone.quaternion.copy(quaternion);
    const timelineRotation = autoMotion.checked ? sampleMotionTrack(name) : 0;
    bone.rotateZ((rotations[name] ?? 0) + timelineRotation);
  });
  const motionName = autoMotion.checked ? currentMotion().name : "manual";
  if (motionState.dataset.name !== motionName) {
    motionState.dataset.name = motionName;
    motionState.textContent = `motion: ${motionName}`;
    stage.dataset.motion = motionName;
  }
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
  applyLayerParallax();
  vrm?.update(delta);
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

[mouth, lookX, lookY].forEach((control) => control.addEventListener("input", updateControls));
audioFile.addEventListener("change", async () => {
  const file = audioFile.files?.[0];
  if (!file) return;
  try {
    audioSource?.stop();
  } catch {
    // An already-ended BufferSource cannot be stopped twice.
  }
  audioContext ??= new AudioContext();
  await audioContext.resume();
  const buffer = await audioContext.decodeAudioData(await file.arrayBuffer());
  audioAnalyser = audioContext.createAnalyser();
  audioAnalyser.fftSize = 1024;
  audioFrequencyData = new Uint8Array(audioAnalyser.frequencyBinCount);
  audioSource = audioContext.createBufferSource();
  audioSource.buffer = buffer;
  audioSource.connect(audioAnalyser);
  audioAnalyser.connect(audioContext.destination);
  audioSource.addEventListener("ended", () => {
    audioAnalyser = null;
    audioStatus.value = "再生終了";
  });
  audioSource.start();
  audioStatus.value = `再生中: ${file.name}`;
});
blinkButton.addEventListener("click", () => { startBlink(performance.now()); });
recordButton.addEventListener("click", () => {
  renderer.setPixelRatio(2);
  renderer.setClearColor(0x111827, 1);
  resize();
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
    renderer.setPixelRatio(defaultPixelRatio);
    renderer.setClearColor(0x000000, 0);
    resize();
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
