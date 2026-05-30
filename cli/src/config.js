import fs from "node:fs/promises";
import path from "node:path";

export const CONFIG_FILE_NAME = ".helix.json";
export const DEFAULT_BACKEND_URL = "http://localhost:3001";

export async function loadConfig(projectRoot) {
  const configPath = path.join(projectRoot, CONFIG_FILE_NAME);

  try {
    const rawConfig = await fs.readFile(configPath, "utf8");
    return {
      config: JSON.parse(rawConfig),
      configPath,
      exists: true,
    };
  } catch (error) {
    if (error.code === "ENOENT") {
      return {
        config: {},
        configPath,
        exists: false,
      };
    }
    throw error;
  }
}

export async function createConfig(configPath, config) {
  await fs.writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}

export function resolveConfigDefaults(options, loadedConfig) {
  const config = loadedConfig.config ?? {};
  const projectRoot = options.project ?? config.projectRoot ?? process.cwd();
  const backendUrl = options.backend ?? config.backendUrl ?? DEFAULT_BACKEND_URL;

  return {
    backendUrl,
    projectRoot,
  };
}
