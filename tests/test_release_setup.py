import contextlib,importlib.util,io,json,os,re,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runtime',ROOT/'tools/runtime-env.py');runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class ReleaseSetupTests(unittest.TestCase):
 def test_private_values_roundtrip_and_doctor_masks(self):
  with tempfile.TemporaryDirectory() as directory:
   parent=Path(directory);parent.chmod(0o700);file=parent/'runtime.env';value='authored fixture with trailing space '
   runtime.write_config(file,{'WEBSHARE_PROXY_PASS':value});self.assertEqual(runtime.read_config(file)['WEBSHARE_PROXY_PASS'],value)
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(runtime.main(['doctor','--file',str(file)]),0)
   self.assertNotIn(value,out.getvalue());self.assertTrue(json.loads(out.getvalue())['fields']['WEBSHARE_PROXY_PASS'])
 def test_inherited_accounts_and_enable_flag_are_removed(self):
  env=runtime.child_env({}, {'WEBSHARE_PROXY_USER':'fixture','WEBSHARE_PROXY_PASS':'fixture','CANCHA_ENABLE_PROXY':'1','AWS_PROFILE':'fixture','PATH':'/bin'})
  for key in ['WEBSHARE_PROXY_USER','WEBSHARE_PROXY_PASS','CANCHA_ENABLE_PROXY','AWS_PROFILE']:self.assertNotIn(key,env)
  self.assertEqual(env['PATH'],'/bin')
 def test_private_file_guards(self):
  with tempfile.TemporaryDirectory() as directory:
   parent=Path(directory);parent.chmod(0o700);file=parent/'runtime.env';runtime.write_config(file,{})
   link=parent/'linked';link.symlink_to(file)
   with self.assertRaises(runtime.ConfigError):runtime.private_path(str(link))
   file.chmod(0o644)
   with self.assertRaises(runtime.ConfigError):runtime.private_path(str(file))
 def test_signing_inputs_are_references_and_shell_parses(self):
  paths=list((ROOT/'scripts').glob('*.sh'))+list((ROOT/'android').rglob('*.gradle.kts'))
  for path in paths:
   text=path.read_text()
   unsafe=bool(re.search(r'--(?:ks|key)-pass\s+pass:',text) or re.search(r'(?:storePassword|keyPassword)\s*=\s*"[^"\n]+"',text))
   self.assertFalse(unsafe,'Signing input must remain recipient-owned: '+str(path.relative_to(ROOT)))
   if path.suffix=='.sh':self.assertEqual(subprocess.run(['bash','-n',str(path)],capture_output=True).returncode,0)
 def test_private_signer_is_excluded(self):
  self.assertFalse(any(p.suffix in {'.jks','.keystore','.p12','.pem'} for p in ROOT.rglob('*') if p.is_file()))

if __name__=='__main__':unittest.main()
