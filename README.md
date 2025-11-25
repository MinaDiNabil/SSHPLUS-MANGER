# SSHPLUS

## Installation from Public Repository

```bash
apt update -y && apt upgrade -y && wget https://raw.githubusercontent.com/MinaDiNabil/SSHPLUS-MANGER/main/Plus && chmod 777 Plus && ./Plus
```

## Installation from Private Repository

If you're installing from a private GitHub repository, you'll need to use a Personal Access Token (PAT).

### Step 1: Create a GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name (e.g., "SSHPLUS Installation")
4. Select scopes: **repo** (Full control of private repositories)
5. Click "Generate token" and copy the token

### Step 2: Install using your token

Replace `YOUR_GITHUB_TOKEN` with your actual token, and `YOUR_USERNAME/YOUR_REPO` with your repository details:

```bash
apt update -y && apt upgrade -y
GITHUB_TOKEN="YOUR_GITHUB_TOKEN"
GITHUB_USER="YOUR_USERNAME"
GITHUB_REPO="YOUR_REPO"
BRANCH="main"

wget --header="Authorization: token ${GITHUB_TOKEN}" \
     --header="Accept: application/vnd.github.v3.raw" \
     -O Plus \
     "https://api.github.com/repos/${GITHUB_USER}/${GITHUB_REPO}/contents/Plus?ref=${BRANCH}"

chmod 777 Plus && ./Plus
```

### Quick Installation (One-liner for Private Repo)

```bash
apt update -y && apt upgrade -y && GITHUB_TOKEN="YOUR_TOKEN" && wget --header="Authorization: token ${GITHUB_TOKEN}" --header="Accept: application/vnd.github.v3.raw" -O Plus "https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/contents/Plus?ref=main" && chmod 777 Plus && ./Plus
```

## Root Access

### From Public Repository
```bash
wget https://raw.githubusercontent.com/MinaDiNabil/SSHPLUS-MANGER/main/senharoot.sh && chmod 777 senharoot.sh && ./senharoot.sh
```

### From Private Repository
```bash
GITHUB_TOKEN="YOUR_GITHUB_TOKEN" && wget --header="Authorization: token ${GITHUB_TOKEN}" --header="Accept: application/vnd.github.v3.raw" -O senharoot.sh "https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/contents/senharoot.sh?ref=main" && chmod 777 senharoot.sh && ./senharoot.sh
```

## Notes

- **Security Warning**: Never share your GitHub token publicly
- For private repositories, the token must have `repo` scope permissions
- Tokens can be revoked anytime from GitHub settings
- Consider using environment variables or secure methods to store tokens instead of hardcoding them
