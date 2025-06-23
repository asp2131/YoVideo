"""
Performance Benchmarking for Video Highlight Pipeline

This script benchmarks the performance of the video highlight pipeline components
and provides detailed timing information for optimization.
"""
import time
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
import statistics
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.editing.pipeline import HighlightPipeline, Context
from app.editing.processors import SilenceRemover, SceneDetector, EnhancedHighlightDetector
from app.editing.segmenters import IntelligentSegmenter


@dataclass
class BenchmarkResult:
    """Stores benchmarking results for a single run."""
    component: str
    duration: float
    input_size: Optional[int] = None  # Input size in bytes if applicable
    output_size: Optional[int] = None  # Output size in bytes if applicable
    metadata: Optional[Dict[str, Any]] = None


class PipelineBenchmarker:
    """Benchmarks the performance of pipeline components."""
    
    def __init__(self, warmup_runs: int = 1, test_runs: int = 3):
        """Initialize the benchmarker.
        
        Args:
            warmup_runs: Number of warmup runs to perform
            test_runs: Number of test runs to average results over
        """
        self.warmup_runs = warmup_runs
        self.test_runs = test_runs
        self.results: List[BenchmarkResult] = []
    
    def benchmark_component(self, name: str, func, *args, **kwargs) -> BenchmarkResult:
        """Benchmark a single component function.
        
        Args:
            name: Name of the component being benchmarked
            func: Function to benchmark
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            BenchmarkResult with timing information
        """
        # Warmup runs
        for _ in range(self.warmup_runs):
            func(*args, **kwargs)
        
        # Test runs
        durations = []
        for _ in range(self.test_runs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            durations.append(end_time - start_time)
        
        # Calculate statistics
        avg_duration = statistics.mean(durations)
        
        # Create result
        result = BenchmarkResult(
            component=name,
            duration=avg_duration,
            metadata={
                'min_duration': min(durations),
                'max_duration': max(durations),
                'stddev': statistics.stdev(durations) if len(durations) > 1 else 0,
                'runs': len(durations)
            }
        )
        
        self.results.append(result)
        return result
    
    def benchmark_pipeline_component(self, component, context: Context, name: Optional[str] = None) -> BenchmarkResult:
        """Benchmark a pipeline component.
        
        Args:
            component: The pipeline component to benchmark
            context: Context to pass to the component
            name: Optional custom name for the component
            
        Returns:
            BenchmarkResult with timing information
        """
        component_name = name or component.__class__.__name__
        
        def run_component():
            return component.process(context)
            
        return self.benchmark_component(component_name, run_component)
    
    def benchmark_full_pipeline(self, pipeline: HighlightPipeline, context: Context) -> List[BenchmarkResult]:
        """Benchmark each component in the pipeline.
        
        Args:
            pipeline: The pipeline to benchmark
            context: Context to pass to the pipeline
            
        Returns:
            List of BenchmarkResult objects for each component
        """
        # Benchmark each component individually
        for processor in pipeline.processors:
            self.benchmark_pipeline_component(processor, context)
        
        # Benchmark the full pipeline
        def run_pipeline():
            ctx = context.copy()
            return pipeline.run(ctx)
            
        self.benchmark_component("Full Pipeline", run_pipeline)
        
        return self.results
    
    def print_results(self, file=None):
        """Print benchmarking results in a readable format."""
        if not self.results:
            print("No benchmark results available.", file=file)
            return
        
        # Find the longest component name for formatting
        max_name_len = max(len(r.component) for r in self.results)
        header_fmt = f"{{:<{max_name_len + 2}}} {{:<12}} {{:<12}} {{:<12}} {{:<12}}"
        row_fmt = f"{{:<{max_name_len + 2}}} {{:<12.4f}} {{:<12.4f}} {{:<12.4f}} {{:<12.4f}}"
        
        print("\n" + "=" * 80, file=file)
        print("Pipeline Performance Benchmarks", file=file)
        print("-" * 80, file=file)
        print(header_fmt.format("Component", "Avg (s)", "Min (s)", "Max (s)", "StdDev"), file=file)
        print("-" * 80, file=file)
        
        for result in self.results:
            print(row_fmt.format(
                result.component,
                result.duration,
                result.metadata['min_duration'],
                result.metadata['max_duration'],
                result.metadata['stddev']
            ), file=file)
        
        print("=" * 80 + "\n", file=file)
    
    def save_results(self, output_path: str):
        """Save benchmark results to a JSON file."""
        with open(output_path, 'w') as f:
            json.dump([asdict(r) for r in self.results], f, indent=2)


def create_test_pipeline() -> HighlightPipeline:
    """Create a test pipeline with default settings."""
    return HighlightPipeline([
        SilenceRemover(),
        SceneDetector(),
        IntelligentSegmenter(),
        EnhancedHighlightDetector()
    ])


def main():
    """Command line interface for the benchmark tool."""
    parser = argparse.ArgumentParser(description='Benchmark the video highlight pipeline.')
    parser.add_argument('video_path', help='Path to the input video file')
    parser.add_argument('--output', '-o', help='Output JSON file for results')
    parser.add_argument('--warmup', type=int, default=1, help='Number of warmup runs')
    parser.add_argument('--runs', type=int, default=3, help='Number of test runs')
    
    args = parser.parse_args()
    
    # Initialize benchmarker
    benchmarker = PipelineBenchmarker(
        warmup_runs=args.warmup,
        test_runs=args.runs
    )
    
    # Create context
    context = Context(
        video_path=args.video_path,
        output_dir=str(Path(args.video_path).parent / "output"),
        metadata={
            'benchmark': True,
            'test_runs': args.runs,
            'warmup_runs': args.warmup
        }
    )
    
    # Create pipeline
    pipeline = create_test_pipeline()
    
    try:
        # Run benchmarks
        print(f"Starting benchmarks with {args.runs} test runs and {args.warmup} warmup runs...")
        benchmarker.benchmark_full_pipeline(pipeline, context)
        
        # Print results
        benchmarker.print_results()
        
        # Save results if output file specified
        if args.output:
            benchmarker.save_results(args.output)
            print(f"Results saved to {args.output}")
            
    except Exception as e:
        print(f"Error during benchmarking: {str(e)}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


# Example usage:
# python benchmarks/benchmark_pipeline.py path/to/video.mp4
# python benchmarks/benchmark_pipeline.py path/to/video.mp4 --output results.json --runs 5
