import { useState, useEffect } from 'react';

type BreakpointKey = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';

interface Breakpoints {
  xs: number;
  sm: number;
  md: number;
  lg: number;
  xl: number;
  '2xl': number;
}

interface ResponsiveContainerProps {
  children: React.ReactNode;
  className?: string;
}

// Default breakpoints matching Tailwind CSS
const defaultBreakpoints: Breakpoints = {
  xs: 0,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
};

export default function ResponsiveContainer({
  children,
  className = '',
}: ResponsiveContainerProps) {
  return (
    <div className={`w-full mx-auto px-4 sm:px-6 lg:px-8 ${className}`}>
      {children}
    </div>
  );
}

// Custom hook to detect current breakpoint
export function useBreakpoint(customBreakpoints?: Partial<Breakpoints>) {
  const breakpoints = { ...defaultBreakpoints, ...customBreakpoints };
  const [breakpoint, setBreakpoint] = useState<BreakpointKey>('xs');

  useEffect(() => {
    // Function to determine the current breakpoint
    const determineBreakpoint = () => {
      const width = window.innerWidth;
      
      if (width >= breakpoints['2xl']) {
        setBreakpoint('2xl');
      } else if (width >= breakpoints.xl) {
        setBreakpoint('xl');
      } else if (width >= breakpoints.lg) {
        setBreakpoint('lg');
      } else if (width >= breakpoints.md) {
        setBreakpoint('md');
      } else if (width >= breakpoints.sm) {
        setBreakpoint('sm');
      } else {
        setBreakpoint('xs');
      }
    };

    // Set initial breakpoint
    determineBreakpoint();

    // Add event listener for window resize
    window.addEventListener('resize', determineBreakpoint);

    // Clean up event listener
    return () => {
      window.removeEventListener('resize', determineBreakpoint);
    };
  }, [breakpoints]);

  return breakpoint;
}

// Custom hook to check if the current breakpoint is at least the specified size
export function useBreakpointAtLeast(size: BreakpointKey, customBreakpoints?: Partial<Breakpoints>) {
  const currentBreakpoint = useBreakpoint(customBreakpoints);
  const breakpoints = { ...defaultBreakpoints, ...customBreakpoints };
  
  const breakpointOrder: BreakpointKey[] = ['xs', 'sm', 'md', 'lg', 'xl', '2xl'];
  const currentIndex = breakpointOrder.indexOf(currentBreakpoint);
  const targetIndex = breakpointOrder.indexOf(size);
  
  return currentIndex >= targetIndex;
}

// Custom hook to check if the current breakpoint is at most the specified size
export function useBreakpointAtMost(size: BreakpointKey, customBreakpoints?: Partial<Breakpoints>) {
  const currentBreakpoint = useBreakpoint(customBreakpoints);
  const breakpoints = { ...defaultBreakpoints, ...customBreakpoints };
  
  const breakpointOrder: BreakpointKey[] = ['xs', 'sm', 'md', 'lg', 'xl', '2xl'];
  const currentIndex = breakpointOrder.indexOf(currentBreakpoint);
  const targetIndex = breakpointOrder.indexOf(size);
  
  return currentIndex <= targetIndex;
}

// Responsive layout components
export function MobileOnly({ children }: { children: React.ReactNode }) {
  const isMobile = useBreakpointAtMost('sm');
  return isMobile ? <>{children}</> : null;
}

export function TabletOnly({ children }: { children: React.ReactNode }) {
  const breakpoint = useBreakpoint();
  return breakpoint === 'md' ? <>{children}</> : null;
}

export function DesktopOnly({ children }: { children: React.ReactNode }) {
  const isDesktop = useBreakpointAtLeast('lg');
  return isDesktop ? <>{children}</> : null;
}

export function MobileAndTablet({ children }: { children: React.ReactNode }) {
  const isMobileOrTablet = useBreakpointAtMost('md');
  return isMobileOrTablet ? <>{children}</> : null;
}

export function TabletAndDesktop({ children }: { children: React.ReactNode }) {
  const isTabletOrDesktop = useBreakpointAtLeast('md');
  return isTabletOrDesktop ? <>{children}</> : null;
}

// Responsive grid component
interface ResponsiveGridProps {
  children: React.ReactNode;
  cols?: {
    xs?: number;
    sm?: number;
    md?: number;
    lg?: number;
    xl?: number;
    '2xl'?: number;
  };
  gap?: string;
  className?: string;
}

export function ResponsiveGrid({
  children,
  cols = { xs: 1, sm: 2, md: 3, lg: 4, xl: 5, '2xl': 6 },
  gap = '4',
  className = '',
}: ResponsiveGridProps) {
  // Generate the grid-cols classes based on the cols prop
  const gridColsClasses = Object.entries(cols)
    .map(([breakpoint, count]) => {
      if (breakpoint === 'xs') {
        return `grid-cols-${count}`;
      }
      return `${breakpoint}:grid-cols-${count}`;
    })
    .join(' ');

  return (
    <div className={`grid ${gridColsClasses} gap-${gap} ${className}`}>
      {children}
    </div>
  );
}
