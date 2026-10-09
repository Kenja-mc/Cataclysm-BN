# Bright Nights Overhaul: agent guide

This file has two parts. Part 1 is for this fork. Part 2 is the upstream guide. Obey the two parts.

## Part 1: The fork

### Purpose

This repository is a fork of Cataclysm: Bright Nights (BN). The fork makes the game easier to
learn and use. It keeps the BN game rules. `OVERHAUL.md` explains each change.
`CHANGELOG-OVERHAUL.md` lists the changes by date.

### Rules

1. Do not change the game balance. Change the interface, the controls and duplicate item data only.
2. Put a new behavior behind an option when a player can want the old behavior.
3. Keep the classic control scheme the same as upstream.
4. Do not add AI art.
5. Write few comments. Write a comment only when the code does not show the reason.
6. Obey the upstream code rules in Part 2.

### Build

1. Run `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCURSES=ON -DTILES=OFF -DTESTS=ON`.
2. Run `ninja -C build cataclysm-bn cata_test`.

### Test

Do all three tests before you push. All results must be good.

1. Data check: run `./cataclysm-bn --basepath ./ --userdir /tmp/chk/ --check-all-mods`. Make sure
   that there are no errors.
2. Upstream unit tests: use the software GPU, as upstream CI does. Refer to "Unit tests" in
   `OVERHAUL.md`.
3. Fork end-to-end tests: run `python3 tests/e2e/run.py`. Do not run other heavy work at the same
   time, because slow input makes these tests fail.

Write one end-to-end test for each new fork feature. Do not write unit tests for fork features.

### Where to find the fork code

| Subject | Location |
| --- | --- |
| Modern keys | `data/raw/control_schemes/modern.json` |
| Options | `src/options.cpp` |
| Fork interface | `src/hud_boxes.cpp`, `src/body_panel.cpp`, `src/keyhints_panel.cpp`, `src/tile_selection.cpp`, `src/first_tips.cpp` |
| Quick stack and sort pile | `src/quick_stack.cpp` |
| Item variants and stack modifiers | `src/item_variant.cpp`, `src/stack_modifier.cpp`, `data/json/item_variants.json` |
| Save migrations for removed items | `data/json/obsoletion/` |
| End-to-end tests | `tests/e2e/` |

### Upstream merges

1. Merge the upstream `main` branch. Do not rebase.
2. Upstream can add items that the fork folded, for example `bp_` ammo, jewelry or novels. Fold the
   new items in the same way. Add a migration for each item that you remove.
3. Do not change the authors of upstream commits.

## Part 2: Upstream guide

### Cataclysm: Bright Nights - Agent Guidelines

## HARD CONSTRAINTS (NEVER VIOLATE)

Before writing **ANY** code, verify:

| ❌ VIOLATION                           | ✅ REQUIRED                                                                      |
| -------------------------------------- | -------------------------------------------------------------------------------- |
| manual iterator loops (`it++`, `++it`) | `std::ranges::*`, `collection \| std::views::*`, or range-based `for` if clearer |
| `int foo()`                            | `auto foo() -> int`                                                              |
| `Type x = value`                       | `auto x = value`                                                                 |
| `void fn(a, b, c, d, e)`               | `void fn(options_struct)`                                                        |
| `[](){\n return 1; \n }`               | `[](){ return 1; }`                                                              |

**Prefer `std::ranges`/`std::views`/`std::ranges::to`/cata_algo.h for collection work. Avoid manual iterator increment loops unless required by mutation semantics.**

- Ranges preference means composable iterator/view pipelines. Do not replace a clear counted/nested loop with `views::iota` + `ranges::for_each` just to avoid loop syntax; use a plain `for` when index access, early break, mutation, or nested traversal is clearer.
- prefer function-local `using namespace std::views;` and use `transform`/`filter` unqualified.
- prefer function-local `namespace ranges = std::ranges;` and use `ranges::*` without `std::`
- prefer method/function references over lambdas whenever possible, e.g. `transform( &vpart_position::part_index )` instead of `transform( []( const auto &vp ) { return vp.part_index(); } )`.

## Coding Convention

```c++
const auto foo = 3; //< **MUST** use `auto` for type. `const` **MUST** come before `auto`.

auto bar() -> int; //< **MUST** use trailing return types.
using my_callback_t = std::function<auto( int ) -> bool>; //< **MUST** use trailing return types in type aliases.
auto baz() -> int&; // *NOPAD*  //< **MUST** append `// *NOPAD*` for references/pointer returns to prevent astyle bugs.
auto qux() -> int { return 42; } //< **MUST** use single-line functions whenever possible.

auto qux = my_struct{ .a = 1, .b = 2 }; //< **MUST** use designated initializers.
auto two_value() -> my_data; //< **MUST NOT** use `std::pair`/`std::tuple` for multiple return values. Create a struct instead.
auto may_have_value() -> std::optional<int>; //< **MUST** use `std::optional` for functions that may not return a value.
auto may_fail() -> std::expected<int, std::string>; //< **MUST** use `std::expected` for functions that may fail.

/// **MUST** use triple slash for doc comments like rust's.
/// **MUST** use snake_case for functions and variables.
struct comparable {
  int x;
  int y;
  auto operator<=>( const comparable & ) const = default; // *NOPAD* //< **MUST** use `<=>` for comparisons and append `// *NOPAD*` at the end to prevent astyle bugs.
}

auto values = xs
  | std::views::filter( []( const auto & v ) { return v.is_valid(); } ) //< **MUST** use single line expression if it's single line expression
  | std::views::transform( []( const auto & v ) { return v.get_value(); } ) //< **SHOULD** use `auto` for lambda params
  | std::ranges::to<std::vector>(); //< **MUST** use `std::ranges` over for loops for collections.

namespace { // **MUST** use anonymous namespace for internal linkage over `static`.

// **MUST** use options struct for functions with >3 parameters
struct button_options {
  point pos;
  std::string text;
  nc_color fg = c_white;
  nc_color bg = c_black;
  bool enabled = true;
};
auto print_button( const catacurses::window &w, const button_options &opts ) -> void;

} // namespace
```

- **SHOULD NOT** modify existing headers with >10 usages. Create new header with pure functions.
- **MUST** use modern C++23 features.
- **MUST** preserve unused parameter names as comments instead of deleting them, e.g. `bool /*is_avatar*/` not `bool`; applies to functions and lambdas.
- **MUST** keep Lua function parameters typed with EmmyLua/LuaLS annotations, including existing and local helper functions: `---@param` and table `---@class`/`---@field` shapes where parameters are tables. Do not require or add `---@return` solely for annotation enforcement when the return type is inferable. Before touching Lua, inspect the file's annotation style and preserve complete function typing.
- **MUST** fix missing Lua binding type declarations at the binding/doc-generation source; do not hard-code generated binding classes in `data/raw/generate_types.lua` as a shortcut.
- **MUST** test C++ Lua binding behavior with real bound objects when adding or changing bindings; Lua-only mocks may supplement but must not be the sole validation for binding correctness.
- **MUST** use options struct for functions with more than 3 parameters. Use designated initializers at call sites.
- **MUST NOT** manually write an options/struct type at a call site when the function parameter type makes it inferable; use `{ .field = value }` instead of `options_type{ .field = value }`.
- **SHOULD** search for existing solution because it's a large, legacy codebase.
- **MUST** verify helper-specific matching semantics before relying on string prefixes. For overmap terrain `OtMatchType.PREFIX` / `is_ot_match`, pass the base token without a trailing separator, e.g. `"robofachq"`, because the matcher itself requires the following character to be `_`.

## Workflow

### WHEN given a link to an issue

- **Context**: Fetch issue details via GitHub MCP.
- **Branch**: Use `coderabbitai/git-worktree-runner` to create branch: `git gtr new <type>/<issue-id>/<issue-slug>`
  - type MUST be one of: `feat`, `fix`, `refactor`, `chore`, `build`, `ci`
- **Code**: Refer to [code changes](#when-working-on-code-changes).
- **PR**: Use [Template](./.github/pull_request_template.md). **DO NOT ADD fluff**. create via `git push && gh pr create --web --fill`.
- After opening or updating a Cataclysm-BN PR, track `gh pr checks` until CI finishes or a concrete blocker is identified; inspect failing job logs, fix branch-owned failures, commit, and push before finalizing. For transient or infrastructure failures, rerun when permitted or report the exact failing job and evidence.
- Before running broad formatter targets, prefer file-scoped formatting for touched files when available; if only a broad target exists, inspect and revert unrelated formatter-only changes before continuing.

### WHEN working on code changes

- **Style**: Follow [Code Style](./docs/en/dev/explanation/code_style.md). Use `_( "text" )` for L10n.
- **Format**: Format code before building/testing.

```sh
# Format C++ code
cmake --build build --target format
# Format JSON files
cmake --build build --target style-json-parallel
# Format scripts
deno fmt
deno task dprint fmt
```

- **Verify**: Build and fix any issues. Do not skip the game binary target when validating code changes; build `cataclysm-bn-tiles` together with tests.

```sh
# Build project and tests
cmake --preset linux-full
cmake --build --preset linux-full --target cataclysm-bn-tiles cata_test-tiles
```

- **Test**: Create/update relevant `tests/` (Catch2).

```sh
# Run Tests
./out/build/linux-full/tests/cata_test-tiles "[optional-filter]"

# Validate JSON
./build-scripts/lint-json.sh

# Check Mods (validates mod JSON files)
./out/build/linux-full/cataclysm-bn-tiles --check-mods

# Generate Lua Documentation (if conflicts with lua_annotations.lua or docs/en/mod/lua/reference/lua.md)
deno task docs:gen
```

- **Commit**: Commit **ATOMICALLY**. **MUST** Follow [Conventional Commits](./docs/en/contribute/changelog_guidelines.md). **MUST NOT** add body/footer unless critical.

## WHEN working on i18n / PO context

- **MUST NOT** reduce requested string/context coverage for review risk or churn. If the user names a word and its meanings, handle every named meaning.
- If adding JSON context requires loader support, add loader support instead of leaving a source uncontexted.
- **MUST** run `msgfmt -f -c -o /tmp/ko.mo lang/po/ko.po` after touching Korean PO files and fix reported errors before PR.
- **MUST** run `./tools/check_po_printf_format.py` after touching PO files and fix reported errors before PR.
- Do not call PO/printf errors pre-existing to skip them when the task touches that locale or validation path.
- If a mistake is found during the task, update AGENTS/skill immediately and fix the current branch before summarizing.

## WHEN translating docs

When translating, MUST search for correct glossary, e.g

```sh
rg -C2 -i '<<TARGET>>' lang/po/<<LANG>>.po | rg -v '^(#:|--)' | head -n 20
rg -C2 -i 'speedway' lang/po/ko.po | rg -v '^(#:|--)' | head -n 20
```

## References

- **Docs**: [Building](./docs/en/dev/guides/building/cmake.md), [Formatting](./docs/en/dev/guides/formatting.md), [Dev Index](./docs/en/dev/).
- **Review**: [LLM Guide](./.github/llm_review_guide.md).

- When fixing a bug, preserve requested behavior and visible content unless the user explicitly asks to remove it; fix the underlying issue instead of suppressing the affected feature.
- When reviewing PRs that stop tracking generated or externally pulled files, verify ignore rules by running the generator/pull command or checking `git status --ignored`; do not assume removed tracked files are ignored.
- When generated or externally pulled files are removed from tracking, verify all CI and release consumers still receive required files or directories.
