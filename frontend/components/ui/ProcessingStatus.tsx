import { useState, useEffect } from 'react';

export type ProcessingStage = 
  | 'queued' 
  | 'transcribing' 
  | 'analyzing' 
  | 'extracting' 
  | 'rendering' 
  | 'exporting' 
  | 'completed' 
  | 'failed';

interface ProcessingStep {
  stage: ProcessingStage;
  label: string;
  description: string;
  progress: number; // 0-100
  isActive: boolean;
  isCompleted: boolean;
  error?: string;
}

interface ProcessingStatusProps {
  currentStage: ProcessingStage;
  progress: number; // 0-100 for the current stage
  error?: string;
  estimatedTimeRemaining?: number; // in seconds
  onCancel?: () => void;
  className?: string;
}

export default function ProcessingStatus({
  currentStage,
  progress,
  error,
  estimatedTimeRemaining,
  onCancel,
  className = ''
}: ProcessingStatusProps) {
  const [steps, setSteps] = useState<ProcessingStep[]>([]);
  
  // Define the processing steps
  useEffect(() => {
    const allSteps: ProcessingStep[] = [
      {
        stage: 'queued',
        label: 'Queued',
        description: 'Your video is in the processing queue',
        progress: 0,
        isActive: false,
        isCompleted: false
      },
      {
        stage: 'transcribing',
        label: 'Transcribing',
        description: 'Converting speech to text',
        progress: 0,
        isActive: false,
        isCompleted: false
      },
      {
        stage: 'analyzing',
        label: 'Analyzing',
        description: 'Analyzing content for highlights',
        progress: 0,
        isActive: false,
        isCompleted: false
      },
      {
        stage: 'extracting',
        label: 'Extracting',
        description: 'Extracting selected clip',
        progress: 0,
        isActive: false,
        isCompleted: false
      },
      {
        stage: 'rendering',
        label: 'Rendering',
        description: 'Applying templates and effects',
        progress: 0,
        isActive: false,
        isCompleted: false
      },
      {
        stage: 'exporting',
        label: 'Exporting',
        description: 'Finalizing your video',
        progress: 0,
        isActive: false,
        isCompleted: false
      },
      {
        stage: 'completed',
        label: 'Completed',
        description: 'Your video is ready',
        progress: 100,
        isActive: false,
        isCompleted: false
      }
    ];
    
    // Update steps based on current stage and progress
    const updatedSteps = allSteps.map(step => {
      const stageIndex = allSteps.findIndex(s => s.stage === step.stage);
      const currentStageIndex = allSteps.findIndex(s => s.stage === currentStage);
      
      if (currentStage === 'failed') {
        // If failed, mark the current stage as active with error
        return {
          ...step,
          isActive: step.stage === 'failed' || step.stage === currentStage,
          isCompleted: stageIndex < currentStageIndex,
          progress: step.stage === currentStage ? progress : (stageIndex < currentStageIndex ? 100 : 0),
          error: step.stage === currentStage ? error : undefined
        };
      }
      
      return {
        ...step,
        isActive: step.stage === currentStage,
        isCompleted: stageIndex < currentStageIndex || (step.stage === 'completed' && currentStage === 'completed'),
        progress: step.stage === currentStage ? progress : (stageIndex < currentStageIndex ? 100 : 0)
      };
    });
    
    setSteps(updatedSteps);
  }, [currentStage, progress, error]);
  
  // Format estimated time remaining
  const formatTimeRemaining = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds} seconds`;
    }
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    if (minutes < 60) {
      return `${minutes} minute${minutes > 1 ? 's' : ''}${remainingSeconds > 0 ? ` ${remainingSeconds} second${remainingSeconds > 1 ? 's' : ''}` : ''}`;
    }
    
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    
    return `${hours} hour${hours > 1 ? 's' : ''}${remainingMinutes > 0 ? ` ${remainingMinutes} minute${remainingMinutes > 1 ? 's' : ''}` : ''}`;
  };
  
  // Calculate overall progress
  const calculateOverallProgress = (): number => {
    if (currentStage === 'completed') return 100;
    if (currentStage === 'failed') return 0;
    
    const stageWeight = 100 / (steps.length - 2); // Exclude queued and completed
    const completedStages = steps.filter(step => 
      step.isCompleted && step.stage !== 'queued' && step.stage !== 'completed'
    ).length;
    
    const currentStageProgress = steps.find(step => step.isActive)?.progress || 0;
    const currentStageContribution = (currentStageProgress / 100) * stageWeight;
    
    return Math.min(100, Math.max(0, (completedStages * stageWeight) + currentStageContribution));
  };
  
  const overallProgress = calculateOverallProgress();
  const activeStep = steps.find(step => step.isActive);
  
  return (
    <div className={`${className}`}>
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Processing Status</h3>
        </div>
        
        {/* Overall progress */}
        <div className="p-4 bg-gray-50">
          <div className="flex justify-between text-sm text-gray-700 mb-1">
            <span>Overall Progress</span>
            <span>{Math.round(overallProgress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5 mb-2">
            <div
              className={`h-2.5 rounded-full ${
                currentStage === 'failed' ? 'bg-red-600' : 'bg-blue-600'
              }`}
              style={{ width: `${overallProgress}%` }}
            ></div>
          </div>
          
          {estimatedTimeRemaining !== undefined && currentStage !== 'completed' && currentStage !== 'failed' && (
            <p className="text-xs text-gray-500 mt-1">
              Estimated time remaining: {formatTimeRemaining(estimatedTimeRemaining)}
            </p>
          )}
          
          {currentStage === 'failed' && (
            <div className="mt-2 p-3 bg-red-50 text-red-700 text-sm rounded-md">
              <div className="font-medium">Processing failed</div>
              <p className="text-xs mt-1">{error || 'An unknown error occurred. Please try again.'}</p>
            </div>
          )}
        </div>
        
        {/* Processing steps */}
        <div className="p-4">
          <div className="space-y-4">
            {steps.filter(step => step.stage !== 'failed').map((step, index) => (
              <div key={step.stage} className="relative">
                {/* Connector line */}
                {index < steps.length - 1 && (
                  <div 
                    className={`absolute left-3.5 top-10 w-0.5 h-full -ml-px ${
                      step.isCompleted ? 'bg-blue-500' : 'bg-gray-200'
                    }`}
                  ></div>
                )}
                
                <div className="relative flex items-start">
                  {/* Status circle */}
                  <div className="flex-shrink-0 h-7 w-7">
                    {step.isCompleted ? (
                      <div className="h-7 w-7 rounded-full bg-blue-500 flex items-center justify-center">
                        <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    ) : step.isActive ? (
                      <div className="h-7 w-7 rounded-full border-2 border-blue-500 bg-white flex items-center justify-center">
                        <div className="h-3 w-3 rounded-full bg-blue-500"></div>
                      </div>
                    ) : (
                      <div className="h-7 w-7 rounded-full border-2 border-gray-300 bg-white"></div>
                    )}
                  </div>
                  
                  {/* Step content */}
                  <div className="ml-3 w-full">
                    <div className="flex justify-between items-center">
                      <h4 className={`text-sm font-medium ${
                        step.isActive ? 'text-blue-700' : 
                        step.isCompleted ? 'text-gray-900' : 'text-gray-500'
                      }`}>
                        {step.label}
                      </h4>
                      {step.isActive && (
                        <span className="text-xs text-blue-600">{Math.round(step.progress)}%</span>
                      )}
                    </div>
                    
                    <p className="text-xs text-gray-500 mt-0.5">{step.description}</p>
                    
                    {/* Progress bar for active step */}
                    {step.isActive && (
                      <div className="w-full bg-gray-200 rounded-full h-1.5 mt-2">
                        <div
                          className="h-1.5 rounded-full bg-blue-500"
                          style={{ width: `${step.progress}%` }}
                        ></div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Action buttons */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-end">
            {currentStage !== 'completed' && currentStage !== 'failed' && onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Cancel Processing
              </button>
            )}
            
            {currentStage === 'failed' && (
              <button
                type="button"
                className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Try Again
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
