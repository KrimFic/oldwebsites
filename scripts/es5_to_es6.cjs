#!/usr/bin/env node

const fs = require("node:fs");
const lebab = require("lebab");

const transforms = [
  "let",
  "arrow",
  "class",
  "default-param",
  "destruct-param",
  "for-of",
  "includes",
  "obj-method",
  "obj-shorthand",
  "template",
  "exponent",
];

function main() {
  const [mode, ...files] = process.argv.slice(2);
  if (!["--check", "--write"].includes(mode) || files.length === 0) {
    console.error("Usage: es5_to_es6.cjs [--check|--write] <file.js...>");
    return 2;
  }

  let changed = 0;
  let failed = false;
  for (const file of files) {
    try {
      const source = fs.readFileSync(file, "utf8");
      const result = lebab.transform(source, transforms);
      if (result.code !== source) {
        changed += 1;
        if (mode === "--write") {
          fs.writeFileSync(file, result.code);
          console.log(`Converted ${file}`);
        } else {
          console.log(`Would convert ${file}`);
        }
      }
      for (const warning of result.warnings || []) {
        console.warn(`${file}: ${warning}`);
        failed = true;
      }
    } catch (error) {
      console.error(`${file}: ${error.message}`);
      failed = true;
    }
  }

  console.log(`${mode === "--check" ? "Found" : "Converted"} ${changed} file(s).`);
  return failed ? 1 : 0;
}

process.exitCode = main();