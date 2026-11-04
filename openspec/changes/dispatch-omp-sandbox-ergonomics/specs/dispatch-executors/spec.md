## MODIFIED Requirements

### Requirement: An omp lane's shell runs inside an operating-system sandbox
Every shell command an omp lane runs — through its shell tool or a user-entered shell command — SHALL execute inside an operating-system sandbox whose writable locations are only the lane's worktree, the parts of the repository's common git directory a commit writes (objects, loose and packed refs, reflogs and LFS objects) plus the lane's own administrative directory, the user's package-manager caches, a temporary directory private to the lane, and the system temporary directory `/tmp` (by its real path) unless the repository's main checkout, the lane's worktree or the common git directory lies under it, in which case `/tmp` SHALL stay closed and the launch SHALL report it. Nothing that tells git where a repository or its configuration is — the worktree's `.git` pointer, the lane's administrative `commondir`, `gitdir` and `config.worktree`, the common directory's `config`, `commondir`, `config.worktree` and hooks, and other worktrees' administrative files — SHALL be writable, and the dispatcher's own git commands SHALL NOT run a repository-configured file-system monitor. The sandbox SHALL deny reading the user's SSH, cloud, GnuPG, container, Kubernetes, `netrc`, GitHub and GitLab CLI, codex and omp credential locations. Shell commands SHALL be allowed to listen on and connect to `localhost` ports, and SHALL NOT be allowed to listen on any other interface. Outbound network access beyond `localhost` SHALL be limited to an allowlist of package-registry hosts: the public registries and the registries and mirrors the user configured for npm, pip, Go, Maven and Cargo. Package managers that do not use the sandbox's proxy on their own SHALL be configured inside the sandbox to use it. When the sandbox cannot be initialized, shell commands SHALL be refused rather than run unsandboxed.

#### Scenario: Commit from the lane
- **WHEN** an omp lane runs `git commit` in its worktree
- **THEN** the commit SHALL succeed

#### Scenario: Installing dependencies
- **WHEN** an omp lane installs a dependency with npm, pnpm, bun, pip, uv, Go, Maven or Cargo from a registry on the allowlist
- **THEN** the install SHALL succeed, writing only to the worktree, the package-manager caches and the lane's temporary directory, and leaving the worktree's other files untouched

#### Scenario: Test with a local server
- **WHEN** a test in an omp lane starts a server on a `localhost` port and connects to it
- **THEN** the server SHALL start and the connection SHALL succeed

#### Scenario: Listening beyond loopback
- **WHEN** an omp lane's shell command listens on a non-loopback interface such as `0.0.0.0`
- **THEN** the bind SHALL fail with a permission error

#### Scenario: Scratch file in /tmp
- **WHEN** an omp lane writes `/tmp/DebugFreezeTest.java` through its shell or its write tool, in a repository that does not live under `/tmp`
- **THEN** the write SHALL succeed

#### Scenario: Repository under /tmp
- **WHEN** an omp lane is launched for a repository whose main checkout lies under `/tmp`
- **THEN** `/tmp` SHALL NOT be added to the writable locations, a shell write to the main checkout SHALL still fail, and the launch result SHALL say that `/tmp` stayed closed

#### Scenario: Write outside the lane through the shell
- **WHEN** an omp lane's shell command writes to the main checkout, the home directory, the common git directory's hooks, config or `commondir`, or another worktree's administrative files
- **THEN** the write SHALL fail with a permission error

#### Scenario: Redirecting git
- **WHEN** an omp lane tries to rewrite or remove its worktree's `.git` pointer or the worktree's `commondir`
- **THEN** the write SHALL fail, and a later `list` SHALL run no program named in a repository configuration

#### Scenario: Host not on the allowlist
- **WHEN** an omp lane's shell command connects to a host that is not on the allowlist
- **THEN** the connection SHALL be refused

#### Scenario: Sandbox unavailable
- **WHEN** the sandbox fails to initialize in an omp lane
- **THEN** every shell command SHALL be refused with that reason and no shell command SHALL run outside the sandbox
