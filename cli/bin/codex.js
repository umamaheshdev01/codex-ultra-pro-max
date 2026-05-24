#!/usr/bin/env node

import chalk from "chalk";
import { Command } from "commander";
import dotenv from "dotenv";
import ora from "ora";

dotenv.config({ path: "../.env" });
dotenv.config();

const program = new Command();

program
  .name("codex")
  .description("CLI entry point for codex-ultra-pro-max")
  .version("0.1.0");

program
  .command("health")
  .description("Check that the CLI can start")
  .action(() => {
    const spinner = ora("Checking CLI").start();
    spinner.succeed(chalk.green("CLI is ready"));
  });

program.action(() => {
  program.help();
});

program.parse(process.argv);
