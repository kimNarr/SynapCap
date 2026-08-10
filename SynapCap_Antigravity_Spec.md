# SynapCap - AI Usage HUD Widget Building Specification

This specification document is designed for **Antigravity AI** (or any AI coding assistant) to build the complete **SynapCap** application step by step.

---

## 1. Project Overview

- **Project Name**: SynapCap
- **Description**: A lightweight, cross-platform desktop HUD widget and system tray application for tracking real-time usage, limits, and quotas across multiple AI services (OpenAI Codex, Google Antigravity, Anthropic Claude, and custom providers).
- **Target Platforms**: Windows 10/11 & macOS (Intel & Apple Silicon)
- **Primary Tech Stack**: Python 3.10+, PySide6 (Qt for Python), `requests`

---

## 2. Key Requirements & Features

1. **Floating Frameless HUD Widget**:
   - Frameless, semi-transparent dark UI overlay (`#1E1E2E` Catppuccin Macchiato style palette).
   - Always-on-top toggleable window.
   - Smooth drag-and-drop repositioning anywhere on the screen.
   - Dynamic progress bars with color alerts (e.g., changes to warning color when usage > 80%).

2. **System Tray Integration**:
   - System tray / Menu bar icon on both Windows and macOS.
   - Context menu options: Show/Hide Widget, Refresh Now, Settings, Quit.

3. **Dynamic Provider Architecture**:
   - Abstract Base Class `BaseAIProvider` for easy model extensions.
   - External JSON configuration (`synapcap.json`) to add, enable/disable, or modify providers without changing code.
   - Multi-unit support (`%`, `$`, `k tokens`, `reqs`).

4. **Non-Blocking Background Worker**:
   - `QThread`-based async API polling loop so the UI never freezes or stutters.

---

## 3. Directory & File Structure

```
SynapCap/
├── main.py                    # Application Entry Point
├── synapcap.json              # Runtime Config File
├── requirements.txt           # Dependencies
├── config.py                  # Config loader and validator
├── workers/
│   └── usage_worker.py        # Background QThread for API updates
├── providers/
│   ├── __init__.py
│   ├── base.py                # Data models & Abstract Provider Class
│   ├── codex.py               # Codex Provider Implementation
│   ├── antigravity.py         # Google Antigravity Provider Implementation
│   ├── claude.py              # Anthropic Claude Provider Implementation
│   └── factory.py             # Dynamic Provider Loader from JSON
└── ui/
    ├── __init__.py
    ├── widget.py              # Floating HUD Widget Window
    └── tray.py                # System Tray Icon & Context Menu
```

---

## 4. Configuration Specification (`synapcap.json`)

```json
{
  "settings": {
    "refresh_interval_sec": 30,
    "always_on_top": true,
    "widget_width": 280,
    "theme": "dark"
  },
  "providers": [
    {
      "id": "codex",
      "name": "Codex",
      "type": "codex",
      "enabled": true,
      "api_key": "",
      "limit": 100,
      "unit": "%"
    },
    {
      "id": "antigravity",
      "name": "Antigravity",
      "type": "antigravity",
      "enabled": true,
      "auth_token": "",
      "limit": 100,
      "unit": "%"
    },
    {
      "id": "claude",
      "name": "Claude 3.7",
      "type": "claude",
      "enabled": true,
      "api_key": "",
      "limit": 50.0,
      "unit": "$"
    }
  ]
}
```

---

## 5. Component Implementations

### 5.1 Abstract Base & Data Model (`providers/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ModelUsage:
    provider_id: str
    provider_name: str
    model_name: str
    used: float
    limit: float
    unit: str  # "%", "$", "tokens", "reqs"

class BaseAIProvider(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.provider_id = config.get("id", "")
        self.name = config.get("name", "Unknown AI")

    @abstractmethod
    def fetch_usage(self) -> ModelUsage:
        pass
```

### 5.2 Concrete Providers (`providers/codex.py`, `providers/antigravity.py`, `providers/claude.py`)

_Each provider inherits from `BaseAIProvider` and implements `fetch_usage()`. If API keys are missing or invalid, fallback gracefully with error status._

### 5.3 Dynamic Provider Factory (`providers/factory.py`)

```python
from typing import List, Dict, Type
from .base import BaseAIProvider
from .codex import CodexProvider
from .antigravity import AntigravityProvider
from .claude import ClaudeProvider

PROVIDER_REGISTRY: Dict[str, Type[BaseAIProvider]] = {
    "codex": CodexProvider,
    "antigravity": AntigravityProvider,
    "claude": ClaudeProvider
}

def load_providers_from_config(config_data: dict) -> List[BaseAIProvider]:
    providers = []
    for p_cfg in config_data.get("providers", []):
        if not p_cfg.get("enabled", True):
            continue
        p_type = p_cfg.get("type", "").lower()
        if p_type in PROVIDER_REGISTRY:
            provider_cls = PROVIDER_REGISTRY[p_type]
            providers.append(provider_cls(p_cfg))
    return providers
```

### 5.4 Background Worker (`workers/usage_worker.py`)

```python
import time
from typing import List
from PySide6.QtCore import QThread, Signal
from providers.base import BaseAIProvider, ModelUsage

class UsageWorker(QThread):
    updated = Signal(list)

    def __init__(self, providers: List[BaseAIProvider], interval_sec: int = 30):
        super().__init__()
        self.providers = providers
        self.interval_sec = interval_sec
        self.is_running = True

    def run(self):
        while self.is_running:
            results = []
            for provider in self.providers:
                try:
                    results.append(provider.fetch_usage())
                except Exception as e:
                    print(f"[SynapCap] Error fetching {provider.name}: {e}")
            self.updated.emit(results)
            time.sleep(self.interval_sec)

    def stop(self):
        self.is_running = False
        self.wait()
```

### 5.5 HUD Widget UI (`ui/widget.py`)

```python
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame

class SynapCapWidget(QWidget):
    def __init__(self, config: dict, providers: list):
        super().__init__()
        self.config = config
        self.providers = providers
        self.old_pos = None
        self.model_ui_map = {}
        self.init_ui()

    def init_ui(self):
        # Window Flags for Floating HUD
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.config.get("settings", {}).get("always_on_top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(280)

        # Style & Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1E1E2E;
                border-radius: 12px;
                border: 1px solid #313244;
            }
            QLabel { color: #CDD6F4; font-family: sans-serif; }
            QProgressBar {
                border: none;
                background-color: #313244;
                height: 8px;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #89B4FA;
                border-radius: 4px;
            }
        """)

        card_layout = QVBoxLayout(card)
        title_lbl = QLabel("SynapCap")
        title_lbl.setStyleSheet("font-weight: bold; color: #A6ADC8; font-size: 12px;")
        card_layout.addWidget(title_lbl)

        for p in self.providers:
            p_box = QVBoxLayout()
            header_layout = QHBoxLayout()

            name_lbl = QLabel(f"<b>{p.name}</b>")
            val_lbl = QLabel("...")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

            header_layout.addWidget(name_lbl)
            header_layout.addWidget(val_lbl)

            pbar = QProgressBar()
            pbar.setTextVisible(False)
            pbar.setRange(0, 100)

            p_box.addLayout(header_layout)
            p_box.addWidget(pbar)
            card_layout.addLayout(p_box)

            self.model_ui_map[p.provider_id] = (val_lbl, pbar)

        layout.addWidget(card)

    def update_data(self, usage_list: list):
        for usage in usage_list:
            if usage.provider_id in self.model_ui_map:
                val_lbl, pbar = self.model_ui_map[usage.provider_id]
                pct = int((usage.used / usage.limit) * 100) if usage.limit > 0 else 0

                if usage.unit == "$":
                    text = f"${usage.used:.2f} / ${usage.limit:.2f}"
                elif usage.unit == "%":
                    text = f"{usage.used:.0f}%"
                else:
                    text = f"{usage.used:.0f} {usage.unit}"

                val_lbl.setText(text)
                pbar.setValue(min(pct, 100))

                if pct >= 80:
                    pbar.setStyleSheet("QProgressBar::chunk { background-color: #F38BA8; }")
                else:
                    pbar.setStyleSheet("QProgressBar::chunk { background-color: #89B4FA; }")

    # Drag and Drop Window
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
```

---

## 6. Execution Instructions for Antigravity AI

When Antigravity AI processes this specification, perform the following actions:

1. **Create the Project Directory Structure**: Generate all folders and empty `__init__.py` files.
2. **Implement Modules**: Create `config.py`, `providers/`, `workers/`, `ui/`, and `main.py`.
3. **Generate Dependencies File (`requirements.txt`)**:
   ```text
   PySide6>=6.5.0
   requests>=2.28.0
   ```
4. **Platform Testing**: Verify that `Qt.WindowType.FramelessWindowHint` and drag operations function smoothly on both macOS and Windows.
5. **Run Script**: Start `python main.py` to launch the SynapCap HUD Widget.
