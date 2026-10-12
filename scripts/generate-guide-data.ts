#!/usr/bin/env -S deno run --allow-read --allow-write --allow-run=git,convert
/** @module Generate the fork guide dataset and its licensed tile assets from this checkout. */
import { Command } from "@cliffy/command"
import { copy, ensureDir, walk } from "@std/fs"
import { basename, dirname, join, relative, resolve } from "@std/path"
import * as v from "@valibot/valibot"

const FORK_REPO = "Kenja-mc/Cataclysm-BN"
const FORK_URL = `https://github.com/${FORK_REPO}`
const ObjectSchema = v.record(v.string(), v.unknown())
const ObjectsSchema = v.union([v.array(ObjectSchema), ObjectSchema])
const ChunkSchema = v.array(v.looseObject({ file: v.string() }))
type GameObject = v.InferOutput<typeof ObjectSchema>
type ModData = { info: GameObject; data: GameObject[]; directory: string }

async function run(command: string, args: string[], cwd?: string): Promise<string> {
  const result = await new Deno.Command(command, { args, cwd, stdout: "piped", stderr: "piped" })
    .output()
  const decode = new TextDecoder()
  if (!result.success) {
    throw new Error(
      `${command} failed (${result.code}): ${decode.decode(result.stdout)}${
        decode.decode(result.stderr)
      }`,
    )
  }
  return decode.decode(result.stdout).trim()
}

function containedPath(root: string, path: string): string {
  const target = resolve(root, path)
  const rel = relative(resolve(root), target)
  if (
    !rel || rel === ".." || rel.startsWith("../") || rel.startsWith("..\\") ||
    resolve(path) === path
  ) {
    throw new Error(`Asset path escapes its directory: ${path}`)
  }
  return target
}

async function jsonFiles(root: string): Promise<string[]> {
  const files: string[] = []
  for await (const entry of walk(root, { exts: [".json"], followSymlinks: false })) {
    if (entry.isFile) files.push(entry.path)
  }
  return files.sort()
}

async function readObjects(path: string, repoRoot: string): Promise<GameObject[]> {
  const text = await Deno.readTextFile(path)
  const root = v.parse(ObjectsSchema, JSON.parse(text))
  const objects = Array.isArray(root) ? root : [root]
  // Preserve the upstream guide's source-line anchors, after validating the entire JSON document.
  let depth = 0
  let line = 1
  let startLine = 1
  let inString = false
  let escaped = false
  let index = 0
  for (const character of text) {
    if (inString) {
      if (escaped) escaped = false
      else if (character === "\\") escaped = true
      else if (character === '"') inString = false
    } else if (character === '"') {
      inString = true
    } else if (character === "{") {
      if (depth++ === 0) startLine = line
    } else if (character === "}") {
      if (--depth === 0) {
        objects[index++].__filename = `${relative(repoRoot, path)}#L${startLine}-L${line}`
      }
    }
    if (character === "\n") line++
  }
  if (index !== objects.length) throw new Error(`Cannot locate source objects in ${path}`)
  return objects
}

async function copyNotices(source: string, destination: string): Promise<void> {
  for await (const entry of walk(source, { followSymlinks: false })) {
    if (
      !entry.isFile ||
      !/(?:licen[sc]e|credits?|readme|copying|authors?)/i.test(basename(entry.path))
    ) continue
    const target = join(destination, relative(source, entry.path))
    await ensureDir(dirname(target))
    await Deno.copyFile(entry.path, target)
  }
}

async function copyAsset(source: string, destination: string): Promise<void> {
  await ensureDir(dirname(destination))
  if (/\.png$/i.test(source)) {
    // ImageMagick's portable CLI is also available in Ubuntu's ImageMagick 6 package.
    await run("convert", [
      source,
      "-define",
      "webp:lossless=true",
      destination.replace(/\.png$/i, ".webp"),
    ])
  } else {
    await Deno.copyFile(source, destination)
  }
}

async function copyChunks(chunks: unknown, source: string, destination: string): Promise<number> {
  const files = new Set(v.parse(ChunkSchema, chunks).map((chunk) => chunk.file))
  for (const file of files) {
    await copyAsset(containedPath(source, file), containedPath(destination, file))
  }
  return files.size
}

async function generate(output: string): Promise<void> {
  const repoRoot = resolve(".")
  const [commit, commitDate] = (await run("git", ["log", "-1", "--format=%H%n%cI"], repoRoot))
    .split("\n")
  if (!/^[a-f0-9]{40}$/.test(commit) || Number.isNaN(Date.parse(commitDate))) {
    throw new Error("Invalid checkout provenance")
  }
  const dirty = Boolean(
    await run("git", [
      "status",
      "--porcelain",
      "--untracked-files=all",
      "--",
      "data/json",
      "data/mods",
      "gfx",
    ], repoRoot),
  )
  const buildNumber = `${commitDate.slice(0, 10).replaceAll("-", ".")}+${commit.slice(0, 12)}${
    dirty ? "-dirty" : ""
  }`
  const provenance = {
    repo: FORK_REPO,
    repo_url: FORK_URL,
    branch: "main",
    commit_sha: commit,
    commit_url: `${FORK_URL}/commit/${commit}`,
    commit_date: commitDate,
    working_tree_changes: dirty,
    generated_at: new Date().toISOString(),
  }
  const buildDir = join(resolve(output), buildNumber)
  const guideRoot = dirname(resolve(output))
  await ensureDir(buildDir)
  const mods: Record<string, ModData> = Object.create(null)
  for (const path of await jsonFiles(join(repoRoot, "data/mods"))) {
    if (basename(path) !== "modinfo.json") continue
    const infos = (await readObjects(path, repoRoot)).filter((object) =>
      object.type === "MOD_INFO" && !object.obsolete
    )
    if (!infos.length) continue
    const directory = dirname(path)
    const data: GameObject[] = []
    for (const file of await jsonFiles(directory)) {
      data.push(
        ...(await readObjects(file, repoRoot)).filter((object) => object.type !== "MOD_INFO"),
      )
    }
    for (const info of infos) {
      const id = v.parse(v.string(), info.id)
      if (!id || id === "." || id === ".." || /[/\\]/.test(id)) {
        throw new Error(`Unsafe mod ID: ${id}`)
      }
      if (Object.hasOwn(mods, id)) throw new Error(`Duplicate mod ID: ${id}`)
      mods[id] = { info, data, directory }
    }
  }
  const data: GameObject[] = []
  for (const path of await jsonFiles(join(repoRoot, "data/json"))) {
    data.push(...await readObjects(path, repoRoot))
  }
  const modInfos = Object.fromEntries(Object.entries(mods).map(([id, mod]) => [id, mod.info]))
  const modData = Object.fromEntries(
    Object.entries(mods).map(([id, mod]) => [id, { info: mod.info, data: mod.data }]),
  )
  const writeJson = async (path: string, value: unknown) =>
    await Deno.writeTextFile(path, JSON.stringify(value))
  await writeJson(join(buildDir, "all.json"), {
    build_number: buildNumber,
    release: {
      tag_name: buildNumber,
      name: `${FORK_REPO}${dirty ? " (uncommitted data)" : ""}`,
      published_at: commitDate,
      prerelease: false,
      fork: provenance,
    },
    data,
    mods: modInfos,
  })
  await writeJson(join(buildDir, "all_mods.json"), modData)

  let images = 0
  const gfx = join(repoRoot, "gfx")
  for await (
    const entry of walk(gfx, { maxDepth: 1, includeFiles: false, followSymlinks: false })
  ) {
    if (entry.path === gfx) continue
    const config = join(entry.path, "tile_config.json")
    const raw = v.parse(
      v.looseObject({ "tiles-new": ChunkSchema }),
      JSON.parse(await Deno.readTextFile(config)),
    )
    const destination = join(buildDir, "gfx", basename(entry.path))
    await ensureDir(destination)
    await Deno.copyFile(config, join(destination, "tile_config.json"))
    images += await copyChunks(raw["tiles-new"], entry.path, destination)
    await copyNotices(entry.path, destination)
  }
  for (const [id, mod] of Object.entries(mods)) {
    const tiles = mod.data.filter((object) => object.type === "mod_tileset")
    if (!tiles.length) continue
    const destination = join(buildDir, "mods", id)
    const files = new Set(
      tiles.flatMap((tile) => v.parse(ChunkSchema, tile["tiles-new"]).map((chunk) => chunk.file)),
    )
    for (const file of files) {
      const source = containedPath(repoRoot, relative(repoRoot, resolve(mod.directory, file)))
      const target = containedPath(buildDir, relative(buildDir, resolve(destination, file)))
      await copyAsset(source, target)
      images++
    }
    await copyNotices(mod.directory, destination)
  }
  const external = join(repoRoot, "data/json/external_tileset")
  for await (const entry of walk(external, { exts: [".png"], followSymlinks: false })) {
    if (!entry.isFile) continue
    await copyAsset(
      entry.path,
      join(buildDir, "gfx/external_tileset", relative(external, entry.path)),
    )
    images++
  }
  await copyNotices(external, join(buildDir, "gfx/external_tileset"))
  // ponytail: one current fork snapshot, split aliases when stable and nightly fork datasets are published separately.
  for (const alias of ["stable", "nightly", "latest"]) {
    await copy(buildDir, join(resolve(output), alias), { overwrite: true })
  }
  await writeJson(join(guideRoot, "builds.json"), [{
    build_number: buildNumber,
    prerelease: false,
    created_at: commitDate,
    langs: [],
    fork: provenance,
  }])
  await writeJson(join(guideRoot, "provenance.json"), { ...provenance, build_number: buildNumber })
  console.log(
    `${buildNumber}: ${data.length} objects, ${
      Object.keys(mods).length
    } mods, ${images} tile sheets`,
  )
  console.log(
    `Source: ${provenance.commit_url}${dirty ? " plus uncommitted game-data changes" : ""}`,
  )
}

if (import.meta.main) {
  await new Command().name("generate-guide-data")
    .description(
      "Generate the current fork's guide data and WebP tile assets (requires ImageMagick).",
    )
    .option("-o, --output <dir:string>", "Guide data directory", {
      default: "docs/_site/guide/data",
    })
    .action(async ({ output }) => await generate(output))
    .parse(Deno.args)
}
