/**
 * lane-guard — the boundary of a /dispatch:pi lane.
 *
 * - Shell: pi's `bash` tool and user `!` commands run inside @anthropic-ai/sandbox-runtime (Seatbelt on
 *   macOS, bubblewrap on Linux). Without a policy, or when the sandbox cannot start, every shell command is
 *   refused: nothing ever falls back to an unsandboxed shell.
 * - Files: `write` and `edit` may only touch the policy's writable roots minus its denied paths. The default
 *   posture blocks anything else and tells the model why; the strict posture asks a human instead.
 *
 * The policy comes only from `--lane-policy <file>`, written by lane.py outside the repository. Nothing is
 * read from the lane's own files, so the repository cannot widen its own boundary.
 */

import { spawn } from "node:child_process";
import { existsSync, readFileSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, resolve, sep } from "node:path";
import { SandboxManager } from "@anthropic-ai/sandbox-runtime";
import type { BashOperations, ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createBashTool } from "@earendil-works/pi-coding-agent";

interface LanePolicy {
	version: number;
	posture: "block" | "strict";
	allowWrite: string[];
	denyWrite: string[];
	denyRead: string[];
	allowedDomains: string[];
}

// Resolve symlinks on the nearest existing ancestor, so /tmp/... and /private/tmp/... compare equal.
function canonical(path: string): string {
	let head = path;
	const tail: string[] = [];
	while (!existsSync(head) && dirname(head) !== head) {
		tail.unshift(head.slice(dirname(head).length + 1));
		head = dirname(head);
	}
	return resolve(realpathSync(head), ...tail);
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
	return p;
}

function sandboxedOps(): BashOperations {
	return {
		async exec(command, cwd, { onData, signal, timeout }) {
			if (!existsSync(cwd)) throw new Error(`Working directory does not exist: ${cwd}`);
			const wrapped = await SandboxManager.wrapWithSandbox(command);
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
		description: "Sandbox and write policy of a /dispatch:pi lane (JSON written by lane.py)",
		type: "string",
		default: "",
	});

	const cwd = process.cwd();
	const localBash = createBashTool(cwd);
	let policy: LanePolicy | undefined;
	let roots: string[] = [];
	let denied: string[] = [];
	// Fail closed: until the sandbox is up, this is the reason every shell command is refused.
	let refusal: string | undefined = "lane-guard has not started yet";

	pi.registerTool({
		...localBash,
		label: "bash (lane sandbox)",
		async execute(id, params, signal, onUpdate) {
			if (refusal) throw new Error(`lane-guard refused the shell command: ${refusal}`);
			const sandboxed = createBashTool(cwd, { operations: sandboxedOps() });
			return sandboxed.execute(id, params, signal, onUpdate);
		},
	});

	pi.on("user_bash", () => {
		if (refusal) throw new Error(`lane-guard refused the shell command: ${refusal}`);
		return { operations: sandboxedOps() };
	});

	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "write" && event.toolName !== "edit") return undefined;
		if (!policy) return { block: true, reason: `lane-guard has no policy: ${refusal}` };
		const raw = String((event.input as { path?: unknown }).path ?? "");
		const target = canonical(isAbsolute(raw) ? raw : resolve(ctx.cwd, raw));
		const inside = roots.some((r) => within(target, r)) && !denied.some((d) => within(target, d));
		if (inside) return undefined;
		const reason = `${target} is outside this lane's writable paths (the lane worktree and the repository's git directory, except its hooks and config)`;
		if (policy.posture === "strict" && ctx.hasUI) {
			const ok = await ctx.ui.confirm("lane-guard: allow a write outside the lane?", `${event.toolName} ${target}`);
			if (ok) return undefined;
			return { block: true, reason: `${reason}; a human declined it` };
		}
		return { block: true, reason };
	});

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
		if (process.platform !== "darwin" && process.platform !== "linux") {
			return fail(`no OS sandbox on ${process.platform}`);
		}
		try {
			await SandboxManager.initialize({
				network: { allowedDomains: policy.allowedDomains, deniedDomains: [] },
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
