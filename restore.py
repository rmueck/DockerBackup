#!/usr/bin/python3
import os
import sys
import subprocess
import argparse
import glob
import tarfile

def run_cmd(cmd, shell=False):
    """Wrapper for subprocess to handle errors and output."""
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        # We handle the print elsewhere to avoid cluttering during checks
        return None

def get_running_containers():
    """Returns IDs of currently running containers."""
    out = run_cmd(["docker", "ps", "-q"])
    return out.split() if out else []

def get_all_container_names():
    """Returns a list of all container names on the system (running or stopped)."""
    out = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}"])
    return out.split() if out else []

def main():
    parser = argparse.ArgumentParser(description="Multi-Component Docker Restore")
    parser.add_argument("backup_folder", help="Path to the timestamped backup folder")
    parser.add_argument("--container", "-c", help="Comma-separated components (e.g., joplin,seafile)")
    args = parser.parse_args()

    if os.geteuid() != 0:
        print("CRITICAL: This script must be run as root (sudo).")
        sys.exit(1)

    backup_path = os.path.abspath(args.backup_folder)
    target_components = [c.strip() for c in args.container.split(',')] if args.container else []

    # 1. CAPTURE STATE AND STOP
    originally_running_ids = get_running_containers()
    # Get names of running containers to cross-reference later
    originally_running_names = run_cmd(["docker", "ps", "--format", "{{.Names}}"]).split() if originally_running_ids else []

    if originally_running_ids:
        print(f"Stopping {len(originally_running_ids)} containers for a safe restore...")
        run_cmd(["docker", "stop"] + originally_running_ids)

    # 2. RESTORE DOCKER VOLUMES & CONFIGS
    main_archive = os.path.join(backup_path, "docker_backup.tar.gz")
    if os.path.exists(main_archive):
        if target_components:
            print(f"--- Selective Restore for: {', '.join(target_components)} ---")
            with tarfile.open(main_archive, "r:gz") as tar:
                members = [
                    m for m in tar.getmembers()
                    if any(comp in m.name for comp in target_components)
                ]
                if members:
                    tar.extractall(path="/", members=members)
                    print(f"Successfully restored {len(members)} system files.")
                else:
                    print(f"Warning: No volume data found matching targets.")
        else:
            print("--- Full Volume Restore: All Containers ---")
            run_cmd(["tar", "--use-compress-program=pigz", "-xf", main_archive, "-C", "/"])

    # 3. RESTORE HOST FOLDERS (/var/Containers/...)
    extra_archives = glob.glob(f"{backup_path}/*.tar.gz")
    for archive in extra_archives:
        filename = os.path.basename(archive)
        if filename == "docker_backup.tar.gz": continue

        if target_components and not any(comp in filename for comp in target_components):
            continue

        print(f"--- Restoring Host Folder Archive: {filename} ---")
        run_cmd(["tar", "--use-compress-program=pigz", "-xf", archive, "-C", "/"])

    # 4. RESTART ENVIRONMENT
    print("--- Restore Complete: Restarting Environment ---")

    all_known_names = get_all_container_names()
    to_start = set(originally_running_names) # Start with what was running

    # Add containers that match our restore keywords if they actually exist
    if target_components:
        for name in all_known_names:
            if any(comp in name for comp in target_components):
                to_start.add(name)

    if to_start:
        # Convert set to list and remove any empty strings
        start_list = [n for n in to_start if n]
        print(f"Restarting {len(start_list)} containers...")
        for name in start_list:
            # Final check to ensure the name exists before starting
            if name in all_known_names:
                run_cmd(["docker", "start", name])

    print("Done. System state restored correctly.")

if __name__ == "__main__":
    main()
