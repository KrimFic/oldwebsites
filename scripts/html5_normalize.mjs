#!/usr/bin/env node

import fs from "node:fs";
import { parse, serialize } from "parse5";

function setStyle(node, property, value) {
  let style = node.attrs.find((attribute) => attribute.name === "style");
  if (!style) {
    style = { name: "style", value: "" };
    node.attrs.push(style);
  }
  const current = style.value.trim().replace(/;?\s*$/, "");
  style.value = current ? `${current}; ${property}: ${value}` : `${property}: ${value}`;
}

function migrateAttribute(attribute, rule, migratedStyles) {
  const value = rule.values ? rule.values[attribute.value] : attribute.value;
  if (value === undefined) {
    return false;
  }
  migratedStyles.push({ property: rule.property, value });
  return true;
}

function migrateNode(node, migrations) {
  if (node.tagName) {
    const element = migrations.elements?.[node.tagName];
    if (element) {
      node.tagName = element.tag;
      node.nodeName = element.tag;
      for (const [property, value] of Object.entries(element.style || {})) {
        setStyle(node, property, value);
      }
    }

    const elementAttributes = element?.attributes || {};
    const migratedStyles = [];
    node.attrs = node.attrs.filter((attribute) => {
      const rule = elementAttributes[attribute.name] || migrations.attributes?.[attribute.name];
      return !rule || !migrateAttribute(attribute, rule, migratedStyles);
    });
    for (const style of migratedStyles) {
      setStyle(node, style.property, style.value);
    }
  }

  for (const child of node.childNodes || []) {
    migrateNode(child, migrations);
  }
}

function main() {
  const [mode, mappingPath, ...files] = process.argv.slice(2);
  if (!["--check", "--write"].includes(mode) || !mappingPath || files.length === 0) {
    console.error("Usage: html5_normalize.mjs [--check|--write] <mapping.json> <file.html...>");
    return 2;
  }

  let migrations;
  try {
    migrations = JSON.parse(fs.readFileSync(mappingPath, "utf8"));
  } catch (error) {
    console.error(`${mappingPath}: ${error.message}`);
    return 1;
  }

  let changed = 0;
  let failed = false;
  for (const file of files) {
    try {
      const source = fs.readFileSync(file, "utf8");
      const document = parse(source);
      migrateNode(document, migrations);
      let normalized = serialize(document);
      if (!/^\s*<!doctype html>/i.test(normalized)) {
        normalized = `<!DOCTYPE html>\n${normalized}`;
      }
      if (normalized !== source) {
        changed += 1;
        if (mode === "--write") {
          fs.writeFileSync(file, normalized);
          console.log(`Normalized ${file} to HTML5`);
        } else {
          console.log(`Would normalize ${file} to HTML5`);
        }
      }
    } catch (error) {
      console.error(`${file}: ${error.message}`);
      failed = true;
    }
  }

  console.log(`${mode === "--check" ? "Found" : "Normalized"} ${changed} file(s).`);
  return failed ? 1 : 0;
}

process.exitCode = main();