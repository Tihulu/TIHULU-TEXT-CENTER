"""Reversible cleanup of old TIHULU Satellite Center .desktop icons."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess

def value(path,field):
    try: data=path.read_text(encoding="utf-8",errors="replace")
    except OSError: return ""
    match=re.search("^"+re.escape(field)+r"=(.*)$",data,re.M)
    return match.group(1).strip() if match else ""

def belongs(path):
    if path.suffix!=".desktop" or path.is_symlink() or not path.is_file():
        return False
    name=value(path,"Name").lower()
    command=value(path,"Exec").lower()
    return ("tihulu" in name and "satellite" in name
            and ("satellite" in command or "--app-id=" in command))

def native_local(path):
    command=value(path,"Exec").lower()
    return (path.name=="tihulu-satellite.desktop" and belongs(path)
            and "/tihulu-satellite" in command and "-web" not in command
            and "serve" not in command and "--app=" not in command)

def installed_native(entry=Path("/usr/share/applications/tihulu-satellite-center.desktop")):
    if not entry.is_file() or entry.is_symlink() or value(entry,"Exec")!="tihulu-satellite-center desktop":
        return False
    try:
        proc=subprocess.run(
            ["dpkg-query","-W","-f=$"+"{Status}","tihulu-satellite-center"],
            capture_output=True,text=True,timeout=5,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return False
    return proc.returncode==0 and proc.stdout.strip()=="install ok installed"

def choose(applications,system):
    if not applications.is_dir():return [],[],"No user-local shortcuts found."
    found=sorted((p for p in applications.glob("*.desktop") if belongs(p)),key=lambda p:p.name)
    if system:
        return [],found,"Keep installed system Qt application shortcut."
    desktop=next((p for p in found if native_local(p)),None)
    if desktop:
        return [desktop],[p for p in found if p!=desktop],"Keep single user-local native Qt app."
    return found,[],"Native Qt app not verified; no icons will be removed."

def cleanup(*,apply=False,applications=None,backups=None,system=None):
    base=Path(os.environ.get("XDG_DATA_HOME",str(Path.home()/".local/share")))
    directory=Path(applications) if applications is not None else base/"applications"
    backup=Path(backups) if backups is not None else base/"tihulu-satellite-center"/"shortcut-backups"
    keep,remove,note=choose(directory,installed_native() if system is None else system)
    print(note)
    for path in keep:print("KEEP",path)
    for path in remove:print("ARCHIVE" if apply else "WOULD ARCHIVE",path)
    if not remove:
        print("Nothing to clean.");return 0
    if not apply:
        print("Dry run only. Add --apply to back up redundant shortcuts.");return 0
    dest=backup/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+str(os.getpid()))
    dest.mkdir(mode=0o700,parents=True,exist_ok=False)
    for path in remove:
        if path.parent.resolve()!=directory.resolve() or not belongs(path):
            raise RuntimeError("Shortcut changed; stopping safely")
        shutil.move(str(path),str(dest/path.name))
    print("Archived",len(remove),"user shortcuts to",dest)
    print("No browser data, recordings, programs, services or system .desktop files touched.")
    return 0

def main(argv=None):
    p=argparse.ArgumentParser(description="Keep Qt Satellite Center; archive old PWA/Local menu entries.")
    p.add_argument("--apply",action="store_true")
    return cleanup(apply=p.parse_args(argv).apply)

if __name__=="__main__":raise SystemExit(main())
