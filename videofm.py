'''
video.fm
Create video compilations of your top songs from Last.fm.
'''

import os
import sys
import codecs
import subprocess

# Debugging function for encoding issues
def safe_decode(data):
    """Safely decode bytes to string, handling different types."""
    if data is None:
        return None
    if isinstance(data, bytes):
        return data.decode('utf-8', errors='replace')
    if isinstance(data, str):
        return data
    return str(data)

# Fix for multiprocessing with PyInstaller
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    os.environ['PYTHONHASHSEED'] = '1'
    # Handle multiprocessing freeze support
    import multiprocessing
    multiprocessing.freeze_support()

# Force UTF-8 encoding for stdout
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    
import requests
import yt_dlp
import ffmpeg
import json
import time
import datetime
import calendar
import re
import argparse
import tempfile
from dotenv import load_dotenv
from collections import Counter
from tqdm import tqdm
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from shutil import which

# Determine if running as packaged app
is_frozen = getattr(sys, 'frozen', False)

# Set up paths based on if we're running packaged or as a script
if is_frozen:
    # If running as packaged app, use user's home directory
    base_dir = os.path.expanduser("~/Library/Application Support/video.fm")
    # Ensure directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    # Set cache and video output directories
    CACHE_DIR = os.path.join(base_dir, "cache")
    VIDEO_OUTPUT_DIR = os.path.join(base_dir, "clips")
else:
    # When running as script, use current directory
    CACHE_DIR = "cache"
    VIDEO_OUTPUT_DIR = "clips"

# Parse command-line arguments
parser = argparse.ArgumentParser(description='video.fm - Create music video compilations')
parser.add_argument('--env-path', help='Path to .env file')
parser.add_argument('--output-dir', help='Directory to save output videos')
parser.add_argument('--codec', default='libx264', help='Video codec to use')
parser.add_argument('--lastfm-api-key', help='Last.fm API key')
parser.add_argument('--youtube-api-key', help='YouTube API key')
args = parser.parse_args()

if args and hasattr(args, 'env_path') and args.env_path:
    load_dotenv(args.env_path)
else:
    load_dotenv()  # Fallback to default behavior

SELECTED_CODEC = args.codec if args and hasattr(args, 'codec') and args.codec else "libx264"
    
# ==== Configuration ====
LASTFM_API_KEY = args.lastfm_api_key or os.getenv("LASTFM_API_KEY")
YOUTUBE_API_KEY = args.youtube_api_key or os.getenv("YOUTUBE_API_KEY")
CHORUS_START = "00:01:00"  # Approximate start time of the chorus
CLIP_DURATION = 15  # Duration of each clip in seconds

# ===== USER CONFIGURATION =====
# Codec selection - Change this value to use a different encoder
# Available options:
# - "h264_videotoolbox": Hardware accelerated H.264 (Mac)
# - "libx264": Software H.264 (compatible with all systems)
# - "h264_nvenc": NVIDIA GPU accelerated H.264
# - "h264_amf": AMD GPU accelerated H.264
# - "h264_qsv": Intel QuickSync hardware accelerated H.264
# - "copy": Copy codec (fastest, no re-encoding)

# OLD - SELECTED_CODEC = "libx264"  # Default codec - change this line if needed

# Check if ffmpeg is installed
if not which("ffmpeg"):
    print("FFmpeg not found. Attempting to find bundled FFmpeg...")
    try:
        # Initialize flag to track if we've found FFmpeg
        ffmpeg_found = False
        
        if is_frozen:
            # Check app-bundled FFmpeg first
            base_path = os.path.dirname(sys.executable)
            
            if sys.platform == 'darwin':
                # For macOS app structure
                if '.app' in base_path:
                    # Go up to Contents
                    contents_path = base_path
                    while os.path.dirname(contents_path) and os.path.basename(os.path.dirname(contents_path)) != 'Contents':
                        contents_path = os.path.dirname(contents_path)
                        if contents_path == os.path.dirname(contents_path):  # Prevent infinite loop
                            break
                    
                    # Look for bundled FFmpeg
                    bundled_path = os.path.join(
                        os.path.dirname(contents_path),
                        'Resources/extraResources/bin'
                    )
                    
                    if os.path.exists(os.path.join(bundled_path, 'ffmpeg')):
                        os.environ["PATH"] = bundled_path + os.pathsep + os.environ.get("PATH", "")
                        print(f"✅ Using app-bundled FFmpeg from: {bundled_path}")
                        ffmpeg_found = True
            
            elif sys.platform == 'win32':
                # Windows-specific code here - won't affect Mac
                # For Windows app structure
                base_path = os.path.dirname(sys.executable)
                
                # Try multiple possible locations for extraResources
                resources_path = os.path.join(os.path.dirname(base_path), 'resources')
                extraResources_path = os.path.join(resources_path, 'extraResources', 'bin')
                
                # Print paths for debugging
                print(f"Checking for FFmpeg.exe in {extraResources_path}")
                
                # Check main location first
                if os.path.exists(os.path.join(extraResources_path, 'ffmpeg.exe')):
                    os.environ["PATH"] = extraResources_path + os.pathsep + os.environ.get("PATH", "")
                    print(f"Found bundled FFmpeg in: {extraResources_path}")
                    ffmpeg_found = True
                else:
                    # Try alternate paths (Windows-specific)
                    alternate_paths = [
                        os.path.join(resources_path, 'bin'),
                        os.path.join(base_path, 'resources', 'extraResources', 'bin'),
                        os.path.join(os.path.dirname(os.path.dirname(base_path)), 'resources', 'extraResources', 'bin')
                    ]
                    
                    for alt_path in alternate_paths:
                        print(f"Checking alternate path: {alt_path}")
                        if os.path.exists(os.path.join(alt_path, 'ffmpeg.exe')):
                            os.environ["PATH"] = alt_path + os.pathsep + os.environ.get("PATH", "")
                            print(f"Found bundled FFmpeg in alternate path: {alt_path}")
                            ffmpeg_found = True
                            break
        
        # Continue with existing path checks if not found
        if not ffmpeg_found:
            # Define potential paths based on environment
            if is_frozen:
                # When frozen, check relative to the executable
                base_path = os.path.dirname(sys.executable)
                potential_ffmpeg_paths = [
                    os.path.join(base_path, "bin"),
                    os.path.join(base_path, "Resources", "bin")
                ]
                
                # Add platform-specific paths
                if sys.platform == 'darwin':
                    potential_ffmpeg_paths.extend([
                        "/usr/local/bin",
                        "/opt/homebrew/bin"
                    ])
                elif sys.platform == 'win32':
                    potential_ffmpeg_paths.extend([
                        "C:\\Program Files\\ffmpeg\\bin",
                        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "ffmpeg", "bin")
                    ])
            else:
                # In development mode
                if sys.platform == 'darwin':
                    potential_ffmpeg_paths = [
                        "/usr/local/bin",
                        "/opt/homebrew/bin"
                    ]
                elif sys.platform == 'win32':
                    potential_ffmpeg_paths = [
                        "C:\\Program Files\\ffmpeg\\bin",
                        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "ffmpeg", "bin")
                    ]
                else:
                    potential_ffmpeg_paths = [
                        "/usr/local/bin",
                        "/usr/bin"
                    ]
            
            # Check each potential path
            for check_path in potential_ffmpeg_paths:
                ffmpeg_exe = "ffmpeg.exe" if sys.platform == 'win32' else "ffmpeg"
                if os.path.exists(os.path.join(check_path, ffmpeg_exe)):
                    ffmpeg_path = check_path
                    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")
                    print(f"✅ Found FFmpeg path: {ffmpeg_path}")
                    ffmpeg_found = True
                    break
            
            if not ffmpeg_found:
                print("❌ FFmpeg not found in expected locations")
                print("Please install FFmpeg manually: https://ffmpeg.org/download.html")
                sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to setup FFmpeg: {e}")
        print("Please install FFmpeg manually: https://ffmpeg.org/download.html")
        sys.exit(1)

# Validate API keys before proceeding
if not LASTFM_API_KEY:
    print("❌ Error: LASTFM_API_KEY environment variable is not set")
    print("Please create a .env file with your Last.fm API key or set it in your environment")
    sys.exit(1)
    
if not YOUTUBE_API_KEY:
    print("❌ Error: YOUTUBE_API_KEY environment variable is not set")
    print("Please create a .env file with your YouTube API key or set it in your environment")
    sys.exit(1)

# Create necessary directories
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

def get_youtube_service():
    """Creates and returns a YouTube API service with the current API key."""
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Initialize YouTube service
youtube = get_youtube_service()

def load_cache(filename):
    """Load a JSON cache file from the cache directory.
    
    Args:
        filename: Name of the cache file to load
        
    Returns:
        dict: Loaded cache data, or empty dict if file doesn't exist
    """
    path = os.path.join(CACHE_DIR, filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_cache(data, filename):
    """Save data to a JSON cache file in the cache directory.
    
    Args:
        data: Data to save
        filename: Name of the cache file to save to
    """
    path = os.path.join(CACHE_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# Load cached data
video_cache = load_cache("video_cache.json")
progress = load_cache("progress.json")
lastfm_cache = load_cache("lastfm_cache.json")

# Save caches to ensure they exist
save_cache(video_cache, "video_cache.json") 
save_cache(progress, "progress.json")  
save_cache(lastfm_cache, "lastfm_cache.json") 

# ==== User Configuration ====

# Get Last.fm username
LASTFM_USER = input("Enter your Last.fm username: ").strip()

# Get target year and month
TARGET_YEAR = input("Enter the target year (YYYY): ").strip()
TARGET_MONTH = input("Enter the target month (MM): ").strip()

# Get number of songs to include
while True:
    num_songs_input = input("Enter the number of top songs to include (1-50): ").strip()
    
    if num_songs_input.isdigit():
        num_songs = int(num_songs_input)
        if 1 <= num_songs <= 50:
            NUM_SONGS = num_songs
            break
        else:
            print("❌ Please enter a number between 1 and 50.")
    else:
        print("❌ Invalid input. Please enter a valid number.")

# Display the selected codec to the user
print(f"\n🎬 Using video codec: {SELECTED_CODEC}")

# Ask if user wants to manually input YouTube URLs for missing videos
manual_youtube_input = input(
    "❓ Do you want to manually input YouTube URLs if a search fails? (yes/no): "
).strip().lower()

ALLOW_MANUAL_YOUTUBE = manual_youtube_input == "yes"

# Set up final video filename based on running mode
if args and hasattr(args, 'output_dir') and args.output_dir:
    # Use output directory specified by command line
    FINAL_VIDEO = os.path.join(args.output_dir, f"{LASTFM_USER}_top{NUM_SONGS}_{TARGET_YEAR}_{TARGET_MONTH}.mp4")
else:
    # If no output directory specified, use base directory
    if is_frozen:
        FINAL_VIDEO = os.path.join(base_dir, f"{LASTFM_USER}_top{NUM_SONGS}_{TARGET_YEAR}_{TARGET_MONTH}.mp4")
    else:
        FINAL_VIDEO = f"{LASTFM_USER}_top{NUM_SONGS}_{TARGET_YEAR}_{TARGET_MONTH}.mp4"

# Validate inputs
if not TARGET_YEAR.isdigit() or len(TARGET_YEAR) != 4:
    print("❌ Invalid year format. Please enter a valid year (YYYY).")
    sys.exit(1)

if not TARGET_MONTH.isdigit() or not (1 <= int(TARGET_MONTH) <= 12):
    print("❌ Invalid month format. Please enter a number between 1 and 12.")
    sys.exit(1)

def get_top_songs():
    """Fetch top songs for the specified month and year from Last.fm.
    
    Uses cached data when available. Otherwise, fetches all scrobbles for the 
    month and calculates the top songs.
    
    Returns:
        list: List of tuples containing (artist, title) for the top songs
    """
    cache = load_cache("lastfm_cache.json")
    month_key = f"{LASTFM_USER}_{TARGET_YEAR}-{int(TARGET_MONTH):02d}"
    current_time = int(time.time())

    # Check cache first (valid for 6 hours)
    if month_key in cache and current_time - cache[month_key].get("last_fetched", 0) < 6 * 3600:
        print(f"✅ Using cached data for {month_key}")
        return [
            artist_title
            for artist_title, _ in Counter(map(tuple, cache[month_key]["scrobbles"])).most_common(NUM_SONGS)
        ]

    # Determine timestamp range for the target month
    start_date = int(datetime.datetime(int(TARGET_YEAR), int(TARGET_MONTH), 1).timestamp())
    
    # Calculate end date (first day of next month)
    if int(TARGET_MONTH) < 12:
        end_date = int(datetime.datetime(int(TARGET_YEAR), int(TARGET_MONTH) + 1, 1).timestamp())
    else:
        end_date = int(datetime.datetime(int(TARGET_YEAR) + 1, 1, 1).timestamp())

    all_tracks = []
    page = 1
    found_earliest = False  # Flag to track when we've found the earliest track for the month

    # Fetch all scrobbles from Last.fm API
    while not found_earliest:
        print(f"📥 Fetching page {page} from Last.fm...")

        url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={LASTFM_USER}&api_key={LASTFM_API_KEY}&format=json&limit=1000&page={page}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if "error" in data:
                print(f"❌ Last.fm API error: {data['message']}")
                sys.exit(1)

            # Validate response structure
            if 'recenttracks' not in data or 'track' not in data['recenttracks']:
                print("❌ Error: Invalid API response. The expected data structure is missing.")
                print("Response:", data)
                break

            tracks = data["recenttracks"]["track"]
            if not tracks:
                break  # No more tracks to fetch

            for track in tracks:
                # Skip currently playing track (no timestamp)
                if "date" in track:
                    timestamp = int(track["date"]["uts"])

                    if start_date <= timestamp < end_date:
                        # Track belongs to our target month
                        artist = track["artist"]["#text"]
                        title = track["name"]
                        all_tracks.append((artist, title))
                    elif timestamp < start_date:
                        # We've reached tracks before our target month
                        print(f"✅ Found earliest track for {TARGET_YEAR}-{int(TARGET_MONTH):02d}, stopping fetch.")
                        found_earliest = True
                        break

            if found_earliest:
                break

        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching data: {e}")
            break

        page += 1
        time.sleep(0.5)  # Prevent API rate-limiting

    # Count occurrences of each song and get the most-played ones
    track_counts = Counter(all_tracks).most_common(NUM_SONGS)

    # Save results to cache
    cache[month_key] = {
        "last_fetched": int(time.time()),
        "scrobbles": all_tracks
    }
    save_cache(cache, "lastfm_cache.json") 

    return [song[0] for song in track_counts]

def load_progress():
    """Load progress data from cache."""
    return load_cache("progress.json")

def save_progress(progress):
    """Save progress data to cache."""
    save_cache(progress, "progress.json")

# Load previous progress
progress = load_progress()

def clean_query(text):
    """Remove special characters from text for YouTube search.
    
    Args:
        text: Text string to clean
        
    Returns:
        str: Cleaned text string
    """
    return re.sub(r"[^\w\s-]", "", text)  # Removes punctuation except spaces and hyphens

def update_youtube_api_key():
    """Prompt user for a new YouTube API key and update the service globally."""
    global YOUTUBE_API_KEY, youtube
    print("⚠️ API quota exceeded. Try again tomorrow, or enter a new API key:")
    YOUTUBE_API_KEY = input("Enter new API key: ").strip()
    youtube = get_youtube_service()

def search_youtube_video(artist, title):
    """Search for a YouTube video matching the artist and title.
    
    Optimized for all languages and international music while
    being efficient with API usage. Prioritizes official music videos
    over lyric videos and other content.
    
    Args:
        artist: Artist name
        title: Song title
        
    Returns:
        str: YouTube URL if found, None if not found
    """
    global youtube
    artist, title = str(artist), str(title)
    
    # Use a less aggressive cleaning function for non-Latin scripts
    def gentle_clean(text):
        # Remove only problematic characters but preserve non-Latin characters
        return re.sub(r'[#<>:"?*|/\\]', "", text)
    
    # Create query with minimal cleaning to preserve non-Latin characters
    query = f"{gentle_clean(artist)} - {gentle_clean(title)}"

    # Check progress cache for previously processed queries
    if query in progress:
        print(f"🔁 Using cached result for: {query}")
        return progress[query]

    # Define search queries with international terms
    # These terms are common across many languages
    search_queries = [
        # First try: Artist - Title (exact match)
        f"{artist} - {title}",
        
        # Second try: Add universal terms for official content
        f"{artist} - {title} official MV"
    ]
    
    # Group indicators by priority tiers (1 = highest, 3 = lowest)
    quality_indicators = {
        # Tier 1: Official music videos (highest priority)
        "music_video": [
            # Universal
            "official music video", "official video", "mv", "m/v", "vevo", "music video",
            # Korean
            "뮤직비디오", "official mv", "performance video", "special clip",
            # Japanese
            "ミュージックビデオ", "pv", "オフィシャル",
            # Spanish
            "video oficial",
            # Portuguese 
            "vídeo oficial", "clipe oficial",
            # French
            "clip officiel", "vidéo officielle",
            # Chinese
            "官方完整版", "官方版", "官方高清", "官方网易云", "MV超清", "官方MV", "完整版",
            # Hindi/Indian
            "official video song", "full video song",
            # Russian/Slavic
            "официальное видео", "официальный клип", "официальная премьера", "музыкальный клип",
            # German
            "offizielles video", "offizielles musikvideo", "offizieller musikfilm",
            # Arabic
            "فيديو كليب رسمي", "الفيديو الرسمي",
            # Italian
            "video ufficiale", "videoclip ufficiale",
            # Turkish
            "resmi video", "resmi müzik video", "official video klip",
            # Thai
            "เอ็มวี", "มิวสิควิดีโอ",
            # Indonesian/Malay
            "video klip resmi", "video rasmi", "musik video"
        ],
        
        # Tier 2: Topic channels and official audio (medium priority)
        "audio": [
            # Official audio indicators
            "official audio", "audio oficial", "audio ufficiale", 
            # Generic Topic channel indicators
            "topic", "studio", "audio", "- Topic"
        ],
        
        # Tier 3: Lyric videos (lowest priority)
        "lyrics": [
            "lyric video", "lyrics", "with lyrics", "letra", "paroles",
            "लिरिक्स", "lirik video", "official visualizer", "visualizer"
        ]
    }
    
    # Function to check what tier a video belongs to
    def get_match_tier(video_title_lower, channel_title):
        # Check for Topic channels specifically
        if "- Topic" in channel_title:
            return "audio", "- Topic"
            
        # Check each tier from highest to lowest
        for tier, indicators in quality_indicators.items():
            for indicator in indicators:
                if indicator.lower() in video_title_lower:
                    return tier, indicator
                    
        # No specific tier found
        return None, None
    
    # Try each query
    best_matches = {
        "music_video": None,  # Best music video match
        "audio": None,        # Best audio match
        "lyrics": None,       # Best lyric video match
        "other": None         # Fallback match
    }
    
    for search_query in search_queries:
        try:
            print(f"🔍 Searching: {search_query}...")
            request = youtube.search().list(
                part="snippet",
                q=search_query,
                type="video",
                maxResults=8,
                order="relevance",
                videoCategoryId="10"  # Music category
            )
            response = request.execute()
            
            # First pass: Categorize all videos by tier and find the best in each
            for item in response.get("items", []):
                video_title = item["snippet"]["title"]
                video_title_lower = video_title.lower()
                channel_title = item["snippet"]["channelTitle"]
                
                # Basic relevance check - need either title or artist in the video title
                is_relevant = (title.lower() in video_title_lower) or (artist.lower() in video_title_lower)
                
                # Skip if not even relevant
                if not is_relevant:
                    continue
                    
                # Get the tier of this video
                tier, indicator = get_match_tier(video_title_lower, channel_title)
                
                # If no specific tier, check other quality signals
                is_artist_channel = artist.lower() in channel_title.lower()
                title_exact_match = (
                    f"{artist} - {title}".lower() in video_title_lower or 
                    f"{title} - {artist}".lower() in video_title_lower
                )
                
                # Store the video in its tier if we don't have one yet for this tier
                if 'videoId' in item['id']:  # Add this check
                    video_id = item['id']['videoId']
                    video_data = {
                        'id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'title': video_title,
                        'channel': channel_title,
                        'exact_match': title_exact_match,
                        'artist_channel': is_artist_channel,
                        'indicator': indicator
                    }
                    
                    # High-quality perfect match
                    if title_exact_match or (is_artist_channel and title.lower() in video_title_lower):
                        # Put in appropriate tier, or "other" if no specific tier
                        tier_key = tier if tier else "other"
                        if not best_matches[tier_key]:
                            best_matches[tier_key] = video_data
                    elif is_relevant:
                        # Less perfect but still relevant match
                        tier_key = tier if tier else "other"
                        if not best_matches[tier_key]:
                            best_matches[tier_key] = video_data
            
            # If we found at least one good match, stop searching
            if any(best_matches.values()):
                break
                
        except HttpError as e:
            if e.resp.status == 403:
                # API quota exceeded, ask for a new key
                update_youtube_api_key()
            else:
                raise
    
    # Return the best match based on priority tier
    for tier in ["music_video", "audio", "lyrics", "other"]:
        if best_matches[tier]:
            match = best_matches[tier]
            
            # Determine the match type description
            if tier == "music_video":
                match_type = "music video"
            elif tier == "audio":
                match_type = "audio" if match['indicator'] != "- Topic" else "topic channel"
            elif tier == "lyrics":
                match_type = "lyric video"
            else:
                match_type = "relevant video"
                
            print(f"✅ Found {match_type}: {match['url']}")
            print(f"   Title: '{match['title']}'")
            print(f"   Channel: {match['channel']}")
            
            # Save results in both caches
            video_cache[query] = match['url']
            save_cache(video_cache, "video_cache.json")
            progress[query] = match['url']
            save_progress(progress)
            
            return match['url']
    
    # No matches found through automatic search
    print(f"❌ No valid video found for {artist} - {title}")
    
    # Allow user manual input if enabled
    if ALLOW_MANUAL_YOUTUBE:
        user_input = input(f"❌ No valid video found for {artist} - {title}. Enter a manual YouTube URL (or press Enter to skip): ").strip()
        
        if user_input.startswith("https://www.youtube.com/watch"):
            return user_input
    
    return None

def download_video(video_url, output_path, start_time=None, duration=None):
    """Download a video and optionally extract a precise clip.
    
    Args:
        video_url: YouTube URL to download
        output_path: Path to save the output video
        start_time: Start time for clip extraction (string HH:MM:SS or seconds)
        duration: Duration of clip in seconds
        
    Returns:
        bool: True if successful, False otherwise
    """

    # Windows-specific handling
    if sys.platform == 'win32':
        print("Windows platform detected - using hidden batch approach for download")
        try:
            # Create Windows-appropriate paths
            base_dir = os.path.expanduser("~/AppData/Local/video.fm/clips")
            os.makedirs(base_dir, exist_ok=True)
            
            # Create temporary download path
            tmp_download_path = output_path.replace(".mp4", "_download.mp4")
            
            print(f"Downloading from {video_url} to {tmp_download_path}")
            
            # Create a temporary batch file to run yt-dlp
            batch_file = os.path.join(base_dir, "download.bat")
            
            # Write batch file contents for downloading - with hidden window execution
            with open(batch_file, "w") as f:
                f.write(f'@echo off\n')
                f.write(f'echo Downloading with yt-dlp...\n')
                f.write(f'yt-dlp "{video_url}" -o "{tmp_download_path}" --format mp4\n')
            
            # Execute batch file with hidden window
            print(f"Executing hidden batch file for download")
            
            # Use startupinfo to hide the console window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
            # Run the process with hidden window
            subprocess.run(batch_file, startupinfo=startupinfo)
            
            # Clean up batch file
            try:
                os.remove(batch_file)
            except:
                pass
            
            # Check if download succeeded, then proceed with normal processing
            if os.path.exists(tmp_download_path) and os.path.getsize(tmp_download_path) > 0:
                print(f"Download successful: {tmp_download_path}")
                
                # Extract clip if needed
                if start_time is not None and duration is not None:
                    # Convert start_time to seconds if it's in HH:MM:SS format
                    if isinstance(start_time, str) and ":" in start_time:
                        h, m, s = map(int, start_time.split(":"))
                        start_seconds = h * 3600 + m * 60 + s
                    else:
                        start_seconds = int(start_time)
                    
                    # Format time for ffmpeg
                    start_time_str = str(datetime.timedelta(seconds=start_seconds))
                    
                    print(f"✂️ Extracting {duration}s clip starting at {start_time_str}")
                    
                    # Use os.system for clip extraction to avoid encoding issues
                    cmd = f'ffmpeg -i "{tmp_download_path}" -ss {start_time_str} -t {duration} -c:v {SELECTED_CODEC} -c:a aac -b:a 192k -r 30 "{output_path}" -y'
                    print(f"Running command: {cmd}")
                    os.system(cmd)
                    
                    # Clean up downloaded file
                    try:
                        os.remove(tmp_download_path)
                    except:
                        pass
                    
                    return os.path.exists(output_path)
                else:
                    # If no clip extraction needed, just rename
                    os.rename(tmp_download_path, output_path)
                    return True
            else:
                print(f"Download failed: {tmp_download_path} not found or empty")
                return False
        
        except Exception as e:
            print(f"❌ Error during Windows approach: {type(e).__name__}: {str(e)}")
            return False
    
    # Original code for non-Windows platforms
    
    # Ensure all path and URL arguments are strings, not bytes
    if isinstance(video_url, bytes):
        video_url = video_url.decode('utf-8')
    if isinstance(output_path, bytes):
        output_path = output_path.decode('utf-8')
    if isinstance(start_time, bytes) and start_time is not None:
        start_time = start_time.decode('utf-8')
    
    # Temporary paths for processing
    tmp_path = output_path.replace(".mp4", "_full.mp4")
    tmp_clip_path = output_path.replace(".mp4", "_tmp.mp4")
    
    # Create progress bar for download
    progress_bar = tqdm(total=100, desc="Downloading", unit="%", position=0, leave=True)

    def progress_hook(d):
        """Update progress bar during download."""
        if d['status'] == 'downloading' and 'downloaded_bytes' in d and 'total_bytes' in d:
            percentage = (d['downloaded_bytes'] / d['total_bytes']) * 100
            progress_bar.n = percentage
            progress_bar.refresh()
        elif d['status'] == 'finished':
            progress_bar.n = 100
            progress_bar.close()
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': tmp_path,
        'progress_hooks': [progress_hook],
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': True,  # Continue on download errors
        'noplaylist': True,
        'nocheckcertificate': True,
        'prefer_insecure': True,  # Try to avoid HTTPS issues
        'socket_timeout': 15
    }
    
    try:
        # Step 1: Download the video
        print(f"Starting download for URL: {video_url}")
        print(f"Output path for download: {tmp_path}")
        
        # Make sure paths are appropriate for Windows
        if sys.platform == 'win32':
            # Remove any problematic characters from paths
            tmp_path = tmp_path.replace('/', '\\')
            output_path = output_path.replace('/', '\\')
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
            
        # Check if download succeeded
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            print(f"✅ Download successful: {tmp_path} ({os.path.getsize(tmp_path)} bytes)")
        else:
            print(f"❌ Download failed: File not found or empty at {tmp_path}")
            return False
        
        # Step 2: Extract clip if needed
        if start_time is not None and duration is not None and os.path.exists(tmp_path):
            # Convert start_time to seconds if it's in HH:MM:SS format
            if isinstance(start_time, str) and ":" in start_time:
                h, m, s = map(int, start_time.split(":"))
                start_seconds = h * 3600 + m * 60 + s
            else:
                start_seconds = int(start_time)
            
            # Format time for ffmpeg
            start_time_str = str(datetime.timedelta(seconds=start_seconds))
            
            print(f"✂️ Extracting {duration}s clip starting at {start_time_str}")
            
            # For Method 1:
            try:
                # Method 1: Direct extraction with selected codec
                cmd1 = f'ffmpeg -i "{tmp_path}" -ss {start_time_str} -t {duration} -c:v {SELECTED_CODEC} -c:a aac -b:a 192k -r 30 -vsync cfr "{output_path}" -y -loglevel warning'
                print(f"Running FFmpeg command (method 1): {cmd1}")
                
                # Use subprocess instead of os.system
                process1 = subprocess.run(cmd1, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                exit_code1 = process1.returncode
                
                # Print more detailed error information if available
                if exit_code1 != 0:
                    stderr1 = safe_decode(process1.stderr)
                    stdout1 = safe_decode(process1.stdout)
                    print(f"⚠️ FFmpeg method 1 exited with code: {exit_code1}")
                    print(f"FFmpeg stderr: {stderr1}")
                    print(f"FFmpeg stdout: {stdout1}")
                
                # Check if successful
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    print(f"✅ Clip extracted successfully to {output_path}")
                else:
                    print("⚠️ Clip extraction failed with method 1, trying method 2...")
                    
                    # Method 2: Two-pass with segment extraction
                    cmd2 = f'ffmpeg -i "{tmp_path}" -ss {start_time_str} -t {duration} -c copy "{tmp_clip_path}" -y -loglevel warning'
                    print(f"Running FFmpeg command (method 2, part 1): {cmd2}")
                    
                    process2 = subprocess.run(cmd2, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    exit_code2 = process2.returncode
                    
                    if exit_code2 != 0:
                        stderr2 = safe_decode(process2.stderr)
                        stdout2 = safe_decode(process2.stdout)
                        print(f"⚠️ FFmpeg method 2 part 1 exited with code: {exit_code2}")
                        print(f"FFmpeg stderr: {stderr2}")
                        print(f"FFmpeg stdout: {stdout2}")
                    
                    if os.path.exists(tmp_clip_path) and os.path.getsize(tmp_clip_path) > 0:
                        cmd3 = f'ffmpeg -i "{tmp_clip_path}" -c:v {SELECTED_CODEC} -c:a aac -b:a 192k -r 30 -vsync cfr "{output_path}" -y -loglevel warning'
                        print(f"Running FFmpeg command (method 2, part 2): {cmd3}")
                        
                        process3 = subprocess.run(cmd3, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                        exit_code3 = process3.returncode
                        
                        if exit_code3 != 0:
                            stderr3 = safe_decode(process3.stderr)
                            stdout3 = safe_decode(process3.stdout)
                            print(f"⚠️ FFmpeg method 2 part 2 exited with code: {exit_code3}")
                            print(f"FFmpeg stderr: {stderr3}")
                            print(f"FFmpeg stdout: {stdout3}")
                        
                        print(f"✅ Clip extracted successfully with method 2 to {output_path}")
                    else:
                        print("⚠️ Clip extraction failed with method 2, trying method 3...")
                        
                        # Method 3: Fallback to copy codec
                        cmd4 = f'ffmpeg -i "{tmp_path}" -ss {start_time_str} -t {duration} -c copy "{output_path}" -y -loglevel warning'
                        print(f"Running FFmpeg command (method 3): {cmd4}")
                        
                        process4 = subprocess.run(cmd4, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                        exit_code4 = process4.returncode
                        
                        if exit_code4 != 0:
                            stderr4 = safe_decode(process4.stderr)
                            stdout4 = safe_decode(process4.stdout)
                            print(f"⚠️ FFmpeg method 3 exited with code: {exit_code4}")
                            print(f"FFmpeg stderr: {stderr4}")
                            print(f"FFmpeg stdout: {stdout4}")
                        
                        print(f"✅ Clip extracted with basic method to {output_path}")
            
            except Exception as e:
                print(f"❌ Error during clip extraction: {type(e).__name__}: {str(e)}")
                # Use full video as fallback
                if os.path.exists(tmp_path):
                    import shutil
                    shutil.copy(tmp_path, output_path)
                    print("⚠️ Using full video as fallback due to extraction error")
            
            # Clean up temporary files
            for file_path in [tmp_path, tmp_clip_path]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"⚠️ Could not remove temporary file {file_path}: {str(e)}")
        
        elif not os.path.exists(tmp_path):
            print(f"❌ Download failed: {tmp_path} does not exist")
            return False
        
        else:
            # If no clip extraction needed, just rename the file
            if os.path.exists(tmp_path):
                os.rename(tmp_path, output_path)
                
        return os.path.exists(output_path)
    
    except Exception as e:
        print(f"❌ Error during video processing: {type(e).__name__}: {str(e)}")
        # Try to salvage by renaming if possible
        if os.path.exists(tmp_path) and not os.path.exists(output_path):
            try:
                os.rename(tmp_path, output_path)
                return True
            except Exception as rename_error:
                print(f"❌ Could not rename temp file: {str(rename_error)}")
        
        return False

def get_video_duration(video_path):
    """Get the duration of a video in seconds."""
    try:
        # Ensure path is a string, not bytes
        if isinstance(video_path, bytes):
            video_path = video_path.decode('utf-8')
            
        print(f"Probing video file: {video_path}")
        print(f"File exists: {os.path.exists(video_path)}")
        print(f"File size: {os.path.getsize(video_path) if os.path.exists(video_path) else 'N/A'}")
        probe = ffmpeg.probe(video_path)
        duration = float(probe["format"]["duration"])
        return duration
    except ffmpeg.Error as e:
        print(f"⚠️ FFprobe error: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            stderr_text = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else str(e.stderr)
            print(f"FFprobe stderr: {stderr_text}")
        return None
    except Exception as e:
        print(f"⚠️ Unexpected error in get_video_duration: {type(e).__name__}: {str(e)}")
        print(f"Path type: {type(video_path)}")
        return None

def prepare_black_screen():
    """Generate a black screen with title text and silent audio.
    
    Returns:
        str: Path to the black screen video file
    """
    BLACK_SCREEN_WITH_TEXT = os.path.join(VIDEO_OUTPUT_DIR, "black_screen_with_text.mp4")
    BLACK_SCREEN_FINAL = os.path.join(VIDEO_OUTPUT_DIR, "black_screen_final.mp4")
    
    # Generate black screen with text overlay
    MONTH_NAME = calendar.month_name[int(TARGET_MONTH)]
    black_screen_text = f"{LASTFM_USER}'s Top {NUM_SONGS} songs of {MONTH_NAME} {TARGET_YEAR}"
    
    if not os.path.exists(BLACK_SCREEN_WITH_TEXT):
        print("✏️ Generating black screen with text...")
        
        # Determine font path for different operating systems
        font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"  # Mac path
        if not os.path.exists(font_path):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Linux fallback
            if not os.path.exists(font_path):
                font_path = "C:\\Windows\\Fonts\\arialuni.ttf"  # Windows Unicode font
                if not os.path.exists(font_path):
                    font_path = "C:\\Windows\\Fonts\\arial.ttf"  # Windows regular Arial
                    if not os.path.exists(font_path):
                        font_path = None  # Let ffmpeg use default font
        
        try:
            # Generate a 3-second black video with text
            text_filter = {
                "text": black_screen_text,
                "fontsize": 50,
                "fontcolor": "white",
                "x": "(w-text_w)/2",
                "y": "(h-text_h)/2"
            }
            
            if font_path:
                text_filter["fontfile"] = font_path
                
            # Create a black video source and add text
            ffmpeg.input('color=c=black:s=1920x1080:r=30', f='lavfi', t=3).filter(
                "drawtext", **text_filter
            ).output(
                BLACK_SCREEN_WITH_TEXT, 
                vcodec=SELECTED_CODEC,
                vsync="cfr",
                r=30
            ).run()
        except ffmpeg.Error as e:
            print(f"❌ Error creating black screen: {e}")
            return None
    
    # Add silent audio track to ensure compatibility
    if not os.path.exists(BLACK_SCREEN_FINAL):
        print("🔇 Adding silent audio track to black screen...")
        try:
            # Create two separate inputs
            video = ffmpeg.input(BLACK_SCREEN_WITH_TEXT)
            audio = ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi', t=3)
            
            # Combine video and audio streams
            ffmpeg.output(
                video,
                audio,
                BLACK_SCREEN_FINAL,
                vcodec=SELECTED_CODEC,
                acodec="aac",
                shortest=None
            ).run()
        except ffmpeg.Error as e:
            print(f"❌ Error adding silent audio: {e}")
            print(f"Detailed error: {str(e)}")
            # Use version with text as fallback
            if os.path.exists(BLACK_SCREEN_WITH_TEXT):
                import shutil
                shutil.copy(BLACK_SCREEN_WITH_TEXT, BLACK_SCREEN_FINAL)
                print("⚠️ Using black screen without audio as fallback")
    
    return BLACK_SCREEN_FINAL
    
def add_text_overlay(input_clip, output_clip, text):
    """Add text overlay to video clip with consistent sizing and positioning.
    
    Args:
        input_clip: Path to input video
        output_clip: Path to save output video
        text: Text to overlay
    """
    # Get video dimensions using ffprobe
    try:
        probe = ffmpeg.probe(input_clip)
        width = int(probe['streams'][0]['width'])
        height = int(probe['streams'][0]['height'])
        
        # Base font size as percentage of video height
        base_fontsize = int(height * 0.05)  # 5% of video height
        
        # Adjust font size based on text length to ensure it fits
        # Calculate approximate character width (varies by font)
        char_width_factor = 0.6  # Approximate width of a character relative to font size
        
        # Estimate width of text in pixels
        estimated_text_width = len(text) * base_fontsize * char_width_factor
        
        # If estimated width is too large, scale down the font size
        if estimated_text_width > width * 0.85:  # Allow text to use 85% of width
            fontsize = int(base_fontsize * (width * 0.85) / estimated_text_width)
        else:
            fontsize = base_fontsize
        
        # Scale shadow size based on resolution
        shadowx = max(2, int(width * 0.002))
        shadowy = max(2, int(height * 0.002))
        
        # Calculate position from bottom as percentage of height
        bottom_margin = int(height * 0.08)  # 8% from bottom
        y_position = f"h-{bottom_margin}"
    except Exception as e:
        print(f"⚠️ Could not determine video dimensions: {e}")
        # Fallback values
        fontsize = 36
        shadowx = 2
        shadowy = 2
        y_position = "h-100"
    
    # Determine font path for different operating systems
    font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"  # Mac path
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Linux fallback
        if not os.path.exists(font_path):
            font_path = "C:\\Windows\\Fonts\\arialuni.ttf"  # Windows Unicode font
            if not os.path.exists(font_path):
                font_path = "C:\\Windows\\Fonts\\arial.ttf"  # Windows regular Arial
                if not os.path.exists(font_path):
                    font_path = None  # Let ffmpeg use default font
    
    # Text with enhanced shadow for better readability
    text_params = {
        'text': text,
        'fontsize': fontsize,
        'fontcolor': 'white',
        'x': '(w-text_w)/2',  # Center horizontally
        'y': y_position,      # Consistent distance from bottom
        'shadowcolor': 'black',
        'shadowx': shadowx,
        'shadowy': shadowy
    }
    
    if font_path:
        text_params['fontfile'] = font_path
    
    # Apply text filter with shadow
    ffmpeg.input(input_clip).filter(
        'drawtext', **text_params
    ).output(
        output_clip, 
        vcodec=SELECTED_CODEC, 
        acodec="aac", 
        audio_bitrate="192k", 
        map="0:a", 
        preset="slow"
    ).run()

def update_video():
    """Allow user to replace incorrect videos before final merge."""
    while True:
        replace = input("\n❓ Do you need to replace any videos? (yes/no): ").strip().lower()
        if replace != "yes":
            break  # Exit if no replacement needed

        # Print numbered list of videos for reference
        print("\nCurrent videos in compilation:")
        for i, (artist, title) in enumerate(songs):
            print(f"  {i+1}. {artist} - {title}")
        
        try:
            index = int(input("\nEnter the song number to replace (1-50): ")) - 1
            if index < 0 or index >= len(video_clips):
                print("❌ Invalid song number. Try again.")
                continue

            artist, title = songs[index]
            print(f"🔄 Replacing: {artist} - {title}") 

            # Rest of your replacement code...

            print(f"🔄 Replacing: {artist} - {title}")

            # Ask for a new YouTube URL
            new_video_url = input("Enter the correct YouTube URL: ").strip()
            if not new_video_url.startswith("https://www.youtube.com/watch"):
                print("❌ Invalid YouTube URL")
                continue

            # Define file paths
            clip_path = os.path.join(VIDEO_OUTPUT_DIR, f"clip_{index}.mp4")
            final_clip_path = os.path.join(VIDEO_OUTPUT_DIR, f"final_{index}.mp4")

            # Delete old files to prevent conflicts
            for file in [clip_path, final_clip_path]:
                if os.path.exists(file):
                    os.remove(file)

            try:
                # Get video metadata
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(new_video_url, download=False)
                    duration = info.get('duration')
                    
                    # Determine start time
                    start_time_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(CHORUS_START.split(":"))))
                    
                    # Adjust if needed
                    if duration and start_time_seconds + CLIP_DURATION > duration:
                        print(f"⚠️ Video too short ({duration}s). Adjusting start time.")
                        start_time_seconds = max(0, duration - CLIP_DURATION)
                
                # Download and extract clip
                download_video(new_video_url, clip_path, start_time=start_time_seconds, duration=CLIP_DURATION)
                
                # Add text overlay
                add_text_overlay(clip_path, final_clip_path, f"{len(songs)-index}. {artist} - {title}")

                # Update cached YouTube links
                query = f"{artist} - {title}"
                video_cache[query] = new_video_url
                save_cache(video_cache, "video_cache.json")
                progress[query] = new_video_url
                save_cache(progress, "progress.json")

                # Replace the incorrect video in the final list
                video_clips[index] = final_clip_path

                print(f"✅ Successfully replaced {artist} - {title}!")
                
            except Exception as e:
                print(f"❌ Error replacing video: {e}")
                print("Please try again.")

        except ValueError:
            print("❌ Invalid input. Please enter a valid number.")

def merge_videos(video_list, output_file):
    """Merge all video clips into a single video file.
    
    Args:
        video_list: List of video files to merge
        output_file: Path to save the final merged video
    """
    # Save cache before merging
    save_cache(video_cache, "video_cache.json")
    
    # Prepare the black screen with text and audio
    black_screen = prepare_black_screen()
    
    # Verify the black screen exists
    if not os.path.exists(black_screen):
        print(f"❌ Fatal error: Black screen {black_screen} not found. Cannot merge videos.")
        return
    
    # Verify all videos exist before merging
    missing_files = [video for video in video_list if not os.path.exists(video)]
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return
    
    # Create a text file for FFmpeg concat
    FILE_LIST_PATH = os.path.abspath(os.path.join(CACHE_DIR, "file_list.txt"))
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    with open(FILE_LIST_PATH, "w") as f:
        # Add the black screen first
        f.write(f"file '{os.path.abspath(black_screen)}'\n")
        # Add all the video clips
        for video in video_list:
            f.write(f"file '{os.path.abspath(video)}'\n")
    
    print("✅ All files found, proceeding with FFmpeg merge...")
    
    # Merge using FFmpeg
    try:
        ffmpeg.input(FILE_LIST_PATH, format="concat", safe=0).output(
            os.path.abspath(output_file),
            vcodec=SELECTED_CODEC,
            acodec="aac",
            audio_bitrate="192k",
            r=30,
            format="mp4"
        ).run()
        print("🎬 Merging Complete! Final video saved at:", output_file)
    except ffmpeg.Error as e:
        print(f"❌ Error during merge: {e}")

if __name__ == "__main__":
    os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
    songs = get_top_songs()  # Fetches from cache OR API
    video_clips = []

    print(f"\n🎵 Processing your top {NUM_SONGS} songs for {calendar.month_name[int(TARGET_MONTH)]} {TARGET_YEAR}...")
    
    for i, song_data in enumerate(reversed(songs)):
        artist, title = song_data
        print(f"\n🎵 Processing {i+1}/{NUM_SONGS}: {artist} - {title}")
        query = f"{artist} {title}"
        video_url = search_youtube_video(artist, title)
        if not video_url:
            continue
        
        # Define file paths - we now only need two files per song
        clip_path = os.path.join(VIDEO_OUTPUT_DIR, f"clip_{i}.mp4")
        final_clip_path = os.path.join(VIDEO_OUTPUT_DIR, f"final_{i}.mp4")
        
        try:
            # Get video metadata first to determine optimal start time
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                duration = info.get('duration')
                
                # Convert CHORUS_START to seconds
                start_time_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(CHORUS_START.split(":"))))
                
                # Adjust start time if video is too short
                if duration and start_time_seconds + CLIP_DURATION > duration:
                    print(f"⚠️ Video too short ({duration}s). Adjusting start time.")
                    start_time_seconds = max(0, duration - CLIP_DURATION)
            
            # Download only the segment we need directly
            download_video(video_url, clip_path, start_time=start_time_seconds, duration=CLIP_DURATION)
            
            # Add text overlay
            add_text_overlay(clip_path, final_clip_path, f"{len(songs)-i}. {artist} - {title}")
            video_clips.append(final_clip_path)
            
        except Exception as e:
            print(f"❌ Error processing {artist} - {title}: {e}")
            continue

    # Merge the initial version of the final video
    if video_clips:
        merge_videos(video_clips, FINAL_VIDEO)

        print("\n🎬 Initial Video Created Successfully!")
        print("📌 Please review the final video and confirm if any clips need replacement.")
        
        # Track if replacements happen
        need_replacement = False

        # Allow user to manually replace videos after watching
        while True:
            choice = input("❓ Do you need to replace any videos? (yes/no): ").strip().lower()
            if choice == "yes":
                need_replacement = True  # Mark that replacements happened
                update_video()
            elif choice == "no":
                break
            else:
                print("❌ Invalid input. Please enter 'yes' or 'no'.")
        
        # Merge Final Video Again only if replacements were made
        if need_replacement:
            print("🔄 Merging the final version after replacements...")
            merge_videos(video_clips, FINAL_VIDEO)
            print(f"✨ Final video saved as: {FINAL_VIDEO}")
        else:
            print(f"✨ Video compilation complete! Saved as: {FINAL_VIDEO}")
    else:
        print("❌ No videos were successfully processed. Cannot create compilation.")

    # Delete progress.json after successful completion
    progress_path = os.path.join(CACHE_DIR, "progress.json")
    if os.path.exists(progress_path):
        os.remove(progress_path)
        print("✅ Temporary progress file cleaned up.")
    
     # Delete requirements.txt after successful completion
    file_list = os.path.join(CACHE_DIR, "file_list.txt")
    if os.path.exists(file_list):
        os.remove(file_list)
    
    # Delete the video folder with all intermediate clips
    if os.path.exists(VIDEO_OUTPUT_DIR) and os.path.isdir(VIDEO_OUTPUT_DIR):
        print("🧹 Cleaning up temporary video files...")
        # Make sure final video exists before deleting source files
        if os.path.exists(FINAL_VIDEO) and os.path.getsize(FINAL_VIDEO) > 0:
            import shutil
            try:
                # Move the final video to the current directory if it's in the video folder
                if os.path.dirname(os.path.abspath(FINAL_VIDEO)) == os.path.abspath(VIDEO_OUTPUT_DIR):
                    import shutil
                    shutil.copy(FINAL_VIDEO, os.path.basename(FINAL_VIDEO))
                    print(f"✅ Copied final video to current directory: {os.path.basename(FINAL_VIDEO)}")
                
                # Delete the entire video folder
                shutil.rmtree(VIDEO_OUTPUT_DIR)
                print("✅ Temporary video folder cleaned up. May have been moved to Recycle Bin/Trash.")
            except Exception as e:
                print(f"⚠️ Could not remove video folder: {e}. Manually it youxrself")
        else:
            print("⚠️ Final video not found or empty. Keeping temporary files for troubleshooting.")