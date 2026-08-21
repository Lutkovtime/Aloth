"""File tools for the agent — read/write confined to the Aloth home.

Safety by construction: paths are resolved against the home dir and any
attempt to escape (.., absolute path outside home, symlink) is rejected.
"""

from __future__ import annotations

from pathlib import Path


class FileTools:
    def __init__(self, home: Path):
        self.home = home.resolve()

    def _resolve(self, rel: str) -> Path:
        """Resolve a home-relative path; raise ValueError if it escapes."""
        p = (self.home / rel).resolve()
        if not (p == self.home or self.home in p.parents):
            raise ValueError(f"путь вне дома запрещён: {rel}")
        return p

    def read(self, rel: str) -> str:
        # errors="replace": binary/non-utf8 files must never crash the dialog.
        return self._resolve(rel).read_text(encoding="utf-8", errors="replace")

    def write(self, rel: str, content: str) -> str:
        p = self._resolve(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"записал {rel}"

    def list(self, rel: str = "") -> str:
        p = self._resolve(rel)
        if not p.is_dir():
            raise ValueError(f"не каталог: {rel}")
        return "\n".join(
            str(x.relative_to(self.home)).replace("\\", "/")
            for x in p.rglob("*")
        )


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        ft = FileTools(Path(td))
        assert ft.write("a/b.txt", "hi") == "записал a/b.txt"
        assert ft.read("a/b.txt") == "hi"
        assert "a/b.txt" in ft.list()
        for bad in ("../x", "/etc/passwd", "a/../../x"):
            try:
                ft.read(bad)
                raise AssertionError(f"escape не пойман: {bad}")
            except ValueError:
                pass
    print("files ok")
