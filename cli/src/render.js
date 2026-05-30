import chalk from "chalk";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const packageJson = require("../package.json");

const PREVIEW_LIMIT = 900;
const INDENT = "  ";
const ACCENT = "#7dd3fc";
const MUTED = "#8b94a7";
const PANEL_BG = "#363d49";
const TEXT = "#e5e7eb";
const SUCCESS = "#86efac";
const ERROR = "#fb7185";
const HELIX_LOGO = String.raw`
    __  __     ___
   / / / /__  / (_)  __
  / /_/ / _ \/ / / |/_/
 / __  /  __/ / />  <
/_/ /_/\___/_/_/_/|_|
`;

const color = {
  accent: chalk.hex(ACCENT),
  muted: chalk.hex(MUTED),
  text: chalk.hex(TEXT),
  success: chalk.hex(SUCCESS),
  error: chalk.hex(ERROR),
  panel: chalk.bgHex(PANEL_BG).hex(TEXT),
};

function truncate(value, limit = PREVIEW_LIMIT) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  if (!text) {
    return "";
  }
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit)}...`;
}

function terminalWidth() {
  return Math.max(54, Math.min(process.stdout.columns ?? 88, 110));
}

function panelLine(text) {
  const width = terminalWidth();
  const content = ` ${text}`;
  return color.panel(content.padEnd(width));
}

function commandFromArgs(args) {
  if (args?.command) {
    return String(args.command);
  }
  if (args?.path) {
    return String(args.path);
  }
  return truncate(args, 120);
}

function toolVerb(name) {
  if (name === "run_command") {
    return "Ran";
  }
  if (name === "read_file") {
    return "Read";
  }
  if (name === "write_file") {
    return "Wrote";
  }
  if (name === "list_dir") {
    return "Listed";
  }
  return "Used";
}

function formatToolTarget(name, args) {
  if (name === "list_dir") {
    return "project tree";
  }
  return commandFromArgs(args);
}

function printIndentedPreview(value) {
  const preview = truncate(value).trimEnd();
  if (!preview) {
    return;
  }

  const lines = preview.split("\n");
  const visibleLines = lines.slice(0, 12);
  for (const line of visibleLines) {
    console.log(color.muted(`${INDENT}└ ${line}`));
  }
  if (lines.length > visibleLines.length) {
    console.log(color.muted(`${INDENT}└ ... ${lines.length - visibleLines.length} more lines`));
  }
}

function wrapText(text, width, prefix = "") {
  if (!text.trim()) {
    return [""];
  }

  const words = text.trim().split(/\s+/);
  const lines = [];
  let current = prefix;

  for (const word of words) {
    const next = current.trim() === "" ? `${prefix}${word}` : `${current} ${word}`;
    if (next.length > width && current.trim() !== "") {
      lines.push(current);
      current = `${prefix}${word}`;
    } else {
      current = next;
    }
  }

  lines.push(current);
  return lines;
}

function styleInline(text) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, (_, bold) => chalk.bold(bold))
    .replace(/`([^`]+)`/g, (_, code) => chalk.hex(ACCENT)(code));
}

function formatAssistantText(text) {
  const width = terminalWidth() - 2;
  const lines = text.trim().split("\n");
  const output = [];
  let inCodeBlock = false;

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    if (line.trim().startsWith("```")) {
      inCodeBlock = !inCodeBlock;
      output.push(color.muted(line));
      continue;
    }

    if (inCodeBlock) {
      output.push(color.muted(`  ${line}`));
      continue;
    }

    if (!line.trim()) {
      output.push("");
      continue;
    }

    const numbered = line.match(/^(\d+\.\s+)(.*)$/);
    if (numbered) {
      const prefix = `${numbered[1]}`;
      output.push(
        ...wrapText(numbered[2], width, prefix).map(styleInline),
      );
      continue;
    }

    const bullet = line.match(/^([-*]\s+)(.*)$/);
    if (bullet) {
      const prefix = "• ";
      output.push(...wrapText(bullet[2], width, prefix).map(styleInline));
      continue;
    }

    output.push(...wrapText(line, width).map(styleInline));
  }

  return output.join("\n");
}

export function printToken(text) {
  process.stdout.write(text);
}

export function printAssistantMessage(text) {
  const formatted = formatAssistantText(text);
  if (formatted) {
    console.log(formatted);
  }
}

export function printToolCall(name, args, result) {
  console.log("");
  console.log(
    `${color.success("●")} ${chalk.bold(toolVerb(name))} ${color.accent(formatToolTarget(name, args))}`,
  );
  printIndentedPreview(result);
}

export function printError(msg) {
  console.error("");
  console.error(`${color.error("●")} ${chalk.bold("Error")}`);
  console.error(color.muted(`${INDENT}└ ${msg}`));
}

export function printBanner() {
  console.log(color.accent(HELIX_LOGO));
  console.log(`${chalk.bold("Helix")} ${color.muted(`v${packageJson.version}`)} ${color.muted("terminal agent")}`);
  console.log(color.muted("Type a request. Use /clear to reset, /exit to quit."));
}

export function printConfig({ backend, project }) {
  console.log(color.muted(`backend: ${backend}`));
  console.log(color.muted(`project: ${project}`));
  console.log("");
}

export function printSystemMessage(message) {
  console.log(color.muted(`● ${message}`));
}

export function printSkillActive(name) {
  console.log(`${color.success("●")} ${chalk.bold("Skill")} ${color.accent(name)}`);
}

export function printMcpStatus(payload) {
  console.log("");
  console.log(`${color.success("●")} ${chalk.bold("MCP tools")}`);

  if (!payload.servers?.length) {
    console.log(color.muted(`${INDENT}└ no MCP servers connected`));
    return;
  }

  for (const server of payload.servers) {
    const status = server.error
      ? `${server.status}: ${server.error}`
      : server.status;
    console.log(
      `${INDENT}${color.accent(server.name)} ${color.muted(status)} ${color.muted(`(${server.tools.length} tools)`)}`,
    );

    for (const tool of server.tools.slice(0, 20)) {
      console.log(color.muted(`${INDENT}└ ${tool.name}`));
    }

    if (server.tools.length > 20) {
      console.log(color.muted(`${INDENT}└ ... ${server.tools.length - 20} more tools`));
    }
  }
}

export function printSkills(skills, activeSkill) {
  console.log("");
  console.log(`${color.success("●")} ${chalk.bold("Skills")}`);

  for (const skill of skills) {
    const marker = skill.name === activeSkill ? "*" : " ";
    console.log(
      `${INDENT}${marker} ${skill.icon} ${color.accent(skill.name)} ${color.muted(skill.description)}`,
    );
  }
}

export function promptLabel() {
  return color.accent("› ");
}

export function printAssistantStart() {
  process.stdout.write(`${color.muted("●")} ${chalk.bold("Helix")}\n`);
}

export function printUserInline(message) {
  console.log(panelLine(`› ${message}`));
}
