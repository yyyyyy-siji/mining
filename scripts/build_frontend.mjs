#!/usr/bin/env node
/**
 * Zero-dependency deterministic frontend assembler.
 *
 * Concatenates modular source files in `frontend/src/*.js` (sorted lexicographically)
 * into the runtime bundle `frontend/static/app.js` used by both the browser and
 * Node `vm` frontend test suites.
 *
 * Usage:
 *   node scripts/build_frontend.mjs          # rebuild frontend/static/app.js
 *   node scripts/build_frontend.mjs --check  # verify bundle matches frontend/src/
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const SRC_DIR = path.join(ROOT, 'frontend', 'src');
const OUT_FILE = path.join(ROOT, 'frontend', 'static', 'app.js');

const files = fs
  .readdirSync(SRC_DIR)
  .filter((name) => name.endsWith('.js'))
  .sort();

if (files.length === 0) {
  console.error(`No .js source modules found in ${SRC_DIR}`);
  process.exit(1);
}

const assembled = files
  .map((name) => fs.readFileSync(path.join(SRC_DIR, name), 'utf8'))
  .join('');

const checkOnly = process.argv.includes('--check');

if (checkOnly) {
  const current = fs.existsSync(OUT_FILE) ? fs.readFileSync(OUT_FILE, 'utf8') : '';
  if (current !== assembled) {
    console.error(
      'ERROR: frontend/static/app.js is out of sync with frontend/src/*.js.\n' +
        'Run `node scripts/build_frontend.mjs` to rebuild it.'
    );
    process.exit(1);
  }
  console.log(`OK: frontend/static/app.js matches ${files.length} source modules in frontend/src/.`);
  process.exit(0);
}

fs.writeFileSync(OUT_FILE, assembled, 'utf8');
console.log(`Built frontend/static/app.js from ${files.length} modules (${assembled.length} bytes).`);
