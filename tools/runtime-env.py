#!/usr/bin/env python3
"""Recipient-owned private runtime configuration. Standard library; zero API calls."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {'player': ('CANCHA_CATALOG', 'CANCHA_STATE_DIR', 'CANCHA_LOGO_DIR', 'CANCHA_HOST', 'CANCHA_PORT', 'CANCHA_DVR_WINDOW_S', 'CANCHA_DVR_IDLE_STOP_S', 'CANCHA_MAX_TRANSCODE'), 'proxy': ('CANCHA_ENABLE_PROXY', 'WEBSHARE_PROXY_HOST', 'WEBSHARE_PROXY_PORT', 'WEBSHARE_PROXY_USER', 'WEBSHARE_PROXY_PASS'), 'signing': ('CANCHA_ANDROID_KEYSTORE', 'CANCHA_ANDROID_STORE_PASSWORD', 'CANCHA_ANDROID_KEY_ALIAS', 'CANCHA_ANDROID_KEY_PASSWORD'), 'deployment': ('ANDROID_HOME', 'CANCHA_APK_PATH', 'CANCHA_DEPLOY_HOST', 'CANCHA_DEPLOY_DIR', 'CANCHA_APK_PUBLIC_URL')}
ALLOWED = {name for group in GROUPS.values() for name in group}
SENSITIVE = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|DSN|DATABASE_URL)", re.I)


class ConfigError(ValueError):
    pass


def private_path(raw: str, *, create: bool = False) -> Path:
    p = Path(raw)
    if not p.is_absolute() or ROOT == p or ROOT in p.parents:
        raise ConfigError("Choose an absolute private file outside the checkout.")
    for ancestor in [p, *p.parents]:
        if ancestor.is_symlink():
            raise ConfigError("Private configuration uses ordinary files and directories.")
    if create:
        p.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not p.parent.is_dir() or stat.S_IMODE(p.parent.stat().st_mode) & 0o077:
        raise ConfigError("The private parent directory needs mode 0700.")
    if p.exists():
        info = p.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise ConfigError("The private file needs mode 0600 and one ordinary file link.")
    return p


def read_config(path: Path) -> dict[str, str]:
    result = {}
    if not path.exists():
        return result
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if not sep or name not in ALLOWED or "\x00" in value:
            raise ConfigError(f"Unsupported configuration field on line {number}.")
        if name in result:
            raise ConfigError(f"Repeated configuration field on line {number}.")
        result[name] = value
    return result


def write_config(path: Path, values: dict[str, str]) -> None:
    data = "".join(name + "=" + values[name] + "\n" for name in sorted(values))
    fd, tmp = tempfile.mkstemp(prefix=".runtime-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def child_env(values: dict[str, str], inherited: dict[str, str]) -> dict[str, str]:
    # The selected recipient file owns provider access; cloud home profiles stay out.
    env = {name: value for name, value in inherited.items()
           if name not in ALLOWED and not SENSITIVE.search(name)
           and not name.startswith(("AWS_", "GOOGLE_", "GEMINI_", "CASAFARI_", "NEXT_PUBLIC_", "CANCHA_", "WEBSHARE_", "ELEVENLABS_", "SUPABASE_", "STRIPE_", "SCRAPFLY_", "WHATSAPP_", "RESEND_"))}
    env.update({
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_CONFIG_FILE": os.devnull,
        "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
        "GCE_METADATA_HOST": "127.0.0.1:9",
        "GOOGLE_APPLICATION_CREDENTIALS": "/recipient-google-credentials-not-configured",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    env.update({name: value for name, value in values.items() if value})
    if values.get("GOOGLE_CLOUD_PROJECT_ID"):
        env["GOOGLE_CLOUD_PROJECT"] = values["GOOGLE_CLOUD_PROJECT_ID"]
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "doctor", "run"))
    parser.add_argument("--file", required=True)
    parser.add_argument("--capability", choices=GROUPS)
    args, command = parser.parse_known_args(argv)
    try:
        path = private_path(args.file, create=args.action == "configure")
        values = read_config(path)
        if args.action == "configure":
            if command or not args.capability or not sys.stdin.isatty():
                raise ConfigError("Configure needs a capability and a private interactive terminal.")
            for name in GROUPS[args.capability]:
                value = getpass.getpass(name + " (hidden; Enter keeps current): ")
                if "\n" in value or "\r" in value or "\x00" in value:
                    raise ConfigError("Use one value per configuration field.")
                if value:
                    values[name] = value
            write_config(path, values)
            print(json.dumps({"configured": args.capability, "private_file": True}))
        elif args.action == "doctor":
            if command:
                raise ConfigError("Doctor accepts configuration options only.")
            print(json.dumps({"fields": {name: bool(values.get(name)) for name in sorted(ALLOWED)},
                              "private_file": path.exists(), "provider_calls": 0}, indent=2))
        else:
            if command[:1] == ["--"]:
                command = command[1:]
            if not path.exists() or not command:
                raise ConfigError("Run needs an existing private file and a command after --.")
            return subprocess.run(command, env=child_env(values, dict(os.environ))).returncode
    except (ConfigError, OSError, UnicodeError):
        # Exception text from OS/process/environment parsing may contain private values.
        print("Private runtime configuration could not be used. Check path, permissions and field names.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
