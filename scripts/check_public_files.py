"""Best-effort credential guard. Reports paths/rules only, never matched values.
Not a substitute for credential revocation or provider secret scanning.
"""
import argparse
import re
import subprocess
from pathlib import Path

RULES = {
    'private-key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'google-api-key': rb'AIza[0-9A-Za-z_-]{35}',
    'google-oauth-secret': rb'GOCSPX-[A-Za-z0-9_-]{15,}',
    'github-token': rb'(?:gh[pousr]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{50,})',
    'aws-access-id': rb'(?:AKIA|ASIA)[A-Z0-9]{16}',
    'jwt': rb'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}',
    'credential-in-url': rb'(?:postgres(?:ql)?|redis|mongodb)://[^\s:/]{1,80}:[^\s@]{4,100}@',
}

def forbidden(path):
    p = Path(path)
    name = p.name.lower()
    return ((name == '.env' or name.startswith('.env.')) and name != '.env.example'
            or name in {'credentials.json', 'creds.json'}
            or ('service-account' in name or name.startswith('client_secret')) and name.endswith('.json')
            or p.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.dump', '.sqlite', '.sqlite3', '.db'}
            or 'backups' in p.parts or 'sessions' in p.parts
            or path.startswith('server/config/'))

def findings(data):
    if b'\x00' in data: return []
    return [name for name, pattern in RULES.items() if re.search(pattern, data)]

def git(*args):
    return subprocess.check_output(['git', *args])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path)
    args = parser.parse_args()
    failures = []
    paths = git('ls-files', '-z').decode().split('\0')
    for path in filter(None, paths):
        if forbidden(path): failures.append((path, 'sensitive-filename'))
        file = Path(path)
        if file.is_file():
            failures.extend((path, rule) for rule in findings(file.read_bytes()))
    if args.site:
        for path in ('server','docs','tests','scripts','.git','.github','_site','copi-_config.yml'):
            if (args.site / path).exists(): failures.append((path, 'unexpected-site-output'))
        for file in args.site.rglob('*'):
            if file.is_file():
                name = file.relative_to(args.site).as_posix()
                if forbidden(name): failures.append((name, 'sensitive-site-file'))
                failures.extend((name, rule) for rule in findings(file.read_bytes()))
    for path, rule in failures:
        print(f'BLOCKED: {path} [{rule}]')
    if failures: raise SystemExit(1)
    print('OK: no credential-pattern matches or forbidden files in checked content.')

if __name__ == '__main__': main()
