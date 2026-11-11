"""Save verifiable Robot36 PNG + JSON evidence from a real PCM WAV.

Robot36 is an SSTV radio modulation, not an image file type. Decoded pixels
are saved as portable PNG, with the original WAV and source metadata kept.
No PNG is emitted unless the decoder validates repeated line syncs.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import uuid

from .sstv_series35 import extract_robot36_wav

def decode_robot36_to_archive(source_wav,archive, *,
                              compute_mode="auto",compute_targets=None,
                              max_images=12):
    original=Path(source_wav).expanduser()
    root=Path(archive).expanduser()
    root.mkdir(parents=True,exist_ok=True)
    result=extract_robot36_wav(
        original,max_images=max_images,compute_mode=compute_mode,
        compute_targets=compute_targets,output_dir=root)
    paths=[root/item["file"] for item in result.get("images",[])]
    for image in paths:
        if not image.is_file() or image.stat().st_size<32 or (
            image.open("rb").read(8)!=b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Decoder did not produce a valid on-disk PNG")
    result["actual_source_wav"]=str(original.resolve())
    result["actual_png_paths"]=[str(p.resolve()) for p in paths]
    result["output_image_format"]="PNG (320×240 image; Robot36 is radio mode)"
    result["source_not_authenticated"]=True
    result["raw_iq_included"]=False
    result["output_status"] = (
        "saved_synchronized_png_candidates" if paths else
        "no_png_saved_without_valid_robot36_sync")
    stem=re.sub(r"[^A-Za-z0-9_-]+","_",original.stem)[:65].strip("_") or "radio_audio"
    name=stem+"_robot36_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name+="_"+uuid.uuid4().hex[:8]+".json"
    report=root/name
    # Exclusive create: never replace another decoded or imported result.
    with report.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,ensure_ascii=False,default=str)
    result["saved_report_path"]=str(report.resolve())
    return result
