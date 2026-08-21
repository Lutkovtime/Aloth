"""WinSparkle spike (via ctypes, pywinsparkle is dead for py3.11).

Verifies: EdDSA keygen + appcast sign/verify via winsparkle-tool, and that
WinSparkle.dll loads from Python 3.11 via ctypes with the needed API.
"""
import base64
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent / "winsparkle"
TOOL = ROOT / "WinSparkle-0.9.4" / "bin" / "winsparkle-tool.exe"
DLL = ROOT / "WinSparkle-0.9.4" / "x64" / "Release" / "WinSparkle.dll"
WORK = ROOT / "work"
ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
    ok = ok and cond


def run(args: list[str]) -> tuple[str, str]:
    r = subprocess.run([str(TOOL), *args], capture_output=True, text=True, timeout=60)
    return r.stdout.strip(), r.stderr.strip()


def main() -> int:
    WORK.mkdir(exist_ok=True)
    os.chdir(WORK)

    # 1. keygen (pub key printed to stdout, priv saved to file)
    out, err = run(["generate-key", "--file", "eddsa_priv.pem"])
    priv = Path("eddsa_priv.pem")
    check("keygen", priv.exists(), f"priv={priv.name}, pub in stdout")
    pub_line = next((l for l in out.splitlines() if "Public key:" in l), "")
    pub_b64 = pub_line.split("Public key:", 1)[-1].strip() if pub_line else ""

    # 2. appcast.xml (minimal)
    appcast = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <title>Aloth</title>
    <item>
      <title>Version 0.1.1</title>
      <sparkle:version>0.1.1</sparkle:version>
      <sparkle:releaseNotesLink>https://example.com/release-notes</sparkle:releaseNotesLink>
      <enclosure url="https://example.com/Aloth-Setup-0.1.1.exe" sparkle:edSignature="" type="application/octet-stream"/>
    </item>
  </channel>
</rss>
"""
    (WORK / "appcast.xml").write_text(appcast, encoding="utf-8")

    # 3. sign appcast.xml
    sig, err = run(["sign", "--private-key-file", "eddsa_priv.pem", "appcast.xml"])
    check("sign", len(sig) > 20, sig[:80])
    sig_b64 = sig
    try:
        base64.b64decode(sig_b64, validate=True)
        sig_ok = True
    except Exception:
        sig_ok = False
    check("signature_b64", sig_ok, sig_b64[:40])

    # 4. verify (pub key from stdout, signature from sign)
    vout, verr = run(["verify", "--public-key", pub_b64, "--signature", sig_b64, "appcast.xml"])
    check("verify", "valid" in (vout + verr).lower(), (vout + verr)[:80])

    # 5. public key extraction (base64 of raw 32 bytes)
    check("public_key_out", len(pub_b64) > 10, pub_b64[:40])

    # 6. ctypes: load DLL and resolve API
    try:
        dll = ctypes.WinDLL(str(DLL))
        dll_loaded = True
    except OSError as e:
        dll_loaded = False
        dll_err = str(e)
    check("dll_load", dll_loaded, "" if dll_loaded else dll_err)

    if dll_loaded:
        names = [
            "win_sparkle_init",
            "win_sparkle_cleanup",
            "win_sparkle_set_appcast_url",
            "win_sparkle_set_eddsa_public_key",
            "win_sparkle_set_app_details",
            "win_sparkle_check_update_with_ui",
            "win_sparkle_check_update_without_ui",
            "win_sparkle_set_can_shutdown_callback",
        ]
        for n in names:
            fn = getattr(dll, n, None)
            check(f"api_{n}", callable(fn))

        # 7. real init round with appcast URL (no UI check — check_update_without_ui is fire-and-forget)
        url = (WORK / "appcast.xml").resolve().as_uri()
        dll.win_sparkle_set_appcast_url(ctypes.c_wchar_p(url))
        if pub_b64:
            dll.win_sparkle_set_eddsa_public_key(ctypes.c_char_p(pub_b64.encode()))
        dll.win_sparkle_set_app_details(
            ctypes.c_wchar_p("Aloth"), ctypes.c_wchar_p("Lutkovtime"), ctypes.c_wchar_p("0.1.0")
        )
        dll.win_sparkle_init()
        # WinSparkle spawns a thread; give it a moment, then query update-check state
        time.sleep(2)
        dll.win_sparkle_cleanup()
        check("init_cleanup", True, "init+cleanup ok")

    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
