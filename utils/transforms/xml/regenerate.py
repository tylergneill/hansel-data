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
    parser = argparse.ArgumentParser(description="Regenerate XML from plaintext or vice-versa, cleaning stale files.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--xml', action='store_true', help='Convert plaintext to XML.')
    group.add_argument('--txt', action='store_true', help='Convert XML to plaintext.')
    args = parser.parse_args()

    BASE_IN_DIR = Path('texts')
    
    if args.xml:
        script_name = 'utils/transforms/xml/convert_plaintext_to_xml.py'
        in_ext = '.txt'
        out_ext = '.xml'
        use_transforms_subdir_for_input = False
        base_out_dir = BASE_IN_DIR 
        use_transforms_subdir_for_output = True

    elif args.txt:
        script_name = 'utils/transforms/xml/convert_xml_to_plaintext.py'
        in_ext = '.xml'
        out_ext = '.txt'
        use_transforms_subdir_for_input = True
        base_out_dir = Path('utils/transforms/xml/roundtrip_txt')
        use_transforms_subdir_for_output = False


    for tier in ['tier_ii', 'tier_iii']:
        in_dir = BASE_IN_DIR / tier
        if use_transforms_subdir_for_input:
            in_dir = in_dir / 'transforms' / 'xml'

        if not os.path.exists(in_dir):
            print(f"Directory not found, skipping: {in_dir}")
            continue

        out_dir = base_out_dir / tier
        if use_transforms_subdir_for_output:
            out_dir = out_dir / 'transforms' / 'xml'

        out_dir.mkdir(parents=True, exist_ok=True)

        # --- Clean stale files ---
        source_files = [f for f in os.listdir(in_dir) if f.endswith(in_ext)]
        expected_output_stems = {Path(f).stem for f in source_files}
        
        for existing_file in out_dir.glob(f'*{out_ext}'):
            if existing_file.stem not in expected_output_stems:
                os.remove(existing_file)
                print(f"Deleted stale file: {existing_file}")
        # --- End cleaning ---

        for filename in source_files: # iterate over list we already made
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