import re
import json
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class WordTiming:
    """Represents timing for a single word."""
    word: str
    start: float
    end: float
    confidence: float = 1.0


def generate_word_level_timing_enhanced(segments: List[Dict]) -> List[WordTiming]:
    """
    Enhanced word-level timing generation with better speech rhythm modeling.
    """
    word_timings = []
    
    for segment in segments:
        text = segment.get('text', '').strip()
        if not text:
            continue
            
        start_time = segment.get('start', 0.0)
        end_time = segment.get('end', 0.0)
        duration = end_time - start_time
        
        if duration <= 0:
            continue
        
        # Clean and split text into words
        words = clean_and_split_text(text)
        if not words:
            continue
        
        # Calculate timing per word with natural speech patterns
        word_durations = calculate_natural_word_durations(words, duration)
        
        # Generate word timings
        current_time = start_time
        for word, word_duration in zip(words, word_durations):
            word_start = current_time
            word_end = current_time + word_duration
            
            word_timings.append(WordTiming(
                word=word,
                start=word_start,
                end=word_end,
                confidence=segment.get('confidence', 1.0)
            ))
            
            current_time = word_end
    
    return word_timings


def clean_and_split_text(text: str) -> List[str]:
    """Clean text and split into words, preserving punctuation."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Split on whitespace but keep punctuation with words
    words = []
    for word in text.split():
        if word:
            words.append(word)
    
    return words


def calculate_natural_word_durations(words: List[str], total_duration: float) -> List[float]:
    """
    Calculate natural word durations based on word characteristics.
    Longer/complex words get more time, shorter words get less.
    """
    if not words:
        return []
    
    # Base weights for different word characteristics
    word_weights = []
    for word in words:
        weight = 1.0
        
        # Longer words get more time
        weight += len(word) * 0.1
        
        # Words with punctuation get slightly more time for emphasis
        if any(p in word for p in '.,!?;:'):
            weight += 0.2
        
        # All caps words (shouting) get more time
        if word.isupper() and len(word) > 1:
            weight += 0.3
        
        # Common short words get less time
        if word.lower() in ['a', 'an', 'the', 'is', 'was', 'are', 'were', 'to', 'of', 'in', 'on', 'at']:
            weight *= 0.7
        
        word_weights.append(weight)
    
    # Normalize weights to match total duration
    total_weight = sum(word_weights)
    word_durations = [(w / total_weight) * total_duration for w in word_weights]
    
    # Ensure minimum duration per word (0.2 seconds)
    min_duration = 0.2
    for i in range(len(word_durations)):
        if word_durations[i] < min_duration:
            word_durations[i] = min_duration
    
    # Adjust if total exceeds available time
    actual_total = sum(word_durations)
    if actual_total > total_duration:
        scale_factor = total_duration / actual_total
        word_durations = [d * scale_factor for d in word_durations]
    
    return word_durations


def segments_to_professional_ass(segments: List[Dict]) -> str:
    """
    Convert segments to professional ASS format with word-by-word karaoke timing
    like TikTok/Instagram Reels with proper wrapping and professional styling.
    """
    
    # Professional ASS header with modern styling and proper wrapping
    ass_header = """[Script Info]
Title: Professional Short-Form Video Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,78,&H00FFFFFF,&H00000000,&H009966FF,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,80,80,200,1
Style: Highlight,Arial Black,78,&H00FFFFFF,&H009966FF,&H009966FF,&H00000000,-1,0,0,0,105,105,0,0,1,4,0,2,80,80,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Generate word-level timing
    word_timings = generate_word_level_timing_enhanced(segments)
    if not word_timings:
        return ass_header
    
    # Group words by sentences/segments for better visual presentation
    sentence_groups = group_words_by_sentences(word_timings, segments)
    
    ass_events = []
    
    for group in sentence_groups:
        if not group['words']:
            continue
            
        # Create the karaoke effect for this sentence with proper wrapping
        karaoke_text = create_professional_karaoke_effect_with_wrapping(group['words'])
        
        # Add pop-in animation for the whole sentence
        start_time = format_ass_time(group['start'])
        end_time = format_ass_time(group['end'])
        
        # Main caption with word-by-word reveal and proper wrapping
        animated_text = (
            f"{{\\q1\\fade(0,255,0,255,0,200,400)"
            f"\\pos(540,1520)"
            f"\\t(0,300,\\fscx105\\fscy105)"
            f"\\t(300,500,\\fscx100\\fscy100)}}"
            f"{karaoke_text}"
        )
        
        ass_events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{animated_text}")
    
    return ass_header + "\n".join(ass_events)


def group_words_by_sentences(word_timings: List[WordTiming], segments: List[Dict]) -> List[Dict]:
    """Group words by sentences/segments for better visual presentation."""
    groups = []
    current_group = []
    
    segment_index = 0
    current_segment_end = segments[segment_index].get('end', 0) if segments else float('inf')
    
    for word_timing in word_timings:
        # Check if we've moved to the next segment
        while word_timing.start >= current_segment_end and segment_index < len(segments) - 1:
            if current_group:
                groups.append({
                    'words': current_group,
                    'start': current_group[0].start,
                    'end': current_group[-1].end
                })
                current_group = []
            
            segment_index += 1
            current_segment_end = segments[segment_index].get('end', float('inf'))
        
        current_group.append(word_timing)
        
        # Break on sentence-ending punctuation or max words per line for better wrapping
        if (word_timing.word.endswith(('.', '!', '?')) or 
            len(current_group) >= 6):  # Reduced to 6 words per caption line for better wrapping
            
            groups.append({
                'words': current_group,
                'start': current_group[0].start,
                'end': current_group[-1].end
            })
            current_group = []
    
    # Add remaining words
    if current_group:
        groups.append({
            'words': current_group,
            'start': current_group[0].start,
            'end': current_group[-1].end
        })
    
    return groups


def create_professional_karaoke_effect_with_wrapping(words: List[WordTiming]) -> str:
    """
    Create professional karaoke effect with proper timing and automatic wrapping.
    """
    if not words:
        return ""
    
    karaoke_parts = []
    current_line_length = 0
    max_line_length = 35  # Characters per line for proper mobile display
    
    for i, word in enumerate(words):
        # Calculate duration in centiseconds for ASS
        duration_cs = int((word.end - word.start) * 100)
        
        # Ensure minimum duration for readability
        duration_cs = max(duration_cs, 30)  # Minimum 0.3 seconds
        
        # Check if we need to wrap to new line
        word_length = len(word.word)
        if current_line_length + word_length + 1 > max_line_length and current_line_length > 0:
            # Add line break and reset counter
            karaoke_parts.append("\\N")  # Hard line break in ASS
            current_line_length = 0
        
        # Add emphasis effects for important words
        word_text = word.word
        if is_emphasis_word(word_text):
            # Important words get extra styling with purple highlight
            word_effect = (
                f"{{\\k{duration_cs}\\t(0,{duration_cs//2},\\fscx115\\fscy115\\c&H9966FF&)"
                f"\\t({duration_cs//2},{duration_cs},\\fscx100\\fscy100\\c&HFFFFFF&)}}{word_text}"
            )
        else:
            # Regular words with standard karaoke timing
            word_effect = f"{{\\k{duration_cs}}}{word_text}"
        
        karaoke_parts.append(word_effect)
        current_line_length += word_length
        
        # Add space between words (except for the last word or before line breaks)
        if i < len(words) - 1:
            karaoke_parts.append(" ")
            current_line_length += 1
    
    return "".join(karaoke_parts)


def is_emphasis_word(word: str) -> bool:
    """Determine if a word should get emphasis styling."""
    # Remove punctuation for checking
    clean_word = re.sub(r'[^\w]', '', word.lower())
    
    # Words that typically get emphasis in short-form videos
    emphasis_words = {
        'amazing', 'incredible', 'wow', 'awesome', 'fantastic', 'perfect',
        'love', 'hate', 'never', 'always', 'exactly', 'absolutely',
        'definitely', 'obviously', 'literally', 'actually', 'really',
        'super', 'mega', 'ultra', 'best', 'worst', 'crazy', 'insane',
        'look', 'see', 'watch', 'check', 'here', 'this', 'that'
    }
    
    # Check if word is in emphasis list or is all caps
    return (clean_word in emphasis_words or 
            (word.isupper() and len(clean_word) > 2) or
            word.endswith('!'))


def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def optimize_caption_timing(segments: List[Dict]) -> List[Dict]:
    """
    Optimize segment timing for better caption flow.
    Reduces gaps and ensures smooth transitions.
    """
    if len(segments) <= 1:
        return segments
    
    optimized = []
    
    for i, segment in enumerate(segments):
        new_segment = segment.copy()
        
        # Reduce gap to next segment for smoother flow
        if i < len(segments) - 1:
            next_segment = segments[i + 1]
            gap = next_segment['start'] - segment['end']
            
            # If gap is small, extend current segment to reduce it
            if 0 < gap <= 0.5:  # Gaps of 0.5 seconds or less
                new_segment['end'] = next_segment['start'] - 0.05
        
        optimized.append(new_segment)
    
    return optimized


# Example usage function
def create_professional_captions(segments: List[Dict]) -> str:
    """
    Main function to create professional captions with proper positioning and wrapping.
    
    Args:
        segments: List of transcription segments with 'text', 'start', 'end'
    
    Returns:
        ASS subtitle content with professional word-by-word timing and proper wrapping
    """
    if not segments:
        return ""
    
    # Optimize timing
    optimized_segments = optimize_caption_timing(segments)
    
    # Generate professional ASS captions with proper wrapping
    ass_content = segments_to_professional_ass(optimized_segments)
    
    return ass_content