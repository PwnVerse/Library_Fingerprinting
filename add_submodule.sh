#!/bin/bash

# Check if the script is run from a Git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: This script must be run from inside a Git repository."
    exit 1
fi

# Loop through each directory in the current directory
for dir in */; do
    # Skip if not a directory or if it doesn't contain a Git repository
    if [ ! -d "$dir" ] || [ ! -d "$dir/.git" ]; then
        echo "Skipping $dir (not a valid Git repository)"
        continue
    fi

    # Move into the directory
    cd "$dir" || exit

    # Get the remote URL of the repository
    repo_url=$(git remote get-url origin 2>/dev/null)

    if [ -z "$repo_url" ]; then
        echo "Skipping $dir (no remote URL found)"
        cd ..
        continue
    fi

    # Move back to the parent repository
    cd ..

    # Add the directory as a submodule
    submodule_path="${dir%/}" # Remove the trailing slash from the directory name
    echo "Adding $submodule_path as a submodule with URL $repo_url"
    git submodule add "$repo_url" "$submodule_path"
done

# Initialize and update submodules
echo "Initializing and updating submodules..."
git submodule update --init --recursive

echo "All valid submodules have been added!"