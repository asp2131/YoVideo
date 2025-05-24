#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping VideoThingy Development Environment${NC}"

# Kill processes on the required ports
if lsof -i :8080 > /dev/null 2>&1; then
    echo -e "${YELLOW}Stopping API Gateway on port 8080${NC}"
    kill $(lsof -ti:8080)
    echo -e "${GREEN}API Gateway stopped${NC}"
else
    echo -e "${GREEN}No API Gateway running on port 8080${NC}"
fi

if lsof -i :50051 > /dev/null 2>&1; then
    echo -e "${YELLOW}Stopping AI Service on port 50051${NC}"
    kill $(lsof -ti:50051)
    echo -e "${GREEN}AI Service stopped${NC}"
else
    echo -e "${GREEN}No AI Service running on port 50051${NC}"
fi

# The Video Processor doesn't have a specific port, so we'll try to find it by process name
VIDEO_PROCESSOR_PID=$(ps aux | grep "[g]o run.*video-processor" | awk '{print $2}')
if [ -n "$VIDEO_PROCESSOR_PID" ]; then
    echo -e "${YELLOW}Stopping Video Processor with PID $VIDEO_PROCESSOR_PID${NC}"
    kill $VIDEO_PROCESSOR_PID
    echo -e "${GREEN}Video Processor stopped${NC}"
else
    echo -e "${GREEN}No Video Processor running${NC}"
fi

if lsof -i :3000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Stopping Frontend on port 3000${NC}"
    kill $(lsof -ti:3000)
    echo -e "${GREEN}Frontend stopped${NC}"
else
    echo -e "${GREEN}No Frontend running on port 3000${NC}"
fi

echo -e "${GREEN}All services stopped successfully!${NC}"
