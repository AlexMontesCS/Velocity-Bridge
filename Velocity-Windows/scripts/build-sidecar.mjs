import { chmodSync, copyFileSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { platform } from "node:os";
import { spawnSync } from "node:child_process";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDir, "..");
const pythonDir = join(projectRoot, "src-python");
const tauriDir = join(projectRoot, "src-tauri");

const targetTriple =
  process.argv[2] ||
  (platform() === "win32"
    ? "x86_64-pc-windows-msvc"
    : platform() === "linux"
      ? "x86_64-unknown-linux-gnu"
      : "");

if (!targetTriple) {
  console.error(`Unsupported platform: ${platform()}. Pass a target triple explicitly.`);
  process.exit(1);
}

const pythonLaunchers =
  platform() === "win32"
    ? [
        { command: "py", args: ["-3"] },
        { command: "python", args: [] },
        { command: "python3", args: [] },
      ]
    : [
        { command: "python3", args: [] },
        { command: "python", args: [] },
      ];

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: "inherit",
    shell: false,
  });

  if (result.error) {
    return false;
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }

  return true;
}

function findPythonLauncher() {
  for (const launcher of pythonLaunchers) {
    const ok = run(launcher.command, [...launcher.args, "--version"], projectRoot);
    if (ok) {
      return launcher;
    }
  }

  console.error("Could not find a usable Python launcher.");
  process.exit(1);
}

const python = findPythonLauncher();

for (const dir of [join(pythonDir, "build"), join(pythonDir, "dist")]) {
  if (existsSync(dir)) {
    rmSync(dir, { recursive: true, force: true });
  }
}

mkdirSync(tauriDir, { recursive: true });

const pyInstallerArgs = [
  ...python.args,
  "-m",
  "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onefile",
  "--name",
  "velocity-backend",
  "--hidden-import=uvicorn.logging",
  "--hidden-import=uvicorn.loops",
  "--hidden-import=uvicorn.loops.auto",
  "--hidden-import=uvicorn.protocols",
  "--hidden-import=uvicorn.protocols.http",
  "--hidden-import=uvicorn.protocols.http.auto",
  "--hidden-import=uvicorn.lifespan.on",
  "--hidden-import=win32clipboard",
  "--hidden-import=win32con",
  "--hidden-import=PIL.ImageGrab",
  "--hidden-import=pillow_heif",
  "server.py",
];

run(python.command, pyInstallerArgs, pythonDir);

const isWindowsTarget = targetTriple.includes("windows");
const builtBinary = join(
  pythonDir,
  "dist",
  isWindowsTarget ? "velocity-backend.exe" : "velocity-backend",
);
const destination = join(
  tauriDir,
  isWindowsTarget ? `velocity-backend-${targetTriple}.exe` : `velocity-backend-${targetTriple}`,
);

copyFileSync(builtBinary, destination);

if (!isWindowsTarget) {
  chmodSync(destination, 0o755);
}

console.log(`Sidecar built successfully: ${destination}`);
