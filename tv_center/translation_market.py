"""Optional higher-capacity local multilingual NLLB translator.

This model is ~2.5 GB, licensed CC-BY-NC-4.0 (non-commercial); the model
license is NOT inherited from the GPL code. The user must confirm the
download and license. This is an alternative to smaller Argos packages,
not claimed faster, universally more accurate, or compatible with any NPU.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

MODEL_ID = "facebook/nllb-200-distilled-600M"
MODEL_REVISION = "a3e77be725cf30383f1faeb8d2f0b0ea98ac554e"
LICENSE = "CC-BY-NC-4.0 (non-commercial use)"
LANG = {"de":"deu_Latn","en":"eng_Latn","tr":"tur_Latn"}


class TranslationModelMarket:
    def __init__(self, root=None):
        if root is None:
            from .ai_settings import AISettings
            selected = AISettings().values.get("model_dir", "")
            root = (Path(selected) / "translator-models" if selected else
                    Path.home()/".local/share/tihulu-tv-center/translator-models")
        self.root=Path(root).expanduser()
        self.model=self.root/"nllb-600m"
        self.marker=self.model/".tihulu-nllb-ready"

    def status(self):
        return {"installed":self.marker.is_file() and
                (self.model/"model.safetensors").is_file() and
                (self.model/"config.json").is_file(),
                "path":str(self.model),"name":"NLLB-200 distilled 600M",
                "license":LICENSE,"approx_disk_gb":2.5,
                "minimum_ram_gb_recommended":6,
                "runtime":"local Transformers PyTorch (CPU or detected CUDA)"}

    def install(self):
        if os.geteuid()==0:
            raise RuntimeError("Do not install translation models as root")
        from .runtime import AIRuntime
        runtime=AIRuntime()
        if not runtime.status()["installed"]:
            runtime.install_argos()
        python=runtime.status()["python"]
        self.root.mkdir(parents=True,exist_ok=True)
        if self.root.is_symlink() or self.root.resolve() == Path("/"):
            raise RuntimeError("Refusing unsafe translator storage path")
        if self.model.resolve().parent != self.root.resolve():
            raise RuntimeError("Unsafe nested translator model path")
        if self.model.is_symlink():
            raise RuntimeError("Refusing symlink model directory")
        packages=["transformers>=4.44,<5","torch>=2.7","sentencepiece",
                  "huggingface_hub>=0.28,<1","safetensors"]
        result=subprocess.run([python,"-m","pip","install",
           "--disable-pip-version-check",*packages],
           stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
           stderr=subprocess.PIPE,timeout=2400,check=False)
        if result.returncode:
            raise RuntimeError("NLLB dependencies failed: " +
                result.stderr.decode("utf-8","replace")[-500:])
        env=os.environ.copy()
        root=str(Path(__file__).resolve().parent.parent)
        env["PYTHONPATH"]=root+os.pathsep+env.get("PYTHONPATH","")
        outcome=subprocess.run([python,"-m","tv_center.translation_market","--download"],
            env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=2400,check=False)
        if outcome.returncode:
            raise RuntimeError("NLLB model download failed: " +
                outcome.stderr.decode("utf-8","replace")[-600:])
        if not self.status()["installed"]:
            raise RuntimeError("NLLB safetensors or tokenizer files missing")
        return "NLLB translator model installed locally; choose it in AI Market and Save"

    def _download(self):
        from huggingface_hub import snapshot_download
        self.model.mkdir(parents=True,exist_ok=True)
        snapshot_download(repo_id=MODEL_ID,revision=MODEL_REVISION,
            allow_patterns=["*.safetensors","*.json","*.model","*.txt"],
            local_dir=str(self.model),max_workers=2)
        for name in ("model.safetensors","config.json","tokenizer_config.json"):
            if not (self.model/name).is_file():
                raise RuntimeError("Expected NLLB model file missing: "+name)
        self.marker.write_text(
            f"TIHULU managed optional NLLB; revision={MODEL_REVISION}\n",
            encoding="utf-8")

    def remove(self):
        if self.model.is_symlink() or not self.marker.is_file():
            raise RuntimeError("Refusing to remove unverified translator model")
        if self.model.resolve().parent != self.root.resolve() or self.root.resolve() == Path("/"):
            raise RuntimeError("Translator model storage path unsafe; removal refused")
        shutil.rmtree(self.model)
        return "Managed NLLB translator removed; Argos packages preserved"


from functools import lru_cache

@lru_cache(maxsize=1)
def _load_nllb():
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    location=TranslationModelMarket()
    if not location.status()["installed"]:
        raise RuntimeError("NLLB translation weights not installed")
    tokenizer=AutoTokenizer.from_pretrained(
        str(location.model),local_files_only=True,trust_remote_code=False)
    model=AutoModelForSeq2SeqLM.from_pretrained(
        str(location.model),local_files_only=True,
        use_safetensors=True,trust_remote_code=False)
    model.eval()
    device="cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return model,tokenizer,device,torch


def run_nllb(text,source,target):
    """Local model cached once per persistent worker, never per sentence."""
    if source not in LANG or target not in LANG:
        raise ValueError("Unsupported language")
    model,tokenizer,device,torch=_load_nllb()
    tokenizer.src_lang=LANG[source]
    data=tokenizer(text[:1600],return_tensors="pt",truncation=True,
                   max_length=256).to(device)
    with torch.inference_mode():
        output=model.generate(**data,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(LANG[target]),
            max_new_tokens=180,num_beams=3)
    return tokenizer.batch_decode(output,skip_special_tokens=True)[0].strip()


def main():
    if len(sys.argv)==2 and sys.argv[1]=="--download":
        TranslationModelMarket()._download()
        print(json.dumps({"status":"installed","model":MODEL_ID}))
        return 0
    raise SystemExit("Only --download allowed")

if __name__=="__main__":
    raise SystemExit(main())
