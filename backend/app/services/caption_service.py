def format_srt_time(seconds: float) -> str:
    """Converts seconds to SRT time format HH:MM:SS,mmm."""
    millis = int(round(seconds * 1000))
    ss, millis = divmod(millis, 1000)
    mm, ss = divmod(ss, 60)
    hh, mm = divmod(mm, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{millis:03d}"

def segments_to_srt(segments: list) -> str:
    """Converts whisper segments to SRT format."""
    srt_content = ""
    
    for i, segment in enumerate(segments, 1):
        start_time = format_srt_time(segment['start'])
        end_time = format_srt_time(segment['end'])
        text = segment['text'].strip()
        
        # Break text into lines if it's too long
        lines = break_text_into_lines(text, max_chars=50, max_lines=2)
        text_formatted = '\n'.join(lines)
        
        srt_content += f"{i}\n{start_time} --> {end_time}\n{text_formatted}\n\n"
    
    return srt_content.strip()

def segments_to_ass(segments: list) -> str:
    """Converts whisper segments to ASS format with TikTok-style animations."""
    ass_header = """[Script Info]
Title: TikTok-Style Video Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Oswald Black,48,&Hffffff,&Hffffff,&H0,&H90000000,1,0,0,0,100,100,0,0,4,0,0,2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    ass_content = ass_header
    
    # Optimize segment timing for TikTok-style flow
    optimized_segments = optimize_segment_timing(segments)
    
    for segment in optimized_segments:
        start_time = format_ass_time(segment['start'])
        end_time = format_ass_time(segment['end'])
        text = segment['text'].strip()
        
        # Break text into lines if it's too long
        lines = break_text_into_lines(text, max_chars=50, max_lines=2)
        text_formatted = '\\N'.join(lines)
        
        # Check if text is long enough for word-by-word reveal
        words = text.split()
        segment_duration = segment['end'] - segment['start']
        
        if len(words) > 4 and segment_duration > 2.5:  # Use word reveal for medium+ segments
            # Create word-by-word reveal effect with TikTok-style animation
            word_reveal_text = create_tiktok_word_reveal(words, segment_duration)
            # Add TikTok-style entrance animation with scale effect
            animated_text = f"{{\\fade(255,0,0,255,0,150,150)\\t(0,300,\\fscx120\\fscy120)\\t(300,400,\\fscx100\\fscy100)}}{word_reveal_text}"
        else:
            # Use bouncy entrance for shorter segments
            animated_text = f"{{\\fade(255,0,0,255,0,200,200)\\t(0,200,\\fscx110\\fscy110)\\t(200,300,\\fscx100\\fscy100)}}{text_formatted}"
        
        ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{animated_text}\n"
    
    return ass_content

def create_word_reveal_effect(words: list, duration: float) -> str:
    """Creates a word-by-word reveal effect using ASS karaoke timing."""
    if not words:
        return ""
    
    # Calculate timing per word (in centiseconds for ASS)
    time_per_word = (duration * 100) / len(words)  # Convert to centiseconds
    
    # Build karaoke effect string
    karaoke_text = ""
    for word in words:
        # \\k timing makes each word appear progressively
        karaoke_text += f"{{\\k{int(time_per_word)}}}{word} "
    
    return karaoke_text.strip()

def create_tiktok_word_reveal(words: list, duration: float) -> str:
    """Creates a TikTok-style word reveal with pop-in effects."""
    if not words:
        return ""
    
    # Calculate timing per word with faster reveals for TikTok style
    time_per_word = max(20, (duration * 80) / len(words))  # Minimum 0.2s per word, faster overall
    
    # Build karaoke effect with scale animations for each word
    karaoke_text = ""
    for i, word in enumerate(words):
        # Each word gets a subtle scale effect when it appears
        karaoke_text += f"{{\\k{int(time_per_word)}\\t(0,100,\\fscx105\\fscy105)\\t(100,200,\\fscx100\\fscy100)}}{word} "
    
    return karaoke_text.strip()

def optimize_segment_timing(segments: list) -> list:
    """Reduces gaps between segments for smoother TikTok-style flow."""
    if len(segments) <= 1:
        return segments
    
    optimized = []
    for i, segment in enumerate(segments):
        new_segment = segment.copy()
        
        # Reduce gap to next segment to 0.1 seconds max
        if i < len(segments) - 1:
            next_segment = segments[i + 1]
            gap = next_segment['start'] - segment['end']
            if gap > 0.1:
                # Extend current segment to reduce gap
                new_segment['end'] = next_segment['start'] - 0.1
        
        optimized.append(new_segment)
    
    return optimized

def format_ass_time(seconds: float) -> str:
    """Converts seconds to ASS time format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"

def break_text_into_lines(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Breaks text into lines with max_chars and max_lines constraints."""
    words = text.strip().split()
    lines = []
    current_line = ""
    if not words:
        return []

    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= max_chars:
            current_line += " " + word
        else:
            if len(lines) < max_lines - 1:
                lines.append(current_line)
                current_line = word
            else:
                current_line += " " + word
    
    if current_line:
        lines.append(current_line)
    
    return lines[:max_lines]
