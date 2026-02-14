## 1. Project Setup

- [x] 1.1 Create `desktop-kit/` directory structure: `scripts/`, `references/`
- [x] 1.2 Create `desktop-kit/SKILL.md` skeleton with YAML frontmatter (name: desktop-kit, description) and placeholder workflow sections
- [x] 1.3 Register desktop-kit in `.claude-plugin/marketplace.json`

## 2. Project Detection (project-detection spec)

- [x] 2.1 Create `desktop-kit/scripts/detect-project.sh` — framework detection (React/Vue/Svelte/static) by inspecting package.json and directory structure
- [x] 2.2 Add build tool detection (Vite/Webpack/None) to detect-project.sh
- [x] 2.3 Add API call pattern detection (fetch/axios baseURL, .env variables) to detect-project.sh
- [x] 2.4 Add JSON output format with framework, buildTool, apiProxy, appName, appVersion fields
- [x] 2.5 Add error handling for missing package.json (exit 1 with JSON error)

## 3. Wails Scaffold Knowledge (wails-scaffold spec)

- [x] 3.1 Create `desktop-kit/references/wails-scaffold.md` — main.go generation patterns (embed dist, Wails options, AssetServer config)
- [x] 3.2 Add app.go generation patterns to wails-scaffold.md — App struct, startup, with/without API proxy variants
- [x] 3.3 Add wails.json generation patterns to wails-scaffold.md — Vite and Webpack frontend build commands
- [x] 3.4 Create `desktop-kit/references/api-proxy.md` — Go reverse proxy pattern (ServeHTTP, 300s timeout, ldflags backendURL injection)
- [x] 3.5 Create `desktop-kit/references/external-links.md` — frontend JS snippet for intercepting external link clicks via BrowserOpenURL

## 4. App Icon Generation (app-icon-gen spec)

- [x] 4.1 Create `desktop-kit/references/icon-spec.md` — macOS icon canvas specification (1024x1024, safe area, corner radius, gradient SVG structure)
- [x] 4.2 Create `desktop-kit/references/icon-templates.md` — Template A (gradient + letter) and Template B (solid + geometric) complete SVG code with parameterizable color/text placeholders
- [x] 4.3 Create `desktop-kit/scripts/svg-to-icns.sh` — SVG → multi-size PNG iconset → ICNS conversion with rsvg-convert primary and sips fallback

## 5. DMG Background Generation (dmg-background-gen spec)

- [x] 5.1 Create `desktop-kit/references/dmg-background-spec.md` — DMG coordinate system (600x400 canvas, drop zones at 150,185 and 450,185), create-dmg full command, HTML wrapper template
- [x] 5.2 Create `desktop-kit/references/dmg-templates.md` — at least 1 complete DMG background SVG template with locked drop zone coordinates, decorative elements, and ad-hoc signing installation guide text

## 6. Build Pipeline (build-pipeline spec)

- [x] 6.1 Create `desktop-kit/references/build-scripts.md` — build-dmg.sh generation knowledge: version sync from package.json, ldflags injection, wails build, ad-hoc codesign, create-dmg, prerequisite checking
- [x] 6.2 Create `desktop-kit/references/info-plist.md` — Info.plist generation knowledge: localization (zh_CN, en), NSAppTransportSecurity, bundle metadata

## 7. SKILL.md Completion

- [x] 7.1 Complete `desktop-kit/SKILL.md` Phase 1 (project detection) — invoke detect-project.sh, parse JSON result, present detection summary
- [x] 7.2 Complete `desktop-kit/SKILL.md` Phase 2 (interactive confirmation) — app name, API proxy toggle, icon style, DMG style, brand color questions
- [x] 7.3 Complete `desktop-kit/SKILL.md` Phase 3 (code generation) — reference loading decision tree, file generation sequence (Wails shell → icon → DMG → build script → Info.plist)
- [x] 7.4 Complete `desktop-kit/SKILL.md` Phase 4 (post-generation guidance) — environment prerequisites, build commands, SVG→ICNS conversion, first-build notes
- [x] 7.5 Add sub-command routing to SKILL.md — `/desktop-kit init`, `/desktop-kit icon`, `/desktop-kit dmg-bg`, `/desktop-kit doctor`
