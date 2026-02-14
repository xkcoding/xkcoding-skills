## ADDED Requirements

### Requirement: Single source of truth for version
The system SHALL use `package.json` version field as the single source of truth. The build script SHALL read the version from `package.json` and synchronize it to `wails.json` before building.

#### Scenario: Version synchronization
- **WHEN** build script executes
- **THEN** it SHALL read the `version` field from `package.json`, update the `version` field in `wails.json` to match, and use this version in the output DMG filename

### Requirement: Generate build-dmg.sh script
The system SHALL generate a `scripts/build-dmg.sh` script that orchestrates the full macOS build pipeline: version sync → environment variable injection → wails build → codesign → create-dmg.

#### Scenario: Standard build flow
- **WHEN** user runs `scripts/build-dmg.sh`
- **THEN** the script SHALL execute in order: (1) read version from package.json, (2) sync version to wails.json, (3) read backend URL from `.env.production` if present, (4) run `wails build -clean` with ldflags injecting backendURL, (5) codesign the .app with ad-hoc signature, (6) run create-dmg to produce the final DMG

#### Scenario: Build without API proxy
- **WHEN** the project does not use API proxy (no `.env.production` or no backend URL configured)
- **THEN** the build script SHALL skip the ldflags backendURL injection and proceed with standard wails build

### Requirement: Correct codesign execution order
The system SHALL codesign components in the correct order. For builds without Sparkle: the .app bundle SHALL be signed with `codesign --deep -s -`. For builds with Sparkle (future P1): components MUST be signed in order: XPC services → Autoupdate → Updater.app → Sparkle.framework → .app.

#### Scenario: Ad-hoc codesign for MVP
- **WHEN** build script runs codesign step (MVP without Sparkle)
- **THEN** it SHALL execute `codesign --deep --force -s - "path/to/AppName.app"`

### Requirement: Generate Info.plist
The system SHALL generate a `build/darwin/Info.plist` file with appropriate macOS application configuration.

#### Scenario: Info.plist with localization and network access
- **WHEN** Agent generates Info.plist
- **THEN** the file SHALL include `CFBundleDevelopmentRegion` set to `zh_CN`, `CFBundleLocalizations` with `zh_CN`, `zh-Hans`, and `en`, and `NSAppTransportSecurity` with `NSAllowsArbitraryLoads` set to true (for internal API access)

### Requirement: DMG output naming convention
The system SHALL name the output DMG file using the pattern `AppName-VERSION-macOS.dmg`.

#### Scenario: DMG filename format
- **WHEN** building an app named "MyTool" at version "1.0.0"
- **THEN** the output DMG SHALL be named `MyTool-1.0.0-macOS.dmg`

### Requirement: Prerequisite checking
The build script SHALL verify that required tools are installed before proceeding with the build.

#### Scenario: All prerequisites available
- **WHEN** `go`, `wails`, and `create-dmg` are all found in PATH
- **THEN** the build SHALL proceed normally

#### Scenario: Missing prerequisite
- **WHEN** any of `go`, `wails`, or `create-dmg` is not found in PATH
- **THEN** the script SHALL exit with code 1 and print a clear error message identifying which tool is missing and how to install it
