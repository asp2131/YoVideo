"""
Enhanced Multi-Modal Highlight Detector

This module provides an advanced highlight detector that combines:
- Audio analysis (energy, speech patterns, music)
- Visual analysis (scene changes, motion, plant detection)
- Content analysis (transcription, gardening keywords, sentiment)
"""
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import cv2
import librosa
from textblob import TextBlob
import re
import json
from scipy.signal import find_peaks

from app.editing.core.processor import VideoProcessor

logger = logging.getLogger(__name__)

class HighlightDetector(VideoProcessor):
    """
    Advanced highlight detector optimized for gardening videos with plant-specific features.
    Combines audio, visual, and content analysis to identify engaging moments.
    """
    
    # Content keywords that indicate important moments
    ENGAGEMENT_KEYWORDS = {
        'high_energy': ['excited', 'amazing', 'incredible', 'wow', 'awesome', 'fantastic'],
        'instructional': ['how to', 'step', 'first', 'next', 'then', 'finally', 'important'],
        'emotional': ['love', 'hate', 'feel', 'happy', 'sad', 'frustrated', 'proud'],
        'conclusion': ['summary', 'conclusion', 'finally', 'in summary', 'to wrap up'],
        'question': ['what', 'how', 'why', 'when', 'where', 'which'],
        'emphasis': ['really', 'very', 'extremely', 'absolutely', 'definitely', 'obviously']
    }
    
    # Gardening-specific keywords
    GARDENING_KEYWORDS = {
        'plant_health': ['healthy', 'wilting', 'thriving', 'dying', 'pest', 'disease'],
        'garden_tasks': ['planting', 'watering', 'harvesting', 'pruning', 'fertilizing'],
        'plant_species': ['cilantro', 'sweet potato', 'comfrey', 'shiso', 'marigold', 'basil'],
        'garden_conditions': ['sunlight', 'soil', 'compost', 'mulch', 'drainage']
    }
    
    # Visual analysis parameters
    VISUAL_ANALYSIS_INTERVAL = 0.5  # seconds between frames for analysis
    MIN_PLANT_RATIO = 0.1  # Minimum green pixel ratio to consider as plant
    MOTION_THRESHOLD = 30  # Threshold for motion detection
    
    def __init__(
        self,
        min_duration: float = 5.0,           # Minimum highlight duration in seconds
        max_duration: float = 20.0,          # Maximum highlight duration in seconds
        min_silence_len: int = 1500,         # Minimum silence length in ms for cuts
        silence_thresh: int = -32,           # Silence threshold in dB
        keep_silence: int = 500,             # How much silence to keep around cuts (ms)
        min_highlight_duration: int = 30,    # Target minimum total highlight duration
        always_include_first: int = 20,      # First N seconds to always include
        plant_context_buffer: float = 2.0,   # Seconds to add around plant mentions
        audio_weight: float = 0.3,           # Weight for audio features
        visual_weight: float = 0.4,          # Weight for visual features
        content_weight: float = 0.3,         # Weight for content features
        analysis_interval: float = 0.5,      # Seconds between analysis frames
        use_gpu: bool = False,               # Use GPU acceleration if available
    ):
        """
        Initialize the highlight detector with processing parameters.
        
        Args:
            min_duration: Minimum duration of a highlight segment in seconds
            max_duration: Maximum duration of a highlight segment in seconds
            min_silence_len: Minimum silence length in milliseconds to detect for cuts
            silence_thresh: Silence threshold in dB (lower values make it more sensitive)
            keep_silence: How much silence to keep around cuts in milliseconds
        """
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.min_silence_len = min_silence_len
        self.silence_thresh = silence_thresh
        self.keep_silence = keep_silence
        self.min_highlight_duration = min_highlight_duration
        self.always_include_first = always_include_first
        self.plant_context_buffer = plant_context_buffer
        
        # Feature weights (normalized to sum to 1)
        total_weight = audio_weight + visual_weight + content_weight
        self.audio_weight = audio_weight / total_weight
        self.visual_weight = visual_weight / total_weight
        self.content_weight = content_weight / total_weight
        
        # Analysis settings
        self.analysis_interval = analysis_interval
        self.use_gpu = use_gpu and cv2.cuda.getCudaEnabledDeviceCount() > 0
        
        # Initialize models
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            if self.use_gpu:
                logger.info("CUDA is available - using GPU acceleration")
                self.gpu_frame = cv2.cuda_GpuMat()
            else:
                logger.info("Using CPU for visual analysis")
        except Exception as e:
            logger.warning(f"Could not initialize face detection: {e}")
            self.face_cascade = None
    
    @property
    def name(self) -> str:
        """Return the name identifier for this processor."""
        return "enhanced_highlight_detector"
        
    def _analyze_audio(self, video_path: Path) -> Dict:
        """
        Analyze audio features to detect important moments.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary containing audio analysis features
        """
        logger.info("Analyzing audio features...")
        
        try:
            # Load audio
            y, sr = librosa.load(str(video_path), sr=None)
            
            # 1. Energy analysis
            hop_length = 512
            frame_length = 2048
            
            # RMS energy
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Spectral centroid (brightness)
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            
            # Zero crossing rate (speech vs music indicator)
            zcr = librosa.feature.zero_crossing_rate(y, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Tempo and beat tracking
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            
            # Convert frame indices to time
            times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
            beat_times = librosa.frames_to_time(beats, sr=sr)
            
            # Find energy peaks
            energy_threshold = np.percentile(rms, 75)  # Top 25% energy moments
            peaks, _ = find_peaks(rms, height=energy_threshold, distance=sr//hop_length)
            peak_times = times[peaks]
            
            # Detect speech segments
            speech_segments = self._detect_speech_segments(y, sr, zcr, times)
            
            return {
                'energy_peaks': peak_times.tolist(),
                'rms_energy': rms.tolist(),
                'spectral_centroid': spectral_centroid.tolist(),
                'zcr': zcr.tolist(),
                'times': times.tolist(),
                'tempo': float(tempo),
                'beat_times': beat_times.tolist(),
                'speech_segments': speech_segments,
                'duration': len(y) / sr
            }
            
        except Exception as e:
            logger.error(f"Error in audio analysis: {e}")
            return {}
            
    def _detect_speech_segments(self, y: np.ndarray, sr: int, zcr: np.ndarray, 
                           times: np.ndarray) -> List[Dict]:
        """Detect segments that likely contain speech vs music."""
        # Speech typically has higher zero-crossing rate than music
        speech_threshold = np.median(zcr)
        is_speech = zcr > speech_threshold
        
        # Group consecutive speech frames
        segments = []
        start_idx = None
        
        for i, speech in enumerate(is_speech):
            if speech and start_idx is None:
                start_idx = i
            elif not speech and start_idx is not None:
                if i - start_idx > 10:  # Minimum length
                    segments.append({
                        'start': times[start_idx],
                        'end': times[i],
                        'type': 'speech'
                    })
                start_idx = None
        
        return segments
        
    def _analyze_visual(self, video_path: Path) -> Dict:
        """
        Analyze visual features to detect important moments.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary containing visual analysis features
        """
        logger.info("Analyzing visual features...")
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps
            
            # Sample frames at regular intervals
            sample_interval = max(1, int(fps * self.analysis_interval))
            
            frames = []
            frame_times = []
            prev_gray = None
            scene_changes = []
            motion_scores = []
            face_detections = []
            plant_frames = []
            
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % sample_interval == 0:
                    current_time = frame_idx / fps
                    
                    # Convert to grayscale for analysis
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Scene change detection
                    if prev_gray is not None:
                        # Calculate histogram difference
                        hist_diff = cv2.compareHist(
                            cv2.calcHist([prev_gray], [0], None, [256], [0, 256]),
                            cv2.calcHist([gray], [0], None, [256], [0, 256]),
                            cv2.HISTCMP_CORREL
                        )
                        
                        # Scene change if correlation is low
                        if hist_diff < 0.7:  # Threshold for scene change
                            scene_changes.append(current_time)
                        
                        # Motion detection
                        frame_diff = cv2.absdiff(prev_gray, gray)
                        motion_score = np.mean(frame_diff)
                        motion_scores.append({
                            'time': current_time,
                            'score': float(motion_score)
                        })
                    
                    # Face detection
                    if self.face_cascade is not None:
                        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
                        if len(faces) > 0:
                            face_detections.append({
                                'time': current_time,
                                'face_count': len(faces),
                                'largest_face_area': max([w*h for (x,y,w,h) in faces])
                            })
                    
                    # Plant detection (green pixel ratio)
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    lower_green = np.array([25, 40, 40])
                    upper_green = np.array([90, 255, 255])
                    mask = cv2.inRange(hsv, lower_green, upper_green)
                    green_ratio = np.sum(mask > 0) / (frame.shape[0] * frame.shape[1])
                    
                    if green_ratio > self.MIN_PLANT_RATIO:
                        plant_frames.append({
                            'time': current_time,
                            'green_ratio': float(green_ratio)
                        })
                    
                    prev_gray = gray
                    frame_times.append(current_time)
                
                frame_idx += 1
            
            cap.release()
            
            return {
                'scene_changes': scene_changes,
                'motion_scores': motion_scores,
                'face_detections': face_detections,
                'plant_frames': plant_frames,
                'frame_times': frame_times,
                'duration': duration,
                'fps': fps
            }
            
        except Exception as e:
            logger.error(f"Error in visual analysis: {e}")
            return {}
            
    def _analyze_content(self, transcription: List[Dict]) -> Dict:
        """
        Analyze transcription content for important moments.
        
        Args:
            transcription: List of transcription segments from Whisper
            
        Returns:
            Dictionary containing content analysis features
        """
        logger.info("Analyzing content features...")
        
        if not transcription:
            return {}
        
        try:
            keywords_found = []
            sentiment_scores = []
            speaking_rates = []
            
            for segment in transcription:
                text = segment.get('text', '').lower()
                start_time = segment.get('start', 0)
                end_time = segment.get('end', 0)
                duration = end_time - start_time
                
                # Keyword detection
                for category, words in {**self.ENGAGEMENT_KEYWORDS, **self.GARDENING_KEYWORDS}.items():
                    for keyword in words:
                        if keyword in text:
                            keywords_found.append({
                                'keyword': keyword,
                                'category': category,
                                'time': start_time,
                                'text': text
                            })
                
                # Sentiment analysis
                if text.strip():
                    blob = TextBlob(text)
                    sentiment_scores.append({
                        'time': start_time,
                        'polarity': float(blob.sentiment.polarity),
                        'subjectivity': float(blob.sentiment.subjectivity)
                    })
                
                # Speaking rate (words per second)
                word_count = len(text.split())
                if duration > 0:
                    speaking_rate = word_count / duration
                    speaking_rates.append({
                        'time': start_time,
                        'rate': speaking_rate,
                        'word_count': word_count
                    })
            
            # Find emphasis moments (questions, exclamations)
            emphasis_moments = []
            for segment in transcription:
                text = segment.get('text', '')
                start_time = segment.get('start', 0)
                
                # Count questions and exclamations
                question_count = text.count('?')
                exclamation_count = text.count('!')
                caps_words = len(re.findall(r'\b[A-Z]{2,}\b', text))
                
                if question_count > 0 or exclamation_count > 0 or caps_words > 0:
                    emphasis_moments.append({
                        'time': start_time,
                        'questions': question_count,
                        'exclamations': exclamation_count,
                        'caps_words': caps_words
                    })
            
            return {
                'keywords': keywords_found,
                'sentiment_scores': sentiment_scores,
                'speaking_rates': speaking_rates,
                'emphasis_moments': emphasis_moments
            }
            
        except Exception as e:
            logger.error(f"Error in content analysis: {e}")
            return {}
    
    def _score_segments(
        self,
        segments: List[Dict],
        audio_features: Dict,
        visual_features: Dict,
        content_features: Dict
    ) -> List[Dict]:
        """
        Score segments based on audio, visual, and content features.
        
        Args:
            segments: List of candidate segments
            audio_features: Audio analysis results
            visual_features: Visual analysis results
            content_features: Content analysis results
            
        Returns:
            List of segments with scores
        """
        logger.info("Scoring segments based on multi-modal features...")
        
        scored_segments = []
        
        for segment in segments:
            start_time = segment.get('start', 0)
            end_time = segment.get('end', 0)
            duration = end_time - start_time
            
            if duration <= 0:
                continue
                
            score = 0.0
            
            # Audio scoring
            if audio_features:
                # Energy peaks in this segment
                energy_peaks = [t for t in audio_features.get('energy_peaks', []) 
                              if start_time <= t <= end_time]
                score += len(energy_peaks) * 0.1 * self.audio_weight
                
                # Average energy in this segment
                times = np.array(audio_features.get('times', []))
                rms_energy = np.array(audio_features.get('rms_energy', []))
                
                mask = (times >= start_time) & (times <= end_time)
                if np.any(mask):
                    avg_energy = np.mean(rms_energy[mask])
                    score += avg_energy * 0.2 * self.audio_weight
                
                # Speech segments
                speech_segments = audio_features.get('speech_segments', [])
                speech_overlap = sum(
                    max(0, min(seg['end'], end_time) - max(seg['start'], start_time))
                    for seg in speech_segments
                    if seg['start'] < end_time and seg['end'] > start_time
                )
                score += (speech_overlap / duration) * 0.1 * self.audio_weight
            
            # Visual scoring
            if visual_features:
                # Scene changes
                scene_changes = [t for t in visual_features.get('scene_changes', [])
                               if start_time <= t <= end_time]
                score += len(scene_changes) * 0.05 * self.visual_weight
                
                # Motion
                motion_scores = visual_features.get('motion_scores', [])
                segment_motion = [m['score'] for m in motion_scores 
                                if start_time <= m['time'] <= end_time]
                if segment_motion:
                    avg_motion = np.mean(segment_motion)
                    score += avg_motion * 0.001 * self.visual_weight
                
                # Face presence
                face_detections = visual_features.get('face_detections', [])
                faces_in_segment = [f for f in face_detections 
                                  if start_time <= f['time'] <= end_time]
                if faces_in_segment:
                    score += len(faces_in_segment) * 0.1 * self.visual_weight
                
                # Plant content
                plant_frames = visual_features.get('plant_frames', [])
                plant_in_segment = [p for p in plant_frames
                                  if start_time <= p['time'] <= end_time]
                if plant_in_segment:
                    avg_green = np.mean([p['green_ratio'] for p in plant_in_segment])
                    score += avg_green * 0.15 * self.visual_weight
            
            # Content scoring
            if content_features:
                # Keywords
                keywords = content_features.get('keywords', [])
                segment_keywords = [k for k in keywords 
                                  if start_time <= k['time'] <= end_time]
                
                # Weight different keyword categories
                keyword_weights = {
                    'high_energy': 0.3,
                    'instructional': 0.2,
                    'emotional': 0.25,
                    'conclusion': 0.15,
                    'question': 0.2,
                    'emphasis': 0.1,
                    'plant_health': 0.4,  # Higher weight for plant health
                    'garden_tasks': 0.35,
                    'plant_species': 0.3,
                    'garden_conditions': 0.25
                }
                
                for keyword in segment_keywords:
                    weight = keyword_weights.get(keyword['category'], 0.1)
                    score += weight * self.content_weight
                
                # Sentiment (prefer positive or highly negative - both engaging)
                sentiment_scores = content_features.get('sentiment_scores', [])
                segment_sentiment = [s['polarity'] for s in sentiment_scores
                                   if start_time <= s['time'] <= end_time]
                if segment_sentiment:
                    avg_sentiment = np.mean([abs(s) for s in segment_sentiment])
                    score += avg_sentiment * 0.1 * self.content_weight
                
                # Speaking rate (prefer moderate to fast)
                speaking_rates = content_features.get('speaking_rates', [])
                segment_rates = [r['rate'] for r in speaking_rates
                               if start_time <= r['time'] <= end_time]
                if segment_rates:
                    avg_rate = np.mean(segment_rates)
                    # Optimal speaking rate is around 2-4 words per second
                    if 2 <= avg_rate <= 4:
                        score += 0.1 * self.content_weight
                    elif avg_rate > 4:  # Fast speech can be engaging
                        score += 0.05 * self.content_weight
                
                # Emphasis moments
                emphasis_moments = content_features.get('emphasis_moments', [])
                segment_emphasis = [e for e in emphasis_moments
                                  if start_time <= e['time'] <= end_time]
                for emphasis in segment_emphasis:
                    score += (emphasis['questions'] + emphasis['exclamations'] + 
                             emphasis['caps_words']) * 0.05 * self.content_weight
            
            # Add score to segment
            segment['score'] = score
            scored_segments.append(segment)
        
        return scored_segments
    
    def _select_best_segments(
        self, 
        segments: List[Dict], 
        target_duration: float,
        min_segments: int = 1
    ) -> List[Dict]:
        """
        Select the best segments to include in the final highlight.
        
        Args:
            segments: List of scored segments
            target_duration: Target total duration in seconds
            min_segments: Minimum number of segments to include
            
        Returns:
            List of selected segments
        """
        if not segments:
            return []
        
        # Sort segments by score (highest first)
        sorted_segments = sorted(segments, key=lambda x: x.get('score', 0), reverse=True)
        
        selected = []
        total_duration = 0
        
        # Always include the highest scoring segments first
        for segment in sorted_segments:
            if total_duration >= target_duration and len(selected) >= min_segments:
                break
                
            segment_duration = segment['end'] - segment['start']
            
            # Skip if adding this segment would exceed target duration
            if total_duration + segment_duration > target_duration and len(selected) >= min_segments:
                continue
                
            selected.append(segment)
            total_duration += segment_duration
        
        # Sort selected segments by time
        selected.sort(key=lambda x: x['start'])
        
        return selected
    
    def _invert_silent_segments(
        self, 
        silent_segments: List[Dict], 
        total_duration: float
    ) -> List[Dict]:
        """
        Convert silent segments into segments to keep.
        
        Args:
            silent_segments: List of silent segments with 'start' and 'end' times
            total_duration: Total duration of the video in seconds
            
        Returns:
            List of segments to keep (non-silent)
        """
        logger.info(f"Inverting {len(silent_segments)} silent segments (total duration: {total_duration:.2f}s)")
        logger.info(f"Min duration: {self.min_duration:.2f}s, Max duration: {self.max_duration:.2f}s")
        
        if not silent_segments:
            logger.info("No silent segments found, keeping entire video")
            return [{"start": 0.0, "end": total_duration, "type": "full_video"}]
        
        # Sort silent segments by start time
        silent_segments.sort(key=lambda x: x.get("start", 0))
        
        # Log all silent segments
        for i, seg in enumerate(silent_segments, 1):
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            logger.debug(f"Silent segment {i}: {seg_start:.2f}s - {seg_end:.2f}s (duration: {seg_end - seg_start:.2f}s)")
        
        # Find the non-silent segments (gaps between silent segments)
        keep_segments = []
        prev_end = 0.0
        
        # Process each gap between silent segments
        for i, seg in enumerate(silent_segments, 1):
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            gap = seg_start - prev_end
            
            logger.debug(f"Gap {i}: {prev_end:.2f}s - {seg_start:.2f}s (duration: {gap:.2f}s)")
            
            # Add segment before this silent period if it's long enough
            if gap > 0:  # Only process positive gaps
                if gap >= self.min_duration:
                    logger.debug(f"  KEEPING segment: {prev_end:.2f}s - {seg_start:.2f}s (duration: {gap:.2f}s)")
                    keep_segments.append({
                        "start": prev_end,
                        "end": seg_start,
                        "type": "gap",
                        "duration": gap
                    })
                else:
                    logger.debug(f"  SKIPPING segment (too short): {prev_end:.2f}s - {seg_start:.2f}s (duration: {gap:.2f}s < {self.min_duration:.2f}s)")
            
            prev_end = seg_end
        
        # Add final segment if applicable
        final_gap = total_duration - prev_end
        if final_gap > 0:  # Only process if there's actually content after the last silent segment
            if final_gap >= self.min_duration:
                logger.debug(f"KEEPING final segment: {prev_end:.2f}s - {total_duration:.2f}s (duration: {final_gap:.2f}s)")
                keep_segments.append({
                    "start": prev_end,
                    "end": total_duration,
                    "type": "final",
                    "duration": final_gap
                })
            else:
                logger.debug(f"SKIPPING final segment (too short): {prev_end:.2f}s - {total_duration:.2f}s (duration: {final_gap:.2f}s < {self.min_duration:.2f}s)")
        
        # If no segments meet the minimum duration, try to find the longest segment
        if not keep_segments and silent_segments:
            logger.warning("No segments meet the minimum duration. Trying to find the longest segment...")
            
            # Find the longest gap between silent segments
            max_gap = 0
            best_segment = None
            
            # Check gaps between silent segments
            for i in range(1, len(silent_segments)):
                gap = silent_segments[i]["start"] - silent_segments[i-1]["end"]
                if gap > max_gap:
                    max_gap = gap
                    best_segment = {
                        "start": silent_segments[i-1]["end"],
                        "end": silent_segments[i]["start"],
                        "type": "longest_gap"
                    }
            
            # Check gap at the beginning
            first_gap = silent_segments[0]["start"] - 0
            if first_gap > max_gap:
                max_gap = first_gap
                best_segment = {
                    "start": 0.0,
                    "end": silent_segments[0]["start"],
                    "type": "longest_gap"
                }
            
            # Check gap at the end
            last_gap = total_duration - silent_segments[-1]["end"]
            if last_gap > max_gap:
                max_gap = last_gap
                best_segment = {
                    "start": silent_segments[-1]["end"],
                    "end": total_duration,
                    "type": "longest_gap"
                }
            
            if best_segment:
                duration = best_segment["end"] - best_segment["start"]
                logger.warning(f"Using longest gap found: {best_segment['start']:.2f}s - {best_segment['end']:.2f}s (duration: {duration:.2f}s)")
                keep_segments.append(best_segment)
            else:
                logger.warning("No valid segments found, defaulting to first segment")
                first_seg = silent_segments[0]
                keep_segments.append({
                    "start": 0.0,
                    "end": min(5.0, total_duration),  # Default to first 5 seconds or total duration if shorter
                    "type": "default"
                })
        
        logger.info(f"Found {len(keep_segments)} segments before max duration check")
        
        # Ensure segments don't exceed max duration
        result = []
        for seg in keep_segments:
            start = seg["start"]
            end = seg["end"]
            duration = end - start
            
            if duration > self.max_duration:
                # Split long segments into max_duration chunks
                num_chunks = int(duration // self.max_duration) + 1
                chunk_duration = duration / num_chunks
                logger.debug(f"Splitting long segment ({duration:.2f}s) into {num_chunks} chunks of ~{chunk_duration:.2f}s")
                
                for i in range(num_chunks):
                    chunk_start = start + i * chunk_duration
                    chunk_end = min(start + (i + 1) * chunk_duration, end)
                    chunk = {
                        "start": chunk_start,
                        "end": chunk_end,
                        "type": f"split_{i+1}_of_{num_chunks}",
                        "duration": chunk_end - chunk_start
                    }
                    result.append(chunk)
                    logger.debug(f"  Created chunk: {chunk['start']:.2f}s - {chunk['end']:.2f}s (duration: {chunk['duration']:.2f}s)")
            else:
                seg["duration"] = duration
                result.append(seg)
        
        # Log final segments
        logger.info(f"Returning {len(result)} segments after max duration check")
        total_duration = sum(seg.get("duration", 0) for seg in result)
        logger.info(f"Total duration of all segments: {total_duration:.2f}s")
        
        for i, seg in enumerate(result, 1):
            seg_duration = seg.get("duration", seg.get("end", 0) - seg.get("start", 0))
            logger.info(f"  Segment {i}: {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f} (duration: {seg_duration:.2f}s) [{seg.get('type', 'normal')}]")
        
        return result
        
    def _create_initial_segment(self, duration: float) -> List[Dict]:
        """Create the initial segment that should always be included."""
        # Always include first N seconds (or entire video if shorter)
        first_segment_end = min(self.always_include_first, duration)
        return [{
            'start': 0.0,
            'end': first_segment_end,
            'type': 'initial_segment',
            'priority': 1  # Highest priority
        }]
    
    def _find_plant_mentions(self, transcription: List[Dict]) -> List[Dict]:
        """Find segments where plants or their status are mentioned."""
        plant_segments = []
        
        for segment in transcription:
            text = segment.get('text', '').lower()
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            
            # Check for plant names or status words
            has_plant = any(plant in text for plant in self.PLANT_NAMES)
            has_status = any(status in text for status in self.STATUS_WORDS)
            
            if has_plant or has_status:
                # Add buffer around plant mentions
                buffered_start = max(0, start - self.plant_context_buffer)
                buffered_end = min(segment.get('duration', duration), end + self.plant_context_buffer)
                
                plant_segments.append({
                    'start': buffered_start,
                    'end': buffered_end,
                    'type': 'plant_mention',
                    'priority': 0.8,  # High priority to keep plant context
                    'reason': 'Plant name/status mentioned'
                })
        
        return plant_segments
    
    def _analyze_content(self, input_path: str, duration: float, transcription: List[Dict] = None) -> List[Dict]:
        """Analyze video content to find important segments."""
        segments = []
        
        # If video is short, just return the whole thing
        if duration <= self.min_highlight_duration:
            return [{'start': 0, 'end': duration, 'type': 'full_video', 'priority': 1}]
        
        # Add plant mentions if transcription is available
        if transcription:
            plant_segments = self._find_plant_mentions(transcription)
            segments.extend(plant_segments)
        
        # Sample from the video at regular intervals, but avoid overlapping with plant segments
        sample_interval = min(15, duration / 4)  # Sample every 15s or divide video into 4 parts
        
        for i in range(0, int(duration), int(sample_interval)):
            if i + self.min_duration > duration:
                break
                
            # Create segment with some overlap
            segment_start = max(0, i - 2.0)  # Start 2s earlier for context
            segment_end = min(duration, i + self.min_duration + 2.0)  # End 2s later for context
            
            segments.append({
                'start': float(segment_start),
                'end': float(segment_end),
                'type': 'sampled_segment',
                'priority': 0.4  # Lower priority than plant mentions
            })
        
        return segments
    
    def _merge_segments(self, segments: List[Dict], duration: float) -> List[Dict]:
        """Merge and prioritize segments to create final highlight segments."""
        if not segments:
            return []
            
        # Sort segments by start time first
        segments.sort(key=lambda x: x['start'])
        
        merged = []
        
        for seg in segments:
            if not merged:
                merged.append(seg)
                continue
                
            last = merged[-1]
            
            # Calculate gap between segments
            gap = seg['start'] - last['end']
            
            # If segments are close or overlapping, merge them
            if gap <= 5.0:  # 5 second maximum gap to merge
                # Extend the end time to include the new segment
                last['end'] = max(last['end'], seg['end'])
                
                # Update type and priority
                if seg.get('priority', 0) > last.get('priority', 0):
                    last['type'] = seg['type']
                    last['priority'] = seg['priority']
                elif seg.get('priority', 0) == last.get('priority', 0):
                    last['type'] = 'merged_segment'
                
                # Preserve any additional metadata from higher priority segments
                if seg.get('reason'):
                    last['reason'] = seg['reason']
            else:
                # If segments are far apart, add as new segment
                merged.append(seg)
        
        # Ensure we don't exceed max duration for any segment
        for seg in merged:
            seg_duration = seg['end'] - seg['start']
            if seg_duration > self.max_duration:
                # If segment is too long, take the middle portion
                mid = (seg['start'] + seg['end']) / 2
                seg['start'] = mid - (self.max_duration / 2)
                seg['end'] = mid + (self.max_duration / 2)
                seg['type'] = 'trimmed_segment'
        
        return merged
    
    def process(self, input_path: Path, output_path: Path = None, transcription: List[Dict] = None, **kwargs) -> Dict:
        """
        Process a video to create highlight segments.
        
        Args:
            video_path: Path to the video file
            video_info: Dictionary containing video metadata
            
        Returns:
            Dictionary containing:
                - status: "success" or "error"
                - segments: List of segments to keep
                - total_duration: Total duration of the original video
                - message: Error message if status is "error"
        """
        logger.info(f"Processing video for highlights: {input_path}")
        
        try:
            # Get video info from kwargs or get it ourselves
            video_info = kwargs.get('video_info', {})
            if not video_info:
                logger.info("No video_info provided in kwargs, getting video info...")
                from ..utils.video_utils import get_video_info
                video_info = get_video_info(input_path)
                logger.info(f"Retrieved video info: {video_info}")
            else:
                logger.info(f"Using provided video info: {video_info}")
            
            # Ensure we have a valid duration
            if 'duration' not in video_info or not video_info['duration']:
                raise ValueError("Could not determine video duration")
            
            duration = video_info['duration']
            logger.info(f"Video duration: {duration:.2f}s")
            
            # Step 1: Always include the first N seconds
            initial_segment = self._create_initial_segment(duration)
            
            # Step 2: Analyze content to find important segments, including plant mentions
            content_segments = self._analyze_content(str(input_path), duration, transcription)
            
            # Step 3: Combine and prioritize segments
            all_segments = initial_segment + content_segments
            keep_segments = self._merge_segments(all_segments, duration)
            
            # Ensure we have at least the initial segment
            if not keep_segments and initial_segment:
                keep_segments = initial_segment
                
            logger.info(f"Final selection: {len(keep_segments)} segments")
            for i, seg in enumerate(keep_segments, 1):
                seg_duration = seg['end'] - seg['start']
                logger.info(f"  Segment {i}: {seg['start']:.1f}s - {seg['end']:.1f}s "
                           f"({seg_duration:.1f}s) [{seg.get('type', 'unknown')}]")
            
            total_duration = sum(s['end'] - s['start'] for s in keep_segments)
            logger.info(f"Total highlight duration: {total_duration:.1f}s")
            
            # If there's an output path, process the video to extract highlights
            if output_path and keep_segments:
                try:
                    logger.info(f"Extracting {len(keep_segments)} segments to {output_path}")
                    from ..utils.video_utils import extract_segments
                    
                    # Ensure we have at least min_highlight_duration of content
                    total_duration = sum(s['end'] - s['start'] for s in keep_segments)
                    if total_duration < self.min_highlight_duration and duration > self.min_highlight_duration:
                        logger.warning(f"Highlight duration ({total_duration:.1f}s) is less than minimum target "
                                     f"({self.min_highlight_duration}s), adding more content")
                        # Add more content from the middle of the video
                        mid_point = duration / 2
                        extra_duration = self.min_highlight_duration - total_duration
                        extra_start = max(0, mid_point - (extra_duration / 2))
                        extra_end = min(duration, mid_point + (extra_duration / 2))
                        
                        keep_segments.append({
                            'start': extra_start,
                            'end': extra_end,
                            'type': 'extra_content',
                            'priority': 0.3
                        })
                        
                        # Re-merge segments to handle any overlaps
                        keep_segments = self._merge_segments(keep_segments, duration)
                    
                    extract_segments(
                        input_path=input_path,
                        segments=keep_segments,
                        output_path=output_path
                    )
                    logger.info("Successfully extracted segments")
                    
                except Exception as e:
                    logger.error(f"Error extracting segments: {e}", exc_info=True)
                    # If extraction fails, try with just the first 30 seconds
                    logger.warning("Falling back to first 30 seconds")
                    try:
                        extract_segments(
                            input_path=input_path,
                            segments=[{'start': 0, 'end': min(30, duration), 'type': 'fallback'}],
                            output_path=output_path
                        )
                        keep_segments = [{'start': 0, 'end': min(30, duration), 'type': 'fallback'}]
                    except Exception as fallback_error:
                        logger.error(f"Fallback extraction failed: {fallback_error}", exc_info=True)
                        raise e from fallback_error
            
            return {
                "status": "success" if keep_segments else "no_highlights",
                "segments": keep_segments,
                "total_duration": duration,
                "message": None if keep_segments else "No highlight segments found"
            }
        
        except Exception as e:
            error_msg = f"Error processing video: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "message": error_msg,
                "segments": [],
                "total_duration": 0
            }
    
    def _detect_silent_segments(self, video_path: Path) -> List[Dict]:
        """
        Detect silent segments in the audio using pydub's silence detection.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            List of silent segments with 'start' and 'end' times in seconds
        """
        try:
            logger.info(f"Loading audio from {video_path}")
            # Load audio using pydub
            audio = AudioSegment.from_file(str(video_path))
            
            # Log audio properties
            logger.info(f"Audio properties: {len(audio)}ms, {audio.channels} channels, {audio.frame_rate}Hz, {audio.sample_width*8}-bit")
            
            # Log detection parameters
            logger.info(f"Detection parameters: min_silence_len={self.min_silence_len}ms, "
                       f"silence_thresh={self.silence_thresh}dB, keep_silence={self.keep_silence}ms")
            
            # Detect silent chunks (ensure all parameters are integers)
            silent_chunks = silence.detect_silence(
                audio,
                min_silence_len=int(self.min_silence_len),
                silence_thresh=int(self.silence_thresh),
                seek_step=10  # 10ms step for better precision
            )
            
            logger.info(f"Found {len(silent_chunks)} silent chunks")
            
            # Convert from ms to seconds and adjust with keep_silence
            silent_segments = []
            for i, (start, end) in enumerate(silent_chunks, 1):
                # Convert from ms to seconds
                start_sec = start / 1000.0
                end_sec = end / 1000.0
                
                # Apply keep_silence adjustment (convert to seconds)
                start_adj = max(0, start_sec - (self.keep_silence / 1000.0))
                end_adj = min(len(audio) / 1000.0, end_sec + (self.keep_silence / 1000.0))
                
                segment = {
                    "start": start_adj,
                    "end": end_adj,
                    "original_start": start_sec,
                    "original_end": end_sec
                }
                
                logger.debug(f"Adjusted segment {i}: {start_adj:.2f}s - {end_adj:.2f}s (original: {start_sec:.2f}s - {end_sec:.2f}s)")
                silent_segments.append(segment)
            
            return silent_segments
            
        except Exception as e:
            logger.error(f"Error detecting silent segments: {e}", exc_info=True)
            # Log the full traceback for debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

# Register the processor
from app.editing.registry import register_processor

# Register the processor
register_processor('highlight_detector', HighlightDetector)
