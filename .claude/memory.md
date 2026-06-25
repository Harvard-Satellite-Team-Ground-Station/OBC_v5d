# Pinned / Deferred Items

Running list of things explicitly put on hold ("pin that", "think about later",
"keep in the back of your mind"). Newest context at top of each section.

Last updated: 2026-06-25 (added section 5: pre-blast reconnaissance)

---

## Current state of the patch-upload work (context for everything below)

A software-patch uplink feature was added to
[cdh.py](../src/flight-software/lib/pysquared/cdh.py): four authenticated
commands `patch_new` / `patch_put` / `patch_status` / `patch_apply` that deliver
a file as base64 chunks with selective-repeat resume, MD5 integrity, and a
stage-only write (writes a new file, never overwrites a live one). It replaces
the old "blast the exec command 10-20x and pray" method.

- Verified: 36/36 standalone harness checks + a second sonnet review pass
  (82 total checks) green; ruff + pyright clean; no em-dashes.
- Footprint: compacted from +338 to +205 added lines, behavior identical.
- NOTHING COMMITTED yet. All changes are working-tree only.
- Scope rule for this work: communications layer only. Do NOT edit FSM, boot, or
  main loop.

---

## 1. Orientation algorithm revisit (oldest pin)

"Put a pin in that, I'll come back to the orient algo later."

- Open thread: the orient sun-tracking algorithm in
  [state_orient.py](../src/flight-software/fsm/state_processes/state_orient.py),
  broadly, to revisit later.
- The specific sub-question already answered (kept here so we do not re-derive
  it): `best_direction` (argmax over the 4 light sensors = which face saw the
  most light) and `orient_best_direction` (telemetry label / which spring axis
  fires) intentionally differ by ~90 degrees. That is physical, not a bug: the
  light sensor and the spring actuator live on adjacent faces, so firing the
  spring on the bright face rotates the body ~90 degrees to point the intended
  axis at the Sun.
- Still to do (per the user): a broader look at the orient algorithm itself.

---

## 2. Two design decisions to weigh in on (patch feature)

"Keep those two points in the back of mind, for now."

### 2a. Stage-only vs in-place overwrite for `patch_apply`
- Current behavior: `patch_apply` REFUSES to overwrite an existing target file.
  The operator uploads to a NEW path, confirms the downlinked MD5/size, then
  swaps it in deliberately. Chosen because it makes corrupting a live file in
  place structurally impossible (no remove+rename window, no boot-critical
  brick), matching the "be extra sure about bricking" priority.
- Tradeoff: replacing an existing file needs a separate, deliberate swap step.
- If we want overwrite-in-place instead: implement the safest-on-FAT ordering
  (rename existing target to .bak, rename tmp to target, remove .bak) so the old
  file stays recoverable during the swap. Internal flash is FAT (no atomic
  replace), so a tiny window is unavoidable; .bak keeps it recoverable.
- DECISION OWNER: user. Default stays stage-only until told otherwise.

### 2b. Filesystem writability dependency
- `boot.py` is empty and nothing in the app code calls
  `storage.remount("/", False)`. So writing to flash from code depends on the FS
  being writable at runtime. This is the SAME dependency every existing
  persistent-config command already has (config `temporary=False` writes).
- If the FS is read-only, `patch_apply` fails cleanly with "write failed
  (filesystem read only?)" (no hang, no brick).
- Fixing writability would mean editing `boot.py`, which is OUT of the comms
  scope set for this work. Flagged for a separate decision.

---

## 3. Uplink-size reduction options (patch feature)

"Pin that for now." (raised when discussing how to make the ~300-line update
easier to blast up via the exec method)

### 3a. Stripped "blast payload" (recommended further win)
- The 205 repo lines are the readable source. What the one-time bootstrap blast
  actually costs is BYTES, and docstrings/comments/blank lines are pure overhead.
- Idea: generate a comment-and-docstring-stripped copy purely for the bootstrap
  upload. The MD5 self-check means a garbled blast is caught automatically. Repo
  keeps the readable version untouched.
- Not yet produced. This was the specific thing pinned.

### 3b. Merge four commands into one `patch <subcommand>` command
- Saves ~10-15 more lines (one dispatch branch, one class attr) but changes the
  wire interface the user likes and makes one long method. Leaning against it.

---

## 4. Review-driven hardening batch (patch feature)

"Pin those thoughts for now." (the recommended fixes from the second sonnet
review; all in cdh.py, all cheap, all in-scope). No regressions or critical bugs
were found; these are pre-existing hardening opportunities.

Recommended batch (do #1-#4 + harness fix; cosmetics optional):

1. Watchdog headroom on a MAX-size patch. `patch_apply` runs in the command loop
   and the watchdog is petted around, not inside, `listen_for_commands`. A 32 KB
   patch hashes twice in pure-Python MD5 (~3-5 s). Whether that trips the WDT
   depends on the board WDT period (hardware-set, not in software). Mitigation:
   lower the size cap (`_patch_max_chunks` 128 -> 64 => 16 KB max), which halves
   worst-case apply time AND RAM. JUDGMENT CALL: shrink the cap, or keep 128 and
   just document an operator size limit. Petting inside apply would touch
   main.py (out of scope).

2. RAM peak / misleading `del content` comment. When `del content` runs,
   `s["chunks"]` still holds the bytes, so peak is ~chunks + readback, not "one
   copy." Fix: free `s["chunks"] = {}` right after assembling `content`, and
   correct the comment. (Lowering the cap in #1 also bounds this.)

3. Stale `.tmp` cleanup. A reset between write and rename leaves `target.tmp`
   (harmless to boot, but wastes flash). One-liner: `_remove_quiet(target +
   ".tmp")` at the start of `patch_new`.

4. Zero-length chunk silently accepted (`0 > 256` is False). MD5 catches it but
   only at apply time (a wasted pass on a lossy link). One-line reject in
   `patch_put`.

Harness gap (scratchpad verify_patch.py): the S2/S3 "tmp cleaned up" assertions
are vacuous (those paths bail before `.tmp` is created). Add a scenario that
forces a readback failure (mock `open` to raise) to actually exercise
`_remove_quiet`.

Cosmetic / near-zero real risk (optional, probably skip):
- `os.stat` `except OSError` treats any error as "absent"; on FAT there are no
  permission bits so it is effectively unreachable. An `errno != 2` guard is
  cosmetic.
- base64 padding tolerance (pad before `a2b_base64`) for operator convenience.
- Add a comment explaining the magic `24` in `_format_missing` (packet-fit cap).
- Add a `dict | None` annotation to `_patch_session` (tooling only; MicroPython
  ignores annotations).

---

## 5. Pre-blast reconnaissance plan (do this BEFORE the one-time blast)

Idea: spend one cheap, fully read-only pass gathering facts before committing to
the irreversible bootstrap blast. Resolves most open unknowns (filesystem
writability, free RAM, free flash, FAT vs not, link margin) without changing any
state. Two existing repo tools do this for free.

### 5a. One bundled `exec` "status report"
`exec` captures stdout and downlinks it, and it runs in the handler frame so it
can reach `self`. One script can print everything in a single pass. Send it as a
SINGLE args string so newlines survive (exec joins multiple args with spaces,
which would flatten Python indentation). Read-only and self-cleaning:

```python
import os, gc
gc.collect()
print("uname:", os.uname())                     # board + FS/CP version (FAT vs not)
print("ram:", gc.mem_free())                    # informs the patch size cap (item 4 #1)
v = os.statvfs("/"); print("flash:", v[0]*v[3]) # room for the patch + its .tmp
print("root:", os.listdir("/"))                 # confirm paths, spot stale .tmp files
try:
    f = open("/probe.tmp", "w"); f.write("x"); f.close(); os.remove("/probe.tmp")
    print("writable: YES")                       # directly tests item 2b
except Exception as e:
    print("writable: NO", e)
print("rssi:", self._packet_manager.get_last_rssi())  # link margin, via self
```

Each line maps to a risk: `uname` settles the FAT question; `gc.mem_free()`
informs the 16 vs 32 KB cap decision (4 #1); `statvfs` confirms room; the
write-then-delete probe directly tests the read-only-filesystem caveat (2b)
instead of guessing from the empty boot.py.

### 5b. First contact and blast sizing via OSCAR ping / repeat
- `ping` returns "Pong! {rssi}": confirms two-way comms + link strength this pass.
  Uses the simple OSCAR password, not full command auth.
- `repeat` echoes back whatever you send: send progressively larger payloads and
  watch where they stop returning clean to MEASURE reliable bytes-per-transmission
  empirically. That number sizes the patch chunks and estimates blast count.

### Why it is safe and how it shapes the patch
All non-destructive (ping/repeat change nothing; the exec probe only reads plus
writes-then-deletes one throwaway file). If "writable: NO" comes back, we learn
the patch-to-disk path will not work BEFORE wasting a pass (pivot to a RAM-only
monkey-patch, or fix the boot remount first, see 2b). Tight RAM caps the patch
size; RSSI/repeat numbers tell us one pass vs several.
