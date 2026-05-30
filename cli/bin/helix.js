#!/usr/bin/env node

import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import chalk from "chalk";
import { Command } from "commander";
import dotenv from "dotenv";
import ora from "ora";

import {
  clearSession,
  fetchMcpTools,
  fetchSkills,
  streamChat,
} from "../src/api.js";
import { ensureBackend, stopBackend } from "../src/backend.js";
import {
  createConfig,
  loadConfig,
  resolveConfigDefaults,
} from "../src/config.js";
import {
  printBanner,
  printAssistantMessage,
  printAssistantStart,
  printConfig,
  printError,
  printMcpStatus,
  printSkillActive,
  printSkills,
  printSystemMessage,
  printToolCall,
  printUserInline,
  promptLabel,
} from "../src/render.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "../..");

dotenv.config({ path: path.join(REPO_ROOT, ".env") });
dotenv.config();

const DEFAULT_SESSION_ID = "default";

const program = new Command();

program
  .name("helix")
  .description("Terminal coding agent")
  .version("0.1.0");

program
  .command("health")
  .description("Check that the CLI can start")
  .action(() => {
    const spinner = ora("Checking Helix").start();
    spinner.succeed(chalk.green("Helix is ready"));
  });

program
  .command("chat [message...]")
  .description("Chat with the backend coding agent")
  .option("--project <path>", "Project root")
  .option("--backend <url>", "Backend URL")
  .option("--no-server", "Do not start the local backend automatically")
  .action(async (messageParts, options, command) => {
    await runChatCommand(messageParts, {
      ...options,
      ...command.opts(),
    });
  });

program
  .action(async () => {
    await runChatCommand([], {});
  });

program.exitOverride((error) => {
  if (error.code === "commander.helpDisplayed") {
    process.exit(0);
  }
  throw error;
});

await program.parseAsync(process.argv);

async function runChatCommand(messageParts, options) {
  const message = messageParts.join(" ").trim();
  let backendProcess = null;
  let cleanupRegistered = false;

  function cleanupAndExit(signal) {
    stopBackend(backendProcess);
    process.exit(signal === "SIGINT" ? 130 : 143);
  }

  function registerCleanup() {
    if (cleanupRegistered) {
      return;
    }
    cleanupRegistered = true;
    process.once("SIGINT", cleanupAndExit);
    process.once("SIGTERM", cleanupAndExit);
  }

  printBanner();

  try {
    const resolvedOptions = await loadChatOptions(options);

    const shouldStartServer =
      options.server !== false && !process.argv.includes("--no-server");

    if (shouldStartServer) {
      backendProcess = await ensureBackend(resolvedOptions.backend, {
        onStatus: printSystemMessage,
        projectRoot: resolvedOptions.project,
      });
      registerCleanup();
    }

    printConfig(resolvedOptions);
    await printMcpTools(resolvedOptions.backend);

    if (message) {
      printUserInline(message);
      await runOnce(message, resolvedOptions);
      return;
    }

    await runReadlineLoop(resolvedOptions);
  } catch (error) {
    printError(error.message);
  } finally {
    if (cleanupRegistered) {
      process.removeListener("SIGINT", cleanupAndExit);
      process.removeListener("SIGTERM", cleanupAndExit);
    }
    stopBackend(backendProcess);
  }
}

async function loadChatOptions(options) {
  const projectRootForConfig = options.project ?? process.cwd();
  const loadedConfig = await loadConfig(projectRootForConfig);
  const defaults = resolveConfigDefaults(options, loadedConfig);

  if (!loadedConfig.exists) {
    await offerCreateConfig(loadedConfig.configPath, defaults);
  }

  return {
    backend: defaults.backendUrl,
    project: defaults.projectRoot,
    skill: null,
  };
}

async function offerCreateConfig(configPath, defaults) {
  if (!input.isTTY) {
    return;
  }

  const rl = createInterface({ input, output });

  try {
    const answer = (
      await rl.question(`Create ${configPath} with current defaults? [y/N] `)
    )
      .trim()
      .toLowerCase();

    if (answer === "y" || answer === "yes") {
      await createConfig(configPath, {
        backendUrl: defaults.backendUrl,
        projectRoot: defaults.projectRoot,
      });
      printSystemMessage(`created ${configPath}`);
    }
  } finally {
    rl.close();
  }
}

async function runReadlineLoop(options) {
  const rl = createInterface({ input, output });

  try {
    while (true) {
      const line = (await rl.question(promptLabel())).trim();

      if (!line) {
        continue;
      }
      if (line === "exit" || line === "/exit" || line === "quit" || line === "/quit") {
        printSystemMessage("bye");
        break;
      }
      if (line === "clear" || line === "/clear") {
        await clearSession(DEFAULT_SESSION_ID, options.backend);
        printSystemMessage("session cleared");
        continue;
      }
      if (line === "mcp" || line === "/mcp") {
        await printMcpTools(options.backend);
        continue;
      }
      if (line === "skills" || line === "/skills") {
        await printAvailableSkills(options);
        continue;
      }
      if (line.startsWith("skill ") || line.startsWith("/skill ")) {
        const skillName = line.replace(/^\/?skill\s+/, "").trim();
        options.skill = skillName || null;
        await clearSession(DEFAULT_SESSION_ID, options.backend);
        printSystemMessage(
          options.skill
            ? `skill set to ${options.skill}; session cleared`
            : "skill cleared; session cleared",
        );
        continue;
      }

      await runOnce(line, options);
    }
  } catch (error) {
    printError(error.message);
  } finally {
    rl.close();
  }
}

async function printMcpTools(backendUrl) {
  try {
    printMcpStatus(await fetchMcpTools(backendUrl));
  } catch (error) {
    printError(error.message);
  }
}

async function printAvailableSkills(options) {
  try {
    printSkills(await fetchSkills(options.backend), options.skill);
  } catch (error) {
    printError(error.message);
  }
}

async function runOnce(message, options) {
  let assistantStarted = false;
  let assistantBuffer = "";

  try {
    for await (const event of streamChat(
      message,
      DEFAULT_SESSION_ID,
      options.project,
      options.backend,
      options.skill,
    )) {
      const routed = routeEvent(event, assistantStarted, assistantBuffer);
      assistantStarted = routed.assistantStarted;
      assistantBuffer = routed.assistantBuffer;
    }
  } catch (error) {
    printError(error.message);
  }
}

function routeEvent(event, assistantStarted, assistantBuffer) {
  if (event.type === "token") {
    if (!assistantStarted) {
      printAssistantStart();
      assistantStarted = true;
    }
    return {
      assistantStarted,
      assistantBuffer: assistantBuffer + event.content,
    };
  }

  if (event.type === "tool_call" || event.type === "tool") {
    printToolCall(event.name, event.args, event.result);
    return { assistantStarted, assistantBuffer };
  }

  if (event.type === "error") {
    printError(event.content);
    return { assistantStarted, assistantBuffer };
  }

  if (event.type === "skill") {
    printSkillActive(event.name);
    return { assistantStarted, assistantBuffer };
  }

  if (event.type === "done") {
    printAssistantMessage(assistantBuffer);
  }

  return { assistantStarted, assistantBuffer };
}
