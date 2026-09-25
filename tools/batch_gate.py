"""Opt-in batch runner: exact declared inputs, prerequisite receipts, rerun reasons.

This is not a hook and does not intercept commands run outside this entry point.
Commands are argv arrays executed without a shell. Existing checkers stay unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


class Blocked(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(root, name):
    if not isinstance(name, str) or Path(name).is_absolute():
        raise Blocked("input/log paths must be relative")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root:
        raise Blocked("path leaves declared root: " + name)
    return path


def read_json(path, default=None):
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_batch(path):
    path = path.resolve()
    batch = read_json(path)
    if batch.get("version") != 1 or not re.fullmatch(r"[A-Za-z0-9_-]+", batch.get("id", "")):
        raise Blocked("version 1 and a simple batch id are required")
    root = (path.parent / batch["root"]).resolve()
    inputs = batch.get("inputs")
    checks = batch.get("checks")
    if not isinstance(inputs, dict) or not inputs or not isinstance(checks, dict) or not checks:
        raise Blocked("nonempty inputs and checks are required")
    for name, expected in inputs.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
            raise Blocked("SHA256 required: " + name)
        target = inside(root, name)
        if not target.is_file() or file_hash(target) != expected:
            raise Blocked("stale/missing input: " + name)
    for key, check in checks.items():
        argv = check.get("argv")
        if (check.get("kind") not in ("chapter", "whole") or not isinstance(argv, list)
                or not argv or not all(isinstance(a, str) and a for a in argv)):
            raise Blocked("invalid check: " + key)
        for arg in argv[1:]:
            if arg.endswith((".py", ".js", ".cjs", ".ps1", ".sh")):
                script = (root / arg).resolve()
                if not script.is_relative_to(root) or script.relative_to(root).as_posix() not in inputs:
                    raise Blocked("checker script must be a declared input: " + arg)
    required = batch.get("required", {})
    chapters = batch.get("chapters")
    if (not isinstance(required, dict) or not isinstance(chapters, list)
            or not all(isinstance(c, str) for c in chapters) or set(chapters) != set(required)):
        raise Blocked("required must map chapter input paths to check ids")
    for chapter, ids in required.items():
        if chapter not in inputs or not isinstance(ids, list) or not ids:
            raise Blocked("chapter needs a frozen input and nonempty prerequisites: " + chapter)
        if any(i not in checks or checks[i]["kind"] != "chapter" for i in ids):
            raise Blocked("unknown/nonchapter prerequisite: " + chapter)
    ready = batch.get("ready", [])
    if not isinstance(ready, list) or not all(isinstance(i, str) and i for i in ready):
        raise Blocked("ready must list candidate ids")
    # Fingerprint includes commands and prerequisite scope, not only content.
    fingerprint = digest({"root": str(root), "id": batch["id"], "inputs": inputs,
                          "checks": checks, "required": required, "chapters": chapters})
    store = path.parent / (path.name + ".receipts")
    return batch, root, fingerprint, store


def history(store):
    data = read_json(store / "history.json", [])
    if not isinstance(data, list):
        raise Blocked("invalid receipt history")
    return data


def good_receipt(row, fingerprint, store):
    log = inside(store.resolve(), row.get("log", ""))
    return (row.get("fingerprint") == fingerprint and row.get("valid_inputs") is True
            and row.get("exit_code") == 0 and log.is_file()
            and file_hash(log) == row.get("log_sha256"))


def check_ready(batch, key, fingerprint, store, reason):
    if key not in batch["checks"]:
        raise Blocked("unknown check: " + key)
    rows = history(store)
    if batch["checks"][key]["kind"] == "whole":
        for chapter, ids in batch.get("required", {}).items():
            for needed in ids:
                matches = [r for r in rows if r.get("check") == needed
                           and r.get("fingerprint") == fingerprint]
                if not matches or not good_receipt(matches[-1], fingerprint, store):
                    raise Blocked("missing/stale/failed preflight: " + chapter + " / " + needed)
        if any(r.get("check") == key and r.get("fingerprint") == fingerprint
               and r.get("completed") is True for r in rows) and not reason.strip():
            raise Blocked("same-input whole check already completed; --reason is required")
    return rows


def run_check(path, key, reason):
    batch, root, fp, store = load_batch(path)
    store.mkdir(parents=True, exist_ok=True)
    lock = store / "running.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise Blocked("batch run locked; verify the prior process before clearing running.lock")
    os.close(fd)
    try:
        rows = check_ready(batch, key, fp, store, reason)
        log = store / (uuid.uuid4().hex + ".log")
        with log.open("wb") as stream:
            result = subprocess.run(batch["checks"][key]["argv"], cwd=root,
                                    stdout=stream, stderr=subprocess.STDOUT, shell=False)
        try:
            valid = load_batch(path)[2] == fp
        except (Blocked, OSError, ValueError):
            valid = False
        rows.append({"check": key, "fingerprint": fp, "completed": True,
                     "exit_code": result.returncode, "valid_inputs": valid,
                     "reason": reason.strip(), "log": log.name, "log_sha256": file_hash(log)})
        temp = store / "history.tmp"
        temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(store / "history.json")
        if not valid:
            raise Blocked("inputs changed during execution; receipt is not reusable")
        print("check=%s exit=%s receipt=%s" % (key, result.returncode, store / "history.json"))
        return result.returncode
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "run", "scope"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("target", help="check id, or proposed scope name")
    parser.add_argument("--reason", default="")
    args = parser.parse_args(argv)
    try:
        if args.mode == "run":
            return run_check(args.manifest, args.target, args.reason)
        batch, root, fp, store = load_batch(args.manifest)
        if args.mode == "scope":
            if batch.get("ready") and not args.reason.strip():
                raise Blocked("ready candidates remain; integrate them before new scope, or record --reason")
            print("scope check passed; reason=%r; no scope or ready state was changed" % args.reason.strip())
        else:
            check_ready(batch, args.target, fp, store, args.reason)
            print("precheck passed; no command was executed")
        return 0
    except (Blocked, OSError, ValueError, KeyError, TypeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
