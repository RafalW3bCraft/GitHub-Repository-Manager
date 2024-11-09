<<<<<<< HEAD
# git-master-init
The 'Git-master-init' repository is an initial phase Git toolset aimed at simplifying and optimizing developers' workflow. Its focus on automation and a unified CLI interface for repository management promises enhanced productivity and efficiency. Developers can expect a powerful set of features to manage Git repositories, even in this early stage.
=======
<<<<<<< HEAD
# git-master-init
The 'Git-master-init' repository is an initial phase Git toolset aimed at simplifying and optimizing developers' workflow. Its focus on automation and a unified CLI interface for repository management promises enhanced productivity and efficiency. Developers can expect a powerful set of features to manage Git repositories, even in this early stage.
=======
To create a Python script that automatically commits changes to a Git repository each time Kali Linux starts:

1. A **Python script** to perform the Git commit.
2. A **systemd service** or **autostart script** to launch this Python script on startup.

Below is a guide to help you set this up.

---

### 1. Create the Python Script

This script will:
- Navigate to the Git repository.
- Check if there are any changes.
- If there are changes, stage them, commit with a timestamped message, and push to the remote repository.


```python
#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime

# Path to your Git repository
REPO_PATH = "/path/to/your/git-repo"

def git_commit_push():
    os.chdir(REPO_PATH)
    
    # Check for any changes
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if result.stdout.strip() == "":
        print("No changes to commit.")
        return
    
    # Stage all changes
    subprocess.run(["git", "add", "."])

    # Create a commit message with the current date and time
    commit_message = f"Auto commit on startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    subprocess.run(["git", "commit", "-m", commit_message])

    # Push changes to the remote repository
    subprocess.run(["git", "push"])

    print("Changes committed and pushed.")

if __name__ == "__main__":
    git_commit_push()
```

#### Make the Script Executable

1. Save this script as `auto_commit.py`.
2. Make it executable:

   ```bash
   chmod +x /path/to/auto_commit.py
   ```

---

### 2. Set Up Auto-launch on Startup

You can use a **systemd service** to run this script each time the system boots.

#### Create a Systemd Service File

1. Create a new service file in `/etc/systemd/system/`:

   ```bash
   sudo nano /etc/systemd/system/git-auto-commit.service
   ```

2. Add the following content to this file:

   ```ini
   [Unit]
   Description=Auto Commit and Push Git Repository on Startup
   After=network.target

   [Service]
   ExecStart=/path/to/auto_commit.py
   Restart=on-failure

   [Install]
   WantedBy=default.target
   ```

   - Replace `/path/to/auto_commit.py` with the full path to your script.
   - The `After=network.target` ensures that the script waits until the network is available, which is necessary for `git push`.

3. **Save and close** the file.

#### Enable the Service

To make this service run at every startup, enable it with:

```bash
sudo systemctl enable git-auto-commit.service
```

#### Start the Service (for Immediate Testing)

You can start it immediately to test it without rebooting:

```bash
sudo systemctl start git-auto-commit.service
```

### 3. Verify the Setup

After rebooting (or starting the service manually), check if the script committed and pushed the changes as expected by running:

```bash
git log -1
```
>>>>>>> 1543a2e (initialization mode)
>>>>>>> 2d99eae (initialization mod)
