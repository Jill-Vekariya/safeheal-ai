"""Install the checksum-pinned local-process benchmark Prometheus on Linux x86_64."""
import hashlib
from pathlib import Path
import platform
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.15.0"
ARCHIVE = f"prometheus-{VERSION}.linux-amd64.tar.gz"
# Official release sha256sums.txt, verified 2026-10-22.
SHA256 = "2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0"
URL = f"https://github.com/prometheus/prometheus/releases/download/v{VERSION}/{ARCHIVE}"
DESTINATION = ROOT / ".tools" / f"prometheus-{VERSION}" / "prometheus"


def install():
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("This optional local-process installer supports Linux x86_64 only; use the Kubernetes backend elsewhere.")
    if DESTINATION.exists():
        print(f"Already installed: {DESTINATION}")
        return
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="safeheal-prometheus-") as folder:
        archive = Path(folder) / ARCHIVE
        digest = hashlib.sha256()
        with urllib.request.urlopen(URL, timeout=45) as response, archive.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != SHA256:
            raise RuntimeError("Official Prometheus archive checksum mismatch")
        with tarfile.open(archive, "r:gz") as source:
            member = source.getmember(f"prometheus-{VERSION}.linux-amd64/prometheus")
            if not member.isfile():
                raise RuntimeError("Unexpected Prometheus archive member")
            with source.extractfile(member) as binary, DESTINATION.open("xb") as output:
                while chunk := binary.read(1024 * 1024):
                    output.write(chunk)
        DESTINATION.chmod(0o755)
        DESTINATION.with_suffix(".sha256").write_text(hashlib.sha256(DESTINATION.read_bytes()).hexdigest() + "\n")
    print(f"Installed checksum-verified Prometheus {VERSION}: {DESTINATION}")


if __name__ == "__main__":
    install()
