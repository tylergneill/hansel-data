import subprocess
from pathlib import Path

def main():
    # This script should be run from the project root directory.
    # We determine the project root relative to this script's location to ensure that.
    project_root = Path(__file__).parent.parent.parent

    commands = [
        "python utils/transforms/metadata/regenerate.py",
        "python utils/transforms/xml/regenerate.py --xml",
        "python utils/transforms/html/regenerate.py"
    ]

    for command_str in commands:
        command = command_str.split()
        print(f"\n--- Running: {command_str} ---")
        
        # Run the command from the project root directory
        subprocess.run(command, cwd=project_root, check=True)

    print("\n--- All regeneration scripts completed. ---")

if __name__ == "__main__":
    main()

