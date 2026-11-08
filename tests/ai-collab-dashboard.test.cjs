"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const {test} = require("node:test");

const page = fs.readFileSync(path.resolve(__dirname, "../ai-collab/status.html"), "utf8");
const scripts = [...page.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(x => x[1]);
test("status dashboard is a standalone syntactically valid page", () => {
  assert.match(page, /<html lang="ko">/);
  assert.equal(scripts.length, 1);
  assert.doesNotThrow(() => new vm.Script(scripts[0], {filename:"ai-collab/status.html"}));
});
test("dashboard is public-only and cannot change repository", () => {
  assert.match(page, /https:\/\/api\.github\.com\/repos\/mauveplace\/jjooni-control-tower/);
  assert.doesNotMatch(page, /localStorage|sessionStorage|Authorization["':]|\.innerHTML\s*=|fetch\([^)]*\{\s*method\s*:\s*["'](?:POST|PATCH|PUT|DELETE)/i);
  assert.match(page, /cache:"no-store"/);
  assert.doesNotMatch(page, /setInterval\s*\(/);
});
test("rendering respects explicit unverified provenance / current HEAD distinction", () => {
  assert.match(page, /UNVERIFIED|미인증|검증되지 않은/);
  assert.match(page, /과거 HEAD/);
  assert.match(page, /parsed\.claim\.head===head/);
  assert.match(page, /textContent/);
  assert.match(page, /사용량/);
});
test("UI works at mobile width and prevents rapid refresh", () => {
  assert.match(page, /@media\(max-width:430px\)/);
  assert.match(page, /Date\.now\(\)-state\.lastReload<20000/);
  assert.match(page, /target="_blank"|a\.target="_blank"/);
  assert.match(page, /rel="noopener noreferrer"|a\.rel="noopener noreferrer"/);
});
