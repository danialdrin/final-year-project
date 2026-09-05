import logging
from typing import Tuple, List, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

logger = logging.getLogger(__name__)

class TranscriptService:
    @staticmethod
    def get_transcript(video_id: str) -> Tuple[str, List[Dict[str, Any]], bool]:
        """
        Fetches transcript for a YouTube video.
        Returns (full_text, list_of_segments, transcript_available_boolean).
        """
        if video_id.startswith("mock_vid_"):
            mock_text = "In this tutorial we will learn about React Hooks including useState for state management and useEffect for side effects. For example, useState allows functional components to hold state. useEffect handles cleanup functions when unmounting."
            segments = [
                {"text": "In this tutorial we will learn about React Hooks", "start": 0.0, "duration": 5.0},
                {"text": "including useState for state management and useEffect for side effects.", "start": 5.0, "duration": 5.0},
                {"text": "For example, useState allows functional components to hold state.", "start": 10.0, "duration": 5.0},
                {"text": "useEffect handles cleanup functions when unmounting.", "start": 15.0, "duration": 5.0}
            ]
            return mock_text, segments, True

        try:
            if hasattr(YouTubeTranscriptApi, "get_transcript"):
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            else:
                transcript_list = YouTubeTranscriptApi().fetch(video_id).to_raw_data()
            full_text = " ".join([item["text"] for item in transcript_list])
            return full_text, transcript_list, True
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            logger.warning(f"No transcript found for video_id {video_id}: {e}")
            return "", [], False
        except Exception as e:
            logger.error(f"Error fetching transcript for video_id {video_id}: {e}")
            return "", [], False

transcript_service = TranscriptService()
