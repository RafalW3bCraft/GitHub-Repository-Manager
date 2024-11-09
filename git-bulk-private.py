import requests

# Replace with your GitHub username and personal access token
USERNAME = 'Your-username'
TOKEN = 'PUT-YOUR-TOKEN-HERE'

# Get all repositories for the user
url = f'https://api.github.com/users/{USERNAME}/repos'
response = requests.get(url, auth=(USERNAME, TOKEN))

if response.status_code == 200:
    repos = response.json()
    for repo in repos:
        repo_name = repo['name']
        if repo['private'] is False:  # Check if repo is public
            # Change repository visibility to private
            update_url = f'https://api.github.com/repos/{USERNAME}/{repo_name}'
            update_data = {'private': True}
            update_response = requests.patch(update_url, json=update_data, auth=(USERNAME, TOKEN))
            
            if update_response.status_code == 200:
                print(f'Successfully made {repo_name} private.')
            else:
                print(f'Failed to update {repo_name}: {update_response.json()}')
else:
    print('Failed to retrieve repositories:', response.json())