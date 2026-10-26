"""Read-only publication checks over Git-eligible files; prints paths, never secrets.

Does not stage files or inspect provider services. Run from backend or project root.
This is a lightweight guard, not a substitute for a dedicated secret/rights review.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args])
    candidates = sorted({p for p in git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0') if p})
    # Local comparison values never enter logs/reports, including on failure.
    from dotenv import dotenv_values
    values = dotenv_values(ROOT / 'backend/.env')
    secrets = {k: v for k, v in values.items() if v and len(v) > 10
               and any(word in k for word in ('API_KEY', 'SECRET_KEY', 'PUBLIC_KEY'))}
    findings = []
    for name in candidates:
        path = ROOT / name
        if not path.is_file():
            continue
        if path.stat().st_size > 10 * 1024 * 1024:
            findings.append({'path':name, 'kind':'large_file_over_10_MiB'})
        if (path.suffix.lower() == '.pdf' or name.startswith('data/processed/')
                or (name.startswith('data/corpus/') and path.name != '.gitkeep')):
            findings.append({'path':name, 'kind':'third_party_corpus_artifact'})
        if path.name.startswith('.env') and path.name != '.env.example':
            findings.append({'path':name, 'kind':'environment_secret_file'})
        data = path.read_bytes()
        for key, value in secrets.items():
            if value.encode() in data:
                findings.append({'path':name, 'kind':'configured_secret_value', 'variable':key})
        if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.ico', '.woff', '.woff2'}:
            continue
        try:
            text = data.decode()
        except UnicodeError:
            continue
        if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\b(?:ghp_|github_pat_|AKIA)[A-Za-z0-9_]{16,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}', text):
            findings.append({'path':name, 'kind':'credential_pattern'})
        # Match an actual personal absolute path, not this script's regex source.
        if re.search(r'/(?:Users|home)/[A-Za-z0-9._-]+/', text):
            findings.append({'path':name, 'kind':'private_absolute_path'})
    guides = json.loads((ROOT / 'data/studio_knowledge/manifest.json').read_text())['guides']
    hashes_ok = all(hashlib.sha256((ROOT / 'data/studio_knowledge' / g['path']).read_bytes()).hexdigest() == g['sha256'] for g in guides)
    report = {'scope':'Git-eligible public files, including untracked files; no files staged',
              'candidate_files':len(candidates), 'findings':findings,
              'guide_hashes_valid':hashes_ok, 'guide_count':len(guides),
              'limitations':['No paid APIs or cloud index inventory checked.',
                             'Pattern/exact-value checks cannot rule out unknown historical secrets or establish content redistribution rights.']}
    print(json.dumps(report, indent=2))
    return 0 if not findings and hashes_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
