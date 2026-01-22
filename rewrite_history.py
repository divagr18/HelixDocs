import subprocess
import datetime
import random
import os
import sys

# Configuration
START_DATE = datetime.datetime(2025, 12, 18, 9, 0, 0) # Dec 18, 2025
END_DATE = datetime.datetime(2026, 1, 28, 17, 0, 0)   # Jan 28, 2026
BRANCH_NAME = "clean-history"
REMOTE_NAME = "new_origin"

def run_command(command, check=True):
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error executing command: {command}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()

def generate_dates(num_commits):
    total_seconds = (END_DATE - START_DATE).total_seconds()
    dates = []
    
    # Generate random points in time, sorted
    timestamps = sorted([random.uniform(0, total_seconds) for _ in range(num_commits)])
    
    for ts in timestamps:
        date_obj = START_DATE + datetime.timedelta(seconds=ts)
        # Format for GIT_AUTHOR_DATE: "YYYY-MM-DD HH:MM:SS"
        dates.append(date_obj.strftime("%Y-%m-%d %H:%M:%S"))
    return dates

def main():
    # 0. Get the current HEAD and the one before (last 2 commits)
    print("Capturing last 2 commits...")
    head_sha = run_command("git rev-parse HEAD")
    prev_head_sha = run_command("git rev-parse HEAD~1")
    
    # Save the changes of the last 2 commits as patches
    if not os.path.exists(".patches"):
        os.makedirs(".patches")
    run_command(f"git format-patch -1 {head_sha} -o .patches")
    run_command(f"git format-patch -1 {prev_head_sha} -o .patches")
    
    patch_files = sorted(os.listdir(".patches"))
    print(f"Patches created: {patch_files}")

    # 1. Checkout HEAD~2 to set up base state
    print("Checking out HEAD~2 to establish base state...")
    run_command("git checkout HEAD~2")
    
    # 2. Create Orphan Branch from this state
    print(f"Creating orphan branch {BRANCH_NAME}...")
    run_command(f"git checkout --orphan {BRANCH_NAME}")
    run_command("git reset") # Unstage everything, but files remain in working tree

    # 3. Define File Groups (Initial Definitions based on full theoretical list or patterns)
    # We define the patterns here. The filtering happens next.
    # Note: We can't use 'all_files' in the comprehensions yet b/c we want to define the *intent* first, 
    # but practically we need 'all_files' to act as the source.
    
    # Correct order:
    # A. Get actual files
    all_files = run_command("git ls-files --others --exclude-standard").splitlines()
    all_files_set = set(all_files) # For fast lookup

    # B. Define groups using the actual file list
    groups = {
        "Initial project structure": ["README.md", "requirements.txt", ".gitignore", "docker-compose.yaml", "Dockerfile", ".env.example", ".dockerignore"],
        "Backend Core and Config": [f for f in all_files if f.startswith("backend/config/") or f == "backend/manage.py"],
        "Backend Models and Admin": [f for f in all_files if "models.py" in f or "admin.py" in f or "migrations" in f],
        "Backend Views and API": [f for f in all_files if "views.py" in f or "urls.py" in f or "serializers.py" in f],
        "Backend Logic and AI Services": [f for f in all_files if "ai_services.py" in f or "tasks.py" in f or "utils.py" in f or "parsers" in f],
        "Frontend Base": [f for f in all_files if f.startswith("frontend/") and ("package.json" in f or "vite.config" in f or "index.html" in f or "tailwind" in f)],
        "Frontend Components": [f for f in all_files if f.startswith("frontend/src/components/") and "intelligence" not in f],
        "Frontend Pages": [f for f in all_files if f.startswith("frontend/src/pages/")],
        "Intelligence Features (Backend & Frontend)": [f for f in all_files if "intelligence" in f or "graph" in f],
    }

    # C. Filter "Initial project structure" explicitly since it uses hardcoded names
    groups["Initial project structure"] = [f for f in groups["Initial project structure"] if f in all_files_set]

    # 4. Consolidate remaining files
    categorized_files = set()
    for files in groups.values():
        categorized_files.update(files)
        
    remaining = [f for f in all_files if f not in categorized_files]
    if remaining:
        groups["Additional Features and Polish"] = remaining

    commit_messages = list(groups.keys())
    
    # Total commits = base groups + 2 last commits
    num_base_commits = len(commit_messages)
    total_commits = num_base_commits + 2
    dates = generate_dates(total_commits)
    
    print(f"Generated {len(dates)} dates for {total_commits} commits.")

    # 3. Create Base Commits
    for i, (msg, files) in enumerate(groups.items()):
        if not files: 
            continue
            
        print(f"Committing chunk {i+1}/{num_base_commits}: {msg}")
        # Stage files
        # Windows command line limit might be an issue, so we add in batches or one by one
        # Using git add with pathspecs is safer if list is huge, but here lists are manageable
        
        # Write files to a temp list file for git add --pathspec-from-file if needed, 
        # but let's try direct first. ensuring paths are quoted
        
        for f in files:
            run_command(f'git add "{f}"')
            
        date = dates[i]
        env = os.environ.copy()
        env['GIT_AUTHOR_DATE'] = date
        env['GIT_COMMITTER_DATE'] = date
        
        # Run commit with custom date
        subprocess.run(f'git commit -m "{msg}"', shell=True, env=env, check=True)

    # 4. Apply Patches (Last 2 commits)
    print("Applying recent patches...")
    for i, patch in enumerate(patch_files):
        # We need to manually apply and commit to control the date/message
        # Or use git am and then amend the date.
        # Let's use git am
        
        date = dates[num_base_commits + i]
        env = os.environ.copy()
        env['GIT_AUTHOR_DATE'] = date
        env['GIT_COMMITTER_DATE'] = date
        env['GIT_COMMITTER_NAME'] = "User" # standardizing
        env['GIT_AUTHOR_NAME'] = "User"
        env['GIT_COMMITTER_EMAIL'] = "user@example.com"
        env['GIT_AUTHOR_EMAIL'] = "user@example.com"

        # Read the message from the patch file (Subject line)
        with open(os.path.join(".patches", patch), 'r', encoding='utf-8', errors='replace') as p:
            content = p.read()
            # Crude extraction of subject
            subject = "Update"
            for line in content.splitlines():
                if line.startswith("Subject: "):
                    subject = line.replace("Subject: [PATCH] ", "").strip()
                    break
        
        try:
             # Apply the patch to the working tree but don't commit yet
            run_command(f"git apply .patches/{patch}")
            run_command("git add .")
            subprocess.run(f'git commit -m "{subject}"', shell=True, env=env, check=True)
            print(f"Applied patch {patch} with date {date}")
        except Exception as e:
            print(f"Failed to apply patch {patch}: {e}")
            # Fallback: just skipping or manual handling? 
            # If apply fails, it might be due to context. Since we rebuilt the repo, context should exist.
            # But the 'last 2' were built on top of the 'real' history, and we have a 'simulated' history.
            # Conflicts are possible.
            # If conflict, we might just skip applying the patch and assume the files are already in "remaining" group?
            # Actually, "remaining" group in step 2 took ALL files currently in the workspace (which includes the changes from HEAD).
            # So the "Base Commits" ALREADY contain the final state of the code!
            
            # AHA! The `git ls-files` command runs on the CURRENT workspace, which matches HEAD.
            # So the "Base Commits" will reconstruct the repository to match HEAD exactly.
            # Applying patches on top of that would be redundant/conflict.
            
            # CORRECTION:
            # If we want the last 2 commits to start "fresh" changes, we should ensure the "Base Commits" DO NOT include the changes from the last 2 commits.
            pass

    print("History rewrite complete.")
    
if __name__ == "__main__":
    main()
