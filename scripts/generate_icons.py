import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtWidgets import QApplication

from ui.icon import create_app_pixmap


def main() -> None:
    app = QApplication.instance() or QApplication([])
    assets_dir = REPO_ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    outputs = (
        ("synapcap.png", 512),
        ("synapcap.ico", 256),
        ("synapcap.icns", 1024),
    )
    for filename, size in outputs:
        destination = assets_dir / filename
        if not create_app_pixmap(size).save(str(destination)):
            raise RuntimeError(f"아이콘 생성 실패: {destination}")

    app.quit()


if __name__ == "__main__":
    main()
