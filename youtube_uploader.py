"""
youtube_uploader.py — Upload videos to YouTube using Data API v3 with OAuth2
"""
import os
import json
import pickle
import time
import httplib2
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import config

# OAuth2 scopes needed
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PICKLE = "youtube_token.pickle"

# Retry settings for resumable uploads
MAX_RETRIES = 10
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


def get_authenticated_service():
    """
    Authenticate with YouTube via OAuth2.
    On first run, opens a browser window for authorization.
    Subsequent runs use the cached token in youtube_token.pickle.
    """
    creds = None

    # Load cached credentials
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, "rb") as token:
            creds = pickle.load(token)

    # Refresh or re-authorize
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.YOUTUBE_CLIENT_SECRETS_FILE):
                raise FileNotFoundError(
                    f"YouTube client secrets file not found: {config.YOUTUBE_CLIENT_SECRETS_FILE}\n"
                    "See SETUP_GUIDE.md for instructions to get this file."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.YOUTUBE_CLIENT_SECRETS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save for next run
        with open(TOKEN_PICKLE, "wb") as token:
            pickle.dump(creds, token)
        print("✅ YouTube authentication saved to youtube_token.pickle")

    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: str,
    script: dict,
    privacy: str = "private",
    category_id: str = "28",
    made_for_kids: bool = False,
) -> str:
    """
    Upload a video to YouTube.

    Args:
        video_path: Path to the video file
        script: Script dict (used for title, description, tags)
        privacy: 'private', 'unlisted', or 'public'
        category_id: YouTube category (28 = Science & Technology, 22 = People & Blogs)
        made_for_kids: Whether this content is made for kids

    Returns:
        YouTube video URL
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    title = script.get("title", "Untitled Video")[:100]
    description = script.get("description", "")[:5000]
    tags = script.get("tags", [])

    # Ensure #Shorts is in tags and description
    if "#Shorts" not in tags:
        tags.append("#Shorts")
    if "#Shorts" not in description:
        description += "\n\n#Shorts"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    print(f"\n📤 Uploading to YouTube: \"{title}\"")
    print(f"   Privacy: {privacy}")
    print(f"   File: {video_path} ({os.path.getsize(video_path) / (1024**2):.1f} MB)")

    youtube = get_authenticated_service()

    media = MediaFileUpload(
        video_path,
        chunksize=1024 * 1024 * 4,  # 4MB chunks
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    # Resumable upload with exponential backoff
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            print("   Uploading...", end="\r")
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"   Upload progress: {pct}%  ", end="\r")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"HTTP {e.resp.status}: {e.content}"
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"Network error: {e}"

        if error:
            retry += 1
            if retry > MAX_RETRIES:
                raise RuntimeError(f"Upload failed after {MAX_RETRIES} retries: {error}")
            wait = min(2 ** retry, 64)
            print(f"\n   ⚠️  Retry {retry}/{MAX_RETRIES} in {wait}s: {error}")
            time.sleep(wait)
            error = None

    video_id = response.get("id", "")
    url = f"https://www.youtube.com/watch?v={video_id}"
    shorts_url = f"https://www.youtube.com/shorts/{video_id}"

    print(f"\n✅ Upload complete!")
    print(f"   YouTube URL:  {url}")
    print(f"   Shorts URL:   {shorts_url}")
    print(f"   Video ID:     {video_id}")

    return url


if __name__ == "__main__":
    import sys
    import json
    config.validate_config()
    if len(sys.argv) < 3:
        print("Usage: python youtube_uploader.py <video.mp4> <script.json> [privacy]")
        sys.exit(1)
    with open(sys.argv[2]) as f:
        script = json.load(f)
    privacy = sys.argv[3] if len(sys.argv) > 3 else "private"
    upload_video(sys.argv[1], script, privacy=privacy)
