"""Ground-station uplink helpers.

Adds an acknowledged round-trip on top of the radio (send, then wait for the
satellite's ACK and text reply), a resumable patch uploader that drives the
satellite's patch_new / patch_put / patch_status / patch_apply commands with
selective repeat, and a one-time bootstrap blast that writes a file using the
existing exec command (for installing the patch commands the first time).

Designed to run on the CircuitPython ground-station board next to main.py. The
radio packet manager, config, and logger are passed in so this stays testable.
"""

import json


def build_msg(config, password, command, args):
    """Builds the JSON command bytes the satellite expects."""
    return json.dumps(
        {
            "name": config.cubesat_name,
            "command": command,
            "args": args,
            "password": password,
        }
    ).encode("utf-8")


def _show(resp):
    """Renders a satellite reply for logging."""
    if resp is None:
        return "(no response)"
    if isinstance(resp, bytes):
        try:
            return resp.decode("utf-8")
        except Exception:
            return repr(resp)
    return str(resp)


def send_and_receive(
    pm, msg_bytes, retries=3, prime_timeout=0.5, ack_timeout=2, resp_timeout=4
):
    """Sends one command and waits for the satellite's ACK then text reply.

    Returns the reply bytes, or None if no reply arrived. The command is only
    resent when no ACK comes back (the satellite did not receive it), never after
    an ACK, so a non-idempotent command is not executed twice just because its
    reply was lost. All patch_* commands are idempotent, so the patch uploader
    can safely resend regardless.
    """
    for _ in range(retries):
        # Prime the receiver so the radio is buffering before the reply lands.
        pm.listen(prime_timeout)
        pm.send(msg_bytes)
        if pm.listen(ack_timeout) != b"ACK":
            continue
        return pm.listen(resp_timeout)
    return None


def _md5_hex(data):
    """MD5 hex digest, matching the satellite's adafruit_hashlib MD5."""
    import adafruit_hashlib

    h = adafruit_hashlib.new("md5")
    h.update(data)
    return h.hexdigest()


def _chunks_b64(data, chunk_size):
    """Splits raw bytes into base64 strings, one per chunk_size-byte slice.

    Each slice is base64-encoded independently so the satellite can decode each
    chunk on its own.
    """
    import binascii

    out = []
    for i in range(0, len(data), chunk_size):
        out.append(
            binascii.b2a_base64(data[i : i + chunk_size]).decode("utf-8").strip()
        )
    return out


def _parse_missing(text):
    """Pulls the missing-chunk indices out of a patch_status reply.

    Returns (indices, more) where more is True if the satellite truncated the
    list (the "(+N more)" suffix).
    """
    if "missing" not in text:
        return [], False
    frag = text.split("missing", 1)[1]
    more = "more)" in frag
    nums = []
    lb = frag.find("[")
    rb = frag.find("]")
    if lb != -1 and rb > lb:
        for tok in frag[lb + 1 : rb].split(","):
            tok = tok.strip()
            if tok.isdigit():
                nums.append(int(tok))
    return nums, more


def upload_patch(
    pm,
    config,
    logger,
    password,
    local_path,
    remote_path,
    chunk_size=96,
    prime_timeout=0.5,
    log=print,
):
    """Uploads local_path to remote_path on the satellite, resumably.

    Reads the file, fingerprints it with MD5, sends it as base64 chunks, uses
    patch_status to find and resend whatever dropped, then applies it. Returns
    True only when the satellite confirms patch_apply.
    """
    with open(local_path, "rb") as f:
        data = f.read()

    md5 = _md5_hex(data)
    chunks = _chunks_b64(data, chunk_size)
    total = len(chunks)
    if total < 1:
        log("patch: refusing to upload an empty file")
        return False
    if total > 128:
        log(
            f"patch: {total} chunks exceeds the satellite cap of 128, use a bigger chunk_size"
        )
        return False
    log(f"patch: {len(data)} bytes -> {total} chunks, md5 {md5}")

    def sr(command, args):
        return send_and_receive(
            pm, build_msg(config, password, command, args), prime_timeout=prime_timeout
        )

    resp = sr("patch_new", [remote_path, str(total), md5])
    log(f"patch_new -> {_show(resp)}")
    if resp is None or b"patch_new ok" not in resp:
        log("patch: patch_new not confirmed, aborting")
        return False

    acked = set()

    def put(idx):
        r = sr("patch_put", [str(idx), chunks[idx]])
        if r is not None and b"patch_put ok" in r:
            acked.add(idx)
        return r

    # First pass: send every chunk.
    for idx in range(total):
        log(f"patch_put {idx}/{total - 1} -> {_show(put(idx))}")

    # Selective repeat: ask what is missing and resend until ready or stuck.
    ready = False
    for round_i in range(20):
        resp = sr("patch_status", [])
        log(f"patch_status -> {_show(resp)}")
        text = _show(resp)
        if resp is not None and "ready to apply" in text:
            ready = True
            break
        # _more is intentionally ignored, the next patch_status returns a fresh
        # list with whatever is still missing.
        missing, _more = _parse_missing(text)
        if not missing:
            missing = [i for i in range(total) if i not in acked]
        if not missing:
            log(
                f"patch: all chunks acked locally but satellite not ready, re-checking ({round_i + 1}/20)"
            )
            continue
        for idx in missing:
            if 0 <= idx < total:
                log(f"resend {idx} -> {_show(put(idx))}")
            else:
                log(f"patch: ignoring out-of-range chunk index {idx} from satellite")

    if not ready:
        log("patch: could not get all chunks delivered, not applying")
        return False

    resp = sr("patch_apply", [])
    log(f"patch_apply -> {_show(resp)}")
    if resp is None:
        # patch_apply is NOT idempotent: if the reply was lost, the file may still
        # have been written. Do not blindly retry, a second apply would be refused
        # with "already exists". Verify on the satellite first.
        log(
            "patch: patch_apply reply not received, the file may have applied, verify on the satellite before retrying"
        )
        return False
    ok = b"patch_apply ok" in resp
    log("patch: SUCCESS" if ok else "patch: apply not confirmed, check the satellite")
    return ok


def blast_file(
    pm,
    config,
    logger,
    password,
    local_path,
    remote_path,
    chunk_size=64,
    prime_timeout=0.5,
    log=print,
):
    """One-time bootstrap: write local_path to remote_path using exec.

    Works before the patch commands exist on the satellite. Truncates the target,
    appends each base64 chunk via exec, then verifies by hashing the written file
    on the satellite. Does NOT reboot, the operator sends 'reset' afterward to
    load the new file.
    """
    with open(local_path, "rb") as f:
        data = f.read()
    md5 = _md5_hex(data)
    chunks = _chunks_b64(data, chunk_size)
    total = len(chunks)
    log(f"blast: {len(data)} bytes -> {total} exec writes to {remote_path}, md5 {md5}")

    def sr(code):
        return send_and_receive(
            pm, build_msg(config, password, "exec", [code]), prime_timeout=prime_timeout
        )

    resp = sr("f=open(%r,'wb');f.close()" % remote_path)
    log(f"blast truncate -> {_show(resp)}")
    if resp is None or b"executed successfully" not in resp:
        log("blast: could not truncate target, aborting")
        return False

    for idx, c in enumerate(chunks):
        resp = sr(
            "import binascii;f=open(%r,'ab');f.write(binascii.a2b_base64(%r));f.close()"
            % (remote_path, c)
        )
        log(f"blast {idx}/{total - 1} -> {_show(resp)}")
        # Continue on a lost reply (the write still happened if it was received);
        # only abort on an explicit failure. The final hash check is the real gate.
        if resp is not None and b"Failed to execute" in resp:
            log(f"blast: chunk {idx} failed on the satellite, aborting")
            return False

    verify = (
        "import binascii,adafruit_hashlib;"
        "d=open(%r,'rb').read();"
        "h=adafruit_hashlib.new('md5');h.update(d);"
        "print('BLASTMD5',h.hexdigest(),len(d))" % remote_path
    )
    resp = sr(verify)
    log(f"blast verify -> {_show(resp)}")
    ok = resp is not None and md5.encode("utf-8") in resp
    if ok:
        log(f"blast: file md5 MATCHES. Send 'reset' to reboot and load {remote_path}.")
    else:
        log(f"blast: file md5 MISMATCH, expected {md5}. Do not reset, investigate.")
    return ok
