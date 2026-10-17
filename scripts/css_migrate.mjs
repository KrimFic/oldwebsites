#!/usr/bin/env node

import fs from "node:fs";
import postcss from "postcss";

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function applyMigrations(css, migrations) {
  const root = postcss.parse(css);
  const properties = migrations.properties || {};
  const values = migrations.values || {};
  const declarations = migrations.declarations || {};
  const valuePattern = Object.keys(values).length
    ? new RegExp(Object.keys(values).sort((a, b) => b.length - a.length).map(escapeRegExp).join("|"), "g")
    : null;

  root.walkDecls((declaration) => {
    const declarationMap = declarations[declaration.prop.toLowerCase()];
    const directMigration = declarationMap && declarationMap[declaration.value];
    if (directMigration) {
      declaration.prop = directMigration.property || declaration.prop;
      declaration.value = directMigration.value;
      return;
    }

    declaration.prop = properties[declaration.prop] || declaration.prop;
    if (valuePattern) {
      declaration.value = declaration.value.replace(valuePattern, (oldValue) => values[oldValue]);
    }
  });

  return root.toResult().css;
}

function main() {
  const [mode, mappingPath, ...files] = process.argv.slice(2);
  if (!["--check", "--write"].includes(mode) || !mappingPath || files.length === 0) {
    console.error("Usage: css_migrate.mjs [--check|--write] <mapping.json> <file.css...>");
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
      const migrated = applyMigrations(source, migrations);
      if (migrated !== source) {
        changed += 1;
        if (mode === "--write") {
          fs.writeFileSync(file, migrated);
          console.log(`Migrated CSS declarations in ${file}`);
        } else {
          console.log(`Would migrate CSS declarations in ${file}`);
        }
      }
    } catch (error) {
      console.error(`${file}: ${error.message}`);
      failed = true;
    }
  }

  console.log(`${mode === "--check" ? "Found" : "Migrated"} ${changed} file(s).`);
  return failed ? 1 : 0;
}

process.exitCode = main();