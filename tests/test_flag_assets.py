import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FlagAssets(unittest.TestCase):
 def test_country_flags_are_bundled_and_checked(self):
  manifest={x['path']:x for x in json.loads((ROOT/'third-party-assets.json').read_text())['assets']}
  for code in ('mx','pe','co','ar','es','fr','sn','ci','de','gb','us'):
   path=f'server/assets/flags/{code}.svg';self.assertIn(path,manifest);self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),manifest[path]['sha256'])
 def test_africa_uses_native_globe_without_missing_asset(self):
  for path in ('web/index.html','server/web.py'):
   text=(ROOT/path).read_text();self.assertNotIn("AFR: 'afr'",text);self.assertIn("AFR: '🌍'",text);self.assertIn("cc === 'AFR' ? '🌍'",text)
if __name__=='__main__':unittest.main()
