#!/usr/bin/env node
// extract-prompts.mjs — Extract the user's *typed* prompts from Claude Code
// transcripts (~/.claude/projects/<dir>/*.jsonl) and emit them plus
// quantitative stats. The output is the raw material for cc-usage-audit:
// you reason over the user's own words, never invent the philosophy.
//
// Usage:
//   node extract-prompts.mjs --list                 # list all project dirs + prompt counts
//   node extract-prompts.mjs --match <substr>       # extract from dirs whose name contains <substr>
//   node extract-prompts.mjs                         # auto-derive <substr> from $PWD git root
//   node extract-prompts.mjs --match foo --json out.json   # also write full JSON
//   node extract-prompts.mjs --match foo --since 2026-05-01 # filter by ISO date prefix
//
// Transcript dir names encode the cwd path with '/'→'-'. One project can
// span several worktrees (different paths) — match on a shared token
// (repo name, worktree-group id) to gather them all.

import fs from 'fs';
import path from 'path';
import os from 'os';
import { execSync } from 'child_process';

const PROJECTS = path.join(os.homedir(), '.claude/projects');

function arg(flag) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : undefined;
}
const has = (flag) => process.argv.includes(flag);

// Lines that are injected by the harness or are not genuine typed prompts.
const SKIP_PREFIXES = [
  '<command-name>', '<command-message>', '<local-command-stdout>',
  '<bash-input>', '<bash-stdout>', '<bash-stderr>', 'Caveat:',
  '<task-notification>', '<system-reminder>', '[Request interrupted',
];
function isRealPrompt(text) {
  if (!text || !text.trim()) return false;
  const t = text.trim();
  return !SKIP_PREFIXES.some((p) => t.startsWith(p));
}

function deriveMatch() {
  try {
    const root = execSync('git rev-parse --show-toplevel', { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString().trim();
    // worktrees often live under .../worktrees/<group-id>/<slug>; the group id
    // is the most reliable shared token across a project's worktrees.
    const m = root.match(/worktrees\/([0-9a-f-]{8,})\//);
    return m ? m[1] : path.basename(root);
  } catch {
    return path.basename(process.cwd());
  }
}

function projectDirs() {
  if (!fs.existsSync(PROJECTS)) return [];
  return fs.readdirSync(PROJECTS).filter((d) =>
    fs.statSync(path.join(PROJECTS, d)).isDirectory());
}

function extractFromDir(dir, since) {
  const full = path.join(PROJECTS, dir);
  const out = [];
  for (const f of fs.readdirSync(full).filter((x) => x.endsWith('.jsonl'))) {
    const lines = fs.readFileSync(path.join(full, f), 'utf8').split('\n').filter(Boolean);
    for (const line of lines) {
      let o; try { o = JSON.parse(line); } catch { continue; }
      if (o.type !== 'user' || o.isSidechain || o.isMeta) continue;
      const msg = o.message;
      if (!msg || msg.role !== 'user') continue;
      const c = msg.content;
      const texts = typeof c === 'string'
        ? [c]
        : Array.isArray(c) ? c.filter((b) => b && b.type === 'text' && typeof b.text === 'string').map((b) => b.text) : [];
      for (const t of texts) {
        if (!isRealPrompt(t)) continue;
        if (since && (o.timestamp || '') < since) continue;
        out.push({ worktree: dir, ts: o.timestamp || '', text: t.trim() });
      }
    }
  }
  return out;
}

// ── --list mode ──────────────────────────────────────────────────────────
if (has('--list')) {
  const rows = projectDirs().map((d) => ({ d, n: extractFromDir(d).length }))
    .filter((r) => r.n > 0).sort((a, b) => b.n - a.n);
  console.log('prompts  project-dir');
  for (const r of rows) console.log(String(r.n).padStart(7), ' ', r.d);
  process.exit(0);
}

// ── extract mode ───────────────────────────────────────────────────────────
const match = arg('--match') || deriveMatch();
const since = arg('--since');
const dirs = projectDirs().filter((d) => d.includes(match));
if (dirs.length === 0) {
  console.error(`No project transcript dirs match "${match}".`);
  console.error('Run with --list to see available dirs, or pass --match <substr>.');
  process.exit(1);
}

let all = [];
for (const d of dirs) all = all.concat(extractFromDir(d, since));
all.sort((a, b) => (a.ts < b.ts ? -1 : 1));

const jsonPath = arg('--json');
if (jsonPath) fs.writeFileSync(jsonPath, JSON.stringify(all, null, 1));

// ── stats ───────────────────────────────────────────────────────────────────
const lens = all.map((o) => o.text.length).sort((a, b) => a - b);
const sum = lens.reduce((a, b) => a + b, 0);
const pct = (n) => ((100 * n) / (all.length || 1)).toFixed(0) + '%';

const byWt = {};
for (const o of all) byWt[o.worktree] = (byWt[o.worktree] || 0) + 1;

const byHour = {};
for (const o of all) {
  if (!o.ts) continue;
  const h = new Date(o.ts).getHours();
  byHour[h] = (byHour[h] || 0) + 1;
}

console.log(`# matched dirs: ${dirs.length}  (match="${match}")`);
console.log(`# prompts: ${all.length}`);
if (all.length) {
  console.log(`# chars: total ${sum}, mean ${Math.round(sum / lens.length)}, median ${lens[Math.floor(lens.length / 2)]}, max ${lens[lens.length - 1]}`);
  const span = [all[0].ts, all[all.length - 1].ts].map((t) => (t || '').slice(0, 16));
  console.log(`# timespan: ${span[0]} .. ${span[1]} (UTC)`);

  console.log('\n## prompts per project-dir');
  for (const [k, v] of Object.entries(byWt).sort((a, b) => b[1] - a[1]))
    console.log(String(v).padStart(4), k);

  console.log('\n## length buckets');
  const b = { '1-30': 0, '31-80': 0, '81-200': 0, '201-500': 0, '500+': 0 };
  for (const l of lens) {
    if (l <= 30) b['1-30']++; else if (l <= 80) b['31-80']++;
    else if (l <= 200) b['81-200']++; else if (l <= 500) b['201-500']++; else b['500+']++;
  }
  for (const [k, v] of Object.entries(b)) console.log(String(v).padStart(4), k, 'chars');

  console.log('\n## prompts by local hour');
  for (let i = 0; i < 24; i++)
    if (byHour[i]) console.log(String(i).padStart(2) + ':00', '█'.repeat(byHour[i]), byHour[i]);

  console.log('\n## all prompts (chronological)');
  let i = 0;
  for (const o of all) {
    i++;
    console.log(`\n──[${String(i).padStart(3)}] ${(o.ts || '').slice(0, 16).replace('T', ' ')} (${o.worktree.replace(/^-Users-[^-]+-/, '…')})──`);
    console.log(o.text);
  }
}
if (jsonPath) console.error(`\n(full JSON written to ${jsonPath})`);
