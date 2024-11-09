#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime

# Local path to the Git repository
REPO_PATH = "/home/rafal/Downloads/test/git-private/git-master-resp"  # Update this path

def git_commit_push():
    os.chdir(REPO_PATH)
    
    # Logging to capture output
    with open("/home/rafal/Downloads/test/git-private/git-master-resp/logs/auto_commit.log", "a") as log:
        log.write(f"\n--- Auto commit at {datetime.now()} ---\n")
        
        # Update or create a heartbeat file with the current timestamp
        with open("last_startup.txt", "w") as f:
            f.write(f"Last startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Stage all changes, including the updated heartbeat file
        subprocess.run(["git", "add", "."], stdout=log, stderr=log)

        # Create a commit message with the current date and time
        commit_message = f"Auto commit on startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_message], stdout=log, stderr=log)

        # Push changes to the correct branch (main instead of master)
        subprocess.run(["git", "push", "origin", "main"], stdout=log, stderr=log)

        log.write("Changes committed and pushed.\n")

if __name__ == "__main__":
    git_commit_push()
