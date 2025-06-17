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
