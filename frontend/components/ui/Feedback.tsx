import { useState, useEffect } from 'react';

export type FeedbackType = 'success' | 'error' | 'warning' | 'info';

export interface FeedbackMessage {
  id: string;
  type: FeedbackType;
  title: string;
  message: string;
  autoClose?: boolean;
  duration?: number; // in milliseconds
}

interface FeedbackProps {
  message?: FeedbackMessage;
  onClose?: (id: string) => void;
  className?: string;
}

export default function Feedback({
  message,
  onClose,
  className = ''
}: FeedbackProps) {
  const [isVisible, setIsVisible] = useState<boolean>(!!message);
  const [timeoutId, setTimeoutId] = useState<NodeJS.Timeout | null>(null);

  // Handle auto-close functionality
  useEffect(() => {
    if (message) {
      setIsVisible(true);
      
      // Clear any existing timeout
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      
      // Set up auto-close if enabled
      if (message.autoClose) {
        const duration = message.duration || 5000; // Default to 5 seconds
        const id = setTimeout(() => {
          setIsVisible(false);
          if (onClose) {
            onClose(message.id);
          }
        }, duration);
        
        setTimeoutId(id);
      }
    } else {
      setIsVisible(false);
    }
    
    // Cleanup timeout on unmount
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [message, onClose, timeoutId]);

  // Handle close button click
  const handleClose = () => {
    setIsVisible(false);
    if (message && onClose) {
      onClose(message.id);
    }
  };

  // If no message or not visible, don't render anything
  if (!message || !isVisible) {
    return null;
  }

  // Get the appropriate styles based on the message type
  const getTypeStyles = (): { bg: string; border: string; text: string; icon: JSX.Element } => {
    switch (message.type) {
      case 'success':
        return {
          bg: 'bg-green-50',
          border: 'border-green-400',
          text: 'text-green-800',
          icon: (
            <svg className="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
            </svg>
          )
        };
      case 'error':
        return {
          bg: 'bg-red-50',
          border: 'border-red-400',
          text: 'text-red-800',
          icon: (
            <svg className="w-5 h-5 text-red-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"></path>
            </svg>
          )
        };
      case 'warning':
        return {
          bg: 'bg-yellow-50',
          border: 'border-yellow-400',
          text: 'text-yellow-800',
          icon: (
            <svg className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"></path>
            </svg>
          )
        };
      case 'info':
      default:
        return {
          bg: 'bg-blue-50',
          border: 'border-blue-400',
          text: 'text-blue-800',
          icon: (
            <svg className="w-5 h-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"></path>
            </svg>
          )
        };
    }
  };

  const { bg, border, text, icon } = getTypeStyles();

  return (
    <div className={`${className} ${bg} border-l-4 ${border} p-4 rounded-md shadow-sm`} role="alert">
      <div className="flex items-start">
        <div className="flex-shrink-0">
          {icon}
        </div>
        <div className="ml-3 flex-1">
          <div className="flex justify-between items-start">
            <p className={`text-sm font-medium ${text}`}>{message.title}</p>
            <button
              type="button"
              className={`ml-auto -mx-1.5 -my-1.5 ${bg} ${text} rounded-lg focus:ring-2 focus:ring-blue-400 p-1.5 inline-flex h-8 w-8 hover:bg-opacity-75`}
              onClick={handleClose}
              aria-label="Close"
            >
              <span className="sr-only">Close</span>
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"></path>
              </svg>
            </button>
          </div>
          <p className={`mt-1 text-sm ${text}`}>{message.message}</p>
        </div>
      </div>
    </div>
  );
}

// FeedbackContainer component to manage multiple feedback messages
interface FeedbackContainerProps {
  messages: FeedbackMessage[];
  onClose: (id: string) => void;
  className?: string;
}

export function FeedbackContainer({
  messages,
  onClose,
  className = ''
}: FeedbackContainerProps) {
  if (messages.length === 0) {
    return null;
  }

  return (
    <div className={`fixed top-4 right-4 z-50 space-y-2 max-w-md ${className}`}>
      {messages.map(message => (
        <Feedback
          key={message.id}
          message={message}
          onClose={onClose}
        />
      ))}
    </div>
  );
}

// Custom hook for managing feedback messages
export function useFeedback() {
  const [messages, setMessages] = useState<FeedbackMessage[]>([]);

  const addMessage = (message: Omit<FeedbackMessage, 'id'>) => {
    const id = `feedback-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newMessage: FeedbackMessage = {
      ...message,
      id,
      autoClose: message.autoClose !== false, // Default to true if not specified
    };
    
    setMessages(prevMessages => [...prevMessages, newMessage]);
    return id;
  };

  const removeMessage = (id: string) => {
    setMessages(prevMessages => prevMessages.filter(message => message.id !== id));
  };

  const clearMessages = () => {
    setMessages([]);
  };

  // Helper functions for common message types
  const showSuccess = (title: string, message: string, options?: Partial<FeedbackMessage>) => {
    return addMessage({ type: 'success', title, message, ...options });
  };

  const showError = (title: string, message: string, options?: Partial<FeedbackMessage>) => {
    return addMessage({ type: 'error', title, message, ...options });
  };

  const showWarning = (title: string, message: string, options?: Partial<FeedbackMessage>) => {
    return addMessage({ type: 'warning', title, message, ...options });
  };

  const showInfo = (title: string, message: string, options?: Partial<FeedbackMessage>) => {
    return addMessage({ type: 'info', title, message, ...options });
  };

  return {
    messages,
    addMessage,
    removeMessage,
    clearMessages,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };
}

// Error boundary component
interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
    
    // Log the error to an error reporting service
    console.error('Error caught by ErrorBoundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      
      // Default fallback UI
      return (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md">
          <h2 className="text-lg font-medium text-red-800 mb-2">Something went wrong</h2>
          <p className="text-sm text-red-700 mb-4">
            An error occurred while rendering this component. Please try refreshing the page.
          </p>
          <details className="text-xs text-red-600 bg-red-100 p-2 rounded">
            <summary>Error details</summary>
            <p className="mt-1 font-mono whitespace-pre-wrap">
              {this.state.error?.toString()}
            </p>
          </details>
          <button
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm font-medium"
            onClick={() => window.location.reload()}
          >
            Refresh Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
