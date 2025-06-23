"""
Content analyzer for video metadata and text content.

This module provides content analysis capabilities including:
- Text analysis (from subtitles/transcripts)
- Sentiment analysis
- Keyword extraction
- Content classification
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
from dataclasses import dataclass
from datetime import timedelta

from textblob import TextBlob
from textblob.sentiments import PatternAnalyzer

from .base import BaseAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)

@dataclass
class TextSegment:
    """Represents a segment of text with timing information."""
    text: str
    start_time: float  # in seconds
    end_time: float    # in seconds
    confidence: float = 1.0
    speaker: Optional[str] = None
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

class ContentAnalyzer(BaseAnalyzer):
    """Analyzes text content and metadata from videos."""
    
    def __init__(self, language: str = "en", **kwargs):
        """
        Initialize the content analyzer.
        
        Args:
            language: Default language for text processing
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.language = language
        self._sentiment_analyzer = PatternAnalyzer()
    
    @property
    def name(self) -> str:
        return "content_analyzer"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def analyze(self, video_path: Path, **kwargs) -> AnalysisResult:
        """
        Analyze content features from the video.
        
        Args:
            video_path: Path to the video file
            **kwargs: Additional parameters including:
                - subtitles_path: Path to subtitles file (optional)
                - transcript: Pre-extracted transcript (optional)
                - metadata: Video metadata (optional)
                
        Returns:
            AnalysisResult with content features
        """
        try:
            # Extract or get text content
            subtitles_path = kwargs.get('subtitles_path')
            transcript = kwargs.get('transcript')
            
            if subtitles_path and Path(subtitles_path).exists():
                segments = self._parse_subtitles(subtitles_path)
            elif transcript:
                segments = [TextSegment(text=transcript, start_time=0, end_time=kwargs.get('duration', 0))]
            else:
                segments = []
            
            # Analyze text content
            features = await self._analyze_text(segments)
            
            # Add metadata
            metadata = {
                'language': self.language,
                'analyzer': self.name,
                'analyzer_version': self.version,
                'segment_count': len(segments),
                'total_text_length': sum(len(s.text) for s in segments)
            }
            
            return AnalysisResult(features=features, metadata=metadata)
            
        except Exception as e:
            logger.error(f"Content analysis failed: {str(e)}", exc_info=True)
            return AnalysisResult(success=False, error=str(e))
    
    def _parse_subtitles(self, subtitles_path: Path) -> List[TextSegment]:
        """Parse subtitles from various formats (SRT, VTT, etc.)."""
        suffix = subtitles_path.suffix.lower()
        
        if suffix == '.srt':
            return self._parse_srt(subtitles_path)
        elif suffix == '.vtt':
            return self._parse_vtt(subtitles_path)
        elif suffix == '.json':
            return self._parse_json_subtitles(subtitles_path)
        else:
            raise ValueError(f"Unsupported subtitle format: {suffix}")
    
    def _parse_srt(self, file_path: Path) -> List[TextSegment]:
        """Parse SRT format subtitles."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        segments = []
        blocks = content.strip().split('\n\n')
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:  # At least: number, timestamp, text
                continue
                
            try:
                # Parse timestamp (format: 00:00:00,000 --> 00:00:02,000)
                time_part = lines[1].strip()
                start_str, end_str = time_part.split('-->')
                
                def parse_time(time_str: str) -> float:
                    hh_mm_ss, ms = time_str.strip().split(',')
                    h, m, s = map(float, hh_mm_ss.split(':'))
                    return h * 3600 + m * 60 + s + float(f"0.{ms}")
                
                start_time = parse_time(start_str)
                end_time = parse_time(end_str)
                
                # Get text (remaining lines)
                text = ' '.join(lines[2:])
                
                segments.append(TextSegment(
                    text=text,
                    start_time=start_time,
                    end_time=end_time
                ))
                
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse SRT block: {e}")
                continue
        
        return segments
    
    def _parse_vtt(self, file_path: Path) -> List[TextSegment]:
        """Parse WebVTT format subtitles."""
        # Similar to SRT but with optional header and different timestamp format
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        segments = []
        current_segment = None
        
        for line in lines:
            line = line.strip()
            if not line or line == 'WEBVTT':
                continue
                
            # Check for timestamp line (format: 00:00:00.000 --> 00:00:02.000)
            if '-->' in line:
                if current_segment and current_segment.text:
                    segments.append(current_segment)
                
                try:
                    start_str, end_str = line.split('-->')
                    
                    def parse_time(time_str: str) -> float:
                        time_str = time_str.strip()
                        # Handle both , and . as decimal separator
                        if ',' in time_str:
                            time_part, ms = time_str.split(',')
                        else:
                            time_part, ms = time_str.split('.')
                        
                        h, m, s = map(int, time_part.split(':'))
                        return h * 3600 + m * 60 + s + float(f"0.{ms}")
                    
                    start_time = parse_time(start_str)
                    end_time = parse_time(end_str)
                    
                    current_segment = TextSegment(
                        text="",
                        start_time=start_time,
                        end_time=end_time
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse VTT timestamp: {e}")
                    current_segment = None
            elif current_segment is not None:
                # Add to current segment's text
                if current_segment.text:
                    current_segment.text += "\n" + line
                else:
                    current_segment.text = line
        
        # Add the last segment if it exists
        if current_segment and current_segment.text:
            segments.append(current_segment)
        
        return segments
    
    def _parse_json_subtitles(self, file_path: Path) -> List[TextSegment]:
        """Parse subtitles from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        segments = []
        
        # Handle different JSON formats
        if isinstance(data, list):
            # Format: [{"text": "...", "start": 0.0, "end": 1.0, ...}]
            for item in data:
                if not all(k in item for k in ['text', 'start', 'end']):
                    continue
                segments.append(TextSegment(
                    text=item['text'],
                    start_time=float(item['start']),
                    end_time=float(item['end']),
                    confidence=float(item.get('confidence', 1.0)),
                    speaker=item.get('speaker')
                ))
        elif 'segments' in data:
            # Format: {"segments": [{"text": "...", "start": 0.0, "end": 1.0, ...}]}
            for seg in data['segments']:
                segments.append(TextSegment(
                    text=seg.get('text', ''),
                    start_time=float(seg['start']),
                    end_time=float(seg['end']),
                    confidence=float(seg.get('confidence', 1.0)),
                    speaker=seg.get('speaker')
                ))
        
        return segments
    
    async def _analyze_text(self, segments: List[TextSegment]) -> Dict[str, Any]:
        """Analyze text segments for various features."""
        if not segments:
            return {}
        
        features = {
            'text_length': 0,
            'word_count': 0,
            'sentence_count': 0,
            'unique_words': set(),
            'sentiment_polarity': [],
            'sentiment_subjectivity': [],
            'reading_time': 0,
            'speaking_rate': [],
            'keywords': {}
        }
        
        # Process each text segment
        for seg in segments:
            if not seg.text.strip():
                continue
                
            text = seg.text
            features['text_length'] += len(text)
            
            # Word and sentence analysis
            blob = TextBlob(text)
            words = blob.words
            sentences = blob.sentences
            
            features['word_count'] += len(words)
            features['sentence_count'] += len(sentences)
            features['unique_words'].update(word.lower() for word in words)
            
            # Sentiment analysis
            sentiment = self._sentiment_analyzer.analyze(text)
            features['sentiment_polarity'].append(sentiment.polarity)
            features['sentiment_subjectivity'].append(sentiment.subjectivity)
            
            # Speaking rate (words per second)
            if seg.duration > 0:
                features['speaking_rate'].append(len(words) / seg.duration)
        
        # Calculate aggregate features
        features['unique_word_count'] = len(features['unique_words'])
        features['avg_word_length'] = (
            sum(len(word) for word in features['unique_words']) / features['unique_word_count']
            if features['unique_word_count'] > 0 else 0
        )
        
        # Sentiment aggregates
        features['avg_polarity'] = (
            sum(features['sentiment_polarity']) / len(features['sentiment_polarity'])
            if features['sentiment_polarity'] else 0
        )
        features['avg_subjectivity'] = (
            sum(features['sentiment_subjectivity']) / len(features['sentiment_subjectivity'])
            if features['sentiment_subjectivity'] else 0
        )
        
        # Speaking rate (words per second)
        features['avg_speaking_rate'] = (
            sum(features['speaking_rate']) / len(features['speaking_rate'])
            if features['speaking_rate'] else 0
        )
        
        # Calculate reading time (assuming average reading speed of 200 WPM)
        features['reading_time'] = features['word_count'] / 200 * 60  # in seconds
        
        # Clean up temporary data
        del features['unique_words']
        del features['sentiment_polarity']
        del features['sentiment_subjectivity']
        del features['speaking_rate']
        
        # Convert all values to native Python types for JSON serialization
        return {k: float(v) if isinstance(v, (float, int)) else v 
               for k, v in features.items()}
    
    def _extract_keywords(self, text: str, top_n: int = 10) -> List[Tuple[str, float]]:
        """Extract keywords using TF-IDF or similar method."""
        # This is a simplified version - in production, use a proper keyword extraction library
        words = re.findall(r'\b\w+\b', text.lower())
        word_counts = {}
        
        for word in words:
            if len(word) < 3:  # Skip very short words
                continue
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_words[:top_n]
