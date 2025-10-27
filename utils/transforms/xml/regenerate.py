import argparse
from pathlib import Path
import os
import subprocess

flag_map = {
    "bANa_kAdambarI": '--line-by-line',
    "kumArilabhaTTa_zlokavArtika": '--verse-only',
    "zukasaptati_s": '--line-by-line --extra-space-after-location',
    "zukasaptati_o": '--line-by-line --extra-space-after-location',
}


def run_conversion(script_name, in_dir, in_ext, out_dir, out_ext, flag_map):
    source_files = [f for f in os.listdir(in_dir) if f.endswith(in_ext)]
    for filename in source_files:
        in_path = in_dir / filename
        stem = Path(filename).stem
        out_path = out_dir / f'{stem}{out_ext}'
        flag = flag_map.get(stem)
        command = ['python', script_name, str(in_path), str(out_path)]
        if flag:
            command.extend(flag.split())
        subprocess.run(command)


def main():
    parser = argparse.ArgumentParser(description="Regenerate XML from plaintext or vice-versa, cleaning stale files.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--xml', action='store_true', help='Convert plaintext to XML and update headers.')
    group.add_argument('--txt', action='store_true', help='Convert XML to plaintext.')
    args = parser.parse_args()

    METADATA_DIR = Path('metadata')
    TEXTS_DIR = Path('texts')
    
    if args.xml:

        # run TWO conversions, corresponding to <teiHeader> and <text> elements
        # TODO: resolve why order of these two matters (namespaces?)

        # metadata => <teiHeader>
        script_kwargs_1 = {
            "script_name": 'utils/transforms/xml/convert_markdown_to_xml.py',
            "in_dir": METADATA_DIR,
            "in_ext": '.md',
            "out_dir": TEXTS_DIR / 'project_editions' / 'xml',
            "out_ext": '.xml',
            "flag_map": {},
        }
        run_conversion(**script_kwargs_1)

        # project_edition plain-text => <text>
        pt_in_dir = TEXTS_DIR / 'project_editions' / 'txt'
        script_kwargs_2 = {
            "script_name": 'utils/transforms/xml/convert_plaintext_to_xml.py',
            "in_dir": pt_in_dir,
            "in_ext": '.txt',
            "out_dir": TEXTS_DIR / 'project_editions' / 'xml',
            "out_ext": '.xml',
            "flag_map": flag_map,
        }
        run_conversion(**script_kwargs_2)

    elif args.txt:
        script_kwargs = {
            "script_name": 'utils/transforms/xml/convert_xml_to_plaintext.py',
            "in_dir": TEXTS_DIR / 'project_editions' / 'xml',
            "in_ext": '.xml',
            "out_dir": Path('utils/transforms/xml/roundtrip_txt'),
            "out_ext": '.txt',
            "flag_map": flag_map,
        }
        run_conversion(**script_kwargs)

if __name__ == "__main__":
    main()
