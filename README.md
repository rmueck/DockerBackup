# Docker Backup Script

This script is tailored for Linux-based systems to automate the backup process
of Docker containers along with their respective volumes. Unfortunately, it is
not compatible with Windows. The script operates by halting the running
containers, backing up their configurations and volumes, and subsequently
restarting the containers in a designated order or all at once if no order is
delineated.

![Docker Backup Notification Screenshot](docker_backup_notification.jpg)
_Above is a screenshot illustrating how the notifications appear on Pushover._

## Prerequisites

Ensure the following prerequisites are satisfied before executing the script:

  * **Python 3:** The script is written in Python 3. Ensure it's installed on your system.
  * **Docker:** Docker needs to be installed and operational on your system.
  * **pigz:** The script utilizes [pigz](https://zlib.net/pigz/) for parallel gzip compression. Install it via your system's package manager, e.g., on Ubuntu: `sudo apt-get install pigz`.
  * **rclone (Optional):** If off-site backups are desired, configure [rclone](https://rclone.org/) with your cloud storage provider.
  * **Pushover (Optional):** To receive notifications on backup status, set up a [Pushover](https://pushover.net/) account and install the app on your device.

## Configuration

The script contains a configuration section at its beginning, allowing you to
tailor various settings to match your environment:



    # Configuration section

    # Temporary directory for creating backup files before moving them to the final backup directory
    # Specify a directory path where temporary backup files will be stored.
    TEMP_BACKUP_DIR = "/tmp/"

    # Base directory where backups are stored
    # Specify the directory path where the final backup files will be stored.
    BASE_BACKUP_DIR = "/backups/"

    # Maximum number of backups to keep (older backups will be deleted)
    # Specify the maximum number of backup directories to keep. Older backups will be deleted.
    MAX_BACKUPS = 8

    # Directory containing Docker volumes / data
    # Specify the directory path where your Docker volumes are located.
    DOCKER_VOLUME_DIR = "/path/to/your/docker_volumes"

    # Additional directories to backup (Optional)
    # If you have any additional directories you want to backup alongside your Docker volumes, specify them here.
    # The backups will be named after the directory's base name and stored in the same location as other backups.
    ADDITIONAL_DIRECTORIES_TO_BACKUP = [
        "/path/to/first/directory",
        "/path/to/second/directory",
        # Add as many directories as you wish.
    ]

    # Off-site backup destination using rclone
    # Specify the rclone remote name and path where backups should be copied.
    # Leave it blank if you do not wish to use rclone for off-site backups.
    RCLONE_DESTINATION = "your_cloud_drive:Backups/"

    # Pushover credentials for receiving notifications
    # Specify your Pushover API token and user key to receive notifications.
    # Leave them blank if you do not wish to receive notifications.
    PUSHOVER_API_TOKEN = "YourTokenHere"
    PUSHOVER_USER_KEY = "YourUserKeyHere"

    # List of Docker containers to be restarted in the specified order after backup
    # Specify the names of your Docker containers in the order you want them to be restarted.
    # Use the command: docker ps --format '{{.Names}}' to get the list of running containers.
    CONTAINERS_IN_ORDER = ["mosquitto", "zigbee2mqtt", "esphome", "homeassistant"]



## Script Operation Breakdown

Here’s a step-by-step breakdown of what the script does:

  1. **Preparation:** A unique backup directory is created based on the current date and time.
  2. **Stopping Containers:** All running Docker containers are halted.
  3. **Configuration Backup:** Each container's configuration is backed up as a JSON file.
  4. **Data Backup:** Docker volumes are compressed into a tar.gz file using pigz for faster compression.
  5. **Additional Directory Backup:** Any additional directories specified in the configuration are backed up.
  6. **Restarting Containers:** Containers are restarted in the order specified or all at once if no order is provided.
  7. **Off-site Backup (Optional):** If configured, the backup directory is copied to a remote location using rclone.
  8. **Local Backup Cleanup:** Older local backups are deleted, ensuring only a specified number of backups are retained.
  9. **Notification (Optional):** A notification summarizing the backup details is sent via Pushover.

## Running the Script

The script should be executed with superuser privileges to avoid permission
issues, although users can adapt the script to suit their requirements. Use
the following command to run the script:



    sudo python3 docker_backup.py


## Automating the Script with Crontab

To automate the backup process, you can schedule the script to run at specific
intervals using crontab. Follow the steps below:

  1. Open the root user's crontab file by running the following command in the terminal:

        sudo crontab -e

  2. This will open the crontab file in the default text editor. Add a new line to the file with the following format to schedule your script:

        MIN HOUR DOM MON DOW /usr/bin/python3 /path/to/your/backup_script.py

     * **MIN:** Minute field (0 to 59)
     * **HOUR:** Hour field (0 to 23)
     * **DOM:** Day of Month field (1 to 31)
     * **MON:** Month field (1 to 12)
     * **DOW:** Day of Week field (0 to 6) (0 for Sunday)
     * Adjust the fields according to your preferred schedule.
  3. For example, to run the script every day at 3:00 AM, you would add the following line to the crontab file:

        0 3 * * * /usr/bin/python3 /path/to/your/backup_script.py

  4. Save and close the crontab file. The new cron job is now scheduled, and will run the backup script at the specified time.

Note: Ensure that the script is executable and the path to the script in the
crontab file is correct.

## Contact

For any additional inquiries or issues, feel free to open an issue on this
repository.

