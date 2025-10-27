import subprocess
from pathlib import Path
import argparse

def main():
    parser = argparse.ArgumentParser(description="Run all regeneration scripts.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--xml', action='store_true', help='Run XML regeneration (plaintext to XML). ')
    group.add_argument('--txt', action='store_true', help='Run XML to plaintext regeneration.')
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.parent

    xml_regenerate_command = "python utils/transforms/xml/regenerate.py"
    if args.xml:
        xml_regenerate_command += " --xml"
    elif args.txt:
        xml_regenerate_command += " --txt"

    commands = [
        "python utils/transforms/metadata/regenerate.py",
        xml_regenerate_command,
        "python utils/transforms/html/regenerate.py",
        "python utils/transforms/zip_texts.py"
    ]

    for command_str in commands:
        command = command_str.split()
        print(f"\n--- Running: {command_str} ---")
        
        subprocess.run(command, cwd=project_root, check=True)

    print("\n--- All regeneration scripts completed. ---")

if __name__ == "__main__":
    main()