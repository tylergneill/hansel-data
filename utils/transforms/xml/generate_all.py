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

def main():
    parser = argparse.ArgumentParser(description="Generate XML from plaintext or vice-versa.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--xml', action='store_true', help='Convert plaintext to XML.')
    group.add_argument('--txt', action='store_true', help='Convert XML to plaintext.')
    args = parser.parse_args()

    BASE_IN_DIR = Path('texts')
    
    if args.xml:
        script_name = 'utils/transforms/xml/convert_plaintext_to_xml.py'
        in_ext = '.txt'
        out_ext = '.xml'
        # Output is in a 'transforms' subdir of the input tier
        use_transforms_subdir_for_input = False
        base_out_dir = BASE_IN_DIR 
        use_transforms_subdir_for_output = True

    elif args.txt:
        script_name = 'utils/transforms/xml/convert_xml_to_plaintext.py'
        in_ext = '.xml'
        out_ext = '.txt'
        # Input is in a 'transforms' subdir of the input tier
        use_transforms_subdir_for_input = True
        base_out_dir = Path('utils/transforms/xml/roundtrip_txt')
        use_transforms_subdir_for_output = False


    for tier in ['tier_ii', 'tier_iii']:
        in_dir = BASE_IN_DIR / tier
        if use_transforms_subdir_for_input:
            in_dir = in_dir / 'transforms'

        if not os.path.exists(in_dir):
            print(f"Directory not found, skipping: {in_dir}")
            continue

        out_dir = base_out_dir / tier
        if use_transforms_subdir_for_output:
            out_dir = out_dir / 'transforms'

        out_dir.mkdir(parents=True, exist_ok=True)

        for filename in os.listdir(in_dir):
            if not filename.endswith(in_ext):
                continue

            in_path = in_dir / filename
            stem = Path(filename).stem
            out_path = out_dir / f'{stem}{out_ext}'

            flag = flag_map.get(stem)

            command = [
                'python',
                script_name,
                str(in_path),
                str(out_path)
            ]
            if flag:
                command.extend(flag.split())

            subprocess.run(command)

if __name__ == "__main__":
    main()
