import argparse
from pathlib import Path
import os
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(PROJECT_ROOT))

from utils.transforms.flag_map import flag_map

METADATA_DIR = PROJECT_ROOT / 'metadata' / 'markdown'
TEXTS_DIR = PROJECT_ROOT / 'texts'


def run_conversion(script_name, in_dir, in_ext, out_dir, out_ext, flag_map, direction):
    source_files = [f for f in os.listdir(in_dir) if f.endswith(in_ext)]
    for filename in source_files:
        in_path = in_dir / filename
        stem = Path(filename).stem
        out_path = out_dir / f'{stem}{out_ext}'
        flags = flag_map.get(stem, '')
        command = ['python', str(script_name), str(in_path), str(out_path)]
        if flags:
            if direction == 'xml':
                # --chaya is a boolean flag in flag_map but takes a path arg in convert_plaintext_to_xml;
                # strip it here and re-add with the resolved path below
                command.extend(f for f in flags.split() if f != '--chaya')
            else:
                command.extend(flags.split())
        if direction == 'xml' and '--chaya' in flags:
            chaya_path = in_dir / 'chaya' / f'{stem}.txt'
            if chaya_path.exists():
                command.extend(['--chaya', str(chaya_path)])
        subprocess.run(command)


def main():
    parser = argparse.ArgumentParser(description="Regenerate XML from plaintext or vice-versa, cleaning stale files.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--xml', action='store_true', help='Convert plaintext to XML and update headers.')
    group.add_argument('--txt', action='store_true', help='Convert XML to plaintext.')
    args = parser.parse_args()

    if args.xml:

        # run TWO conversions, corresponding to <teiHeader> and <text> elements
        # TODO: resolve why order of these two matters (namespaces?)

        # metadata => <teiHeader>
        run_conversion(
            script_name=PROJECT_ROOT / 'utils/transforms/xml/convert_markdown_to_xml.py',
            in_dir=METADATA_DIR,
            in_ext='.md',
            out_dir=TEXTS_DIR / 'project_editions' / 'xml',
            out_ext='.xml',
            flag_map={},
            direction='xml',
        )

        # project_edition plain-text => <text>
        run_conversion(
            script_name=PROJECT_ROOT / 'utils/transforms/xml/convert_plaintext_to_xml.py',
            in_dir=TEXTS_DIR / 'project_editions' / 'txt',
            in_ext='.txt',
            out_dir=TEXTS_DIR / 'project_editions' / 'xml',
            out_ext='.xml',
            flag_map=flag_map,
            direction='xml',
        )

    elif args.txt:
        run_conversion(
            script_name=PROJECT_ROOT / 'utils/transforms/xml/convert_xml_to_plaintext.py',
            in_dir=TEXTS_DIR / 'project_editions' / 'xml',
            in_ext='.xml',
            out_dir=TEXTS_DIR / 'project_editions' / 'txt',
            out_ext='.txt',
            flag_map=flag_map,
            direction='txt',
        )

if __name__ == "__main__":
    main()
