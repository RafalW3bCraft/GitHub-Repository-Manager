# Github-Repository-Manager

A ahigh-performance command-line tool for automating GitHub repository management and user operations. Built with strict asynchronous compliance for optimal performance.

## Features

- **Repository Management**: Create, clone, and manage repository visibility (public/private)
- **User Operations**: Follow/unfollow users with advanced criteria filtering
- **Interactive CLI**: Real-time command interface with comprehensive help system
- **Persistent Mode**: Continuous operation until explicit termination
- **Data Management**: Backup and restore functionality for operation states
- **Advanced Search**: Find users by followers, repositories, language, and location

## Installation

### Prerequisites
- Python 3.11 or higher
- GitHub Personal Access Token
- Git (for repository operations)

### Quick Install
```bash
git clone https://github.com/RafalW3bCraft/Github-Repository-Manager.git
cd Github-Repository-Manager
pip install -e .
```

## Configuration

### Environment Setup
Create a `.env` file in the project root:

```bash
GITHUB_TOKEN=your_github_token_here
GITHUB_USERNAME=your_username
```

### GitHub Token Setup
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with these scopes:
   - `user:follow` (Required for follow/unfollow operations)
   - `repo` (Recommended for private repository access)
3. Add the token to your `.env` file

## Usage

### Interactive Mode
Start the interactive interface:
```bash
python github_automation.py repo-manager --interactive
```

### Available Commands

#### General Commands
- `help` - Show available commands
- `status` - Show API status and rate limits
- `stats [username]` - Display user statistics
- `quit` or `exit` - Exit interactive mode

#### Follow Operations
- `follow <username>` - Follow a specific user
- `unfollow <username>` - Unfollow a specific user
- `followback [limit]` - Follow back your followers (default: 100)
- `check <username>` - Check follow status with user

#### Repository Management
- `create <name>` - Create a new repository
- `clone <url>` - Clone a repository

#### User Search
- `search followers <username>` - List user's followers
- `search following <username>` - List users followed by username
- `users` - Advanced user search with criteria

#### Data Management
- `backup` - Create backup of current state
- `restore [backup_file]` - Restore from backup
- `list backups` - Show available backups

### Command Line Operations

#### Repository Visibility Management
```bash
# Make all public repositories private
python github_automation.py repo-manager --make-private --filter public

# Make all private repositories public
python github_automation.py repo-manager --make-public --filter private

# Toggle visibility of all repositories
python github_automation.py repo-manager --toggle-visibility --filter all
```

#### Follow/Unfollow Automation
```bash
# Auto-follow followers of a user
python github_automation.py repo-manager --auto-follow octocat --limit 50

# Follow back your followers
python github_automation.py repo-manager --follow-back --follow-back-limit 100

# Unfollow users who don't follow back
python github_automation.py repo-manager --unfollow-nonfollowers --min-days 7

# Use whitelist to protect specific users
python github_automation.py repo-manager --unfollow-nonfollowers --whitelist ./data/whitelist.txt
```

#### Advanced User Operations
```bash
# Follow verified users only
python github_automation.py repo-manager --auto-follow techleader --filter-verified

# Follow users with minimum follower count
python github_automation.py repo-manager --auto-follow developer --min-followers 500 --limit 25
```

### Persistent Mode
Run continuously until manual exit:
```bash
python github_automation.py repo-manager --persistent
```

## Examples

### Example 1: Basic Follow Operations
```bash
# Start interactive mode
python github_automation.py repo-manager --interactive

# Follow a user
> follow octocat

# Check follow status
> check octocat

# Get user statistics
> stats torvalds
```

### Example 2: Repository Management
```bash
# Create a new repository
> create my-awesome-project

# Clone an existing repository
> clone https://github.com/user/repository
```

### Example 3: Advanced User Search
```bash
# Search for users
> users

# Follow prompts to set criteria:
# - Minimum followers: 100
# - Minimum repositories: 5
# - Programming language: Python
# - Location: San Francisco
```

### Example 4: Bulk Operations
```bash
# Auto-follow with criteria
python github_automation.py repo-manager --auto-follow python-dev \
    --min-followers 100 \
    --filter-verified \
    --limit 50

# Cleanup non-followers
python github_automation.py repo-manager --unfollow-nonfollowers \
    --whitelist ./data/whitelist.txt \
    --min-days 14
```

## File Structure

```
Github-Repository-Manager/
├── core/                   # Core functionality
│   ├── github_api.py      # GitHub API client
│   ├── file_manager.py    # File operations
│   ├── logger.py          # Logging system
│   └── validators.py      # Input validation
├── cli/                   # Command-line interface
│   ├── commands.py        # CLI commands
│   └── interactive.py     # Interactive mode
├── data/                  # Data storage
│   └── whitelist.txt      # Protected users list
├── github_automation.py   # Main entry point
├── pyproject.toml         # Project configuration
└── LICENSE               # MIT License
```

## Dependencies

- `aiofiles` - Asynchronous file operations
- `aiohttp` - Async HTTP client
- `colorama` - Cross-platform colored output
- `cryptography` - Security utilities
- `httpx` - Modern HTTP client
- `requests` - HTTP library
- `tqdm` - Progress bars

## Performance

- **Asynchronous Operations**: All I/O operations use async/await patterns
- **Rate Limit Optimization**: Intelligent handling of GitHub API limits
- **Memory Efficient**: Optimized for large-scale operations
- **Error Resilient**: Comprehensive error handling and recovery

## Troubleshooting

### Authentication Issues
```bash
# Verify token is set
echo $GITHUB_TOKEN

# Check token validity in interactive mode
> status
```

### Rate Limit Problems
```bash
# Check current limits
> status

# Wait for reset or reduce operation frequency
```

### Common Error Solutions

**Problem**: `GITHUB_TOKEN environment variable is required`
**Solution**: Set your GitHub token in the `.env` file

**Problem**: `Rate limit exceeded`
**Solution**: Wait for rate limit reset (shown in status command)

**Problem**: `Permission denied for repository operations`
**Solution**: Ensure token has `repo` scope for private repositories

## License

MIT License - see [LICENSE](LICENSE) file for details.

**Author**: RafalW3bCraft  
**Email**: thewhitefalcon13@proton.me

---

Built for efficient GitHub automation with performance and reliability in mind.