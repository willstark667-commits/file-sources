#!/usr/bin/env python3
"""
program_launcher.py

A simple interactive shell for macOS and Linux that:
  - Lets you browse/select a working directory
  - Remembers a default directory (with an option to change it permanently)
  - Auto-detects when files/folders are added, removed, or renamed in the
    current directory while you work
  - Runs .sh shell-source files and other executable programs
  - Opens a real terminal/console window (Terminal.app on macOS,
    gnome-terminal/konsole/xterm/etc. on Linux) to run them in, so long
    running or interactive programs get their own window instead of being
    trapped inside this shell

Usage:
    python3 program_launcher.py

Config:
    A small JSON config file is kept at ~/.program_launcher_config.json
    to remember your default directory between runs.
"""

import cmd
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

CONFIG_PATH = Path.home() / ".program_launcher_config.json"
POLL_INTERVAL_SECONDS = 2.0

RUNNABLE_SUFFIXES = {".sh", ".bash", ".zsh", ".command"}


# --------------------------------------------------------------------------
# Config handling
# --------------------------------------------------------------------------
def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        print(f"[warning] could not save config: {e}")


# --------------------------------------------------------------------------
# Directory watcher — polls for added/removed/renamed entries
# --------------------------------------------------------------------------
class DirectoryWatcher:
    def __init__(self, get_path_fn, interval=POLL_INTERVAL_SECONDS):
        self._get_path = get_path_fn
        self._interval = interval
        self._thread = None
        self._stop_event = threading.Event()
        self._snapshot = {}
        self._lock = threading.Lock()

    def _scan(self, path):
        """Return {name: (is_dir, mtime)} for entries in path."""
        result = {}
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        result[entry.name] = (entry.is_dir(), entry.stat().st_mtime)
                    except OSError:
                        continue
        except OSError:
            pass
        return result

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        with self._lock:
            self._snapshot = self._scan(self._get_path())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def resync(self):
        """Call after a manual cd/ls so the next diff isn't noisy."""
        with self._lock:
            self._snapshot = self._scan(self._get_path())

    def _run(self):
        while not self._stop_event.wait(self._interval):
            path = self._get_path()
            current = self._scan(path)
            with self._lock:
                previous = self._snapshot
                self._snapshot = current

            added = [n for n in current if n not in previous]
            removed = [n for n in previous if n not in current]

            # Heuristic rename detection: one removed + one added of the
            # same type (file/dir) within the same poll cycle is very
            # likely a rename rather than an unrelated add+delete.
            renames = []
            if added and removed:
                remaining_added = list(added)
                remaining_removed = list(removed)
                for old_name in list(remaining_removed):
                    old_is_dir = previous[old_name][0]
                    for new_name in list(remaining_added):
                        new_is_dir = current[new_name][0]
                        if old_is_dir == new_is_dir:
                            renames.append((old_name, new_name))
                            remaining_added.remove(new_name)
                            remaining_removed.remove(old_name)
                            break
                added, removed = remaining_added, remaining_removed

            if added or removed or renames:
                self._announce(path, added, removed, renames)

    def _announce(self, path, added, removed, renames):
        print()  # break away from the current prompt line
        print(f"[watch] change detected in {path}")
        for old, new in renames:
            print(f"  renamed: {old}  ->  {new}")
        for name in added:
            print(f"  added:   {name}")
        for name in removed:
            print(f"  removed: {name}")
        print("(program) ", end="", flush=True)


# --------------------------------------------------------------------------
# Terminal launching — cross-platform (macOS + Linux)
# --------------------------------------------------------------------------
class TerminalLauncher:
    LINUX_TERMINALS = [
        ("x-terminal-emulator", ["-e"]),
        ("gnome-terminal", ["--"]),
        ("konsole", ["-e"]),
        ("xfce4-terminal", ["-e"]),
        ("lxterminal", ["-e"]),
        ("mate-terminal", ["-e"]),
        ("tilix", ["-e"]),
        ("xterm", ["-e"]),
    ]

    def __init__(self):
        self.system = platform.system()  # "Darwin", "Linux", ...

    def _find_linux_terminal(self):
        for name, flag in self.LINUX_TERMINALS:
            path = shutil.which(name)
            if path:
                return path, flag
        return None, None

    def open_shell(self, directory):
        """Open a plain terminal window sitting in `directory`."""
        directory = str(directory)
        if self.system == "Darwin":
            subprocess.Popen(["open", "-a", "Terminal", directory])
            return True
        elif self.system == "Linux":
            term, flag = self._find_linux_terminal()
            if not term:
                print("[error] no terminal emulator found (tried gnome-terminal, "
                      "konsole, xfce4-terminal, xterm, ...)")
                return False
            # Most terminals accept a --working-directory style flag OR we
            # just cd inside the shell we launch.
            cmd_str = f"cd '{directory}' && exec $SHELL"
            subprocess.Popen([term, *flag, "bash", "-c", cmd_str])
            return True
        else:
            print(f"[error] unsupported platform: {self.system}")
            return False

    def run_in_terminal(self, filepath, directory):
        """Launch a script/executable inside a new terminal window."""
        filepath = Path(filepath)
        directory = str(directory)

        if self.system == "Darwin":
            # Use AppleScript so Terminal.app opens a fresh window running
            # the command, then drops to an interactive shell.
            escaped_dir = directory.replace('"', '\\"')
            escaped_file = str(filepath).replace('"', '\\"')
            script_cmd = (
                f'cd "{escaped_dir}" && bash "{escaped_file}"; '
                f'echo; echo "[process exited — press enter to close]"; read'
            )
            osa = f'tell application "Terminal" to do script "{script_cmd}"'
            subprocess.Popen(["osascript", "-e", osa])
            return True

        elif self.system == "Linux":
            term, flag = self._find_linux_terminal()
            if not term:
                print("[error] no terminal emulator found (tried gnome-terminal, "
                      "konsole, xfce4-terminal, xterm, ...)")
                return False
            cmd_str = (
                f"cd '{directory}' && bash '{filepath}'; "
                f"echo; echo '[process exited — press enter to close]'; read"
            )
            subprocess.Popen([term, *flag, "bash", "-c", cmd_str])
            return True
        else:
            print(f"[error] unsupported platform: {self.system}")
            return False


# --------------------------------------------------------------------------
# The interactive shell
# --------------------------------------------------------------------------
class LauncherShell(cmd.Cmd):
    intro = (
        "===================================================\n"
        "  Program Launcher — macOS / Linux\n"
        "  type 'help' for a list of commands\n"
        "==================================================="
    )
    prompt = "(program) "

    def __init__(self):
        super().__init__()
        self.config = load_config()
        default_dir = self.config.get("default_directory") or str(Path.home())
        self.default_directory = Path(default_dir).expanduser()
        self.current_directory = self.default_directory
        self.terminal = TerminalLauncher()
        self.watcher = DirectoryWatcher(lambda: self.current_directory)
        self._update_prompt()

    # -- helpers -----------------------------------------------------
    def _update_prompt(self):
        self.prompt = f"({self.current_directory.name or self.current_directory}) "

    def _resolve(self, arg):
        arg = arg.strip().strip('"').strip("'")
        if not arg:
            return self.current_directory
        p = Path(arg).expanduser()
        if not p.is_absolute():
            p = self.current_directory / p
        return p.resolve()

    def _list_dir(self):
        try:
            entries = sorted(self.current_directory.iterdir(), key=lambda p: p.name.lower())
        except OSError as e:
            print(f"[error] cannot list directory: {e}")
            return
        if not entries:
            print("(empty directory)")
            return
        for entry in entries:
            if entry.is_dir():
                print(f"  [DIR]  {entry.name}/")
            elif entry.suffix in RUNNABLE_SUFFIXES or os.access(entry, os.X_OK):
                print(f"  [RUN]  {entry.name}")
            else:
                print(f"         {entry.name}")

    # -- commands ------------------------------------------------------
    def do_pwd(self, arg):
        "Show the current working directory."
        print(self.current_directory)

    def do_ls(self, arg):
        "List the contents of the current directory. [DIR]=folder [RUN]=runnable file"
        self._list_dir()
        self.watcher.resync()

    do_list = do_ls

    def do_cd(self, arg):
        "cd <path>   Change the current directory (relative or absolute)."
        if not arg.strip():
            print(f"Current directory: {self.current_directory}")
            return
        target = self._resolve(arg)
        if not target.exists() or not target.is_dir():
            print(f"[error] not a directory: {target}")
            return
        self.current_directory = target
        self._update_prompt()
        print(f"Now in: {self.current_directory}")
        self.watcher.resync()

    def do_default(self, arg):
        "Show the current default directory."
        print(f"Default directory: {self.default_directory}")

    def do_setdefault(self, arg):
        "setdefault [path]   Set the default directory (uses current dir if no path given)."
        target = self._resolve(arg) if arg.strip() else self.current_directory
        if not target.exists() or not target.is_dir():
            print(f"[error] not a directory: {target}")
            return
        self.default_directory = target
        self.config["default_directory"] = str(target)
        save_config(self.config)
        print(f"Default directory set to: {target}")

    def do_reset(self, arg):
        "Return to the default directory."
        self.current_directory = self.default_directory
        self._update_prompt()
        print(f"Now in: {self.current_directory}")
        self.watcher.resync()

    def do_watch(self, arg):
        "watch [on|off]   Toggle auto-detection of directory changes (default: on)."
        arg = arg.strip().lower()
        if arg in ("off", "stop"):
            self.watcher.stop()
            print("Watching stopped.")
        else:
            self.watcher.start()
            print(f"Watching {self.current_directory} for changes "
                  f"(polling every {POLL_INTERVAL_SECONDS:.0f}s).")

    def do_run(self, arg):
        "run <file>   Run a .sh/.command file or executable in a new terminal window."
        if not arg.strip():
            print("Usage: run <filename>")
            return
        target = self._resolve(arg)
        if not target.exists() or not target.is_file():
            print(f"[error] file not found: {target}")
            return
        ok = self.terminal.run_in_terminal(target, self.current_directory)
        if ok:
            print(f"Launched {target.name} in a new terminal window.")

    def do_term(self, arg):
        "term   Open a plain terminal/console window in the current directory."
        ok = self.terminal.open_shell(self.current_directory)
        if ok:
            print(f"Opened a terminal window in {self.current_directory}")

    def do_exit(self, arg):
        "Exit the program launcher."
        self.watcher.stop()
        print("Goodbye.")
        return True

    do_quit = do_exit
    do_EOF = do_exit

    def emptyline(self):
        pass  # don't repeat the last command on blank input


def main():
    shell = LauncherShell()
    # Watching is on by default so directory changes are picked up
    # automatically without the user having to remember to enable it.
    shell.watcher.start()
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
