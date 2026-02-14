## ADDED Requirements

### Requirement: Generate main.go entry point
The system SHALL generate a `main.go` file that embeds the frontend dist directory using `//go:embed all:dist`, configures Wails v2 application options (title, dimensions, asset server), and binds the App struct.

#### Scenario: Standard main.go generation
- **WHEN** Agent generates main.go for a project with app name "MyApp"
- **THEN** the generated file SHALL contain `//go:embed all:dist`, Wails `options.App` with `Title` set to the app name, default window size 1440x900, minimum size 1024x768, and `AssetServer` configured with embedded assets

#### Scenario: Main.go with API proxy enabled
- **WHEN** project detection reports `apiProxy: true`
- **THEN** the generated main.go SHALL configure `AssetServer.Handler` to point to the App struct (which implements `http.Handler`)

### Requirement: Generate app.go application struct
The system SHALL generate an `app.go` file containing the App struct with a `startup` lifecycle method.

#### Scenario: App.go without API proxy
- **WHEN** project detection reports `apiProxy: false`
- **THEN** the generated app.go SHALL contain only the App struct with `ctx context.Context` field, `NewApp()` constructor, and `startup(ctx)` method

#### Scenario: App.go with API proxy
- **WHEN** project detection reports `apiProxy: true` with `apiPrefix: "/api/"`
- **THEN** the generated app.go SHALL additionally implement `ServeHTTP(w, r)` that proxies requests matching the API prefix to the backend URL, using `http.Client` with 300-second timeout. The backend URL SHALL be injectable via `ldflags -X main.backendURL=...`

### Requirement: Generate wails.json configuration
The system SHALL generate a `wails.json` file with project metadata and frontend build commands.

#### Scenario: Vite-based project
- **WHEN** project detection reports `buildTool: "vite"`
- **THEN** wails.json SHALL set `frontend:install` to `"npm install"`, `frontend:build` to `"npm run build"`, and `frontend:dev:watcher` to `"npm run dev"`

#### Scenario: Webpack-based project
- **WHEN** project detection reports `buildTool: "webpack"`
- **THEN** wails.json SHALL set `frontend:build` to `"npm run build"` and adapt commands to the webpack project structure

### Requirement: Generate external link interception code
The system SHALL generate a frontend code snippet that intercepts clicks on external links (`http://` or `https://`) and opens them in the system default browser via `window.runtime.BrowserOpenURL()`.

#### Scenario: External link click handling
- **WHEN** a user clicks an `<a>` tag with an `href` starting with `http://` or `https://` inside the desktop app
- **THEN** the click SHALL be intercepted, default navigation prevented, and the URL opened in the system browser

#### Scenario: Internal navigation preserved
- **WHEN** a user clicks an `<a>` tag with an `href` starting with `#` or `javascript:`
- **THEN** the click SHALL NOT be intercepted and default behavior SHALL be preserved
