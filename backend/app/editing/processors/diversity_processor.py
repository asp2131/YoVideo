"""
Diversity Processor for highlight selection.

This module implements non-maximum suppression (NMS) and diversity penalties
to ensure selected highlights are both high-quality and diverse.
"""
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from dataclasses import dataclass
import logging

from app.editing.pipeline.core import VideoProcessor, Context, Segment

logger = logging.getLogger(__name__)

@dataclass
class DiversityConfig:
    """Configuration for diversity and NMS parameters."""
    # NMS parameters
    nms_threshold: float = 0.5  # IoU threshold for NMS
    score_threshold: float = 0.3  # Minimum score to consider a segment
    
    # Diversity parameters
    diversity_lambda: float = 0.5  # Weight for diversity term (0 = no diversity, 1 = max diversity)
    feature_weights: Dict[str, float] = None  # Weights for different feature dimensions
    min_segment_duration: float = 2.0  # Minimum duration of a segment in seconds
    max_segment_duration: float = 15.0  # Maximum duration of a segment in seconds
    
    def __post_init__(self):
        """Initialize default feature weights if not provided."""
        if self.feature_weights is None:
            self.feature_weights = {
                'visual': 0.4,
                'audio': 0.3,
                'content': 0.3
            }

class DiversityProcessor(VideoProcessor):
    """
    A processor that applies non-maximum suppression and diversity penalties
    to select a diverse set of high-quality highlights.
    """
    
    def __init__(self, config: Optional[DiversityConfig] = None):
        """
        Initialize the DiversityProcessor.
        
        Args:
            config: Configuration for diversity and NMS parameters.
                   If None, default values will be used.
        """
        self.config = config or DiversityConfig()
    
    async def process(self, context: Context) -> Context:
        """
        Process the context to select diverse highlights.
        
        Args:
            context: The processing context containing segments
            
        Returns:
            Updated context with selected highlights
        """
        if not context.segments:
            logger.warning("No segments found in context")
            return context
        
        # Filter segments by duration and score
        segments = [
            seg for seg in context.segments
            if (self.config.min_segment_duration <= seg.duration <= self.config.max_segment_duration and
                seg.overall_score >= self.config.score_threshold)
        ]
        
        if not segments:
            logger.warning("No segments passed the initial filtering")
            context.highlights = []
            return context
        
        # Sort segments by score (descending)
        segments.sort(key=lambda x: x.overall_score, reverse=True)
        
        # Apply non-maximum suppression
        selected_indices = self._non_max_suppression(segments)
        
        # If diversity is enabled, apply diversity penalty
        if self.config.diversity_lambda > 0 and len(selected_indices) > 1:
            selected_indices = self._apply_diversity_penalty(
                segments, selected_indices
            )
        
        # Update context with selected highlights
        context.highlights = [segments[i] for i in selected_indices]
        logger.info(f"Selected {len(context.highlights)} highlights after diversity processing")
        
        return context
    
    def _non_max_suppression(self, segments: List[Segment]) -> List[int]:
        """
        Apply non-maximum suppression to select non-overlapping segments.
        
        Args:
            segments: List of segments, sorted by score (descending)
            
        Returns:
            Indices of selected segments
        """
        if not segments:
            return []
        
        selected_indices = []
        
        for i, current_seg in enumerate(segments):
            # Check for overlap with already selected segments
            is_overlapping = False
            
            for j in selected_indices:
                iou = self._calculate_iou(current_seg, segments[j])
                if iou > self.config.nms_threshold:
                    is_overlapping = True
                    break
            
            if not is_overlapping:
                selected_indices.append(i)
        
        return selected_indices
    
    def _apply_diversity_penalty(
        self,
        segments: List[Segment],
        selected_indices: List[int],
        k: Optional[int] = None
    ) -> List[int]:
        """
        Apply diversity penalty to selected segments.
        
        Args:
            segments: List of all segments
            selected_indices: Indices of initially selected segments
            k: Maximum number of segments to select. If None, keep all.
            
        Returns:
            Indices of selected segments after applying diversity penalty
        """
        if not selected_indices:
            return []
        
        if k is None or k >= len(selected_indices):
            k = len(selected_indices)
        
        # Convert segments to feature vectors
        features = []
        for idx in selected_indices:
            seg = segments[idx]
            # Create a feature vector from segment annotations and scores
            feat = self._segment_to_feature(seg)
            features.append(feat)
        
        features = np.array(features)
        
        # Normalize features
        feature_norms = np.linalg.norm(features, axis=1, keepdims=True)
        normalized_features = features / (feature_norms + 1e-8)
        
        # Initialize with the highest scoring segment
        selected = [0]
        remaining = list(range(1, len(selected_indices)))
        
        # Greedy selection with diversity penalty
        while len(selected) < k and remaining:
            best_score = -np.inf
            best_idx = -1
            
            # For each remaining segment, calculate its score considering diversity
            for i in remaining:
                # Original score (normalized to [0, 1])
                orig_score = segments[selected_indices[i]].overall_score
                
                # Calculate diversity term (average distance to already selected)
                if selected:
                    sim = np.mean([
                        np.dot(normalized_features[i], normalized_features[s])
                        for s in selected
                    ])
                    diversity = 1.0 - sim  # Convert similarity to distance
                else:
                    diversity = 1.0
                
                # Combined score
                score = ((1 - self.config.diversity_lambda) * orig_score +
                        self.config.diversity_lambda * diversity)
                
                if score > best_score:
                    best_score = score
                    best_idx = i
            
            if best_idx == -1:  # No valid segment found
                break
                
            # Add the best segment to selected and remove from remaining
            selected.append(best_idx)
            remaining.remove(best_idx)
        
        # Map back to original indices
        return [selected_indices[i] for i in selected[:k]]
    
    def _segment_to_feature(self, segment: Segment) -> np.ndarray:
        """
        Convert a segment to a feature vector.
        
        Args:
            segment: The segment to convert
            
        Returns:
            Feature vector as a numpy array
        """
        features = []
        
        # Add basic features
        features.extend([
            segment.duration,
            segment.start / max(segment.start + segment.duration, 1.0),  # Normalized start
            segment.overall_score or 0.0,
            segment.scores.get('audio', 0.0),
            segment.scores.get('visual', 0.0),
            segment.scores.get('content', 0.0)
        ])
        
        # Add annotation-based features if available
        annotations = getattr(segment, 'annotations', {})
        
        # Scene and silence features
        features.extend([
            float(annotations.get('scene_change', False)),
            float(annotations.get('is_scene_boundary', False)),
            float(annotations.get('silence_ratio', 0.0)),
            float(annotations.get('is_silent', False))
        ])
        
        # Add any additional features from annotations
        for key in ['motion', 'face_count', 'brightness', 'contrast']:
            if key in annotations:
                features.append(float(annotations[key]))
            else:
                features.append(0.0)  # Default value for missing features
        
        return np.array(features)
    
    @staticmethod
    def _calculate_iou(seg1: Segment, seg2: Segment) -> float:
        """
        Calculate Intersection over Union (IoU) between two segments.
        
        Args:
            seg1: First segment
            seg2: Second segment
            
        Returns:
            IoU value between 0 and 1
        """
        # Calculate intersection
        start = max(seg1.start, seg2.start)
        end = min(seg1.start + seg1.duration, seg2.start + seg2.duration)
        
        if end <= start:
            return 0.0
        
        intersection = end - start
        
        # Calculate union
        duration1 = seg1.duration
        duration2 = seg2.duration
        union = duration1 + duration2 - intersection
        
        return intersection / union if union > 0 else 0.0
