#!/bin/bash
url="$1"

# Get the video title
video_title=$(yt-dlp --get-title "$url" | sed 's/[^a-zA-Z0-9]/_/g')
output="transcript_${video_title}.txt"

# Download subtitles
yt-dlp --sub-lang en --write-sub --write-auto-sub --skip-download --sub-format vtt "$url"

# Find the most recent .vtt file
vtt_file=$(find $HOME -name "*.en.vtt" -type f -mmin -1 -print -quit)

if [ -f "$vtt_file" ]; then
    echo "Processing subtitle file: $vtt_file"
    # Clean VTT file and remove duplicates
    cat "$vtt_file" | \
    grep -v "^WEBVTT" | \
    grep -v "^NOTE" | \
    grep -v "^Kind:" | \
    grep -v "^Language:" | \
    sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}.*-->.*//' | \
    sed -E 's/<[^>]*>//g' | \
    sed -E 's/align:start position:0%//' | \
    grep -v "^$" | \
    awk '!seen[$0]++' > "$output"
    
    echo "Created transcript at: $output"
else
    echo "No English subtitles found"
    exit 1
fi
