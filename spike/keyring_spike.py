"""Nuitka frozen keyring spike: real secret write/read via Windows Credential Manager."""
import sys


def main() -> int:
    import keyring

    svc = "aloth-frozen-spike"
    keyring.set_password(svc, "k1", "frozen-secret-456")
    v = keyring.get_password(svc, "k1")
    ok = v == "frozen-secret-456"
    backend = f"{type(keyring.get_keyring()).__module__}.{type(keyring.get_keyring()).__name__}"
    print(f"{'PASS' if ok else 'FAIL'}  keyring_roundtrip  {backend}  v={v}")
    if ok:
        keyring.delete_password(svc, "k1")
        print(f"{'PASS' if keyring.get_password(svc, 'k1') is None else 'FAIL'}  keyring_delete")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
