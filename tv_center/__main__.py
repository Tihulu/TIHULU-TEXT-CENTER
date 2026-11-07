"""Launch native TV Center or inspect its dependencies without touching hardware."""
import json
import sys
from .core import receiver_status, discover_channels
from .satellite import SATELLITES, satellite_hardware_note
from .ai_settings import AISettings
from .whisper_engine import WhisperRuntime
from .runtime import AIRuntime

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "ai-market":
        from .settings_ui import open_ai_settings
        from PyQt5.QtWidgets import QApplication
        import os
        if os.environ.get("WAYLAND_DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
        app = QApplication.instance() or QApplication(["TIHULU Whisper / Translator Market"])
        ai = AISettings()
        open_ai_settings(None, ai)
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "kaffeine-captions":
        from kaffeine_next.captions_overlay import main as captions_main
        return captions_main(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "ai":
        from .ai_provision import main as ai_main
        return ai_main(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "doctor":
        ai = AISettings()
        print(json.dumps({
            "receiver": receiver_status(),
            "channels": [{"name": c.name, "frequency": c.frequency,
                          "service_id": c.service_id} for c in discover_channels()],
            "satellite_profiles": SATELLITES,
            "satellite_hardware_note": satellite_hardware_note(),
            "satellite_hardware_verified": False,
            "optional_ai": {
                "asr_enabled": ai.values["asr_enabled"],
                "translation_enabled": ai.values["translation_enabled"],
                "requested_backend": ai.values["backend"],
                "whisper_cpu_engine_installed": WhisperRuntime().ready(),
                "argos_runtime": AIRuntime().status()["installed"],
                "starter_bundle": __import__("tv_center.ai_provision", fromlist=["StarterAI"]).StarterAI(ai).status()
            }
        }, indent=2, ensure_ascii=False))
        return 0
    from .desktop import main as desktop
    return desktop()

if __name__ == "__main__":
    raise SystemExit(main())
