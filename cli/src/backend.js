import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { checkHealth } from "./api.js";

const STARTUP_TIMEOUT_MS = 20_000;
const HEALTH_POLL_MS = 350;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "../..");
const BACKEND_DIR = path.join(REPO_ROOT, "backend");
const PYTHON_BIN = path.join(BACKEND_DIR, ".venv/bin/python");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function portFromBackendUrl(backendUrl) {
  try {
    return new URL(backendUrl).port || "80";
  } catch {
    return "3001";
  }
}

export async function ensureBackend(backendUrl, { onStatus, projectRoot } = {}) {
  if (await checkHealth(backendUrl)) {
    return null;
  }

  onStatus?.("starting backend");

  const child = spawn(
    PYTHON_BIN,
    [
      "-m",
      "uvicorn",
      "src.main:app",
      "--port",
      portFromBackendUrl(backendUrl),
    ],
    {
      cwd: BACKEND_DIR,
      env: {
        ...process.env,
        ...(projectRoot ? { HELIX_PROJECT_ROOT: projectRoot } : {}),
      },
      stdio: ["ignore", "ignore", "pipe"],
    },
  );

  let startupError = "";
  child.stderr.on("data", (chunk) => {
    startupError += chunk.toString();
  });

  const startedAt = Date.now();
  while (Date.now() - startedAt < STARTUP_TIMEOUT_MS) {
    if (child.exitCode !== null) {
      throw new Error(startupError.trim() || "Backend failed to start");
    }

    if (await checkHealth(backendUrl)) {
      onStatus?.("backend ready");
      return child;
    }

    await sleep(HEALTH_POLL_MS);
  }

  child.kill();
  const details = startupError.trim();
  throw new Error(
    details
      ? `Backend did not become ready in time:\n${details}`
      : "Backend did not become ready in time. Run `cd backend && source .venv/bin/activate && pip install -r requirements.txt` if dependencies were just added.",
  );
}

export function stopBackend(child) {
  if (!child || child.killed) {
    return;
  }

  child.kill();
}
