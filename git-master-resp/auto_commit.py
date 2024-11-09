#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime

# Local path to the Git repository
REPO_PATH = "/home/rafal/Downloads/test/git-private"  # Use this exact path

def git_commit_push():
    os.chdir(REPO_PATH)
    
    # Update or create a heartbeat file with the current timestamp
    with open("last_startup.txt", "w") as f:
        f.write(f"Last startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Stage all changes, including the updated heartbeat file
    subprocess.run(["git", "add", "."])

    # Create a commit message with the current date and time
    commit_message = f"Auto commit on startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    subprocess.run(["git", "commit", "-m", commit_message])

    # Push changes to the remote repository
    subprocess.run(["git", "push", "origin", "master"])

    print("Changes committed and pushed.")

if __name__ == "__main__":
    git_commit_push()
