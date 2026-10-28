import base64,concurrent.futures,unittest
from server.tickets import UrlTickets

class TicketTests(unittest.TestCase):
 def test_upstream_is_opaque_and_roundtrips(self):
  registry=UrlTickets();upstream='https://stream.example.invalid/segment.ts?access=synthetic_fixture';ticket=registry.issue(upstream)
  self.assertNotIn('synthetic_fixture',ticket);self.assertNotIn('http',ticket);self.assertEqual(registry.resolve(ticket),upstream)
 def test_visitor_base64_is_rejected(self):
  token=base64.urlsafe_b64encode(b'http://127.0.0.1/private').decode().rstrip('=')
  with self.assertRaises(ValueError):UrlTickets().resolve(token)
 def test_expiry_uses_clock_barrier(self):
  now=[10];r=UrlTickets(ttl=5,clock=lambda:now[0]);token=r.issue('https://stream.example.invalid/a');now[0]=15
  with self.assertRaises(ValueError):r.resolve(token)
 def test_capacity_is_bounded(self):
  r=UrlTickets(capacity=2);old=r.issue('https://stream.example.invalid/a');r.issue('https://stream.example.invalid/b');r.issue('https://stream.example.invalid/c')
  with self.assertRaises(ValueError):r.resolve(old)
  self.assertEqual(len(r._entries),2)
 def test_repeated_manifest_reuses_ticket(self):
  r=UrlTickets();self.assertEqual(r.issue('https://stream.example.invalid/a'),r.issue('https://stream.example.invalid/a'))
 def test_userinfo_and_other_protocols_rejected(self):
  for value in ['file:///etc/passwd','data:text/plain,test','ftp://stream.example.invalid/a','https://user:synthetic@stream.example.invalid/a']:
   with self.assertRaises(ValueError):UrlTickets().issue(value)
 def test_tampering_rejected(self):
  r=UrlTickets();token=r.issue('https://stream.example.invalid/a')
  with self.assertRaises(ValueError):r.resolve(token+'x')
 def test_concurrency_has_one_ticket_per_url(self):
  r=UrlTickets()
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:tokens=list(pool.map(lambda _:r.issue('https://stream.example.invalid/a'),range(100)))
  self.assertEqual(len(set(tokens)),1)

if __name__=='__main__':unittest.main()
