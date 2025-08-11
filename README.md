# GitHub Repository Manager

A command-line tool for managing GitHub repository visibility and settings in bulk operations.

## Overview

GitHub Repository Manager provides efficient bulk operations for repository management, allowing you to quickly change visibility settings, organize repositories, and perform diagnostic operations on your GitHub repositories.

## Features

### Repository Management
- **Repository Visibility Management**: Bulk operations to make repositories private or public
- **Interactive Repository Selection**: Choose specific repositories or filter by visibility type
- **Repository Information Display**: View repository details including stars, forks, language, and last updated
- **Safe Operations**: Confirmation prompts and detailed feedback for all operations

### Automation Features
- **Auto-Follow**: Automatically follow followers of target users with intelligent filtering
- **Smart Cleanup**: Unfollow non-followers with whitelist protection
- **Statistics**: View follow/follower statistics and analytics
- **Backup & Restore**: Complete backup of follow/follower state

### Debug Tools
- **API Diagnostics**: Troubleshoot GitHub API access and permission issues
- **Interactive Mode**: Explore features through interactive interface

## Requirements

- Python 3.11+
- GitHub Personal Access Token with appropriate scopes:
  - `repo` (for repository management)
  - `user:follow` (for follow/unfollow operations)

## Installation

1. Install dependencies:
```bash
pip install requests python-dotenv tqdm colorama cryptography
```

2. Set up your GitHub token:
```bash
export GITHUB_TOKEN="your_github_token_here"
```

## Usage

### Basic Repository Management

List all repositories and select interactively:
```bash
python github_automation.py repo-manager
```

### Bulk Operations

Make all repositories private:
```bash
python github_automation.py repo-manager --make-private
```

Make all repositories public:
```bash
python github_automation.py repo-manager --make-public
```

### Filtering

Work with specific repository types:
```bash
python github_automation.py repo-manager --filter public
python github_automation.py repo-manager --filter private
```

### Toggle Visibility

Switch repository visibility (private ↔ public):
```bash
python github_automation.py repo-manager --toggle-visibility
```

### Automation Features

Auto-follow followers of a user:
```bash
python github_automation.py repo-manager --auto-follow octocat --limit 50
```

Unfollow non-followers:
```bash
python github_automation.py repo-manager --unfollow-nonfollowers --whitelist data/whitelist.txt
```

View statistics:
```bash
python github_automation.py repo-manager --stats --stats-username octocat --detailed
```

Create backup:
```bash
python github_automation.py repo-manager --backup-create
```

### Debug Mode

Check GitHub API access and permissions:
```bash
python github_automation.py repo-manager --debug
```

### Interactive Mode

Start interactive mode for exploratory operations:
```bash
python github_automation.py repo-manager --interactive
```

## Configuration

Create a `.env` file in the project directory:

```env
GITHUB_TOKEN=your_personal_access_token
```

## Command Reference

```
usage: github_automation.py repo-manager [-h] [--make-private] [--make-public]
                                         [--toggle-visibility]
                                         [--filter {all,public,private}]
                                         [--auto-follow USERNAME] [--limit LIMIT]
                                         [--unfollow-nonfollowers] [--whitelist WHITELIST]
                                         [--stats] [--stats-username USERNAME]
                                         [--backup-create] [--interactive] [--debug]

Repository Visibility Management:
  --make-private        Bulk make selected repositories private
  --make-public         Bulk make selected repositories public
  --toggle-visibility   Toggle visibility of selected repositories
  --filter              Filter repositories by visibility (all/public/private)

Automation Features:
  --auto-follow         Auto-follow followers of specified user
  --limit               Maximum users to follow (default: 100)
  --unfollow-nonfollowers  Unfollow users who don't follow back
  --whitelist           Path to whitelist file (users to never unfollow)
  --stats               Show follow/follower statistics
  --stats-username      Username to analyze (default: authenticated user)

Backup Management:
  --backup-create       Create backup of current follow/follower state
  --backup-restore      Restore from backup file
  --backup-list         List available backups

Additional Operations:
  --interactive         Start interactive mode
  --debug               Debug repository access and GitHub API permissions
```

## Project Structure

```
GitHub-Repository-Manager/
├── github_automation.py     # Main entry point
├── cli/                     # Command-line interface
│   ├── commands.py         # Command implementations
│   └── interactive.py      # Interactive mode
├── core/                   # Core functionality
│   ├── github_api.py      # GitHub API client
│   ├── file_manager.py    # File operations
│   ├── logger.py          # Logging system
│   ├── rate_limiter.py    # Rate limiting
│   └── validators.py      # Input validation
├── data/                  # Configuration files
├── logs/                  # Application logs
└── backups/              # Backup storage
```

## License

This project is licensed under the MIT License.