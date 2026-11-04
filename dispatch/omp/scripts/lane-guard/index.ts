/**
 * lane-guard — the boundary of a /dispatch:omp lane.
 *
 * - Shell: the agent's `bash` tool and user `!` commands run inside @anthropic-ai/sandbox-runtime (Seatbelt on
 *   macOS, bubblewrap on Linux). Without a policy, or when the sandbox cannot start, every shell command is
 *   refused: nothing ever falls back to an unsandboxed shell.
 * - Files: `write` and `edit` may only touch the policy's writable roots minus its denied paths (every file an
 *   edit names, symlinks followed). The default posture blocks anything else and tells the model why; the strict
 *   posture asks a human instead. `read`, `grep`, `find` and `ls` take plain paths only and never the policy's
 *   unreadable directories.
 *
 * The policy comes only from `--lane-policy <file>`, written by lane.py outside the repository. Nothing is
 * read from the lane's own files, so the repository cannot widen its own boundary.
 */

import { spawn } from "node:child_process";
import { existsSync, lstatSync, readFileSync, readlinkSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { isAbsolute, resolve, sep } from "node:path";
import { SandboxManager } from "@anthropic-ai/sandbox-runtime";
import type { BashOperations, ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createBashTool } from "@earendil-works/pi-coding-agent";

interface LanePolicy {
	version: number;
	posture: "block" | "strict";
	tmpDir?: string;
	env?: Record<string, string>;
	allowWrite: string[];
	denyWrite: string[];
	denyRead: string[];
	allowedDomains: string[];
	/** Shell commands may listen on and connect to localhost ports (tests that start a local server). */
	allowLocalBinding?: boolean;
}

// The real location a path refers to: every symlink component is followed, including a final link whose
// target does not exist yet (writing through it creates the target), so /tmp/... equals /private/tmp/... and a
// planted link cannot carry a write or read past the policy.
function canonical(path: string, depth = 0): string {
	if (depth > 40) throw new Error(`too many symbolic links: ${path}`);
	const parts = resolve(path).split(sep).filter(Boolean);
	let current = sep;
	for (let i = 0; i < parts.length; i++) {
		const next = resolve(current, parts[i]);
		let link: string | undefined;
		try {
			if (lstatSync(next).isSymbolicLink()) link = readlinkSync(next);
		} catch {
			return resolve(next, ...parts.slice(i + 1)); // nothing exists from here on
		}
		// realpath gives the on-disk spelling, so ".GIT" on a case-insensitive disk compares as ".git".
		current = link === undefined ? realpathSync.native(next) : canonical(resolve(current, link), depth + 1);
	}
	return current;
}

// A tool's path argument, absolute and with symlinks resolved; "~" means the home directory, as in a shell.
function toolPath(raw: unknown, cwd: string): string {
	let p = String(raw ?? "").trim() || ".";
	if (p === "~" || p.startsWith("~/")) p = homedir() + p.slice(1);
	return canonical(isAbsolute(p) ? p : resolve(cwd, p));
}

// omp's read also fetches web pages and internal resources (skill://, ssh://, proc://, vault://, mcp://, urn:...,
// even a repaired "https:/host") from its own process, outside the sandbox, and splits a read target on ";" and
// "," into several reads the guard never sees. The lane reads plain paths only; the goal names the apply skill
// by its path.
// omp's own test for a URI (internal-urls/parse.ts): a scheme, unless it is one letter, contains a dot, or is
// followed by a read selector chain (`Makefile:12`, `README.md:1-20`, `notes:raw`).
const OPAQUE_URI = /^([a-z][a-z0-9+.-]*):(.+)$/is;
const SELECTOR = String.raw`(?:raw|conflicts|img|-?\d+(?:[-+]\d+)?(?:,\d+(?:[-+]\d+)?)*)`;
const SELECTOR_CHAIN = new RegExp(`^${SELECTOR}(?::${SELECTOR})*(?:;|$)`, "i");

/** What makes a tool target something other than a plain path, or undefined for a plain path. */
function nonPathTarget(raw: unknown): string | undefined {
	const p = String(raw ?? "").trim();
	if (p.includes("://")) return "a resource address";
	if (/^www\./i.test(p)) return "a web address";
	const opaque = OPAQUE_URI.exec(p);
	if (opaque && opaque[1].length > 1 && !opaque[1].includes(".") && !SELECTOR_CHAIN.test(opaque[2])) {
		return `a ${opaque[1].toLowerCase()}: resource`;
	}
	return undefined;
}

/** omp's read splits a target on ";" and "," into several reads that never pass the guard, so each piece is
 * checked on its own (a selector such as `a.ts:1-5,10` splits into harmless pieces). */
function readPieces(raw: unknown): string[] {
	const pieces = String(raw ?? "").split(/[;,]/).map((x) => x.trim()).filter(Boolean);
	return pieces.length ? pieces : [""];
}

/** Every file an edit call may touch, or undefined when they cannot all be named. omp fills in `path` only when
 * a hashline patch names one file; several files come as `paths`, a hashline `MV DEST` and the apply_patch
 * headers name more, and patch mode may carry `rename`. */
function editTargets(input: Record<string, unknown>): string[] | undefined {
	const out: string[] = [];
	const str = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim() : undefined);
	for (const key of ["path", "_path", "rename"]) {
		const v = str(input[key]);
		if (v) out.push(v);
	}
	if (Array.isArray(input.paths)) for (const v of input.paths) if (str(v)) out.push(str(v)!);
	// The patch text is scanned whatever else the call carries: omp's native parser reads its headers even when a
	// `path` is present, and tolerates indentation and extra spaces. Collecting too much only blocks more.
	for (const text of [str(input.input), str(input._input)]) {
		if (!text) continue;
		for (const raw of text.split("\n")) {
			if (raw.startsWith("+")) continue; // a body row
			const line = raw.replace(/\r$/, "").trim();
			const m =
				/^\[(.+?)(?:#[0-9a-fA-F]{4})?\]$/.exec(line) ??
				/^¶+\s*(.+?)(?:#[0-9a-fA-F]{4})?$/.exec(line) ??
				/^\*+\s*(?:Add|Update|Delete)\s+File\s*:\s*(.+)$/i.exec(line) ??
				/^\*+\s*Move\s+to\s*:\s*(.+)$/i.exec(line) ??
				/^MV\s+(.+)$/i.exec(line);
			if (m) out.push(m[1].trim().replace(/^(["'])(.*)\1$/, "$2"));
		}
	}
	return out.length ? out : undefined;
}

function within(path: string, root: string): boolean {
	return path === root || path.startsWith(root + sep);
}

function loadPolicy(file: string): LanePolicy {
	const p = JSON.parse(readFileSync(file, "utf-8")) as LanePolicy;
	const lists = [p.allowWrite, p.denyWrite, p.denyRead, p.allowedDomains];
	if (p.version !== 1 || !lists.every(Array.isArray) || !p.allowWrite.length) {
		throw new Error("malformed lane policy");
	}
	if (p.posture !== "block" && p.posture !== "strict") throw new Error(`unknown posture ${p.posture}`);
	if (p.tmpDir !== undefined && typeof p.tmpDir !== "string") throw new Error("tmpDir must be a path");
	if (p.allowLocalBinding !== undefined && typeof p.allowLocalBinding !== "boolean") {
		throw new Error("allowLocalBinding must be true or false");
	}
	for (const [k, v] of Object.entries(p.env ?? {})) {
		if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k) || typeof v !== "string") throw new Error(`bad env entry ${k}`);
	}
	return p;
}

function shellQuote(s: string): string {
	return `'${s.replace(/'/g, `'\\''`)}'`;
}

// Runs inside the sandbox before every command, where the sandbox's proxy is known (known-behaviors P21):
// TMPDIR moves to the lane's own temp dir; Node's built-in fetch is told to use the proxy; the JVM gets an
// IPv4 socket (the proxy is unreachable over its default IPv6 one) and a writable java.io.tmpdir; Maven, whose
// HTTP transport ignores the JVM's proxy properties, gets a global settings file holding only <proxies>.
function prelude(tmpDir: string | undefined, env: Record<string, string> = {}): string {
	const exports = Object.entries(env).map(([k, v]) => `export ${k}=${shellQuote(v)}\n`).join("");
	if (!tmpDir) return `${exports}export NODE_USE_ENV_PROXY=1\n`;
	const tmp = shellQuote(tmpDir);
	const settings = shellQuote(`${tmpDir}/maven-proxy-settings.xml`);
	const proxy = (id: string, protocol: string) =>
		`<proxy><id>${id}</id><active>true</active><protocol>${protocol}</protocol><host>127.0.0.1</host><port>%s</port></proxy>`;
	return exports + [
		`export TMPDIR=${tmp} NODE_USE_ENV_PROXY=1`,
		`export JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true -Djava.io.tmpdir=$TMPDIR\${JAVA_TOOL_OPTIONS:+ $JAVA_TOOL_OPTIONS}"`,
		`if [ -n "\${HTTPS_PROXY:-}" ]; then`,
		`  __lane_port=\${HTTPS_PROXY##*:}; __lane_port=\${__lane_port%%/*}`,
		`  __lane_gs=${settings}`,
		`  printf '<settings><proxies>${proxy("lane-https", "https")}${proxy("lane-http", "http")}</proxies></settings>\\n' "$__lane_port" "$__lane_port" > "$__lane_gs"`,
		// MAVEN_ARGS is word-split by Maven's launcher (3.9+, e.g. ./mvnw): no quotes inside it.
		`  export MAVEN_ARGS="-gs $__lane_gs\${MAVEN_ARGS:+ $MAVEN_ARGS}"`,
		`  mvn() { MAVEN_ARGS= command mvn -gs "$__lane_gs" "$@"; }`,
		`  export __lane_gs`,
		`  export -f mvn`,
		`fi`,
		"",
	].join("\n");
}

function sandboxedOps(policy: LanePolicy | undefined): BashOperations {
	return {
		async exec(command, cwd, { onData, signal, timeout }) {
			if (!existsSync(cwd)) throw new Error(`Working directory does not exist: ${cwd}`);
			const wrapped = await SandboxManager.wrapWithSandbox(prelude(policy?.tmpDir, policy?.env) + command);
			return new Promise((resolvePromise, reject) => {
				const child = spawn("bash", ["-c", wrapped], { cwd, detached: true, stdio: ["ignore", "pipe", "pipe"] });
				const kill = () => {
					if (!child.pid) return;
					try {
						process.kill(-child.pid, "SIGKILL");
					} catch {
						child.kill("SIGKILL");
					}
				};
				let timedOut = false;
				const timer =
					timeout && timeout > 0
						? setTimeout(() => {
								timedOut = true;
								kill();
							}, timeout * 1000)
						: undefined;
				child.stdout?.on("data", onData);
				child.stderr?.on("data", onData);
				child.on("error", (err) => {
					if (timer) clearTimeout(timer);
					reject(err);
				});
				signal?.addEventListener("abort", kill, { once: true });
				child.on("close", (code) => {
					if (timer) clearTimeout(timer);
					signal?.removeEventListener("abort", kill);
					if (signal?.aborted) reject(new Error("aborted"));
					else if (timedOut) reject(new Error(`timeout:${timeout}`));
					else resolvePromise({ exitCode: code });
				});
			});
		},
	};
}

export default function (pi: ExtensionAPI) {
	pi.registerFlag("lane-policy", {
		description: "Sandbox and write policy of a /dispatch:omp lane (JSON written by lane.py)",
		type: "string",
		default: "",
	});

	const cwd = process.cwd();
	const localBash = createBashTool(cwd);
	let policy: LanePolicy | undefined;
	let roots: string[] = [];
	let denied: string[] = [];
	let unreadable: string[] = [];
	// Fail closed: until the sandbox is up, this is the reason every shell command is refused.
	let refusal: string | undefined = "lane-guard has not started yet";

	pi.registerTool({
		...localBash,
		label: "bash (lane sandbox)",
		async execute(id, params, signal, onUpdate) {
			if (refusal) throw new Error(`lane-guard refused the shell command: ${refusal}`);
			const sandboxed = createBashTool(cwd, { operations: sandboxedOps(policy) });
			return sandboxed.execute(id, params, signal, onUpdate);
		},
	});

	pi.on("user_bash", () => {
		if (refusal) throw new Error(`lane-guard refused the shell command: ${refusal}`);
		return { operations: sandboxedOps(policy) };
	});

	pi.on("tool_call", async (event, ctx) => {
		try {
			return await guardFiles(event, ctx);
		} catch (err) {
			// Fail closed: a target the guard cannot resolve is not allowed.
			return { block: true, reason: `lane-guard could not check this call: ${err instanceof Error ? err.message : err}` };
		}
	});

	async function guardFiles(
		event: { toolName: string; input?: unknown },
		ctx: { cwd: string; hasUI?: boolean; ui: { select(title: string, options: string[]): Promise<string | undefined> } },
	) {
		const input = (event.input ?? {}) as Record<string, unknown>;
		const reader = ["read", "grep", "find", "ls"].includes(event.toolName);
		if (!reader && event.toolName !== "write" && event.toolName !== "edit") return undefined;
		if (!policy) return { block: true, reason: `lane-guard has no policy: ${refusal}` };
		const raws = event.toolName === "edit" ? editTargets(input) : reader ? readPieces(input.path) : [input.path];
		if (!raws) {
			return {
				block: true,
				reason: "lane-guard cannot tell which files this edit touches; name the file in the edit's path, or use write",
			};
		}
		for (const raw of raws) {
			const other = nonPathTarget(raw);
			if (other) {
				return {
					block: true,
					reason: `${String(raw)} is ${other}; this lane may only ${reader ? "read" : "write"} plain paths${reader ? "" : " inside its writable locations"}`,
				};
			}
		}
		// The agent's own file readers run outside the OS sandbox, so the sandbox's denyRead is enforced here.
		if (reader) {
			// grep and find recurse, so searching an ancestor of a protected directory reads it too.
			const recursive = event.toolName === "grep" || event.toolName === "find";
			for (const raw of raws) {
				const target = toolPath(raw, ctx.cwd);
				const hit = unreadable.find((d) => within(target, d) || (recursive && within(d, target)));
				if (hit) return { block: true, reason: `${target} reaches ${hit}, which this lane may not read` };
			}
			return undefined;
		}
		const outside = raws
			.map((raw) => toolPath(raw, ctx.cwd))
			.filter((t) => !(roots.some((r) => within(t, r)) && !denied.some((d) => within(t, d))));
		if (!outside.length) return undefined;
		const target = outside.join(", ");
		const reason = `${target} ${outside.length > 1 ? "are" : "is"} outside this lane's writable paths (the lane worktree, the lane's own git data, package-manager caches, and the lane's temp directory)`;
		if (policy.posture === "strict" && ctx.hasUI) {
			// "Deny" comes first so that a stray enter can never approve the write.
			const choice = await ctx.ui.select(`lane-guard: allow ${event.toolName} outside the lane?\n  ${target}`, [
				"Deny",
				"Allow",
			]);
			if (choice === "Allow") return undefined;
			return { block: true, reason: `${reason}; a human declined it` };
		}
		return { block: true, reason };
	}

	pi.on("session_start", async (_event, ctx) => {
		const fail = (why: string) => {
			refusal = why;
			ctx.ui.setStatus("lane-guard", `⛔ lane-guard: shell refused (${why})`);
			ctx.ui.notify(`lane-guard: ${why}; shell commands are refused`, "error");
		};
		const file = String(pi.getFlag("lane-policy") ?? "");
		if (!file) return fail("no --lane-policy given");
		try {
			policy = loadPolicy(file);
		} catch (err) {
			return fail(`cannot read the lane policy ${file}: ${err instanceof Error ? err.message : err}`);
		}
		roots = policy.allowWrite.map((p) => canonical(p));
		denied = policy.denyWrite.map((p) => canonical(p));
		unreadable = policy.denyRead.map((p) => canonical(p));
		if (process.platform !== "darwin" && process.platform !== "linux") {
			return fail(`no OS sandbox on ${process.platform}`);
		}
		try {
			await SandboxManager.initialize({
				network: {
					allowedDomains: policy.allowedDomains,
					deniedDomains: [],
					allowLocalBinding: policy.allowLocalBinding === true,
				},
				filesystem: { denyRead: policy.denyRead, allowWrite: policy.allowWrite, denyWrite: policy.denyWrite },
			});
		} catch (err) {
			return fail(`sandbox did not start: ${err instanceof Error ? err.message : err}`);
		}
		refusal = undefined;
		ctx.ui.setStatus(
			"lane-guard",
			`🔒 lane-guard: ${policy.posture}, ${policy.allowWrite.length} write roots, ${policy.allowedDomains.length} domains`,
		);
	});

	pi.on("session_shutdown", async () => {
		if (!refusal) {
			try {
				await SandboxManager.reset();
			} catch {
				// nothing left to clean up
			}
		}
	});
}
