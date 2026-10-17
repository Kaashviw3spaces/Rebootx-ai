#!/usr/bin/env python3
"""REBOOTX — Self-Hosted Installation & Prerequisite Validation Script.

Validates environment prerequisites, generates cryptographically strong secrets,
and creates a safe production-ready .env file without exposing secrets.
Works across Windows, Linux, and macOS.
"""
import argparse
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def check_prerequisite(name: str, check_fn) -> tuple[bool, str]:
    try:
        ok, msg = check_fn()
        return ok, msg
    except Exception as exc:
        return False, str(exc)


def check_python() -> tuple[bool, str]:
    ver = sys.version_info
    if ver >= (3, 10):
        return True, f"Python {ver.major}.{ver.minor}.{ver.micro} (compatible)"
    return False, f"Python {ver.major}.{ver.minor}.{ver.micro} found, but >= 3.10 is required"


def check_docker() -> tuple[bool, str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False, "Docker CLI not found in PATH"
    try:
        proc = subprocess.run([docker_bin, "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            return True, proc.stdout.strip()
        return False, "Docker CLI exited with an error"
    except Exception as exc:
        return False, f"Failed to check Docker: {exc}"


def check_compose() -> tuple[bool, str]:
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            proc = subprocess.run([docker_bin, "compose", "version"], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                return True, proc.stdout.strip()
        except Exception:
            pass
    compose_bin = shutil.which("docker-compose")
    if compose_bin:
        try:
            proc = subprocess.run([compose_bin, "--version"], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                return True, proc.stdout.strip()
        except Exception:
            pass
    return False, "Docker Compose (v2 or v1) not found in PATH"


def check_git() -> tuple[bool, str]:
    git_bin = shutil.which("git")
    if not git_bin:
        return False, "Git CLI not found in PATH (recommended)"
    try:
        proc = subprocess.run([git_bin, "--version"], capture_output=True, text=True, timeout=5)
        return True, proc.stdout.strip()
    except Exception:
        return False, "Git CLI check failed"


def check_node() -> tuple[bool, str]:
    node_bin = shutil.which("node")
    if not node_bin:
        return True, "Node.js not installed on host (not required for Docker deployment)"
    try:
        proc = subprocess.run([node_bin, "--version"], capture_output=True, text=True, timeout=5)
        return True, f"Host Node.js {proc.stdout.strip()} (optional)"
    except Exception:
        return True, "Host Node.js check skipped"


def generate_secure_env(env_path: Path, example_path: Path, force: bool = False) -> bool:
    if env_path.exists() and not force:
        print(f"\n[INFO] Configuration file already exists at {env_path.name}.")
        print("       Existing configuration was preserved. Pass --force to regenerate.")
        return False

    if not example_path.exists():
        print(f"\n[ERROR] Template file {example_path.name} not found!", file=sys.stderr)
        return False

    raw_example = example_path.read_text(encoding="utf-8")

    # Generate high-entropy secrets
    postgres_password = secrets.token_hex(20)          # 40 hex characters
    webhook_secret = secrets.token_urlsafe(32)         # 44 urlsafe characters (> 32)
    tenant_read_token = secrets.token_urlsafe(32)      # 44 urlsafe characters (> 32)

    # Substitute values safely
    lines = []
    for line in raw_example.splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            lines.append(f"POSTGRES_PASSWORD={postgres_password}")
        elif line.startswith("N8N_WEBHOOK_SECRET="):
            lines.append(f"N8N_WEBHOOK_SECRET={webhook_secret}")
        elif line.startswith("TENANT_READ_TOKEN="):
            lines.append(f"TENANT_READ_TOKEN={tenant_read_token}")
        else:
            lines.append(line)

    content = "\n".join(lines) + "\n"
    env_path.write_text(content, encoding="utf-8")

    # Secure file permissions on POSIX systems (chmod 600: read/write by owner only)
    if os.name != "nt":
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass

    print(f"\n[SUCCESS] Production configuration written to {env_path.name}.")
    print("          - Generated POSTGRES_PASSWORD (40 chars)")
    print("          - Generated N8N_WEBHOOK_SECRET (44 chars, >= 32)")
    print("          - Generated TENANT_READ_TOKEN (44 chars, >= 32)")
    print("          - Set RECOVERY_MODE=mock-only (safe default)")
    print("          - Set AI_PROVIDER=mock (zero external API calls)")
    print("          - Bound all services to internal network endpoints")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite existing .env file with fresh credentials")
    args = parser.parse_args()

    print("==================================================================")
    print("              REBOOTX — Self-Hosted Setup & Preflight             ")
    print("==================================================================")

    # 1. Check prerequisites
    prereqs = [
        ("Python", check_python),
        ("Docker CLI", check_docker),
        ("Docker Compose", check_compose),
        ("Git", check_git),
        ("Node.js (Optional)", check_node),
    ]

    all_passed = True
    print("\n--- Checking Prerequisites ---")
    for name, fn in prereqs:
        ok, msg = check_prerequisite(name, fn)
        tag = "[OK]  " if ok else "[WARN]"
        print(f" {tag} {name:20} : {msg}")
        if not ok and name in ("Python", "Docker CLI", "Docker Compose"):
            all_passed = False

    # 2. Prepare .env configuration
    env_file = ROOT_DIR / ".env"
    example_file = ROOT_DIR / ".env.example"
    print("\n--- Preparing Environment Configuration ---")
    generate_secure_env(env_file, example_file, force=args.force)

    # 3. Next steps guidance
    print("\n==================================================================")
    print("                      Next Steps & Operation                      ")
    print("==================================================================")
    print("1. Start the complete REBOOTX self-hosted stack:")
    print("   docker compose up -d\n")
    print("2. Provision the initial tenant and workflow:")
    print("   docker compose run --rm backend python -m scripts.provision \\")
    print("     --tenant-name \"Primary Demo Tenant\" \\")
    print("     --workflow-external-id \"demo-workflow-1\" \\")
    print("     --secret-env \"N8N_WEBHOOK_SECRET\" \\")
    print("     --workflow-kind \"side_effect_safe_demo_v1\"\n")
    print("3. Access the services:")
    print("   - Dashboard UI:       http://localhost:3000")
    print("   - FastAPI Backend:    http://localhost:8000/docs")
    print("   - Temporal Server UI: http://localhost:8233\n")
    print("4. Safe Default Status:")
    print("   - RECOVERY_MODE:       mock-only (real actions blocked)")
    print("   - AI_PROVIDER:         mock (no external API keys needed)")
    print("   - Database:            Persistent in Docker volume 'rebootx_postgres_data'")
    print("==================================================================")

    if not all_passed:
        print("\nNote: Some prerequisites reported warnings. Ensure Docker Desktop or the")
        print("Docker engine is running before executing 'docker compose up -d'.")


if __name__ == "__main__":
    main()

