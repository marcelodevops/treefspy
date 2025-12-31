#!/usr/bin/env bash

input="$1"

while IFS= read -r line; do
    # Skip header or blank lines
    [[ -z "$line" || "$line" == Project* ]] && continue

    # Remove tree characters
    clean=$(echo "$line" | sed -E 's/[│├└─]+//g' | sed -E 's/^[ ]+//')

    # Skip blank after stripping
    [[ -z "$clean" ]] && continue

    # If seems like a directory
    if [[ "$clean" == */ ]]; then
        mkdir -p "$clean"
    else
        mkdir -p "$(dirname "$clean")"
        touch "$clean"
    fi

    echo "Created: $clean"
done < "$input"
