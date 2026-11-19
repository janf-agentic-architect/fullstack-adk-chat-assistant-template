#!/usr/bin/env python3
import os
import subprocess
import sys


def sync_secrets(env_file: str, project_id: str, output_file: str):
    if not os.path.exists(env_file):
        print(f"Warning: {env_file} does not exist. Skipping secrets sync.", file=sys.stderr)
        return

    pairs = []
    print(f"Syncing all variables from {env_file} to GCP Secret Manager (project: {project_id})...")

    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("\"'")

            # System/platform variables must remain plaintext env vars, not Secret Manager secrets
            if key in ["GOOGLE_CLOUD_PROJECT", "GOOGLE_GENAI_USE_ENTERPRISE", "GOOGLE_CLOUD_LOCATION"]:
                continue

            secret_id = key.lower().replace("_", "-")
            pairs.append(f"{key}={secret_id}")

            # Check if secret already exists
            check = subprocess.run(
                ["gcloud", "secrets", "describe", secret_id, f"--project={project_id}"],
                capture_output=True,
            )

            if check.returncode != 0:
                print(f"  Creating secret: {secret_id}...")
                subprocess.run(
                    [
                        "gcloud",
                        "secrets",
                        "create",
                        secret_id,
                        "--replication-policy=automatic",
                        f"--project={project_id}",
                    ],
                    check=True,
                    capture_output=True,
                )

            # Add new secret version with current value
            subprocess.run(
                [
                    "gcloud",
                    "secrets",
                    "versions",
                    "add",
                    secret_id,
                    "--data-file=-",
                    f"--project={project_id}",
                ],
                input=val.encode(),
                check=True,
                capture_output=True,
            )
            print(f"  ✓ {key} -> secret: {secret_id}")

    secrets_str = ",".join(pairs)
    with open(output_file, "w") as f:
        f.write(secrets_str)

    print(f"✓ All variables synced to GCP Secret Manager ({len(pairs)} secrets).")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: sync_secrets.py <env_file> <project_id> <output_file>", file=sys.stderr)
        sys.exit(1)

    sync_secrets(sys.argv[1], sys.argv[2], sys.argv[3])
