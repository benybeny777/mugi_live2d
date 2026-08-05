#!/usr/bin/env node

/** Extract the immutable drawable topology needed by the atlas builder.
 *
 * The proprietary Cubism Core and the reference MOC remain local.  This
 * script writes a replaceable build manifest under temp/ so the following
 * raster stage does not need a browser or Cubism GUI automation.
 */

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

function usage() {
  console.error("usage: node scripts/extract_moc_topology.mjs CORE_JS MOC3 OUTPUT_JSON");
  process.exit(2);
}

const [, , corePathArgument, mocPathArgument, outputPathArgument] = process.argv;
if (!corePathArgument || !mocPathArgument || !outputPathArgument) usage();

const corePath = path.resolve(corePathArgument);
const mocPath = path.resolve(mocPathArgument);
const outputPath = path.resolve(outputPathArgument);
for (const required of [corePath, mocPath]) {
  if (!fs.existsSync(required)) throw new Error(`required local file is missing: ${required}`);
}

// The distributed Core bundle is CommonJS-shaped even though this wrapper is
// ESM.  It only uses __dirname to locate an optional adjacent WASM payload.
globalThis.__dirname = path.dirname(corePath);
vm.runInThisContext(fs.readFileSync(corePath, "utf8"), {filename: corePath});

function array(values) {
  return Array.from(values ?? []);
}

function extract() {
  const bytes = fs.readFileSync(mocPath);
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const moc = Live2DCubismCore.Moc.fromArrayBuffer(buffer);
  if (!moc) throw new Error(`Cubism Core rejected MOC3: ${mocPath}`);
  const model = Live2DCubismCore.Model.fromMoc(moc);
  if (!model) {
    moc._release();
    throw new Error(`Cubism Core could not initialize MOC3: ${mocPath}`);
  }

  try {
    const drawables = model.drawables;
    const parts = model.parts;
    const document = {
      schema: "mugi-live2d/moc-topology@1",
      source: path.relative(process.cwd(), mocPath).replaceAll("\\", "/"),
      coreVersion: Live2DCubismCore.Version.csmGetVersion(),
      mocVersion: Live2DCubismCore.Version.csmGetMocVersion(buffer),
      canvas: {
        width: model.canvasinfo.CanvasWidth,
        height: model.canvasinfo.CanvasHeight,
        originX: model.canvasinfo.CanvasOriginX,
        originY: model.canvasinfo.CanvasOriginY,
        pixelsPerUnit: model.canvasinfo.PixelsPerUnit,
      },
      parameters: {count: model.parameters.count, ids: array(model.parameters.ids)},
      parts: array(parts.ids).map((id, index) => ({id, index})),
      drawables: array(drawables.ids).map((id, index) => ({
        id,
        index,
        parentPartIndex: drawables.parentPartIndices[index],
        parentPartId: parts.ids[drawables.parentPartIndices[index]] ?? null,
        textureIndex: drawables.textureIndices[index],
        vertexCount: drawables.vertexCounts[index],
        positions: array(drawables.vertexPositions[index]),
        uvs: array(drawables.vertexUvs[index]),
        indices: array(drawables.indices[index]),
        masks: array(drawables.masks[index]),
      })),
    };
    fs.mkdirSync(path.dirname(outputPath), {recursive: true});
    fs.writeFileSync(outputPath, `${JSON.stringify(document, null, 2)}\n`, "utf8");
    console.log(
      `topology ready: ${document.drawables.length} drawables, ` +
      `${document.parameters.count} parameters -> ${outputPath}`,
    );
  } finally {
    model.release();
    moc._release();
  }
}

// Cubism Core may initialize its embedded module asynchronously depending on
// the distributed build.  The local Core exposes a thenable module function;
// a short event-loop turn works for both the asm and WebAssembly variants.
setTimeout(extract, 0);
