import logging
import httpx
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)

class YouTubeService:
    def __init__(self):
        self.api_key = getattr(settings, "YOUTUBE_API_KEY", "")

    async def search_videos(self, query: str, page_token: Optional[str] = None, max_results: int = 50) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "dummy_youtube_api_key":
            if settings.APP_ENV.lower() != "development":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="YOUTUBE_API_KEY is required for live search in non-development environments.",
                )
            logger.warning("No valid YOUTUBE_API_KEY configured; returning explicitly marked development mocks.")
            return {
                "candidates": [
                    {
                        "video_id": f"mock_vid_{i}",
                        "title": f"Comprehensive {query} Tutorial - Part {i+1}",
                        "channel": "Tech Academy",
                        "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
                        "description": f"Learn everything about {query} in this in-depth guide with code examples.",
                        "is_mock": True,
                    }
                    for i in range(5)
                ],
                "next_page_token": None
            }

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "key": self.api_key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": max_results
        }
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.error(f"YouTube Data API error: {resp.status_code} - {resp.text}")
                raise Exception(f"YouTube Data API search failed: {resp.status_code}")

            data = resp.json()
            items = data.get("items", [])
            candidates = []
            for item in items:
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")
                if video_id:
                    candidates.append({
                        "video_id": video_id,
                        "title": snippet.get("title", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                        "description": snippet.get("description", ""),
                        "is_mock": False,
                    })

            return {
                "candidates": candidates,
                "next_page_token": data.get("nextPageToken")
            }

youtube_service = YouTubeService()
