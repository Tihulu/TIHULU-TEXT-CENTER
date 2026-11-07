from pathlib import Path
import tempfile
import unittest
from satellite_center.desktop_shortcuts import belongs,choose,cleanup

def desktop(folder,name,label,command):
    f=folder/name
    f.write_text("[Desktop Entry]\nType=Application\nName="+label+"\nExec="+command+"\n",encoding="utf-8")
    return f

class ShortcutTests(unittest.TestCase):
    def test_system_keep_and_reversible_archive(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);apps=home/"applications";apps.mkdir()
            q=desktop(apps,"tihulu-satellite.desktop","TIHULU Satellite Center","/home/u/.local/bin/tihulu-satellite")
            w=desktop(apps,"tihulu-satellite-web.desktop","TIHULU Satellite Center WebUSB","/home/u/.local/bin/tihulu-satellite-web")
            p=desktop(apps,"chrome-id-Default.desktop","TIHULU Satellite Center (Local)","chromium --app-id=id")
            other=desktop(apps,"another.desktop","TIHULU Flight Radar","/usr/bin/tihulu-flight-radar")
            keep,remove,_=choose(apps,True)
            self.assertEqual(keep,[])
            self.assertEqual(set(remove),{q,w,p})
            self.assertFalse(belongs(other))
            backup=home/"backups"
            cleanup(applications=apps,backups=backup,system=True)
            self.assertTrue(all(x.exists() for x in [q,w,p,other]))
            cleanup(apply=True,applications=apps,backups=backup,system=True)
            self.assertTrue(other.exists())
            self.assertFalse(any(x.exists() for x in [q,w,p]))
            self.assertEqual(len(list(backup.rglob("*.desktop"))),3)
    def test_user_native_is_kept_when_deb_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            q=desktop(root,"tihulu-satellite.desktop","TIHULU Satellite Center","/home/u/.local/bin/tihulu-satellite")
            w=desktop(root,"chrome-id.desktop","TIHULU Satellite Center (Local)","chrome --app-id=id")
            keep,remove,_=choose(root,False)
            self.assertEqual(keep,[q]);self.assertEqual(remove,[w])
    def test_no_native_means_no_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=desktop(root,"chrome-id.desktop","TIHULU Satellite Center (Local)","chrome --app-id=id")
            keep,remove,_=choose(root,False)
            self.assertEqual(keep,[p]);self.assertEqual(remove,[])
