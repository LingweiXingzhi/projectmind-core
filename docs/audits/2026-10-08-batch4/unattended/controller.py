#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ProjectMind architecture-loop CLOSE controller (RUN ZCODE-CLOSE-20261007-1757-K7).

Single-writer controller for this RUN only:
  - audit queue (queue/audit_queue.json) and audit state (state/audit_state.json)
  - process registry (state/processes.json) with ownership-verified cleanup
  - dependency check state (state/deps_state.json)  [read-only remote checks]
  - per-attempt receipts (receipts/<pkg>/attempt-NNN/), never overwritten
  - strict verdict parsing from structured final output / exact fields

It never touches state/dev_state.json (written by the A dev loop) and never
kills a process it cannot prove belongs to this RUN.

Subcommands:
  queue-add       freeze a package into the queue (supersedes older PENDING)
  tick-audit      at most one Codex review call for the newest PENDING package
  tick-deps       read-only dependency check (remote branches, model config)
  tick-all        tick-deps then tick-audit
  self-check      no-model controller self-check (queue/lock/log/verdict/proc tests)
  verdict-selftest  labeled simulated results through the real classifier
  proc-register / proc-ls / proc-stop [--dry-run] / proc-cleanup [--dry-run]
  state-show      print a compact state summary
"""
import argparse
import ctypes
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "ZCODE-CLOSE-20261007-1757-K7"
BASE = Path(__file__).resolve().parent
STATE = BASE / "state"
LEASES = BASE / "leases"
LOGS = BASE / "logs"
QUEUE = BASE / "queue"
RECEIPTS = BASE / "receipts"
PACKAGES = BASE / "packages"
RETRY_MINUTES_DEFAULT = 30
SESSION_ID_FILE = STATE / "codex_session_id.txt"
AUDIT_STATE = STATE / "audit_state.json"
AUDIT_QUEUE = QUEUE / "audit_queue.json"
DEPS_STATE = STATE / "deps_state.json"
PROC_REGISTRY = STATE / "processes.json"
LOCK = LEASES / "audit.lock"
SCHED_LOG = LOGS / "scheduler.log"
SCHEMA_FILE = BASE / "audit_schema.json"
REMOTE = "https://github.com/LingweiXingzhi/projectmind-core.git"

CODEX = shutil.which("codex") or shutil.which("codex.cmd") or "codex"
CODEX_BASE_ARGS = ["exec", "--sandbox", "read-only", "-c", 'approval_policy="never"']

# ---------------------------------------------------------------- utilities

def now():
    return datetime.now(timezone.utc).astimezone()


def iso(dt):
    return dt.isoformat(timespec="seconds")


def log(msg, extra=None):
    SCHED_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = "[%s] %s" % (iso(now()), msg)
    with open(SCHED_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if extra:
        with open(SCHED_LOG, "a", encoding="utf-8") as f:
            f.write("    " + json.dumps(extra, ensure_ascii=False) + "\n")
    return line


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp.%d" % os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def pid_alive(pid):
    if not pid or pid <= 0:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return False
    try:
        code = ctypes.c_ulong(0)
        if k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return code.value == STILL_ACTIVE
        return True
    finally:
        k32.CloseHandle(h)


def proc_info(pid):
    """(creation_iso, exe_path, cmdline) for a live pid, else (None, None, None)."""
    ps = (
        "$p=Get-CimInstance Win32_Process -Filter \"ProcessId=%d\"; "
        "if($p){'{0}|{1}|{2}' -f $p.CreationDate.ToString('o'),$p.ExecutablePath,"
        "($p.CommandLine -replace '\\|','/')} else {'MISSING'}" % int(pid)
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except Exception:
        return None, None, None
    text = (out.stdout or "").strip()
    if not text or text == "MISSING":
        return None, None, None
    parts = text.split("|", 2)
    if len(parts) < 3:
        return None, None, None
    return parts[0].strip(), parts[1].strip(), parts[2].strip()


# ---------------------------------------------------------------- strict verdict

RATE_LIMIT_PATTERNS = [
    r"usage limit", r"rate limit", r"rate_limit", r"429", r"quota",
    r"insufficient_quota", r"too many requests", r"resets? at", r"limit reached",
    r"out of credits", r"credit balance",
]
AUTH_PATTERNS = [r"\b401\b", r"unauthorized", r"invalid_grant", r"not logged in",
                 r"authentication", r"api key"]
NETWORK_PATTERNS = [r"connection refused", r"etimedout", r"timeout", r"getaddrinfo",
                    r"name resolution", r"network", r"econnreset", r"tls", r"dns"]
# the service rejected our request itself (schema/parameter): deterministic,
# needs the caller to fix the request — retrying the same thing is pointless
REQUEST_REJECTED_PATTERNS = [r"invalid_request_error", r"invalid_json_schema",
                             r"response_format", r"400"]

VERDICT_ALLOWED = {"PASS", "CHANGES_REQUESTED"}

NOISE_PATTERNS = [
    r"codex_rmcp_client::oauth::refresh_transaction",
    r"failed to refresh oauth tokens for server hyper3d",
]


def _strip_noise(text):
    kept = [item for item in (text or "").splitlines()
            if not any(re.search(pattern, item, re.I) for pattern in NOISE_PATTERNS)]
    return "\n".join(kept)


def events_error_text(events_file):
    """Error text from the real event stream (turn.failed / error items).

    stderr on this host carries non-blocking MCP OAuth refresh noise, so the
    event stream is the authoritative source for classifying a failed call.
    """
    texts = []
    try:
        with open(events_file, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except Exception:
                    continue
                if event.get("type") in ("turn.failed", "error"):
                    texts.append(json.dumps(event.get("error") or event.get("message") or {},
                                            ensure_ascii=False))
                elif event.get("type") == "item.completed":
                    item = event.get("item") or {}
                    if item.get("type") == "error":
                        texts.append(str(item.get("message", "")))
    except OSError:
        return ""
    return "\n".join(texts)


def classify_error_text(text):
    text = _strip_noise(text)
    low = (text or "").lower()
    for pat in REQUEST_REJECTED_PATTERNS:
        if re.search(pat, low):
            return "REQUEST_REJECTED"
    for pat in RATE_LIMIT_PATTERNS:
        if re.search(pat, low):
            return "RATE_LIMITED"
    for pat in AUTH_PATTERNS:
        if re.search(pat, low):
            return "AUTH_ERROR"
    for pat in NETWORK_PATTERNS:
        if re.search(pat, low):
            return "NETWORK_ERROR"
    return None


def parse_verdict(reply_text, exit_code, manifest):
    """Strict, field-based verdict. Never keyword-scans prose.

    Returns dict(classification=..., fields=..., reasons=[...]).
    classification: PASS / CHANGES_REQUESTED / INVALID_<reason> / CALL_FAILED
    """
    reasons = []
    fields = None
    text = reply_text or ""
    if not text.strip():
        return {"classification": "INVALID_EMPTY_REPLY", "fields": None,
                "reasons": ["reply is empty"], "exit_code": exit_code}

    # 1) structured JSON reply (preferred; produced with --output-schema when supported)
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "verdict" in obj and "target_sha" in obj:
                fields = {
                    "_structured_json": True,
                    "package_id": obj.get("package_id"),
                    "target_sha": obj.get("target_sha"),
                    "scope": obj.get("scope"),
                    "verdict": obj.get("verdict"),
                    "findings": obj.get("findings"),
                    "unverified": obj.get("unverified"),
                }
        except Exception:
            fields = None

    # 2) exact field lines ("- package_id: X"). No prose scanning.
    if fields is None:
        fields = {}
        for name in ("package_id", "target_sha", "scope", "verdict"):
            mm = re.search(r"^[\s>*`-]*%s\s*[:：]\s*(.+?)\s*$" % re.escape(name),
                           text, re.M | re.I)
            fields[name] = mm.group(1).strip().strip("`* ") if mm else None
        fnd = re.search(r"^[\s>*`-]*findings\s*[:：]\s*(.*?)\s*$", text, re.M | re.I)
        fields["findings"] = fnd.group(1).strip() if fnd else None
        unv = re.search(r"^[\s>*`-]*unverified\s*[:：]\s*(.*?)\s*$", text, re.M | re.I)
        fields["unverified"] = unv.group(1).strip() if unv else None
        if not fields.get("verdict"):
            return {"classification": "INVALID_NO_STRUCTURED_RESULT", "fields": fields,
                    "reasons": ["no json object and no 'verdict:' field found"],
                    "exit_code": exit_code}

    # 3) validate against the frozen manifest
    verdict = (fields.get("verdict") or "").strip().strip("`* ").upper()
    if verdict not in VERDICT_ALLOWED:
        reasons.append("verdict field %r not in %s" % (fields.get("verdict"), sorted(VERDICT_ALLOWED)))
    pkg = fields.get("package_id")
    if manifest.get("package_id") and pkg and pkg.strip().strip("` ") != manifest["package_id"]:
        reasons.append("package_id mismatch: reply=%r manifest=%r" % (pkg, manifest["package_id"]))
    elif manifest.get("package_id") and not pkg:
        reasons.append("package_id missing in reply")
    sha = (fields.get("target_sha") or "").strip().strip("` ")
    exp = manifest.get("target_sha") or ""
    if exp and sha != exp:
        reasons.append("target_sha mismatch: reply=%r manifest=%r" % (sha, exp))
    if fields.get("scope") in (None, ""):
        reasons.append("scope missing in reply")

    # findings must be PRESENT, an array, and empty for PASS (BATCH-1 F-01:
    # a missing/null/object/number findings field must never reach PASS)
    findings = fields.get("findings")
    if isinstance(findings, list):
        if verdict == "PASS" and len(findings) > 0:
            reasons.append("verdict PASS but findings is non-empty (%d)" % len(findings))
        for item in findings:
            if not isinstance(item, dict):
                reasons.append("findings entries must be objects, got %s" % type(item).__name__)
    elif isinstance(findings, str) and not fields.get("_structured_json"):
        # the field-line fallback path may state findings as text: PASS needs
        # exactly the empty forms, CHANGES_REQUESTED needs a non-empty list
        # (BATCH-1B F-01)
        text_value = findings.strip().strip("`* ")
        if verdict == "PASS" and text_value != "[]":
            reasons.append("findings text must be exactly [] for PASS when not structured JSON")
        if verdict == "CHANGES_REQUESTED" and text_value in ("", "[]", "无", "none"):
            reasons.append("CHANGES_REQUESTED requires listed findings")
    else:
        reasons.append("findings field missing or of wrong type (must be an array)")

    unverified = fields.get("unverified")
    if fields.get("_structured_json"):
        if not isinstance(unverified, list):
            reasons.append("unverified field missing or not an array (schema requires an array)")
    elif unverified is None or (isinstance(unverified, str) and not unverified.strip()):
        reasons.append("unverified field missing in the reply (must be listed, even when empty)")

    # exit code gate: any nonzero exit invalidates the call (no stale reply credit)
    if exit_code != 0:
        reasons.append("codex exit code %r != 0" % exit_code)

    if reasons:
        return {"classification": "INVALID_" + ("EXIT" if exit_code != 0 else "RESULT"),
                "fields": fields, "reasons": reasons, "exit_code": exit_code}
    return {"classification": verdict, "fields": fields, "reasons": [], "exit_code": exit_code}


# ---------------------------------------------------------------- process registry

def load_registry():
    return read_json(PROC_REGISTRY, {"run_id": RUN_ID, "processes": []})


def save_registry(reg):
    atomic_write_json(PROC_REGISTRY, reg)


def port_owner(port):
    """PID listening on 127.0.0.1:<port>, or None."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=30).stdout
    except Exception:
        return None
    if not out:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(":%s" % port):
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


def _creation_matches(recorded, live):
    """The recorded creation instant must be EXACTLY the live one.

    A tolerance window would let a reused pid pass when the times are close
    (BATCH-1B H-01); the same PowerShell query returns the same instant for the
    same process, so exact equality is the right test.
    """
    try:
        left = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
        right = datetime.fromisoformat(live.replace("Z", "+00:00"))
        return left == right
    except (TypeError, ValueError):
        return False


def _directory_owned(recorded_dir, haystack):
    """The recorded directory must appear as a whole path segment.

    A plain substring match lets G:/run match G:/run-other (BATCH-1B H-01).
    """
    if not recorded_dir or not haystack:
        return False
    pattern = re.escape(recorded_dir.rstrip("/")) + r"(?=[\\/\"\'\s]|$)"
    return re.search(pattern, haystack, re.I) is not None


def stop_decision(entry, dry_run=True):
    """Ownership-verified stop decision. Returns (allow, reason_code, detail).

    Every piece of ownership evidence is MANDATORY: an unregistered, foreign,
    dead, reused, unrecorded, directory-mismatched or port-unconfirmable entry
    is refused — missing evidence is never treated as "probably ours"
    (BATCH-1 H-01).
    """
    if not entry:
        return False, "NOT_REGISTERED", "no registry entry"
    if entry.get("run_id") != RUN_ID:
        return False, "FOREIGN_RUN", "entry belongs to run %r" % entry.get("run_id")
    pid = entry.get("pid")
    if not pid_alive(pid):
        return False, "PID_DEAD", "pid %r is not alive" % pid
    creation, exe, cmdline = proc_info(pid)
    if creation is None:
        return False, "PID_UNVERIFIABLE", "cannot read process info for pid %r" % pid
    recorded = (entry.get("creation") or "").strip()
    if not recorded:
        return False, "CREATION_UNRECORDED", "registry entry has no process creation time"
    if not _creation_matches(recorded, creation):
        return False, "PID_REUSED", "creation time mismatch: live=%s recorded=%s" % (creation, recorded)
    rec_dir = (entry.get("dir") or "").strip().replace("\\", "/").lower()
    if not rec_dir:
        return False, "DIR_UNRECORDED", "registry entry has no directory"
    hay = ((cmdline or "") + " " + (exe or "")).replace("\\", "/").lower()
    if not _directory_owned(rec_dir, hay):
        return False, "DIR_MISMATCH", "recorded dir is not a whole path segment of the live cmdline"
    port = entry.get("port")
    if port:
        owner = port_owner(port)
        if owner is None:
            return False, "PORT_NOT_LISTENING", "port %s has no listener; ownership unconfirmed" % port
        if int(owner) != int(pid):
            return False, "PORT_OWNER_CHANGED", "port %s now owned by pid %s" % (port, owner)
    return True, "VERIFIED_OWNED", "pid=%s creation=%s dir=%s port=%s" % (pid, creation, rec_dir, port)


def kill_verified(entry):
    allow, code, detail = stop_decision(entry, dry_run=False)
    if not allow:
        return {"killed": False, "reason": code, "detail": detail}
    pid = int(entry["pid"])
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    time.sleep(0.5)
    return {"killed": not pid_alive(pid), "reason": "VERIFIED_OWNED", "detail": detail}


# ---------------------------------------------------------------- queue

QUEUE_LOCK = LEASES / "queue.lock"
QUEUE_LOCK_RETRIES = 8
QUEUE_LOCK_WAIT_SECONDS = 0.25


def load_queue():
    return read_json(AUDIT_QUEUE, {"run_id": RUN_ID, "packages": [], "updated": None})


def save_queue(q):
    q["run_id"] = RUN_ID
    q["updated"] = iso(now())
    atomic_write_json(AUDIT_QUEUE, q)


def mutate_queue(mutator):
    """Run one load-modify-save on the audit queue under an exclusive lock.

    Every queue writer (queue-add, tick-audit's status updates) goes through
    here: two concurrent writers used to interleave load→save and silently
    drop the package the other one had just accepted (BATCH-2 G-03). The
    mutator returns the caller-visible result; the queue itself is saved even
    when it returns None.
    """
    last_holder = None
    for attempt in range(QUEUE_LOCK_RETRIES):
        lease, holder = acquire_lock("queue-mutator", "queue", lock_path=QUEUE_LOCK)
        if lease is None:
            last_holder = holder
            time.sleep(QUEUE_LOCK_WAIT_SECONDS)
            continue
        try:
            q = load_queue()
            result = mutator(q)
            save_queue(q)
            return result
        finally:
            release_lock(lock_path=QUEUE_LOCK)
    raise RuntimeError("queue lock held by pid %s; queue not modified" %
                       (last_holder or {}).get("pid"))


def queue_add(pkg_id, target_sha, scope, clone, prompt_file, notes=None):
    def add(q):
        if any(p.get("package_id") == pkg_id and p.get("status") in ("PENDING", "RUNNING", "CLOSED_PASS", "CLOSED_CHANGES")
               for p in q["packages"]):
            return {"added": False, "reason": "PACKAGE_ALREADY_ACTIVE_OR_CLOSED"}
        # supersede older pending packages: only the newest necessary freeze stays queued
        superseded = []
        for p in q["packages"]:
            if p.get("status") == "PENDING":
                p["status"] = "SUPERSEDED"
                p["replaced_by"] = pkg_id
                p["superseded_at"] = iso(now())
                superseded.append(p["package_id"])
        entry = {
            "package_id": pkg_id,
            "target_sha": target_sha,
            "scope": scope,
            "clone": str(clone),
            "prompt_file": str(prompt_file),
            "created": iso(now()),
            "status": "PENDING",
            "notes": notes or "",
            "attempts": 0,
        }
        q["packages"].append(entry)
        return {"added": True, "superseded": superseded, "package": entry}
    return mutate_queue(add)


def newest_pending(q):
    pend = [p for p in q["packages"] if p.get("status") == "PENDING"]
    if not pend:
        return None
    return sorted(pend, key=lambda p: p["created"])[-1]


def has_valid_verdict(pkg_id, target_sha):
    """Reuse an existing valid receipt for the same package+sha (dedup on restart)."""
    d = RECEIPTS / pkg_id
    if not d.is_dir():
        return None
    best = None
    for att in sorted(d.glob("attempt-*")):
        v = read_json(att / "verdict.json", None)
        if not v:
            continue
        if v.get("classification") in ("PASS", "CHANGES_REQUESTED") and \
           (v.get("fields") or {}).get("target_sha", "").strip("` ") == target_sha:
            best = {"attempt": att.name, "classification": v["classification"]}
    return best


# ---------------------------------------------------------------- audit call

LOCK_STALE_SECONDS = 60
LOCK_MAX_ATTEMPTS = 4
# Test seam used ONLY by self-check's reclaim-race case (no model call, real
# files): it runs right after a stale lock was moved aside, so the case can
# simulate another process taking the freed name in that exact window.
RECLAIM_TEST_HOOK = None


def _lock_age_seconds(lock_path=None):
    try:
        return max(0.0, time.time() - (lock_path or LOCK).stat().st_mtime)
    except OSError:
        return None


def acquire_lock(owner, request_id, lock_path=None):
    """Atomic lease acquisition (default: the audit lock; also used for the queue lock).

    A lock file that exists is never removed on sight: an unreadable or
    holder-less lock younger than LOCK_STALE_SECONDS is treated as HELD
    (another controller may be between O_CREAT and its first write — BATCH-1
    G-01). Only a lock whose age exceeds the staleness window and whose owner
    is not alive is reclaimed.
    """
    lock_path = lock_path or LOCK
    LEASES.mkdir(parents=True, exist_ok=True)
    lease = {"owner": owner, "run_id": RUN_ID, "pid": os.getpid(),
             "started": iso(now()), "request_id": request_id}
    for _attempt in range(LOCK_MAX_ATTEMPTS):
        if lock_path.exists():
            existing = read_json(lock_path, {})
            if pid_alive(existing.get("pid")):
                return None, existing
            age = _lock_age_seconds(lock_path)
            if age is None or age < LOCK_STALE_SECONDS:
                return None, existing or {"pid": None, "state": "fresh_unreadable",
                                          "note": "lock exists but is younger than the staleness window"}
            # reclaim by ATOMIC RENAME, never by unlink: another controller may
            # have replaced the stale lock between our read and our removal, and
            # unlinking by name would delete the fresh lock (BATCH-1B G-02).
            reclaimed = lock_path.with_suffix(".reclaim.%d.%s" % (os.getpid(), secrets.token_hex(4)))
            try:
                os.replace(lock_path, reclaimed)
            except (FileNotFoundError, OSError):
                time.sleep(0.05)
                continue
            hook = RECLAIM_TEST_HOOK
            if hook:
                hook(lock_path)
            content = read_json(reclaimed, {})
            # The rename may have taken a lock that another controller has just
            # created and not finished writing (empty/unreadable content), or a
            # live lock. Anything that is not EXACTLY the stale lease we saw must
            # go back — but NEVER by overwriting whatever holds the name now: a
            # restoring os.replace would clobber a lock another process created
            # while we held the moved file, leaving two live holders (BATCH-2
            # G-02). Restore only into a still-free name; otherwise keep the
            # moved lease aside for diagnosis.
            if content != existing:
                try:
                    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError:
                    aside = lock_path.with_suffix(".orphan.%d.%s" % (os.getpid(),
                                                                    secrets.token_hex(4)))
                    try:
                        os.replace(reclaimed, aside)
                        log("reclaim raced a new lock; moved lease kept at %s" % aside.name)
                    except OSError:
                        log("reclaim raced a new lock; could not set the moved lease aside")
                    return None, content or {"pid": None, "state": "reclaim_raced_new_lock"}
                except OSError:
                    return None, content or {"pid": None, "state": "reclaim_restore_failed"}
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(content, handle)
                        handle.flush()
                        os.fsync(handle.fileno())
                except BaseException:
                    try:
                        lock_path.unlink()
                    except FileNotFoundError:
                        pass
                    raise
                try:
                    reclaimed.unlink()
                except FileNotFoundError:
                    pass
                return None, content or {"pid": None, "state": "reclaim_restored"}
            log("stale lock from dead pid %s reclaimed (age %.1fs)"
                % (existing.get("pid"), age))
            try:
                reclaimed.unlink()
            except FileNotFoundError:
                pass
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            time.sleep(0.05)
            continue
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(lease, handle)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            raise
        return lease, None
    existing = read_json(lock_path, {})
    return None, existing or {"pid": None, "state": "contended"}


def release_lock(lock_path=None, lease=None):
    """Release a lock. With `lease`, only while the file still holds THAT lease.

    Deleting by name unconditionally could remove a lock another controller has
    just taken (BATCH-3 G-02).
    """
    path = lock_path or LOCK
    if lease is not None and read_json(path, {}) != lease:
        return False
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def lease_held(lease, lock_path=None) -> bool:
    """True while the lock file still holds exactly this lease (fencing check)."""
    return bool(lease) and read_json(lock_path or LOCK, {}) == lease


class LeaseWatchdog:
    """Stops the holder when its lease is no longer the one on disk.

    A reclaim that races a live holder can hand the name to someone else; the
    displaced holder must STOP rather than finish as a second holder
    (BATCH-3 G-02). The watchdog polls the real lock file and lets the audit
    call kill its child as soon as the lease is lost.
    """

    def __init__(self, lease, lock_path=None, interval=2.0):
        self.lease = lease
        self.lock_path = lock_path or LOCK
        self.interval = interval
        self.lost = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.interval):
            if not lease_held(self.lease, self.lock_path):
                self.lost.set()
                return

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
        return False


def git_check(clone, target_sha):
    head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    status = subprocess.run(["git", "-C", str(clone), "status", "--porcelain"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {
        "clone_head": head.stdout.strip(),
        "clean": status.stdout.strip() == "",
        "head_exit": head.returncode,
        "status_exit": status.returncode,
        "match": head.stdout.strip() == target_sha and head.returncode == 0 and status.returncode == 0,
    }


def next_attempt_dir(pkg_id):
    d = RECEIPTS / pkg_id
    d.mkdir(parents=True, exist_ok=True)
    n = 1
    while (d / ("attempt-%03d" % n)).exists():
        n += 1
    ad = d / ("attempt-%03d" % n)
    ad.mkdir()
    return ad, n


class _null_context:
    """No-op context manager: used when there is no lease to watch."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _run_child(cmd, pin_path, pout_path, perr_path, watchdog=None, timeout=3600):
    """Run one audit child, killing it if the lease is lost (fencing).

    subprocess.run cannot be interrupted on a lost lease, so the child is
    started directly and polled: every poll checks the watchdog (if any) and
    the wall-clock timeout.
    """
    deadline = time.time() + timeout
    with open(pin_path, "rb") as pin, open(pout_path, "wb") as pout, open(perr_path, "wb") as perr:
        proc = subprocess.Popen(cmd, stdin=pin, stdout=pout, stderr=perr)
        while True:
            try:
                returncode = proc.wait(timeout=1)
                return returncode, False, False
            except subprocess.TimeoutExpired:
                pass
            if watchdog is not None and watchdog.lost.is_set():
                try:
                    proc.kill()
                except OSError:
                    pass
                proc.wait(timeout=30)
                return proc.returncode, True, False
            if time.time() > deadline:
                try:
                    proc.kill()
                except OSError:
                    pass
                proc.wait(timeout=30)
                raise subprocess.TimeoutExpired(cmd, timeout)


def run_codex_audit(pkg, attempt_dir, lease=None):
    clone = Path(pkg["clone"])
    prompt_file = Path(pkg["prompt_file"])
    reply_file = attempt_dir / "reply.md"
    events_file = attempt_dir / "events.jsonl"
    err_file = attempt_dir / "stderr.txt"
    session_id = SESSION_ID_FILE.read_text(encoding="utf-8").strip()
    precheck = git_check(clone, pkg["target_sha"])
    if not precheck["match"]:
        return {"classification": "PRECHECK_FAILED", "precheck": precheck}
    use_schema = SCHEMA_FILE.exists()
    schema_args = ["--output-schema", str(SCHEMA_FILE)] if use_schema else []
    cmd = [CODEX] + CODEX_BASE_ARGS + [
        "-C", str(clone), "--json", "-o", str(reply_file),
    ] + schema_args + ["resume", session_id, "-"]
    started = iso(now())
    watchdog = LeaseWatchdog(lease) if lease else None
    with watchdog or _null_context():
        proc_returncode, lease_lost, _ = _run_child(cmd, prompt_file, events_file, err_file,
                                                    watchdog=watchdog)
    ended = iso(now())
    if lease_lost:
        result = {"exit_code": proc_returncode, "started": started, "ended": ended,
                  "schema_used": use_schema, "events_file": str(events_file),
                  "stderr_file": str(err_file), "reply_file": str(reply_file),
                  "precheck": precheck, "postcheck": git_check(clone, pkg["target_sha"]),
                  "lease_lost": True}
        v = {"classification": "LEASE_LOST", "fields": None,
             "reasons": ["租约已被他人取得（回收竞态）；本持有人在失去租约后立即停止执行"],
             "exit_code": proc_returncode, "error_class": "LEASE_LOST"}
        result["verdict"] = v
        atomic_write_json(attempt_dir / "result.json", result)
        atomic_write_json(attempt_dir / "verdict.json", v)
        return result
    proc = type("Proc", (), {"returncode": proc_returncode})()
    if proc.returncode != 0 and use_schema:
        # bounded fallback: only when the failure is the schema flag itself
        try:
            err_probe = err_file.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            err_probe = ""
        if ("unexpected argument" in err_probe or "unknown argument" in err_probe
                or "output-schema" in err_probe or "invalid value" in err_probe):
            fallback_cmd = [CODEX] + CODEX_BASE_ARGS + [
                "-C", str(clone), "--json", "-o", str(reply_file),
            ] + ["resume", session_id, "-"]
            with watchdog or _null_context():
                proc_returncode, lease_lost, _ = _run_child(fallback_cmd, prompt_file, events_file,
                                                            err_file, watchdog=watchdog)
            use_schema = False
            ended = iso(now())
            if lease_lost:
                result = {"exit_code": proc_returncode, "started": started, "ended": ended,
                          "schema_used": use_schema, "events_file": str(events_file),
                          "stderr_file": str(err_file), "reply_file": str(reply_file),
                          "precheck": precheck, "postcheck": git_check(clone, pkg["target_sha"]),
                          "lease_lost": True}
                v = {"classification": "LEASE_LOST", "fields": None,
                     "reasons": ["租约已被他人取得（回收竞态）；本持有人在失去租约后立即停止执行"],
                     "exit_code": proc_returncode, "error_class": "LEASE_LOST"}
                result["verdict"] = v
                atomic_write_json(attempt_dir / "result.json", result)
                atomic_write_json(attempt_dir / "verdict.json", v)
                return result
            returncode = proc_returncode
    reply = ""
    try:
        reply = reply_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    err_text = ""
    try:
        err_text = err_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    result = {
        "exit_code": returncode,
        "started": started,
        "ended": ended,
        "schema_used": use_schema,
        "events_file": str(events_file),
        "stderr_file": str(err_file),
        "reply_file": str(reply_file),
        "precheck": precheck,
        "postcheck": git_check(clone, pkg["target_sha"]),
    }
    v = parse_verdict(reply, returncode, pkg)
    # a failed call may only be classified as an infrastructure error with evidence
    if v["classification"].startswith("INVALID_") or v["classification"] == "REQUEST_REJECTED":
        stream_error = events_error_text(events_file)
        err_class = classify_error_text(stream_error) or classify_error_text(err_text + "\n" + reply)
        if err_class:
            v = {"classification": err_class, "fields": v.get("fields"), "reasons": v["reasons"],
                 "exit_code": returncode, "error_class": err_class,
                 "error_excerpt": (stream_error or err_text or reply)[:1200]}
    result["verdict"] = v
    atomic_write_json(attempt_dir / "result.json", result)
    atomic_write_json(attempt_dir / "verdict.json", v)
    with open(attempt_dir / "input_sha256.txt", "w", encoding="utf-8") as f:
        f.write("prompt_sha256=%s\nmanifest_target=%s\n" % (sha256_file(prompt_file), pkg["target_sha"]))
    return result


def tick_audit(force=False):
    state = read_json(AUDIT_STATE, {"run_id": RUN_ID, "controller": "idle", "next_retry_at": None})
    q = load_queue()
    pkg = newest_pending(q)
    if not pkg:
        state["controller"] = "IDLE_NO_PENDING"
        state["last_tick"] = iso(now())
        atomic_write_json(AUDIT_STATE, state)
        log("tick-audit: no pending package")
        return 0
    # dedup: valid receipt for the same package and sha already exists
    reuse = has_valid_verdict(pkg["package_id"], pkg["target_sha"])
    if reuse:
        def close_from_receipt(q):
            for item in q["packages"]:
                if item["package_id"] == pkg["package_id"]:
                    item["status"] = "CLOSED_PASS" if reuse["classification"] == "PASS" else "CLOSED_CHANGES"
                    item["closed"] = iso(now())
                    item["closed_by"] = "reused_receipt:%s" % reuse["attempt"]
        mutate_queue(close_from_receipt)
        state["controller"] = "CLOSED_BY_REUSED_RECEIPT"
        atomic_write_json(AUDIT_STATE, state)
        log("tick-audit: %s closed from existing receipt %s" % (pkg["package_id"], reuse["attempt"]))
        return 0
    next_retry = state.get("next_retry_at")
    if not force and next_retry:
        try:
            if now() < datetime.fromisoformat(next_retry):
                log("tick-audit: skip %s until %s" % (pkg["package_id"], next_retry))
                return 0
        except ValueError:
            pass
    lease, holder = acquire_lock("audit-controller", pkg["package_id"])
    if lease is None:
        log("tick-audit: lock held by pid %s" % holder.get("pid"))
        return 0
    try:
        def mark_running(q):
            for item in q["packages"]:
                if item["package_id"] == pkg["package_id"]:
                    item["status"] = "RUNNING"
        mutate_queue(mark_running)
        state.update({"controller": "RUNNING", "running_package": pkg["package_id"], "lease": lease,
                      "last_tick": iso(now())})
        atomic_write_json(AUDIT_STATE, state)
        if not lease_held(lease):
            # fencing pre-check: someone already took the name between acquire
            # and the queue update — do not start a second holder (BATCH-3 G-02)
            log("tick-audit: lease lost before the call started; not running %s" % pkg["package_id"])
            return 0
        attempt_dir, attempt_no = next_attempt_dir(pkg["package_id"])
        log("audit call start %s attempt-%03d target=%s" % (pkg["package_id"], attempt_no, pkg["target_sha"]))
        try:
            result = run_codex_audit(pkg, attempt_dir, lease=lease)
        except subprocess.TimeoutExpired:
            result = {"classification": "CALL_TIMEOUT", "exit_code": None}
            atomic_write_json(attempt_dir / "result.json", result)
            atomic_write_json(attempt_dir / "verdict.json", {"classification": "CALL_TIMEOUT"})
        except FileNotFoundError as e:
            result = {"classification": "CALL_FAILED", "error": str(e)}
            atomic_write_json(attempt_dir / "result.json", result)
            atomic_write_json(attempt_dir / "verdict.json", {"classification": "CALL_FAILED"})
        cls = result.get("verdict", {}).get("classification") if isinstance(result.get("verdict"), dict) else result.get("classification")
        def record_attempt(q):
            for p in q["packages"]:
                if p["package_id"] == pkg["package_id"]:
                    p["attempts"] = p.get("attempts", 0) + 1
                    if cls == "PASS":
                        p["status"] = "CLOSED_PASS"
                        p["closed"] = iso(now())
                        p["closed_by"] = "attempt-%03d" % attempt_no
                    elif cls == "CHANGES_REQUESTED":
                        p["status"] = "CLOSED_CHANGES"
                        p["closed"] = iso(now())
                        p["closed_by"] = "attempt-%03d" % attempt_no
                    else:
                        p["status"] = "PENDING"  # retryable (rate limit / network / invalid)
                        p["last_failure"] = cls
        mutate_queue(record_attempt)
        state["running_package"] = None
        state["lease"] = None
        state["last_attempt"] = {"package": pkg["package_id"], "attempt": attempt_no,
                                 "classification": cls, "at": iso(now())}
        if cls == "PASS":
            state["controller"] = "CLOSED_PASS"
            state.pop("next_retry_at", None)
        elif cls == "CHANGES_REQUESTED":
            state["controller"] = "CLOSED_CHANGES"
            state.pop("next_retry_at", None)
        elif cls == "RATE_LIMITED":
            state["controller"] = "RATE_LIMITED"
            state["next_retry_at"] = iso(now() + timedelta(minutes=RETRY_MINUTES_DEFAULT))
        elif cls == "LEASE_LOST":
            # the held lease was taken away mid-call: the call was stopped and
            # the package stays retryable; the next tick re-acquires cleanly
            state["controller"] = "LEASE_LOST"
            state["next_retry_at"] = iso(now() + timedelta(minutes=RETRY_MINUTES_DEFAULT))
        else:
            state["controller"] = cls or "UNKNOWN"
            state["next_retry_at"] = iso(now() + timedelta(minutes=RETRY_MINUTES_DEFAULT))
        atomic_write_json(AUDIT_STATE, state)
        log("audit call done %s attempt-%03d -> %s" % (pkg["package_id"], attempt_no, cls))
        return 0
    finally:
        # only our own lease is released: a lock that now belongs to someone
        # else must survive (BATCH-3 G-02)
        if not release_lock(lease=lease):
            log("tick-audit: lock no longer held by this process; left untouched")


# ---------------------------------------------------------------- dependency check

def tick_deps():
    prev = read_json(DEPS_STATE, {"run_id": RUN_ID, "seen_heads": {}, "history": []})
    seen = prev.get("seen_heads", {})
    branches = {}
    try:
        out = subprocess.run(["git", "ls-remote", "--heads", REMOTE],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        for line in out.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2:
                branches[parts[1].replace("refs/heads/", "")] = parts[0]
        remote_ok = out.returncode == 0
    except Exception as e:
        remote_ok = False
        log("tick-deps: remote check failed: %s" % e)
    changed = {b: h for b, h in branches.items() if seen.get(b) and seen[b] != h}
    new = {b: h for b, h in branches.items() if b not in seen}
    interesting_new = {b: h for b, h in new.items()
                       if b.startswith(("feat/", "fix/", "docs/", "integration/"))}
    interesting_changed = {b: h for b, h in changed.items()
                           if b.startswith(("feat/", "fix/", "docs/", "integration/"))}
    model_cfg = {
        "OPENAI_API_KEY_present": bool(os.environ.get("OPENAI_API_KEY")),
        "PROJECTMIND_AI_MODEL_present": bool(os.environ.get("PROJECTMIND_AI_MODEL")),
        "checked_at": iso(now()),
        "note": "presence only; no model call made by this check",
    }
    history = prev.get("history", [])
    if interesting_new or interesting_changed:
        history.append({"at": iso(now()), "new_branches": interesting_new,
                        "changed_heads": interesting_changed})
    deps = {
        "run_id": RUN_ID,
        "last_check": iso(now()),
        "next_check_at": iso(now() + timedelta(minutes=RETRY_MINUTES_DEFAULT)),
        "remote_ok": remote_ok,
        "branch_count": len(branches),
        "seen_heads": branches or seen,
        "new_branches": interesting_new,
        "changed_heads": interesting_changed,
        "model_config": model_cfg,
        "history": history[-50:],
    }
    atomic_write_json(DEPS_STATE, deps)
    log("tick-deps: remote_ok=%s new=%d changed=%d model_cfg=%s" %
        (remote_ok, len(interesting_new), len(interesting_changed), model_cfg))
    return deps


# ---------------------------------------------------------------- self checks

def verdict_selftest():
    """Labeled simulated results through the real classifier (no model call)."""
    man = {"package_id": "SELFTEST", "target_sha": "a" * 40}
    cases = [
        ("overall_fail_single_item_pass_in_prose", 0,
         "- package_id: SELFTEST\n- target_sha: %s\n- scope: x\n- verdict: CHANGES_REQUESTED\n"
         "- findings: [{\"detail\": \"1 项不通过\"}]\n注意：其中单项测试显示 通过，但总结果失败。\n"
         "- unverified: []\n" % ("a" * 40),
         "CHANGES_REQUESTED"),
        ("fieldline_pass_without_unverified", 0,
         "- package_id: SELFTEST\n- target_sha: %s\n- scope: x\n- verdict: PASS\n- findings: []\n"
         % ("a" * 40),
         "INVALID_RESULT"),
        ("prose_pass_only_no_field", 0,
         "全部通过，无需修改。", "INVALID_NO_STRUCTURED_RESULT"),
        ("nonzero_exit_with_stale_pass_reply", 1,
         "- package_id: SELFTEST\n- target_sha: %s\n- scope: x\n- verdict: PASS\n- findings: []\n" % ("a" * 40),
         "INVALID_EXIT"),
        ("sha_mismatch", 0,
         "- package_id: SELFTEST\n- target_sha: %s\n- scope: x\n- verdict: PASS\n- findings: []\n" % ("b" * 40),
         "INVALID_RESULT"),
        ("empty_reply", 0, "", "INVALID_EMPTY_REPLY"),
        ("structured_json_pass", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": [], "unverified": ["suite"]}),
         "PASS"),
        ("structured_json_pass_with_findings", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": [{"summary": "x"}], "unverified": []}),
         "INVALID_RESULT"),
        ("structured_json_pass_missing_findings", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "unverified": []}),
         "INVALID_RESULT"),
        ("structured_json_pass_null_findings", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": None, "unverified": []}),
         "INVALID_RESULT"),
        ("structured_json_pass_object_findings", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": {"a": 1}, "unverified": []}),
         "INVALID_RESULT"),
        ("structured_json_pass_numeric_findings", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": 1, "unverified": []}),
         "INVALID_RESULT"),
        ("structured_json_pass_nonlist_unverified", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": [], "unverified": "none"}),
         "INVALID_RESULT"),
        ("structured_json_pass_missing_unverified", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": []}),
         "INVALID_RESULT"),
        ("structured_json_pass_null_unverified", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": [], "unverified": None}),
         "INVALID_RESULT"),
        ("findings_text_none_must_not_pass", 0,
         "- package_id: SELFTEST\n- target_sha: %s\n- scope: x\n- verdict: PASS\n"
         "- findings: none\n- unverified: []\n" % ("a" * 40),
         "INVALID_RESULT"),
        ("findings_text_wu_must_not_pass", 0,
         "- package_id: SELFTEST\n- target_sha: %s\n- scope: x\n- verdict: PASS\n"
         "- findings: 无\n- unverified: []\n" % ("a" * 40),
         "INVALID_RESULT"),
        ("structured_json_pass_string_findings", 0,
         json.dumps({"package_id": "SELFTEST", "target_sha": "a" * 40, "scope": "x",
                     "verdict": "PASS", "findings": "", "unverified": []}),
         "INVALID_RESULT"),
        ("quota_error_text_no_reply", 1,
         "stream error: you've hit your usage limit. Resets at 2026-10-08T00:00:00Z",
         "RATE_LIMITED"),
        ("network_error_text", 1, "error: connection refused (os error 10061)", "NETWORK_ERROR"),
        ("auth_error_text", 1, "401 Unauthorized: invalid_grant", "AUTH_ERROR"),
    ]
    results = []
    ok = True
    for name, exit_code, reply, expected in cases:
        v = parse_verdict(reply, exit_code, man)
        cls = v["classification"]
        if cls.startswith("INVALID_") and expected in ("RATE_LIMITED", "NETWORK_ERROR", "AUTH_ERROR"):
            cls2 = classify_error_text(reply)
            cls = cls2 or cls
        passed = (cls == expected)
        ok = ok and passed
        results.append({"case": name, "expected": expected, "got": cls, "pass": passed,
                        "label": "SIMULATED_RESULT_NOT_A_MODEL_CALL"})
    return ok, results


def proc_selftest():
    """Isolated refusal tests for ownership-verified cleanup (dry-run only)."""
    cases = []
    # 1. not registered
    allow, code, _ = stop_decision(None)
    cases.append({"case": "unregistered_pid", "expect_deny": "NOT_REGISTERED", "got": code,
                  "pass": code == "NOT_REGISTERED" and not allow})
    # 2. foreign run
    e = {"run_id": "OTHER-RUN", "pid": os.getpid(), "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "foreign_run_entry", "expect_deny": "FOREIGN_RUN", "got": code,
                  "pass": code == "FOREIGN_RUN" and not allow})
    # 3. dead pid
    e = {"run_id": RUN_ID, "pid": 999999, "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "dead_pid", "expect_deny": "PID_DEAD", "got": code,
                  "pass": code == "PID_DEAD" and not allow})
    # 4. pid reused (creation mismatch)
    creation, exe, cmdline = proc_info(os.getpid())
    e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": "2000-01-01T00:00:00",
         "dir": str(BASE), "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "pid_reused_creation_mismatch", "expect_deny": "PID_REUSED", "got": code,
                  "pass": code == "PID_REUSED" and not allow, "pid_info_available": creation is not None})
    # 4b. creation time not recorded at all -> refuse (missing evidence)
    e = {"run_id": RUN_ID, "pid": os.getpid(), "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "creation_unrecorded", "expect_deny": "CREATION_UNRECORDED", "got": code,
                  "pass": code == "CREATION_UNRECORDED" and not allow})
    # 4c. directory not recorded -> refuse
    e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": creation, "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "dir_unrecorded", "expect_deny": "DIR_UNRECORDED", "got": code,
                  "pass": code == "DIR_UNRECORDED" and not allow})
    # 5. stale registry: dir not in live cmdline
    e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": creation,
         "dir": "G:/some/other/place", "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "dir_ownership_changed", "expect_deny": "DIR_MISMATCH", "got": code,
                  "pass": code == "DIR_MISMATCH" and not allow})
    # 6. port ownership changed: entry claims port 8793 but owner is a different pid
    own_dir = os.path.dirname(sys.executable)  # appears in this process's own cmdline
    owner = port_owner(8793)
    e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": creation, "dir": own_dir,
         "port": 8793, "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    expect = "PORT_OWNER_CHANGED" if (owner is not None and owner != os.getpid()) else "VERIFIED_OWNED"
    cases.append({"case": "port_owner_changed", "expect": expect, "got": code,
                  "pass": code == expect, "observed_port_owner": owner})
    # 6b. recorded port without a listener -> ownership unconfirmed
    free_port = 45999
    if port_owner(free_port) is None:
        e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": creation, "dir": own_dir,
             "port": free_port, "purpose": "simulated"}
        allow, code, _ = stop_decision(e)
        cases.append({"case": "port_not_listening", "expect": "PORT_NOT_LISTENING", "got": code,
                      "pass": code == "PORT_NOT_LISTENING" and not allow})
    # 6c. a near-but-different creation instant must not pass
    if creation:
        shifted = creation
        try:
            from datetime import datetime as _dt, timedelta as _td
            parsed = _dt.fromisoformat(creation.replace("Z", "+00:00"))
            shifted = (parsed + _td(milliseconds=800)).isoformat()
        except ValueError:
            shifted = creation + "0"
        e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": shifted, "dir": own_dir,
             "purpose": "simulated"}
        allow, code, _ = stop_decision(e)
        cases.append({"case": "creation_instant_mismatch", "expect_deny": "PID_REUSED", "got": code,
                      "pass": code == "PID_REUSED" and not allow})
    # 6d. a directory that is only a PREFIX of the real one must not pass
    e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": creation,
         "dir": own_dir.rstrip("/")[:-3] + "-other", "purpose": "simulated"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "dir_prefix_mismatch", "expect_deny": "DIR_MISMATCH", "got": code,
                  "pass": code == "DIR_MISMATCH" and not allow})
    # 7. fully matching entry (dry-run only; nothing is killed)
    e = {"run_id": RUN_ID, "pid": os.getpid(), "creation": creation, "dir": own_dir,
         "purpose": "simulated-dry-run"}
    allow, code, _ = stop_decision(e)
    cases.append({"case": "verified_owned_dry_run", "expect": "VERIFIED_OWNED", "got": code,
                  "pass": code == "VERIFIED_OWNED" and allow, "killed": False})
    return all(c["pass"] for c in cases), cases


def lock_reclaim_selftest():
    """G-02: a reclaim that races a fresh lock must never clobber it.

    Runs the real acquire_lock against a real temp lock file: a stale lock
    (dead owner, old mtime) is in place; right after the reclaim moves it
    aside, the test seam simulates another process taking the freed name. The
    repaired code must refuse (return None with the new holder) and must leave
    the new lock byte-identical — the old restore path overwrote it and left
    two live holders.
    """
    cases = []
    sandbox = STATE / "selftest-locks"
    sandbox.mkdir(parents=True, exist_ok=True)
    lock_path = sandbox / "race.lock"
    for stale in sandbox.glob("race.lock*"):
        try:
            stale.unlink()
        except FileNotFoundError:
            pass
    stale_lease = {"owner": "dead-holder", "run_id": RUN_ID, "pid": 999999,
                   "started": iso(now()), "request_id": "stale"}
    with open(lock_path, "w", encoding="utf-8") as handle:
        json.dump(stale_lease, handle)
    old = time.time() - (LOCK_STALE_SECONDS + 120)
    os.utime(lock_path, (old, old))
    new_lock = {"owner": "racer", "run_id": RUN_ID, "pid": os.getpid(), "started": iso(now()),
                "request_id": "racer-took-the-name"}
    global RECLAIM_TEST_HOOK

    def race(_path):
        with open(lock_path, "w", encoding="utf-8") as handle:
            json.dump(new_lock, handle)
        RECLAIM_TEST_HOOK = None

    RECLAIM_TEST_HOOK = race
    try:
        lease, holder = acquire_lock("reclaim-selftest", "race", lock_path=lock_path)
    finally:
        RECLAIM_TEST_HOOK = None
    surviving = read_json(lock_path, {})
    raced_ok = (lease is None and surviving == new_lock
                and (holder or {}).get("request_id") == "racer-took-the-name")
    cases.append({"case": "reclaim_never_clobbers_a_fresh_lock", "refused": lease is None,
                  "surviving_request": surviving.get("request_id"),
                  "pass": raced_ok})
    # the complementary case: no racer -> the dead owner's stale lock IS reclaimed
    for leftover in sandbox.glob("race.lock*"):
        try:
            leftover.unlink()
        except FileNotFoundError:
            pass
    with open(lock_path, "w", encoding="utf-8") as handle:
        json.dump(stale_lease, handle)
    os.utime(lock_path, (old, old))
    lease2, holder2 = acquire_lock("reclaim-selftest-second", "restore", lock_path=lock_path)
    reclaimed_ok = (lease2 is not None
                    and read_json(lock_path, {}).get("pid") == os.getpid()
                    and not list(sandbox.glob("race.lock.reclaim.*"))
                    and not list(sandbox.glob("race.lock.orphan.*")))
    cases.append({"case": "stale_dead_lock_is_reclaimed_cleanly", "acquired": lease2 is not None,
                  "lock_pid": read_json(lock_path, {}).get("pid"), "pass": reclaimed_ok})
    if lease2:
        release_lock(lock_path=lock_path)
    for leftover in sandbox.glob("race.lock*"):
        try:
            leftover.unlink()
        except FileNotFoundError:
            pass
    return all(c["pass"] for c in cases), cases


def queue_concurrency_selftest():
    """G-03: two concurrent queue_adds must both survive.

    Runs the real queue_add (real locks, real file writes) in two threads
    against a temporary queue file, then checks the file contains both
    packages. The pre-fix pattern (plain load/modify/save) is simulated
    explicitly and its loss is recorded as the red counterpart.
    """
    import threading
    global AUDIT_QUEUE
    cases = []
    sandbox = STATE / "selftest-queue"
    sandbox.mkdir(parents=True, exist_ok=True)
    temp_queue = sandbox / "audit_queue.json"
    if temp_queue.exists():
        temp_queue.unlink()
    original_path = AUDIT_QUEUE
    # explicit red case: the unlocked interleave loses the first writer
    naive = {"run_id": RUN_ID, "packages": [], "updated": None}
    qa = dict(naive, packages=[])
    qb = dict(naive, packages=[])
    qa["packages"].append({"package_id": "SIM-A"})
    atomic_write_json(temp_queue, qa)
    qb["packages"].append({"package_id": "SIM-B"})
    atomic_write_json(temp_queue, qb)
    lost = [p["package_id"] for p in read_json(temp_queue, {}).get("packages", [])] != ["SIM-A", "SIM-B"]
    cases.append({"case": "unlocked_interleave_loses_a_package", "lost": lost, "pass": lost})
    temp_queue.unlink()
    # green case: the real queue_add under the queue lock
    AUDIT_QUEUE = temp_queue
    results = []
    errors = []

    def worker(pkg_id):
        try:
            results.append(queue_add(pkg_id, "a" * 40, "selftest", ".", "prompt.md"))
        except Exception as exc:  # noqa: BLE001 - the failure itself is the evidence
            errors.append(f"{pkg_id}: {type(exc).__name__}: {exc}")

    try:
        threads = [threading.Thread(target=worker, args=(name,))
                   for name in ("SELFTEST-A", "SELFTEST-B")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        final = [p["package_id"] for p in read_json(temp_queue, {}).get("packages", [])]
        both_kept = sorted(final) == ["SELFTEST-A", "SELFTEST-B"]
        both_ok = all(r.get("added") for r in results) and len(results) == 2 and not errors
    finally:
        AUDIT_QUEUE = original_path
        try:
            temp_queue.unlink()
        except FileNotFoundError:
            pass
    cases.append({"case": "locked_concurrent_queue_add_keeps_both", "final": final,
                  "results": [r.get("added") for r in results], "errors": errors,
                  "pass": bool(both_kept and both_ok)})
    return all(c["pass"] for c in cases), cases


def lease_fencing_selftest():
    """G-02 (closing): a displaced holder must STOP, not run on as a second holder.

    Real lock file, real watchdog thread, real child process: the lease is taken
    away mid-flight and the running child must be killed by the watchdog; a
    release of the displaced lease must not remove the foreign lock.
    """
    cases = []
    sandbox = STATE / "selftest-locks"
    sandbox.mkdir(parents=True, exist_ok=True)
    lock_path = sandbox / "fencing.lock"
    for leftover in sandbox.glob("fencing.lock*"):
        try:
            leftover.unlink()
        except FileNotFoundError:
            pass
    lease, holder = acquire_lock("fencing-selftest", "fencing", lock_path=lock_path)
    if lease is None:
        cases.append({"case": "fencing_setup_acquire", "pass": False, "holder": holder})
        return False, cases
    # the name is taken over by a "third party" while we still believe we hold it
    with open(lock_path, "w", encoding="utf-8") as handle:
        json.dump({"owner": "third-party", "run_id": RUN_ID, "pid": os.getpid(),
                   "started": iso(now()), "request_id": "third"}, handle)
    still = lease_held(lease, lock_path)
    cases.append({"case": "displaced_holder_sees_loss", "lease_held": still, "pass": not still})
    pin = sandbox / "child_in.txt"
    pin.write_text("x", encoding="utf-8")
    pout = sandbox / "child_out.txt"
    perr = sandbox / "child_err.txt"
    started = time.time()
    with LeaseWatchdog(lease, lock_path, interval=0.5) as watchdog:
        returncode, lease_lost, _ = _run_child([sys.executable, "-c", "import time; time.sleep(120)"],
                                               pin, pout, perr, watchdog=watchdog, timeout=60)
    elapsed = time.time() - started
    cases.append({"case": "displaced_holder_child_is_killed", "lease_lost": lease_lost,
                  "returncode": returncode, "elapsed_seconds": round(elapsed, 1),
                  "pass": bool(lease_lost) and elapsed < 30 and returncode != 0})
    removed = release_lock(lock_path=lock_path, lease=lease)
    surviving = read_json(lock_path, {}).get("owner")
    cases.append({"case": "release_never_removes_a_foreign_lock", "removed": removed,
                  "surviving_owner": surviving,
                  "pass": removed is False and surviving == "third-party"})
    for leftover in sandbox.glob("fencing.lock*"):
        try:
            leftover.unlink()
        except FileNotFoundError:
            pass
    return all(c["pass"] for c in cases), cases


def self_check():
    report = {"run_id": RUN_ID, "at": iso(now()), "model_call_made": False}
    q = load_queue()
    report["queue_read_ok"] = isinstance(q, dict) and "packages" in q
    report["queue_view"] = {"pending": [p["package_id"] for p in q.get("packages", []) if p.get("status") == "PENDING"],
                            "total": len(q.get("packages", []))}
    lock_ok = True
    for i in (1, 2):
        lease, holder = acquire_lock("self-check", "self-check-%d" % i)
        if lease is None:
            lock_ok = False
            report["lock_holder_%d" % i] = holder
            break
        release_lock()
    report["lock_idempotent_ok"] = lock_ok
    vok, vcases = verdict_selftest()
    report["verdict_selftest_ok"] = vok
    report["verdict_cases"] = vcases
    pok, pcases = proc_selftest()
    report["proc_selftest_ok"] = pok
    report["proc_cases"] = pcases
    # duplicate-trigger test: second acquire while held must be refused
    lease, _ = acquire_lock("self-check-hold", "hold")
    lease2, holder2 = acquire_lock("self-check-second", "second")
    report["duplicate_trigger_refused"] = lease is not None and lease2 is None
    if lease:
        release_lock()
    # fresh-but-unreadable lock (holder not yet written) must never be stolen
    LEASES.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w", encoding="utf-8") as handle:
        handle.write("{")  # torn/partial content, just created
    stolen, _holder = acquire_lock("self-check-third", "third")
    report["fresh_unreadable_lock_protected"] = stolen is None
    if stolen:
        release_lock()
    else:
        try:
            LOCK.unlink()
        except FileNotFoundError:
            pass
    report["log_line"] = log("self-check executed (no model call)")
    rok, rcases = lock_reclaim_selftest()
    report["lock_reclaim_selftest_ok"] = rok
    report["lock_reclaim_cases"] = rcases
    fok, fcases = lease_fencing_selftest()
    report["lease_fencing_selftest_ok"] = fok
    report["lease_fencing_cases"] = fcases
    qok, qcases = queue_concurrency_selftest()
    report["queue_concurrency_selftest_ok"] = qok
    report["queue_concurrency_cases"] = qcases
    atomic_write_json(STATE / "controller_selfcheck.json", report)
    ok = (report["queue_read_ok"] and report["lock_idempotent_ok"] and vok and pok
          and report["duplicate_trigger_refused"] and report["fresh_unreadable_lock_protected"]
          and rok and qok and fok)
    report["ok"] = ok
    atomic_write_json(STATE / "controller_selfcheck.json", report)
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("verdict_cases", "proc_cases", "lock_reclaim_cases",
                                   "queue_concurrency_cases", "lease_fencing_cases")},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 1


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("queue-add")
    p.add_argument("--package-id", required=True)
    p.add_argument("--target-sha", required=True)
    p.add_argument("--scope", required=True)
    p.add_argument("--clone", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--notes", default="")
    sub.add_parser("tick-audit").add_argument("--force", action="store_true")
    sub.add_parser("tick-deps")
    sub.add_parser("tick-all")
    sub.add_parser("self-check")
    sub.add_parser("verdict-selftest")
    p = sub.add_parser("proc-register")
    p.add_argument("--name", required=True)
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--dir", required=True)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--purpose", required=True)
    p = sub.add_parser("proc-stop")
    p.add_argument("--name", required=True)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("proc-cleanup")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("proc-ls")
    sub.add_parser("state-show")
    args = ap.parse_args()

    if args.cmd == "queue-add":
        r = queue_add(args.package_id, args.target_sha, args.scope, args.clone, args.prompt, args.notes)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "tick-audit":
        return tick_audit(force=getattr(args, "force", False))
    if args.cmd == "tick-deps":
        tick_deps()
        return 0
    if args.cmd == "tick-all":
        tick_deps()
        return tick_audit()
    if args.cmd == "self-check":
        return self_check()
    if args.cmd == "verdict-selftest":
        ok, cases = verdict_selftest()
        print(json.dumps({"ok": ok, "cases": cases}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if args.cmd == "proc-register":
        reg = load_registry()
        creation, exe, cmdline = proc_info(args.pid)
        entry = {"name": args.name, "run_id": RUN_ID, "pid": args.pid, "creation": creation,
                 "exe": exe, "dir": args.dir, "port": args.port, "purpose": args.purpose,
                 "registered_at": iso(now())}
        reg["processes"] = [e for e in reg["processes"] if e.get("name") != args.name] + [entry]
        save_registry(reg)
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "proc-ls":
        reg = load_registry()
        for e in reg["processes"]:
            allow, code, detail = stop_decision(e)
            print(json.dumps({"name": e["name"], "pid": e["pid"], "port": e.get("port"),
                              "purpose": e.get("purpose"), "alive": pid_alive(e["pid"]),
                              "stop_decision": code}, ensure_ascii=False))
        return 0
    if args.cmd == "proc-stop":
        reg = load_registry()
        entry = next((e for e in reg["processes"] if e.get("name") == args.name), None)
        allow, code, detail = stop_decision(entry)
        if args.dry_run:
            print(json.dumps({"name": args.name, "allow": allow, "decision": code,
                              "detail": detail, "dry_run": True}, ensure_ascii=False, indent=2))
            return 0 if allow else 3
        if not allow:
            print(json.dumps({"name": args.name, "killed": False, "decision": code, "detail": detail},
                             ensure_ascii=False, indent=2))
            log("proc-stop refused for %s: %s (%s)" % (args.name, code, detail))
            return 3
        r = kill_verified(entry)
        reg = load_registry()
        reg["processes"] = [e for e in reg["processes"] if e.get("name") != args.name]
        save_registry(reg)
        print(json.dumps({"name": args.name, **r}, ensure_ascii=False, indent=2))
        log("proc-stop %s: %s" % (args.name, json.dumps(r, ensure_ascii=False)))
        return 0
    if args.cmd == "proc-cleanup":
        reg = load_registry()
        decisions, killed = [], []
        for e in list(reg["processes"]):
            allow, code, detail = stop_decision(e)
            decisions.append({"name": e.get("name"), "pid": e.get("pid"), "allow": allow, "decision": code})
            if allow and not args.dry_run:
                r = kill_verified(e)
                killed.append({"name": e.get("name"), **r})
        if not args.dry_run:
            reg["processes"] = [e for e in reg["processes"]
                                if next((d for d in decisions if d["name"] == e.get("name") and d["allow"]), None) is None]
            save_registry(reg)
        print(json.dumps({"decisions": decisions, "killed": killed, "dry_run": args.dry_run},
                         ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "state-show":
        print(json.dumps({"audit_state": read_json(AUDIT_STATE, {}),
                          "queue": load_queue(),
                          "deps": {k: v for k, v in read_json(DEPS_STATE, {}).items()
                                   if k in ("last_check", "next_check_at", "remote_ok", "new_branches",
                                            "changed_heads", "model_config")},
                          "processes": read_json(PROC_REGISTRY, {})}, ensure_ascii=False, indent=2)[:6000])
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())