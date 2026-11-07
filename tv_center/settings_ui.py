"""Optional TV AI engine/settings marketplace. No downloads on app startup."""
from __future__ import annotations
import queue
import threading
from pathlib import Path

def open_ai_settings(parent, ai, after_save=None):
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
        QFormLayout, QCheckBox, QComboBox, QLabel, QListWidget, QPushButton,
        QFileDialog, QMessageBox, QLineEdit)

    from .model_market import (CATALOG, ModelLibrary, ModelError,
        argos_available_pairs, argos_installed_pairs, argos_install, argos_remove)
    from textcenter.compute import detect_devices, choose_backend

    class Manager(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle("Settings · Optional ASR & Translation Model Market")
            self.resize(820, 700)
            self.ai = ai
            self.work = queue.Queue()
            self.running = False
            self.library = ModelLibrary(ai.values["model_dir"] or None)
            root = QVBoxLayout(self)
            self.info = QLabel("All models are optional. Downloads occur only after you choose and confirm. "
                               "No AI processing runs while subtitles are off.")
            self.info.setWordWrap(True)
            root.addWidget(self.info)

            settings = QGroupBox("AI features & compute backend")
            root.addWidget(settings)
            form = QFormLayout(settings)
            self.asr = QCheckBox("Enable offline live speech transcription")
            self.asr.setChecked(ai.values["asr_enabled"])
            form.addRow(self.asr)
            self.translator = QCheckBox("Enable offline translated subtitles")
            self.translator.setChecked(ai.values["translation_enabled"])
            form.addRow(self.translator)
            self.backend = QComboBox()
            self.backend.addItems(["auto", "cpu", "gpu", "npu"])
            self.backend.setCurrentText(ai.values["backend"])
            form.addRow("Inference engine", self.backend)
            self.compute = QLabel("")
            self.compute.setWordWrap(True)
            form.addRow("Detected hardware", self.compute)
            refresh_compute = QPushButton("Refresh CPU / GPU / NPU readiness")
            refresh_compute.clicked.connect(self.inspect_compute)
            form.addRow(refresh_compute)
            self.model_path = QLineEdit(ai.values["model_path"])
            self.model_path.setPlaceholderText("No active Whisper model selected")
            form.addRow("Active model (CPU GGML or runtime-specific)", self.model_path)

            models = QGroupBox("Whisper model market · multilingual DE / EN / TR")
            root.addWidget(models)
            models_layout = QVBoxLayout(models)
            self.models = QListWidget()
            self.models.setMaximumHeight(128)
            models_layout.addWidget(self.models)
            line = QHBoxLayout()
            self.download = QPushButton("Download & install selected")
            self.download.clicked.connect(self.download_model)
            self.remove = QPushButton("Delete selected installed model")
            self.remove.clicked.connect(self.remove_model)
            self.choose = QPushButton("Use selected")
            self.choose.clicked.connect(self.use_model)
            for b in (self.download, self.remove, self.choose): line.addWidget(b)
            models_layout.addLayout(line)
            line2 = QHBoxLayout()
            browse = QPushButton("Choose an existing GGML model…")
            browse.clicked.connect(self.import_existing)
            storage = QPushButton("Choose storage folder / external SSD…")
            storage.clicked.connect(self.choose_storage)
            line2.addWidget(browse)
            line2.addWidget(storage)
            models_layout.addLayout(line2)
            self.storage_label = QLabel("")
            self.storage_label.setWordWrap(True)
            models_layout.addWidget(self.storage_label)

            langs = QGroupBox("Argos Translate language packs · download / remove")
            root.addWidget(langs)
            trans_layout = QVBoxLayout(langs)
            trans_row = QHBoxLayout()
            self.source = QComboBox(); self.source.addItems(["de", "en", "tr"])
            self.target = QComboBox(); self.target.addItems(["tr", "de", "en"])
            trans_row.addWidget(QLabel("From")); trans_row.addWidget(self.source)
            trans_row.addWidget(QLabel("To")); trans_row.addWidget(self.target)
            trans_layout.addLayout(trans_row)
            self.available = QLabel("Catalog not refreshed. Optional argostranslate package required.")
            self.available.setWordWrap(True)
            trans_layout.addWidget(self.available)
            controls = QHBoxLayout()
            update = QPushButton("Refresh Argos catalog (internet)")
            update.clicked.connect(self.refresh_argos_catalog)
            install = QPushButton("Install selected pair")
            install.clicked.connect(self.install_argos)
            remove = QPushButton("Uninstall selected pair")
            remove.clicked.connect(self.uninstall_argos)
            for b in (update, install, remove): controls.addWidget(b)
            trans_layout.addLayout(controls)
            self.pairs = QLabel("Installed pairs: not inspected")
            trans_layout.addWidget(self.pairs)

            self.feedback = QLabel("No active downloads.")
            self.feedback.setWordWrap(True)
            root.addWidget(self.feedback)
            finish = QHBoxLayout()
            save = QPushButton("Save settings")
            save.clicked.connect(self.save)
            cancel = QPushButton("Close")
            cancel.clicked.connect(self.reject)
            finish.addWidget(save)
            finish.addWidget(cancel)
            root.addLayout(finish)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.process_events)
            self.timer.start(250)
            self.populate_models()
            self.inspect_compute()
            self.inspect_argos()

        def selected_model(self):
            selected = self.models.currentItem()
            return selected.data(Qt.UserRole) if selected else None

        def populate_models(self):
            old = self.selected_model()
            self.models.clear()
            from PyQt5.QtWidgets import QListWidgetItem
            for model in self.library.installed():
                key = model["id"]
                state = "INSTALLED" if model["installed"] else "not installed"
                item = QListWidgetItem(f"{model['name']} · approx {model['size_mb']} MB · {state}")
                item.setData(Qt.UserRole, key)
                self.models.addItem(item)
                if key == old:
                    self.models.setCurrentItem(item)
            self.storage_label.setText("Managed models: " + str(self.library.root))

        def inspect_compute(self):
            try:
                p = detect_devices()
                parts = [x["id"].upper() + " " + ("detected" if x["detected"] else "absent")
                         for x in p["devices"]]
                ready = [key.upper() for key in ("cpu", "gpu", "npu")
                         if p["speech"].get("ready_" + key)]
                self.compute.setText(" | ".join(parts) + " · Ready speech runtimes: " +
                                     (", ".join(ready) if ready else "none"))
            except (ImportError, OSError, ValueError) as exc:
                self.compute.setText("Hardware inference discovery failed: " + str(exc)[:140])

        def inspect_argos(self):
            try:
                pairs = argos_installed_pairs()
                self.pairs.setText("Installed Argos: " + (", ".join(
                    p["source"] + "→" + p["target"] for p in pairs) if pairs else "none"))
            except (ImportError, OSError, ValueError) as exc:
                self.pairs.setText("Argos runtime unavailable: " + str(exc)[:100])

        def begin(self, label, fn):
            if self.running:
                QMessageBox.information(self, "Model operation", "A model operation is already running")
                return
            self.running = True
            self.feedback.setText(label)
            def worker():
                try:
                    result = fn()
                    self.work.put(("done", result))
                except Exception as exc:
                    self.work.put(("error", str(exc)[:250]))
            threading.Thread(target=worker, daemon=True, name="tihulu-model-manager").start()

        def process_events(self):
            for _ in range(3):
                try: kind, data = self.work.get_nowait()
                except queue.Empty: break
                if kind == "progress":
                    self.feedback.setText(str(data))
                elif kind == "done":
                    self.running = False
                    self.feedback.setText("Completed: " + str(data))
                    self.populate_models()
                    self.inspect_argos()
                else:
                    self.running = False
                    self.feedback.setText("Failed: " + str(data))

        def download_model(self):
            key = self.selected_model()
            if key not in CATALOG: return
            desc = CATALOG[key]
            if QMessageBox.question(self, "Download model",
                  f"Download {desc['name']} (~{desc['size_mb']} MB) to {self.library.root}?\n"
                  "Model file is verified using SHA-256. No background download.") != QMessageBox.Yes:
                return
            def work():
                path = self.library.download(key, progress=lambda n, limit: self.work.put(
                    ("progress", f"Downloading {key}: {n/(1024*1024):.0f} MiB received")))
                return "Installed model " + str(path)
            self.begin("Downloading verified model…", work)

        def use_model(self):
            key = self.selected_model()
            if key in CATALOG and self.library._path(key).is_file():
                self.model_path.setText(str(self.library._path(key)))
                self.feedback.setText("Model selected. Click Save settings to activate.")
            else:
                self.feedback.setText("Install selected model first.")

        def remove_model(self):
            key = self.selected_model()
            if key not in CATALOG: return
            path = self.library._path(key)
            if not path.is_file(): return
            if QMessageBox.question(self, "Delete managed model",
                "Permanently delete " + str(path) + "?") != QMessageBox.Yes:
                return
            if self.model_path.text() == str(path):
                self.model_path.clear()
            self.library.remove(key)
            self.populate_models()
            self.feedback.setText("Managed model deleted; Save settings to update selection.")

        def import_existing(self):
            path, _ = QFileDialog.getOpenFileName(self, "Use locally installed Whisper GGML model",
                                                  str(Path.home()), "GGML model (*.bin);;All files (*)")
            if path:
                self.model_path.setText(path)
                self.feedback.setText("External model selected (not owned or deleted by this app).")

        def choose_storage(self):
            folder = QFileDialog.getExistingDirectory(self, "Choose app-managed model directory or SSD",
                                                       str(self.library.root))
            if folder:
                self.library = ModelLibrary(folder)
                self.populate_models()
                self.feedback.setText("Storage folder selected; current models remain in their original location.")

        def refresh_argos_catalog(self):
            self.begin("Refreshing official Argos language package catalog…",
                       lambda: "Available pairs: " + ", ".join(
                           x["source"] + "→" + x["target"]
                           for x in argos_available_pairs(refresh=True)))

        def install_argos(self):
            a, b = self.source.currentText(), self.target.currentText()
            if a == b: return
            if QMessageBox.question(self, "Download language pack",
                  f"Download and install Argos {a} → {b} from its configured package index?") != QMessageBox.Yes:
                return
            self.begin("Installing Argos " + a + " → " + b, lambda: argos_install(a, b))

        def uninstall_argos(self):
            a, b = self.source.currentText(), self.target.currentText()
            if a == b: return
            if QMessageBox.question(self, "Uninstall language pack",
                  f"Uninstall local Argos {a} → {b}?") != QMessageBox.Yes:
                return
            self.begin("Removing Argos language pack", lambda: argos_remove(a, b))

        def save(self):
            if self.running:
                QMessageBox.warning(self, "Model operation running", "Finish the active install/removal first.")
                return
            try:
                ai.update({
                    "asr_enabled": self.asr.isChecked(),
                    "translation_enabled": self.translator.isChecked(),
                    "backend": self.backend.currentText(),
                    "model_path": self.model_path.text().strip(),
                    "model_dir": str(self.library.root)
                })
                ai.configure_environment()
                if after_save: after_save()
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Settings failed", str(exc))
                return
            self.accept()

    return Manager().exec_()
