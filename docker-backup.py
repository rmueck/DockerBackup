#!/usr/bin/python3
import os
import sys
import json
import argparse
import subprocess
import datetime
import http.client
import urllib
import shutil
import time

# -------------------------
# Config loader + defaults
# -------------------------
DEFAULTS = {
    "temp_backup_dir": "/tmp",
    "base_backup_dir": "/var/tmp/Docker-Backups",
    "max_backups": 3,
    "docker_volume_dir": "/var/lib/docker/volumes",
    "additional_directories_to_backup": [],
    "rclone_destination": "",
    "pushover_api_token": "",
    "pushover_user_key": "",
    "containers_in_order": [],
    "backup_container_name": ""
}


def load_config(path):
    cfg = {}
    try:
        with open(path, "r") as f:
            cfg = json.load(f) or {}
    except FileNotFoundError:
        print(f"Config file '{path}' not found. Using defaults.")
    except json.JSONDecodeError as e:
        print(f"Error parsing config file '{path}': {e}")
        sys.exit(1)

    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)

    if isinstance(cfg.get("temp_backup_dir"), str):
        cfg["temp_backup_dir"] = cfg["temp_backup_dir"].rstrip("/")
    else:
        cfg["temp_backup_dir"] = DEFAULTS["temp_backup_dir"]

    if isinstance(cfg.get("base_backup_dir"), str):
        cfg["base_backup_dir"] = cfg["base_backup_dir"].rstrip("/")
    else:
        cfg["base_backup_dir"] = DEFAULTS["base_backup_dir"]

    if not isinstance(cfg.get("max_backups"), int) or cfg["max_backups"] < 1:
        cfg["max_backups"] = DEFAULTS["max_backups"]

    if not isinstance(cfg.get("additional_directories_to_backup"), list):
        cfg["additional_directories_to_backup"] = DEFAULTS["additional_directories_to_backup"]

    if not isinstance(cfg.get("containers_in_order"), list):
        cfg["containers_in_order"] = DEFAULTS["containers_in_order"]

    return cfg


parser = argparse.ArgumentParser(description="Docker backup script")
parser.add_argument("--config", "-c", default="/etc/docker-backup/config.json",
                    help="Path to JSON config file (default: /etc/docker-backup/config.json)")
parser.add_argument("--dry-run", action="store_true",
                    help="Show actions without stopping/starting containers, creating archives, or uploading")
parser.add_argument("--no-rclone", action="store_true",
                    help="Disable rclone upload even if rclone_destination is set in config")
args, _remaining = parser.parse_known_args()

config = load_config(args.config)

TEMP_BACKUP_DIR = config["temp_backup_dir"]
BASE_BACKUP_DIR = config["base_backup_dir"]
MAX_BACKUPS = config["max_backups"]
DOCKER_VOLUME_DIR = config["docker_volume_dir"]
ADDITIONAL_DIRECTORIES_TO_BACKUP = config["additional_directories_to_backup"]
RCLONE_DESTINATION = "" if args.no_rclone else config["rclone_destination"]
PUSHOVER_API_TOKEN = config["pushover_api_token"]
PUSHOVER_USER_KEY = config["pushover_user_key"]
CONTAINERS_IN_ORDER = config["containers_in_order"]
BACKUP_CONTAINER_NAME = config["backup_container_name"]
DRY_RUN = args.dry_run

os.makedirs(BASE_BACKUP_DIR, exist_ok=True)
os.makedirs(TEMP_BACKUP_DIR, exist_ok=True)

# -------------------------
# Helper functions
# -------------------------


def run(cmd, check=False):
    if DRY_RUN:
        print(f"+ {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
    if check:
        return subprocess.run(cmd, check=True)
    return subprocess.run(cmd, capture_output=True)


def send_pushover_notification(message):
    print("\n" + message)
    if not PUSHOVER_API_TOKEN or not PUSHOVER_USER_KEY or DRY_RUN:
        if DRY_RUN:
            print("DRY RUN: Skipping Pushover notification.")
        else:
            print("Pushover credentials missing. Skipping notification.")
        return
    conn = http.client.HTTPSConnection("api.pushover.net:443")
    conn.request("POST", "/1/messages.json",
                 urllib.parse.urlencode({
                     "token": PUSHOVER_API_TOKEN,
                     "user": PUSHOVER_USER_KEY,
                     "message": message,
                 }), {"Content-type": "application/x-www-form-urlencoded"})
    conn.getresponse()


def is_container_running(container_name):
    result = run(["docker", "inspect", "-f", "{{.State.Running}}", container_name])
    out = result.stdout.decode() if result.stdout else ""
    return out.strip() == "true"


def wait_for_container(container_name, timeout=300):
    start = time.time()
    while not is_container_running(container_name):
        if time.time() - start > timeout:
            print(f"Timeout waiting for {container_name} to start.")
            return False
        print(f"Waiting for {container_name} to start...")
        time.sleep(5)
    return True


def start_container(container_name):
    run(["docker", "start", container_name])


def log_backup_details(timestamp, backup_name, backup_size, cloud_path=None):
    log_entry = f"Date: {timestamp}, Size: {backup_size:.2f} MB, Local Path: {os.path.join(BASE_BACKUP_DIR, timestamp, backup_name)}"
    if cloud_path:
        log_entry += f", Cloud Path: {os.path.join(cloud_path, backup_name)}"
    log_entry += "\n"
    with open(os.path.join(BASE_BACKUP_DIR, "backup_log.txt"), "a") as log_file:
        log_file.write(log_entry)

# -------------------------
# Main
# -------------------------


def main():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    current_backup_dir = os.path.join(BASE_BACKUP_DIR, timestamp)
    if not DRY_RUN:
        os.makedirs(current_backup_dir, exist_ok=True)
    else:
        print(f"DRY RUN: Would create {current_backup_dir}")

    result = run(["docker", "ps", "-q"])
    all_containers_ids = result.stdout.decode().split() if result.stdout else []
    all_containers_names = []
    for container_id in all_containers_ids:
        r = run(["docker", "inspect", "--format={{.Name}}", container_id])
        name = r.stdout.decode().strip().lstrip("/") if r.stdout else container_id
        all_containers_names.append(name)

    for container_id, container_name in zip(all_containers_ids, all_containers_names):
        print(f"Backing up configuration for {container_name} ({container_id})...")
        config_filename = container_name + "_config.json"
        config_path = os.path.join(TEMP_BACKUP_DIR, config_filename)
        if DRY_RUN:
            print(f"DRY RUN: Would write {config_path} with docker inspect output")
        else:
            with open(config_path, "wb") as f:
                subprocess.run(["docker", "inspect", container_id], stdout=f)

    result = run(["docker", "ps", "-q"])
    all_containers_ids = result.stdout.decode().split() if result.stdout else []
    all_containers_names = []
    for container_id in all_containers_ids:
        r = run(["docker", "inspect", "--format={{.Name}}", container_id])
        name = r.stdout.decode().strip().lstrip("/") if r.stdout else container_id
        all_containers_names.append(name)

    if not BACKUP_CONTAINER_NAME:
        print("WARNING: BACKUP_CONTAINER_NAME is not configured. The script might stop the container it's running in.")
    else:
        print(f"Gracefully stopping {len(all_containers_ids)} containers, excluding {BACKUP_CONTAINER_NAME}...")
        for container_id, container_name in zip(all_containers_ids, all_containers_names):
            if container_name != BACKUP_CONTAINER_NAME:
                print(f"Stopping {container_name} ({container_id})...")
                run(["docker", "stop", container_id])

    print("Backing up docker volumes and configurations...")
    temp_backup_path = os.path.join(TEMP_BACKUP_DIR, "docker_backup.tar.gz")
    config_files = [os.path.join(TEMP_BACKUP_DIR, container_name + "_config.json") for container_name in all_containers_names]
    tar_args = ["tar", "--use-compress-program=pigz", "-cvf", temp_backup_path, DOCKER_VOLUME_DIR] + config_files
    run(tar_args)
    if DRY_RUN:
        print(f"DRY RUN: Would move {temp_backup_path} to {os.path.join(current_backup_dir, 'docker_backup.tar.gz')}")
    else:
        os.replace(temp_backup_path, os.path.join(current_backup_dir, "docker_backup.tar.gz"))

    backup_name = "docker_backup.tar.gz"
    if not DRY_RUN:
        backup_size = os.path.getsize(os.path.join(current_backup_dir, backup_name)) / (1024 * 1024)
    else:
        backup_size = 0.0
    log_backup_details(timestamp, backup_name, backup_size, os.path.join(RCLONE_DESTINATION, timestamp, backup_name) if RCLONE_DESTINATION else None)

    for dir_to_backup in ADDITIONAL_DIRECTORIES_TO_BACKUP:
        print(f"Backing up directory {dir_to_backup}...")
        backup_name = os.path.basename(dir_to_backup.rstrip("/")) + ".tar.gz"
        temp_backup_path = os.path.join(TEMP_BACKUP_DIR, backup_name)
        try:
            run(["tar", "--use-compress-program=pigz", "-cvf", temp_backup_path, dir_to_backup], check=True)
            if DRY_RUN:
                print(f"DRY RUN: Would move {temp_backup_path} to {os.path.join(current_backup_dir, backup_name)}")
            else:
                os.replace(temp_backup_path, os.path.join(current_backup_dir, backup_name))
                backup_size = os.path.getsize(os.path.join(current_backup_dir, backup_name)) / (1024 * 1024)
                log_backup_details(timestamp, backup_name, backup_size, os.path.join(RCLONE_DESTINATION, timestamp, backup_name) if RCLONE_DESTINATION else None)
        except subprocess.CalledProcessError:
            print(f"Error while backing up {dir_to_backup}. Skipping.")

    print(f"Restarting {len(CONTAINERS_IN_ORDER)} containers in specified order...")
    remaining = list(all_containers_names)
    for container_name in CONTAINERS_IN_ORDER:
        if container_name in remaining:
            print(f"Starting {container_name}...")
            start_container(container_name)
            if not DRY_RUN:
                wait_for_container(container_name)
            remaining.remove(container_name)

    print(f"Restarting remaining {len(remaining)} containers...")
    for container_name in remaining:
        print(f"Starting {container_name}...")
        start_container(container_name)

    upload_status_icon = "⚠️ Skipped"
    if RCLONE_DESTINATION:
        print(f"Starting rclone copy to {os.path.join(RCLONE_DESTINATION, timestamp)}...")
        if not DRY_RUN:
            rclone_result = run(
                ["rclone", "copy", current_backup_dir, os.path.join(RCLONE_DESTINATION, timestamp)],
                )
            rclone_output = (rclone_result.stdout.decode() if rclone_result.stdout else "") + (rclone_result.stderr.decode() if rclone_result.stderr else "")
            upload_status_icon = "✅" if "Failed to copy" not in rclone_output else "❌"
            print("Rclone copy finished.")
            run([
                "rclone", "copyto",
                os.path.join(BASE_BACKUP_DIR, "backup_log.txt"),
                os.path.join(RCLONE_DESTINATION, "backup_log.txt")
            ])
        else:
            print("DRY RUN: Skipping actual rclone copy.")
            upload_status_icon = "⚠️ Skipped"

    all_backups = sorted([
        entry for entry in os.listdir(BASE_BACKUP_DIR)
        if os.path.isdir(os.path.join(BASE_BACKUP_DIR, entry))
    ])
    while len(all_backups) > MAX_BACKUPS:
        old = all_backups.pop(0)
        path = os.path.join(BASE_BACKUP_DIR, old)
        if DRY_RUN:
            print(f"DRY RUN: Would remove {path}")
        else:
            shutil.rmtree(path)

    elapsed_time = datetime.datetime.now() - datetime.datetime.strptime(timestamp, "%Y-%m-%d-%H-%M-%S")
    if not DRY_RUN:
        backup_size = sum(os.path.getsize(os.path.join(current_backup_dir, f)) for f in os.listdir(current_backup_dir))
    else:
        backup_size = 0
    message = f"🔥 Backup Summary 🔥\n\n"
    message += f"🕒 Time elapsed: {elapsed_time}\n"
    message += f"💾 Backup size: {backup_size / (1024*1024):.2f} MB\n"
    message += f"🚀 Upload status: {upload_status_icon}\n"
    message += f"🐳 Number of containers backed up: {len(all_containers_ids)}\n"
    send_pushover_notification(message)


if __name__ == "__main__":
    main()


