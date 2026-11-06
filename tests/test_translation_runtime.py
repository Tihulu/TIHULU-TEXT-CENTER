import unittest
from textcenter.translation_runtime import select_translation_device
class TranslationDeviceTests(unittest.TestCase):
    def setUp(self):
        self.info={"runtimes":{"argostranslate":True},"devices":[
            {"id":"cpu","kind":"cpu","name":"Test CPU"},
            {"id":"cuda:0","kind":"gpu","name":"Test RTX"},
            {"id":"hailo:hailo0","kind":"npu","name":"Hailo NPU"},
        ]}
    def test_all_backends_manual_and_auto(self):
        self.assertEqual(select_translation_device("cpu",self.info)["name"],"Test CPU")
        self.assertEqual(select_translation_device("auto",self.info,check_cuda=lambda _:False)["id"],"cpu")
        self.assertEqual(select_translation_device("auto",self.info,check_cuda=lambda _:True)["id"],"cuda:0")
        self.assertEqual(select_translation_device("cuda:0",self.info,check_cuda=lambda _:True)["name"],"Test RTX")
        with self.assertRaises(ValueError):
            select_translation_device("hailo:hailo0",self.info,check_cuda=lambda _:True)
        with self.assertRaises(ValueError):
            select_translation_device("cuda:9",self.info,check_cuda=lambda _:True)
        self.info["runtimes"]["argostranslate"]=False
        with self.assertRaises(ValueError):
            select_translation_device("cpu",self.info)


if __name__=="__main__":
    unittest.main()
