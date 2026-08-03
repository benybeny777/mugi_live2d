import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const address = process.env.CUBISM_API_ADDRESS ?? "ws://127.0.0.1:22033";
const tokenPath = resolve(process.env.CUBISM_API_TOKEN_FILE ?? "temp/cubism-api-token.txt");
const clientName = "Mugi Live2D QA";
const holdMs = Number(process.env.CUBISM_QA_HOLD_MS ?? 5000);
const assignments = process.argv.slice(2).map((item) => {
  const [id, rawValue] = item.split("=", 2);
  const value = Number(rawValue);
  if (!id || !Number.isFinite(value)) throw new Error(`Invalid parameter: ${item}`);
  return { Id: id, Value: value };
});

let token = null;
try {
  token = (await readFile(tokenPath, "utf8")).trim() || null;
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}

const socket = new WebSocket(address);
const pending = new Map();
let requestId = 0;

function request(method, data) {
  const id = String(requestId++);
  socket.send(JSON.stringify({
    Version: "0.9.1",
    Timestamp: Date.now(),
    RequestId: id,
    Type: "Request",
    Method: method,
    Data: data,
  }));
  return new Promise((resolveRequest, rejectRequest) => {
    pending.set(id, { resolve: resolveRequest, reject: rejectRequest });
  });
}

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  const waiter = pending.get(message.RequestId);
  if (!waiter) return;
  pending.delete(message.RequestId);
  if (message.Type === "Error") {
    const safeData = { ...message.Data };
    delete safeData.Token;
    waiter.reject(new Error(`Cubism API error: ${JSON.stringify(safeData)}`));
  }
  else waiter.resolve(message);
});

await new Promise((resolveOpen, rejectOpen) => {
  socket.addEventListener("open", resolveOpen, { once: true });
  socket.addEventListener("error", () => rejectOpen(new Error(`Cannot connect to ${address}`)), { once: true });
});

const registrationData = { Name: clientName };
if (token) registrationData.Token = token;
const registration = await request("RegisterPlugin", registrationData);
token = registration.Data.Token;
await mkdir(dirname(tokenPath), { recursive: true });
await writeFile(tokenPath, `${token}\n`, { encoding: "utf8", mode: 0o600 });

const approvalDeadline = Date.now() + 60000;
while (true) {
  const approval = await request("GetIsApproval", {});
  if (approval.Data.Result) break;
  if (Date.now() >= approvalDeadline) throw new Error("Cubism API approval timed out");
  await new Promise((resolveWait) => setTimeout(resolveWait, 500));
}

const currentModel = await request("GetCurrentModelUID", {});
const modelUid = currentModel.Data.ModelUID;
if (!modelUid) throw new Error("Cubism Editor has no active model");
await request("ClearParameterValues", { ModelUID: modelUid });

if (assignments.length) {
  const endAt = Date.now() + holdMs;
  do {
    await request("SetParameterValues", { ModelUID: modelUid, Parameters: assignments });
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  } while (Date.now() < endAt);
  await request("ClearParameterValues", { ModelUID: modelUid });
}

console.log(`QA applied to ${assignments.length} parameter(s) for ${holdMs} ms.`);
socket.close();
