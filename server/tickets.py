"""Bounded in-memory upstream URL tickets for the single-worker player.

Only server-side playlist rewriting issues tickets. Visitors receive an opaque
reference rather than a provider URL or a visitor-editable base64 target.
"""
from collections import OrderedDict
from dataclasses import dataclass
import secrets
import threading
import time
from urllib.parse import urlsplit

@dataclass
class _Entry:
    url: str
    expires_at: float

class UrlTickets:
    def __init__(self, *, capacity=16384, ttl=1200, clock=time.monotonic):
        if not 1 <= capacity <= 65536 or not 0 < ttl <= 7200:
            raise ValueError('Choose bounded ticket capacity and lifetime.')
        self.capacity=capacity;self.ttl=ttl;self.clock=clock
        self._entries=OrderedDict();self._by_url={};self._lock=threading.Lock()

    def _remove(self, ticket):
        entry=self._entries.pop(ticket)
        if self._by_url.get(entry.url)==ticket:self._by_url.pop(entry.url,None)

    def issue(self,url):
        if not isinstance(url,str) or len(url)>8192:raise ValueError('Configure an HTTP stream URL.')
        parsed=urlsplit(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Configure an HTTP stream URL without embedded login credentials.')
        with self._lock:
            now=self.clock();existing=self._by_url.get(url)
            if existing and self._entries[existing].expires_at>now:
                self._entries[existing].expires_at=now+self.ttl
                self._entries.move_to_end(existing);return existing
            if existing:self._remove(existing)
            while self._entries and next(iter(self._entries.values())).expires_at<=now:
                self._remove(next(iter(self._entries)))
            while len(self._entries)>=self.capacity:self._remove(next(iter(self._entries)))
            ticket=secrets.token_urlsafe(24)
            self._entries[ticket]=_Entry(url,now+self.ttl);self._by_url[url]=ticket
            return ticket

    def resolve(self,ticket):
        if not isinstance(ticket,str) or len(ticket)>128:raise ValueError('Reload the channel playlist.')
        with self._lock:
            entry=self._entries.get(ticket)
            if entry is None:raise ValueError('Reload the channel playlist.')
            if entry.expires_at<=self.clock():self._remove(ticket);raise ValueError('Reload the channel playlist.')
            return entry.url
