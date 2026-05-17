#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

export AWS_PROFILE="${AWS_PROFILE:-forgemoe}"
export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
export AWS_PAGER=""
export AWS_CLI_AUTO_PROMPT=off

S3_BUCKET="${S3_BUCKET:-forgemoe-coder-568844635400-us-west-2-an}"
PRIVATE_STATE="${HOME}/forgemoe-private/FORGEMOE_PRIVATE_PROJECT_STATE.md"

echo "=== VSCode/AWS workspace doctor ==="
echo "root: ${ROOT_DIR}"
echo

echo "=== Required tools ==="
git --version
aws --version
gh --version | head -n 1
tar --version | head -n 1
gzip --version | head -n 1
python3 --version
test -x ".venv/bin/python"
.venv/bin/python --version
.venv/bin/python -m pytest --version
.venv/bin/ruff --version
code --version | sed -n '1,2p'
echo

echo "=== VSCode extensions ==="
code --list-extensions | grep -Fx amazonwebservices.aws-toolkit-vscode
code --list-extensions | grep -Fx github.vscode-pull-request-github
code --list-extensions | grep -Fx ms-python.python
code --list-extensions | grep -Fx ms-python.vscode-pylance
echo

echo "=== Git state ==="
test "$(git branch --show-current)" = "main"
git remote get-url origin
git status --short
echo

echo "=== GitHub auth ==="
gh auth status
echo

echo "=== AWS identity and S3 access ==="
aws sts get-caller-identity --output json
aws s3 ls "s3://${S3_BUCKET}/reports/" >/dev/null
aws s3 ls "s3://${S3_BUCKET}/configs/project_scaffold/" >/dev/null
echo "s3_access: OK"
echo

echo "=== Private local state ==="
test -f "${HOME}/forgemoe-aws.env"
test -f "${PRIVATE_STATE}"
test ! -e "${ROOT_DIR}/forgemoe-aws.env"
test ! -e "${ROOT_DIR}/FORGEMOE_PRIVATE_PROJECT_STATE.md"
echo "private_state: OK"
echo

echo "VSCODE_AWS_WORKSPACE_DOCTOR_OK"
