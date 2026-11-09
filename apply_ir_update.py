"""Run from GitHappens root: py -3.11 path/to/apply_ir_update.py [--apply]."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shutil


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    parser=argparse.ArgumentParser(description='Validate and apply the optional IR update.')
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    root=args.root.resolve()
    bundle=Path(__file__).resolve().parent
    if not (root/'accessshift/app.py').is_file():
        parser.error('Run from your GitHappens repository root, or supply --root PATH.')
    manifest=json.loads((bundle/'manifest.json').read_text())
    conflicts=[];pending=[]
    for item in manifest:
        target=root/item['path'];source=bundle/'files'/item['path']
        if digest(source)!=item['after']:
            parser.error('Update bundle is incomplete or modified: '+item['path'])
        actual=digest(target)
        if actual==item['after']:
            continue
        if target.is_dir() or actual!=item['before']:
            conflicts.append(item['path'])
        else:
            pending.append(item)
    if conflicts:
        print('Nothing changed. These files differ from the uploaded snapshot:')
        print('\n'.join(conflicts))
        print('Do not force an overwrite. Merge these files against your latest branch first.')
        return 1
    if not pending:
        print('All IR update files are already applied.')
        return 0
    print('\n'.join(item['path'] for item in pending))
    if not args.apply:
        print('Validation passed. Re-run with --apply to install these files.')
        return 0
    backup=root/('.ir-update-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir()
    applied=[]
    try:
        for item in pending:
            rel=item['path'];target=root/rel
            if target.exists():
                saved=backup/rel;saved.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,saved)
            target.parent.mkdir(parents=True,exist_ok=True)
            applied.append(item)
            shutil.copy2(bundle/'files'/rel,target)
    except Exception:
        for item in reversed(applied):
            rel=item['path'];target=root/rel
            if (backup/rel).is_file():
                shutil.copy2(backup/rel,target)
            elif item['before'] is None:
                target.unlink(missing_ok=True)
        raise
    print('IR update applied. Original files backed up in:',backup)
    print('Next: read IR_SETUP.md. Nothing was committed or pushed.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
