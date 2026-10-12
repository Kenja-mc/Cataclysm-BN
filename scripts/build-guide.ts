#!/usr/bin/env -S deno run --allow-read --allow-write --allow-run=git,pnpm,tar --allow-env
/** @module Build the pinned GPL guide against this fork and publish its corresponding source. */
import { copy, ensureDir, exists } from "@std/fs"
import { join, resolve } from "@std/path"

const GUIDE_REPO = "ushkinaz/cbn-guide"
const GUIDE_COMMIT = "2bb50621d52e5ed7707631cb60b9a5d128b8670b"
const PAGES_URL = "https://kenja-mc.github.io/Cataclysm-BN"
const BASE_PATH = "/Cataclysm-BN/guide/"
const DATA_URL = Deno.env.get("DATA_BASE_URL") ?? `${PAGES_URL}/guide`
const PATCHED_FILES = [
  "vite.config.ts",
  "src/constants.ts",
  "index.html",
  "public/_headers",
  "src/MigoWarning.svelte",
  "public/opensearch.xml",
  "public/robots.txt",
  "public/sitemap.xml",
  "src/JSONView.svelte",
  "src/App.svelte",
  "scripts/gen-sitemap.ts",
]

async function run(command: string[], cwd: string): Promise<string> {
  const result = await new Deno.Command(command[0], {
    args: command.slice(1),
    cwd,
    env: {
      CI: "0",
      HUSKY: "0",
      SHARP_IGNORE_GLOBAL_LIBVIPS: "1",
      FORK_GUIDE_DATA_PATH: resolve("docs/_site/guide"),
    },
    stdout: "piped",
    stderr: "piped",
  }).output()
  const decoder = new TextDecoder()
  if (!result.success) {
    throw new Error(
      `${command.join(" ")} (${result.code}):\n${decoder.decode(result.stdout)}\n${
        decoder.decode(result.stderr)
      }`,
    )
  }
  return decoder.decode(result.stdout)
}

async function patch(path: string, replacements: [RegExp, string][]): Promise<void> {
  let text = await Deno.readTextFile(path)
  for (const [pattern, replacement] of replacements) {
    if (!pattern.test(text)) {
      throw new Error(`Pinned guide patch no longer matches: ${path}: ${pattern}`)
    }
    text = text.replace(pattern, () => replacement)
  }
  await Deno.writeTextFile(path, text)
}

async function main(): Promise<void> {
  const root = resolve(".")
  const guide = join(root, "build/cbn-guide")
  const output = join(root, "docs/_site/guide")
  if (!await exists(join(guide, ".git"))) {
    await ensureDir(join(root, "build"))
    await run(
      ["git", "clone", "--no-checkout", `https://github.com/${GUIDE_REPO}.git`, guide],
      root,
    )
    await run(["git", "checkout", GUIDE_COMMIT], guide)
  }
  if ((await run(["git", "rev-parse", "HEAD"], guide)).trim() !== GUIDE_COMMIT) {
    throw new Error(`Guide checkout must remain at pinned commit ${GUIDE_COMMIT}`)
  }
  const unrelated = (await run(["git", "diff", "--name-only", GUIDE_COMMIT], guide))
    .trim().split("\n").filter((path) => path && !PATCHED_FILES.includes(path))
  if (unrelated.length) {
    throw new Error(`Refusing to publish unrelated tracked clone changes: ${unrelated.join(", ")}`)
  }
  // Restore only owned patches, never another branch or unrelated clone changes.
  await run(["git", "checkout", GUIDE_COMMIT, "--", ...PATCHED_FILES], guide)
  await patch(join(guide, "vite.config.ts"), [
    [/base:\s*"\/"/, `base: "${BASE_PATH}"`],
    [
      new RegExp(RegExp.escape("https:\\/\\/data\\.cataclysmbn-guide\\.com"), "g"),
      RegExp.escape(DATA_URL),
    ],
    [
      /\/\/ The latest nightly \/ updates daily/,
      "// Moving fork aliases revalidate before displaying updated data.",
    ],
    [
      new RegExp(RegExp.escape("data\\/nightly\\/")),
      "data\\/(?:nightly|stable|latest)\\/",
    ],
    [
      /\s*\{\s*\/\/ The latest stable \/ rarely updates[\s\S]*?\n\s*\},(?=\s*\{\s*\/\/ Stable named releases)/,
      "",
    ],
  ])
  await patch(join(guide, "src/constants.ts"), [
    [
      /\bGUIDE_NAME\s*=\s*"[^"]*"/,
      'GUIDE_NAME = "The Hitchhiker\'s Guide to Cataclysm: Bright Nights (Kenja-mc)"',
    ],
    [/\bUI_GUIDE_NAME\s*=\s*"[^"]*"/, 'UI_GUIDE_NAME = "Cataclysm:BN Guide (Kenja-mc)"'],
    [/\bCANONICAL_URL\s*=\s*"[^"]*"/, `CANONICAL_URL = "${PAGES_URL}/guide"`],
    [/\bCBN_DATA_BASE_URL\s*=\s*"[^"]*"/, `CBN_DATA_BASE_URL = ${JSON.stringify(DATA_URL)}`],
    [/\bGAME_REPO_PATH\s*=\s*"[^"]*"/, 'GAME_REPO_PATH = "Kenja-mc/Cataclysm-BN"'],
    [/\bGAME_REPO_URL\s*=.*?$/m, "GAME_REPO_URL = `https://github.com/${GAME_REPO_PATH}`;"],
  ])
  await patch(join(guide, "index.html"), [
    [/href="[^"]*builds\.json"/, `href="${DATA_URL}/builds.json"`],
    [/https:\/\/cataclysmbn-guide\.com\/og-image\.webp/, `${PAGES_URL}/guide/og-image.webp`],
    [
      /<head>/,
      `<head>
    <script>
      const route = new URLSearchParams(location.search).get("_guide");
      if (route) {
        const target = new URL("${BASE_PATH}" + route, location.origin);
        if (target.origin === location.origin && target.pathname.startsWith("${BASE_PATH}")) {
          history.replaceState(null, "", target.href);
        }
      }
    </script>`,
    ],
  ])
  await patch(join(guide, "public/_headers"), [[
    /https:\/\/data\.cataclysmbn-guide\.com/g,
    DATA_URL,
  ]])
  await patch(join(guide, "src/JSONView.svelte"), [
    [/\$\{buildNumber\}/, '${buildNumber?.split("+")[1]?.replace(/-dirty$/, "")}'],
  ])
  await patch(join(guide, "src/App.svelte"), [
    [
      /<\/optgroup>/,
      `<option value="latest">Latest ({latestStableBuild?.build_number ?? "N/A"})</option></optgroup>`,
    ],
    [
      /<div id="credits"><\/div>/,
      `<div id="credits">
      Guide modified for Kenja-mc · <a href="${BASE_PATH}source.tar.gz">Corresponding source</a>
      · <a href="${BASE_PATH}LICENSE">GPL-3.0 license</a>
    </div>`,
    ],
  ])
  await patch(join(guide, "scripts/gen-sitemap.ts"), [
    [/import \{ createWriteStream \} from "node:fs";\n/, ""],
    [/import \{ pipeline \} from "node:stream\/promises";\n/, ""],
    [/BUILDS_URL, CANONICAL_URL, getDataJSONUrl/, "CANONICAL_URL"],
    [
      /const cacheDir = path\.join\(projectRoot, "\.cache", "data-cache"\);/,
      'const cacheDir = path.join(process.env.FORK_GUIDE_DATA_PATH!, "data");',
    ],
    [/async function downloadFile[\s\S]*?\n\}\n/, ""],
    [
      /console\.log\(`Fetching builds[\s\S]*?const builds = \(await res\.json\(\)\) as any\[\];/,
      'const builds = await readJson(path.join(process.env.FORK_GUIDE_DATA_PATH!, "builds.json"));',
    ],
    [
      /path\.join\(cacheDir, `all-\$\{version\}\.json`\)/,
      'path.join(cacheDir, version, "all.json")',
    ],
    [
      /const url = getDataJSONUrl\(version, "all\.json"\);[\s\S]*?await downloadFile\(url, localAllJson\);/,
      'throw new Error("Generate the fork guide dataset before building its sitemap");',
    ],
  ])
  for (
    const path of [
      "src/MigoWarning.svelte",
      "public/opensearch.xml",
      "public/robots.txt",
      "public/sitemap.xml",
    ]
  ) {
    await patch(join(guide, path), [[/https:\/\/cataclysmbn-guide\.com/g, `${PAGES_URL}/guide`]])
  }
  await run(["pnpm", "install", "--frozen-lockfile"], guide)
  await run(["pnpm", "gen:sitemap"], guide)
  await run(["pnpm", "build"], guide)
  await ensureDir(output)
  await copy(join(guide, "dist"), output, { overwrite: true })
  await Deno.copyFile(join(guide, "LICENSE"), join(output, "LICENSE"))
  await Deno.writeTextFile(
    join(guide, "FORK-NOTICE.txt"),
    `Modified ${new Date().toISOString()} for Kenja-mc from ${GUIDE_REPO}@${GUIDE_COMMIT}.\n` +
      "Changes: fork data and source links, project-subpath routing, branding, alias freshness, sitemap and distribution source links.\n" +
      "This modified guide remains licensed under GPL-3.0; original copyright notices are retained.\n",
  )
  const manifest = await Deno.makeTempFile({ prefix: "bn-guide-source-" })
  try {
    // Whitelist tracked source files; never archive credentials, caches or node_modules.
    await Deno.writeTextFile(
      manifest,
      await run(["git", "ls-files", "-z"], guide) + "FORK-NOTICE.txt\0",
    )
    await run(["tar", "--null", "-czf", join(output, "source.tar.gz"), "-T", manifest], guide)
  } finally {
    await Deno.remove(manifest)
  }
  const oldNested404 = join(output, "404.html")
  if (await exists(oldNested404)) await Deno.remove(oldNested404)
  console.log(`Built ${GUIDE_REPO}@${GUIDE_COMMIT} in ${output}; data: ${DATA_URL}`)
}

if (import.meta.main) {
  try {
    await main()
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error))
    Deno.exit(1)
  }
}
