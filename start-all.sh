#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting VideoThingy Development Environment${NC}"
echo -e "${BLUE}=====================================${NC}"

# Function to check if a port is in use
check_port() {
    lsof -i :$1 > /dev/null 2>&1
    return $?
}

# Kill any existing processes on the required ports
echo -e "${YELLOW}Checking for existing processes...${NC}"

if check_port 8080; then
    echo -e "${YELLOW}Killing existing process on port 8080 (API Gateway)${NC}"
    kill $(lsof -ti:8080)
fi

if check_port 50051; then
    echo -e "${YELLOW}Killing existing process on port 50051 (AI Service)${NC}"
    kill $(lsof -ti:50051)
fi

if check_port 3000; then
    echo -e "${YELLOW}Killing existing process on port 3000 (Frontend)${NC}"
    kill $(lsof -ti:3000)
fi

# Create a directory for logs
mkdir -p logs

# Start the AI Service (Python)
echo -e "${GREEN}Starting AI Service (Python)...${NC}"
cd ai-service
python main.py > ../logs/ai-service.log 2>&1 &
AI_PID=$!
cd ..
echo -e "${GREEN}AI Service started with PID: $AI_PID${NC}"

# Wait for AI Service to be ready
echo -e "${YELLOW}Waiting for AI Service to be ready...${NC}"
sleep 5

# Start the Video Processor (Go)
echo -e "${GREEN}Starting Video Processor (Go)...${NC}"
cd video-processor/cmd/processor
go run main.go > ../../../logs/video-processor.log 2>&1 &
VIDEO_PROCESSOR_PID=$!
cd ../../..
echo -e "${GREEN}Video Processor started with PID: $VIDEO_PROCESSOR_PID${NC}"

# Wait for Video Processor to be ready
echo -e "${YELLOW}Waiting for Video Processor to be ready...${NC}"
sleep 3

# Start the API Gateway (Go)
echo -e "${GREEN}Starting API Gateway (Go)...${NC}"
cd api-gateway

# Set Supabase environment variables
export SUPABASE_URL="https://whwbduaefolbnfdrcfuo.supabase.co"
export SUPABASE_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indod2JkdWFlZm9sYm5mZHJjZnVvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NzE1NTYzNCwiZXhwIjoyMDYyNzMxNjM0fQ.Vu3Qy2YMJGgVpnwQDRDDXlMxNTZXZvA0qYEbGzPOYcw"

go run main.go > ../logs/api-gateway.log 2>&1 &
API_PID=$!
cd ..
echo -e "${GREEN}API Gateway started with PID: $API_PID${NC}"

# Wait for API Gateway to be ready
echo -e "${YELLOW}Waiting for API Gateway to be ready...${NC}"
sleep 3

# Start the Frontend (Next.js)
echo -e "${GREEN}Starting Frontend (Next.js)...${NC}"
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}Frontend started with PID: $FRONTEND_PID${NC}"

# Wait for Frontend to be ready
echo -e "${YELLOW}Waiting for Frontend to be ready...${NC}"
sleep 5

echo -e "${GREEN}All services started successfully!${NC}"
echo -e "${BLUE}=====================================${NC}"
echo -e "${GREEN}AI Service:${NC} http://localhost:50051 (gRPC)"
echo -e "${GREEN}Video Processor:${NC} Running as a background service"
echo -e "${GREEN}API Gateway:${NC} http://localhost:8080"
echo -e "${GREEN}Frontend:${NC} http://localhost:3000"
echo -e "${BLUE}=====================================${NC}"
echo -e "${YELLOW}Logs are being written to the logs/ directory${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Function to kill all started processes
cleanup() {
    echo -e "\n${YELLOW}Stopping all services...${NC}"
    kill $AI_PID $VIDEO_PROCESSOR_PID $API_PID $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Register the cleanup function to run when script receives SIGINT (Ctrl+C)
trap cleanup SIGINT

# Keep the script running to maintain the processes
while true; do
    sleep 1
done
