# Debian ARM64 runtime

Open **Linux: Setup and Runtime Dashboard** from the command palette or Linux
status item. The wizard has three steps: install the verified base image, check
runtime compatibility, then install development tools. Setup has progress and
cancellation; the output channel retains errors. Retrying never overwrites an
existing rootfs, home, or project directory.

The pinned Debian 13 image and SHA-256 are in `linux/extension/rootfs.json`, sourced
from [Termux's versioned distribution manifest](https://github.com/termux/proot-distro/blob/v4.29.0/distro-plugins/debian.sh).
APT uses Debian's signed HTTPS repositories and bundled archive keyring. It does
not disable package authentication. DNS defaults to 1.1.1.1 and 8.8.8.8; networks
requiring local DNS can edit `/etc/resolv.conf` from the Linux terminal.

Storage under Android's private `files/`:

| Location | Purpose |
|---|---|
| `linux/rootfs` | Debian system and installed packages |
| `linux/home` | Persistent Linux `/root` |
| `linux/users/<name>` | Persistent home for the optional regular Linux user |
| `projects` | Shared editor workspace; also `/workspace` in Linux |
| `linux/tmp` | Guest `/tmp` and PRoot temporary files |
| `linux/state.json` | Installation and toolchain completion record |

Select **Debian ARM64** from terminal profiles or **Linux: New Debian Terminal**.
`apt update`, Bash, and normal interactive commands run under PRoot. Tools include
GCC/G++, Clang/clangd, GDB, CMake, Make, Git, OpenSSH, Python/pip/venv, Node/npm,
JDK, Maven, Gradle, and Docker clients. Linux processes cannot provide kernel
namespaces, privileged mounts, a local Docker Engine or systemd services.

A build task uses an executable and argument array, without shell interpolation:

```json
{"version":"2.0.0","tasks":[{"label":"Linux: build","type":"vscodroid-linux",
"command":"cmake","args":["--build","build"],"problemMatcher":["$gcc"]}]}
```

For C/C++, open a folder in the shared workspace and run **Linux: Configure C/C++
Language Server**. It installs the `llvm-vs-code-extensions.vscode-clangd` client
from the configured extension registry and sets its executable/arguments to the
Debian launcher. Generate `compile_commands.json` with
`cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -S . -B build` for project-specific flags.
Settings contain device-specific APK paths; rerun the command after an APK update.
The client configuration follows [clangd's extension settings](https://github.com/clangd/vscode-clangd/blob/master/package.json).

For other language servers/debug adapters, configure the extension to launch the native
Python executable with `runtime.py --files … --native … --workspace … exec --
/usr/bin/clangd` (the dashboard and runtime environment expose the actual paths).
Use the identical shared-workspace path in the guest and editor. An extension must
support an executable plus arguments; automatic rewriting of every extension's
spawn is intentionally not implemented. Debugger support depends on Android's
ptrace restrictions and PRoot's own tracing, and requires tool-specific testing.

Node's inspector and Python's `pdb` avoid a second native ptrace tracer. Start
`node --inspect-brk=127.0.0.1:9229 app.js` in the Debian terminal, then use the
built-in JavaScript debugger with this attach configuration. Keep the inspector
bound to loopback, and stop the process when debugging is finished.

```json
{"version":"0.2.0","configurations":[{"name":"Attach to Debian Node",
"type":"node","request":"attach","address":"127.0.0.1","port":9229,
"skipFiles":["<node_internals>/**"]}]}
```

Use the same absolute shared-workspace path when opening files and launching Node
so breakpoints map without a remote-path translation. For Python, run
`python3 -m pdb app.py` directly in the Debian terminal.

**Stop Managed Sessions** closes this extension's terminals and setup jobs. It
checks the runtime executable, rootfs and process identity before cleanup. It
also recognizes restored sessions after an editor reload. Restart creates a fresh
Linux terminal while preserving home and workspace files.
**Clean APT Cache** removes package downloads, not installed tools or workspaces.
No destructive reset button is provided. Back up home/projects before app removal.

After Debian installation, the dashboard offers to create a regular Linux user.
New terminals use that account by default; **New root terminal** remains available
for package administration. Package setup runs as root with a non-interactive
UTC timezone configuration so `tzdata` cannot block on a debconf prompt.
