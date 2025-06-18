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
    """Converts whisper segments to ASS format with word-by-word timing synchronized to audio."""
    ass_header = """[Script Info]
Title: TikTok-Style Video Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,72,&Hffffff,&Hffffff,&H0,&Hf0ffffff,1,0,0,0,100,100,0,0,3,0,2,2,80,80,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    ass_content = ass_header
    
    # Use karaoke timing for word-by-word reveal
    for segment in segments:
        segment_start = segment['start']
        segment_end = segment['end']
        segment_text = segment['text'].strip()
        
        if not segment_text:
            continue
            
        # Create karaoke effect for progressive word reveal
        words = segment_text.split()
        if not words:
            continue
            
        # Calculate timing per word within the segment
        segment_duration = segment_end - segment_start
        time_per_word = segment_duration / len(words)
        
        # Build karaoke timing string for word-by-word reveal
        karaoke_text = ""
        for word in words:
            # Convert to centiseconds for ASS karaoke timing
            word_duration_cs = int(time_per_word * 100)
            karaoke_text += f"{{\\k{word_duration_cs}}}{word} "
        
        # Add TikTok-style pop animation to the karaoke text
        start_time = format_ass_time(segment_start)
        end_time = format_ass_time(segment_end)
        
        # Combine pop animation with karaoke timing
        animated_text = f"{{\\fade(255,0,0,255,0,100,100)\\t(0,150,\\fscx110\\fscy110)\\t(150,300,\\fscx100\\fscy100)}}{karaoke_text.strip()}"
        
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

def generate_word_level_timing(segments: list) -> list:
    """Generates precise word-level timing from Whisper segments."""
    all_word_timings = []
    
    for segment in segments:
        words = segment['text'].strip().split()
        if not words:
            continue
            
        segment_duration = segment['end'] - segment['start']
        
        # Calculate timing per word (evenly distributed across segment)
        time_per_word = segment_duration / len(words)
        
        for i, word in enumerate(words):
            word_start = segment['start'] + (i * time_per_word)
            word_end = segment['start'] + ((i + 1) * time_per_word)
            
            all_word_timings.append({
                'word': word,
                'start': word_start,
                'end': word_end,
                'segment_id': segment.get('id', 0),
                'word_index': i
            })
    
    return all_word_timings

def build_progressive_text_display(current_word_timing: dict, all_word_timings: list) -> str:
    """Builds progressive text display showing words as they're spoken with 3-4 second retention."""
    current_time = current_word_timing['start']
    retention_duration = 3.5  # 3.5 seconds retention
    
    # Find all words that should be visible at this time
    visible_words = []
    
    for word_timing in all_word_timings:
        word_start = word_timing['start']
        word_age = current_time - word_start
        
        # Show word if:
        # 1. It's the current word (word_start <= current_time < word_end)
        # 2. It was spoken recently (within retention_duration)
        # 3. It's not in the future
        if (word_start <= current_time and 
            word_age <= retention_duration and 
            word_age >= 0):
            
            # Highlight current word differently
            if word_timing == current_word_timing:
                # Current word gets highlighted (make it stand out)
                visible_words.append(f"{{\\c&Hffffff&}}{word_timing['word']}{{\\c&H000000&}}")
            else:
                # Previous words are shown normally but slightly faded
                visible_words.append(f"{{\\alpha&H40&}}{word_timing['word']}{{\\alpha&H00&}}")
    
    # Format for display with proper line breaks
    display_text = ' '.join(visible_words)
    
    # Break into lines if too long
    if len(display_text) > 50:
        words_for_lines = [w for w in visible_words]
        lines = break_text_into_lines(' '.join([w.split('}')[-1].split('{')[0] for w in words_for_lines]), max_chars=50, max_lines=2)
        # Rebuild with formatting preserved
        formatted_lines = []
        word_idx = 0
        for line in lines:
            line_words = line.split()
            line_formatted = []
            for _ in line_words:
                if word_idx < len(visible_words):
                    line_formatted.append(visible_words[word_idx])
                    word_idx += 1
            formatted_lines.append(' '.join(line_formatted))
        display_text = '\\N'.join(formatted_lines)
    
    return display_text

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