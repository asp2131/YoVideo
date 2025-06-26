# backend/app/tasks/transcription.py (fixed version)

import os
import tempfile
import logging
import subprocess
import json
from celery import current_task
from app.core.celery_app import celery_app
from app.services.supabase_client import supabase
from app.services.r2_client import get_r2_client
from app.services.caption_service import segments_to_ass
from app.services.enhanced_caption_service import create_professional_captions
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def transcribe_video_task(self, project_id: str, processing_options: dict = None):
    """
    Enhanced transcription task that can either:
    1. Just add captions to the full video
    2. Create intelligent highlights + add captions
    """
    logger.info(f"Starting transcription for project_id: {project_id}")
    
    # Default processing options
    if processing_options is None:
        processing_options = {
            'enable_intelligent_editing': False,
            'editing_style': 'engaging',
            'target_duration': 60,
            'content_type': 'general'
        }
    
    # Handle both camelCase (frontend) and snake_case (backend)
    enable_editing = (
        processing_options.get('enable_intelligent_editing', False) or 
        processing_options.get('enableIntelligentEditing', False)
    )
    
    logger.info(f"🎬 Processing options: {processing_options}")
    logger.info(f"🤖 Intelligent editing: {'ENABLED' if enable_editing else 'DISABLED'}")

    try:
        # 1. Get video path from the projects table
        project_response = supabase.table("projects").select("video_path, name").eq("id", project_id).execute()
        
        if not project_response.data or len(project_response.data) == 0:
            raise ValueError(f"No project found with id {project_id}")
            
        project_data = project_response.data[0]
        video_path = project_data.get("video_path")
        project_name = project_data.get("name", "video")

        if not video_path:
            raise ValueError(f"No video_path found for project {project_id}")

        # 2. Download video from R2 Storage
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_path)[1]) as tmp_video_file:
            tmp_video_file_path = tmp_video_file.name
            
        logger.info(f"📥 Downloading {video_path} from R2 Storage...")
        
        client = get_r2_client()
        if client is None:
            raise Exception("Failed to initialize R2 client")
            
        try:
            client.download_file(video_path, tmp_video_file_path)
            logger.info(f"✅ Video downloaded to {tmp_video_file_path}")
        except Exception as e:
            logger.error(f"❌ Failed to download video from R2: {str(e)}")
            raise Exception(f"Failed to download video: {str(e)}")
            
        # Validate video file
        file_size = os.path.getsize(tmp_video_file_path)
        logger.info(f"📁 Video file size: {file_size} bytes")
        
        if file_size == 0:
            raise Exception("Downloaded video file is empty")

        # 3. Update project status to processing
        supabase.table("projects").update({
            "status": "processing"
        }).eq("id", project_id).execute()

        # 4. Transcribe the video file
        logger.info(f"🎙️ Starting transcription for {tmp_video_file_path}...")
        
        try:
            # Run whisper via subprocess
            result = run_whisper_subprocess(tmp_video_file_path)
            
            # Extract transcription text and segments
            transcription_text = result["text"]
            segments = result.get("segments", [])
            
            logger.info(f"✅ Transcription completed successfully - {len(segments)} segments")
        except Exception as transcription_error:
            logger.error(f"❌ Whisper transcription failed: {str(transcription_error)}")
            raise transcription_error

        # 5. Save transcription to database
        if not segments and not transcription_text:
            logger.warning("⚠️ Whisper produced no segments or text - likely no audible speech in video")
            # Create a minimal transcription entry
            transcription_data = {
                "project_id": project_id,
                "transcription_data": {
                    "text": "",
                    "segments": [],
                    "language": result.get("language", "en")
                },
                "srt_content": ""
            }
            
            supabase.table("transcriptions").insert(transcription_data).execute()
            logger.info(f"💾 Saved empty transcription to database for project {project_id}")
            
            # Update project status to completed
            supabase.table("projects").update({
                "status": "completed"
            }).eq("id", project_id).execute()
            
            return

        # Create professional ASS content for captions
        ass_content = create_professional_captions(segments)

        if not ass_content:
            logger.error("❌ Failed to generate professional captions")
            # Fallback to basic SRT
            from app.services.caption_service import segments_to_srt
            ass_content = segments_to_srt(segments)

        logger.info(f"📝 Generated professional captions ({len(ass_content)} characters)")
        
        # Save transcription data
        transcription_data = {
            "project_id": project_id,
            "transcription_data": {
                "text": transcription_text,
                "segments": result["segments"],
                "language": result.get("language", "en"),
                "word_level_timing": True,
                "caption_style": "professional_shortform",
                "processing_options": processing_options
            },
            "srt_content": ass_content
        }
        
        supabase.table("transcriptions").insert(transcription_data).execute()
        logger.info(f"💾 Saved transcription to database for project {project_id}")

        # 6. Choose processing path based on intelligent editing option
        if enable_editing:
            logger.info(f"🤖 Starting INTELLIGENT EDITING for project {project_id}")
            logger.info(f"🎯 Style: {processing_options.get('editing_style', 'engaging')}")
            logger.info(f"⏱️ Target duration: {processing_options.get('target_duration', 60)}s")
            logger.info(f"📋 Content type: {processing_options.get('content_type', 'general')}")
            
            processed_video_path = asyncio.run(process_intelligent_editing(
                project_id, 
                tmp_video_file_path, 
                segments, 
                processing_options
            ))
            
            if processed_video_path:
                logger.info(f"✅ Intelligent editing completed: {processed_video_path}")
            else:
                logger.warning("⚠️ Intelligent editing failed, falling back to caption overlay")
                processed_video_path = generate_caption_overlay(
                    project_id, 
                    tmp_video_file_path, 
                    ass_content
                )
        else:
            logger.info(f"📝 Starting CAPTION OVERLAY (no intelligent editing) for project {project_id}")
            processed_video_path = generate_caption_overlay(
                project_id, 
                tmp_video_file_path, 
                ass_content
            )
        
        if processed_video_path:
            logger.info(f"🎉 Processing completed for project {project_id}")

        # 7. Update project status to completed
        supabase.table("projects").update({
            "status": "completed"
        }).eq("id", project_id).execute()

        # 8. Update processing job status to completed
        supabase.table("processing_jobs").update({
            "status": "completed"
        }).eq("project_id", project_id).execute()

        logger.info(f"🎉 All processing completed for project {project_id}")

    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ Processing failed for project {project_id}: {error_message}", exc_info=True)
        
        # Update processing job status to failed
        supabase.table("processing_jobs").update({
            "status": "failed",
            "error_message": error_message
        }).eq("project_id", project_id).execute()
        
        # Update project status to failed
        supabase.table("projects").update({
            "status": "failed"
        }).eq("id", project_id).execute()

    finally:
        # Clean up temporary video file
        if 'tmp_video_file_path' in locals() and os.path.exists(tmp_video_file_path):
            os.unlink(tmp_video_file_path)


async def process_intelligent_editing(
    project_id: str, 
    input_video_path: str, 
    transcription_segments: list, 
    processing_options: dict
) -> str:
    """
    Process video with intelligent editing using the OpusClipLevelPipeline.
    """
    try:
        logger.info(f"🤖 Starting intelligent editing for project {project_id}")
        
        # Import the editing pipeline components
        from app.editing.segmenters.intelligent_segmenter import OpusClipLevelPipeline, create_opus_clip_config
        
        # Create optimized config based on processing options
        content_type = processing_options.get('content_type', 'general')
        target_duration = processing_options.get('target_duration', 60)
        editing_style = processing_options.get('editing_style', 'engaging')
        
        config = create_opus_clip_config(
            content_type=content_type,
            target_duration=float(target_duration),
            quality_level='high'
        )
        
        # Create pipeline
        pipeline = OpusClipLevelPipeline(config)
        
        # Process video with intelligent editing
        results = await pipeline.process_video_to_opus_clip_quality(
            video_path=input_video_path,
            transcription=transcription_segments,
            output_dir=None  # We'll handle upload separately
        )
        
        if not results.get('success', False):
            error_msg = results.get('error', 'Unknown error')
            logger.error(f"❌ Intelligent editing failed: {error_msg}")
            return None
        
        highlights = results.get('highlights', [])
        logger.info(f"🎯 Generated {len(highlights)} intelligent highlights")
        
        if not highlights:
            logger.warning("⚠️ No highlights generated from intelligent editing")
            return None
        
        # Create highlight video with precise segment extraction
        highlight_video_path = await create_precise_highlight_video(
            project_id,
            input_video_path,
            highlights,
            transcription_segments
        )
        
        return highlight_video_path
        
    except Exception as e:
        logger.error(f"❌ Intelligent editing failed for project {project_id}: {str(e)}", exc_info=True)
        return None


async def create_precise_highlight_video(
    project_id: str,
    input_video_path: str,
    highlights: list,
    transcription_segments: list
) -> str:
    """
    Create highlight video with precise segment extraction and captions.
    """
    temp_segments = []
    ass_file_path = None
    concat_list_path = None
    output_video_path = None
    
    try:
        logger.info(f"🎬 Creating precise highlight video with {len(highlights)} segments")
        
        # Sort highlights by start time
        sorted_highlights = sorted(highlights, key=lambda h: h.get('start', 0))
        
        # Extract each highlight segment with precise timing
        for i, highlight in enumerate(sorted_highlights):
            start = highlight.get('start', 0)
            end = highlight.get('end', 0)
            duration = end - start
            
            if duration <= 0:
                logger.warning(f"Skipping invalid highlight {i}: start={start}, end={end}")
                continue
            
            # Create temporary file for this segment
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_segment_path = temp_file.name
                temp_segments.append(temp_segment_path)
            
            # Use precise FFmpeg extraction with re-encoding for accuracy
            ffmpeg_cmd = [
                'ffmpeg',
                '-ss', str(start),  # Seek to start time
                '-i', input_video_path,  # Input file
                '-t', str(duration),  # Duration
                '-c:v', 'libx264',  # Re-encode video for precision
                '-c:a', 'aac',  # Re-encode audio
                '-preset', 'fast',  # Fast encoding preset
                '-crf', '23',  # Good quality
                '-avoid_negative_ts', 'make_zero',  # Fix timestamp issues
                '-y',  # Overwrite output
                temp_segment_path
            ]
            
            logger.info(f"📹 Extracting segment {i+1}/{len(sorted_highlights)}: {start:.2f}s - {end:.2f}s")
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            
            if not os.path.exists(temp_segment_path) or os.path.getsize(temp_segment_path) == 0:
                logger.error(f"❌ Failed to create segment {i}: {temp_segment_path}")
                continue
                
            logger.info(f"✅ Created segment {i+1}: {os.path.basename(temp_segment_path)}")
        
        if not temp_segments:
            raise Exception("No valid segments were created")
        
        # Create concatenation list
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as concat_file:
            concat_list_path = concat_file.name
            for segment_path in temp_segments:
                concat_file.write(f"file '{os.path.abspath(segment_path)}'\n")
        
        # Create output video file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_video_path = output_file.name
        
        # Concatenate segments
        concat_cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_path,
            '-c', 'copy',  # Copy streams without re-encoding
            '-y',
            output_video_path
        ]
        
        logger.info("🔗 Concatenating highlight segments...")
        result = subprocess.run(concat_cmd, capture_output=True, text=True, check=True)
        
        # Create captions for highlights
        highlight_segments = []
        current_time = 0.0
        
        for highlight in sorted_highlights:
            start = highlight.get('start', 0)
            end = highlight.get('end', 0)
            
            # Find matching transcription segments and adjust timing
            for seg in transcription_segments:
                seg_start = seg.get('start', 0)
                seg_end = seg.get('end', 0)
                
                # Check if segment overlaps with highlight
                if seg_start < end and seg_end > start:
                    # Adjust timing to be relative to concatenated video
                    adjusted_segment = seg.copy()
                    overlap_start = max(seg_start, start)
                    overlap_end = min(seg_end, end)
                    
                    # Calculate position in concatenated video
                    segment_offset = overlap_start - start
                    adjusted_segment['start'] = current_time + segment_offset
                    adjusted_segment['end'] = current_time + (overlap_end - start)
                    
                    highlight_segments.append(adjusted_segment)
            
            current_time += (end - start)
        
        logger.info(f"📝 Created {len(highlight_segments)} caption segments for highlights")
        
        # Add captions if we have transcription
        if highlight_segments:
            from app.services.enhanced_caption_service import create_professional_captions
            ass_content = create_professional_captions(highlight_segments)
            
            if ass_content:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as ass_file:
                    ass_file.write(ass_content)
                    ass_file.flush()
                    ass_file_path = ass_file.name
                
                # Create final video with captions
                final_output_path = output_video_path + '_with_captions.mp4'
                
                caption_cmd = [
                    'ffmpeg',
                    '-i', output_video_path,
                    '-vf', f"ass={ass_file_path}",
                    '-c:a', 'copy',
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-y',
                    final_output_path
                ]
                
                logger.info("🎨 Adding captions to highlight video...")
                result = subprocess.run(caption_cmd, capture_output=True, text=True, check=True)
                output_video_path = final_output_path
        
        # Upload to R2
        processed_filename = f"processed_{project_id}.mp4"
        client = get_r2_client()
        
        logger.info(f"☁️ Uploading highlight video to R2: {processed_filename}")
        upload_result = client.upload_file(
            output_video_path,
            processed_filename,
            "video/mp4"
        )
        
        if not upload_result.get('success'):
            raise Exception(f"Upload failed: {upload_result}")
        
        # Update project with processed video path
        supabase.table("projects").update({
            "processed_video_path": processed_filename
        }).eq("id", project_id).execute()
        
        logger.info(f"🎉 Intelligent highlight video uploaded: {processed_filename}")
        return processed_filename
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg command failed: {e.stderr}")
        raise Exception(f"Video processing failed: {e.stderr}")
    except Exception as e:
        logger.error(f"❌ Failed to create precise highlight video: {str(e)}", exc_info=True)
        raise
    finally:
        # Clean up temporary files
        for temp_file in temp_segments:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Failed to cleanup {temp_file}: {cleanup_error}")
        
        for cleanup_file in [ass_file_path, concat_list_path, output_video_path]:
            if cleanup_file and os.path.exists(cleanup_file):
                try:
                    os.unlink(cleanup_file)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Failed to cleanup {cleanup_file}: {cleanup_error}")


async def create_highlight_video_with_captions(
    project_id: str,
    input_video_path: str,
    highlights: list,
    transcription_segments: list
) -> str:
    """
    Create a highlight video with captions burned in.
    """
    ass_file_path = None
    highlight_video_path = None
    output_video_path = None
    
    try:
        logger.info(f"🎬 Creating highlight video with {len(highlights)} segments")
        
        # Create segments for highlights
        highlight_segments = []
        for highlight in highlights:
            start = highlight.get('start', 0)
            end = highlight.get('end', 0)
            
            # Find matching transcription segments
            matching_segments = [
                seg for seg in transcription_segments
                if seg.get('start', 0) >= start and seg.get('end', 0) <= end
            ]
            
            highlight_segments.extend(matching_segments)
        
        logger.info(f"📝 Found {len(highlight_segments)} transcription segments for highlights")
        
        # Create ASS content for highlights
        from app.services.enhanced_caption_service import create_professional_captions
        ass_content = create_professional_captions(highlight_segments)
        
        if not ass_content:
            logger.warning("⚠️ Failed to create professional captions, using basic ASS")
            ass_content = segments_to_ass(highlight_segments)
        
        # Create temporary ASS file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as ass_file:
            ass_file.write(ass_content)
            ass_file.flush()
            ass_file_path = ass_file.name
        
        logger.info(f"📝 Created ASS file: {ass_file_path}")
        
        # Create highlight video (without captions first)
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as highlight_file:
            highlight_video_path = highlight_file.name
        
        # Extract highlights using ffmpeg
        from app.editing.utils.video_utils import extract_segments
        segments_for_extraction = [
            {'start': h.get('start', 0), 'end': h.get('end', 0)}
            for h in highlights
        ]
        
        logger.info(f"✂️ Extracting {len(segments_for_extraction)} segments...")
        result_path = extract_segments(
            input_path=input_video_path,
            segments=segments_for_extraction,
            output_path=highlight_video_path
        )
        
        if not result_path:
            raise Exception("Failed to extract highlight segments")
        
        logger.info(f"✅ Highlight segments extracted to: {highlight_video_path}")
        
        # Add captions to highlight video
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_video_path = output_file.name
        
        # FFmpeg command to add captions
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', highlight_video_path,
            '-vf', f"ass={ass_file_path}",
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-movflags', '+faststart',  # Optimize for web playback
            '-y',
            output_video_path
        ]
        
        logger.info("🎨 Adding captions to highlight video...")
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
        logger.info("✅ Captions added successfully")
        
        # Upload to R2
        processed_filename = f"processed_{project_id}.mp4"
        client = get_r2_client()
        
        logger.info(f"☁️ Uploading to R2: {processed_filename}")
        upload_result = client.upload_file(
            output_video_path,
            processed_filename,
            "video/mp4"
        )
        
        if not upload_result.get('success'):
            raise Exception(f"Upload failed: {upload_result}")
        
        # Update project with processed video path
        supabase.table("projects").update({
            "processed_video_path": processed_filename
        }).eq("id", project_id).execute()
        
        logger.info(f"🎉 Highlight video with captions uploaded: {processed_filename}")
        return processed_filename
        
    except Exception as e:
        logger.error(f"❌ Failed to create highlight video with captions: {str(e)}", exc_info=True)
        raise
    finally:
        # Clean up temporary files
        for temp_file in [ass_file_path, highlight_video_path, output_video_path]:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    logger.debug(f"🧹 Cleaned up: {temp_file}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Failed to cleanup {temp_file}: {cleanup_error}")

def run_whisper_subprocess(video_path):
    """Run whisper via subprocess to avoid memory issues."""
    try:
        # Set up environment with virtual environment PATH
        env = os.environ.copy()
        venv_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.venv', 'bin')
        env['PATH'] = f"{venv_bin}:{env.get('PATH', '')}"
        
        # Use whisper CLI with JSON output
        cmd = [
            'whisper', video_path,
            '--model', 'tiny',
            '--output_format', 'json',
            '--output_dir', '/tmp',
            '--fp16', 'False',
            '--verbose', 'False'
        ]
        
        logger.info(f"🎙️ Running whisper command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        
        if result.returncode != 0:
            logger.error(f"❌ Whisper subprocess failed: {result.stderr}")
            raise Exception(f"Whisper failed: {result.stderr}")
        
        # Read the JSON output
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        json_path = f"/tmp/{video_name}.json"
        
        if not os.path.exists(json_path):
            raise Exception(f"Whisper output file not found: {json_path}")
        
        with open(json_path, 'r') as f:
            json_content = f.read()
            logger.debug(f"📄 Raw JSON content from Whisper: {json_content[:500]}...")
            whisper_result = json.loads(json_content)
        
        logger.info(f"📊 Parsed Whisper result - segments: {len(whisper_result.get('segments', []))}")
        
        # Clean up the JSON file
        os.remove(json_path)
        
        return whisper_result
        
    except subprocess.TimeoutExpired:
        logger.error("⏰ Whisper subprocess timed out")
        raise Exception("Transcription timed out")
    except Exception as e:
        logger.error(f"❌ Whisper subprocess error: {str(e)}")
        raise


def generate_caption_overlay(project_id: str, input_video_path: str, ass_content: str) -> str:
    """Generate a video with caption overlay using FFmpeg."""
    ass_file_path = None
    output_video_path = None
    
    try:
        logger.info(f"📝 Generating caption overlay for project {project_id}")
        
        # Create temporary ASS file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as ass_file:
            ass_file.write(ass_content)
            ass_file.flush()
            ass_file_path = ass_file.name

        # Verify ASS file exists and is readable
        if not os.path.exists(ass_file_path):
            raise Exception(f"ASS file was not created: {ass_file_path}")
        
        with open(ass_file_path, 'r') as f:
            ass_check = f.read()
            if not ass_check.strip():
                raise Exception("ASS file is empty")
        
        logger.info(f"📄 Created ASS file: {ass_file_path} ({len(ass_content)} chars)")

        # Create output video file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_video_path = output_file.name

        # Update project status to indicate caption overlay is starting
        supabase.table("projects").update({
            "status": "adding_captions"
        }).eq("id", project_id).execute()

        # FFmpeg command to overlay captions using ASS format
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_video_path,
            '-vf', f"ass={ass_file_path}",
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-c:v', 'libx264',  # Use H.264 for video
            '-preset', 'medium',  # Balance between speed and quality
            '-crf', '23',  # Good quality setting
            '-movflags', '+faststart',  # Optimize for web playback
            '-y',  # Overwrite output file
            output_video_path
        ]

        logger.info(f"🎬 Running FFmpeg caption overlay...")
        
        # Run FFmpeg with progress monitoring
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True
        )
        
        # Capture all output
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"❌ FFmpeg failed with return code {process.returncode}")
            logger.error(f"FFmpeg stderr: {stderr}")
            raise Exception(f"FFmpeg processing failed: {stderr}")
        
        logger.info("✅ FFmpeg caption overlay completed successfully")

        # Upload processed video to R2 Storage
        processed_filename = f"processed_{project_id}.mp4"
        
        logger.info(f"☁️ Uploading processed video to R2: {processed_filename}")
        
        client = get_r2_client()
        if client is None:
            raise Exception("Failed to initialize R2 client for processed video upload")
        
        try:
            upload_result = client.upload_file(
                output_video_path, 
                processed_filename, 
                "video/mp4"
            )
            logger.info(f"✅ Processed video uploaded to R2: {upload_result}")
        except Exception as upload_error:
            logger.error(f"❌ Failed to upload processed video to R2: {str(upload_error)}")
            raise Exception(f"Failed to upload processed video: {str(upload_error)}")

        # Update project with processed video path
        supabase.table("projects").update({
            "processed_video_path": processed_filename
        }).eq("id", project_id).execute()

        logger.info(f"🎉 Caption overlay completed: {processed_filename}")
        
        return processed_filename

    except Exception as e:
        logger.error(f"❌ Caption overlay failed for project {project_id}: {str(e)}")
        raise e
    
    finally:
        # Clean up temporary files
        if ass_file_path and os.path.exists(ass_file_path):
            try:
                os.unlink(ass_file_path)
                logger.debug(f"🧹 Cleaned up ASS file: {ass_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Failed to cleanup ASS file: {cleanup_error}")
                
        if output_video_path and os.path.exists(output_video_path):
            try:
                os.unlink(output_video_path)
                logger.debug(f"🧹 Cleaned up output video: {output_video_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Failed to cleanup output video: {cleanup_error}")