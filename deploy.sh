#!/bin/bash

# VideoThingy Deployment Script
echo "🚀 Starting VideoThingy deployment..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v git &> /dev/null; then
        print_error "Git is required but not installed."
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        print_error "npm is required but not installed."
        exit 1
    fi
    
    print_success "All requirements met!"
}

# Deploy backend to Railway
deploy_backend() {
    print_status "Deploying backend to Railway..."
    
    cd backend
    
    # Check if Railway CLI is installed
    if ! command -v railway &> /dev/null; then
        print_error "Railway CLI not found. Install it with: npm install -g @railway/cli"
        print_status "Then run: railway login"
        exit 1
    fi
    
    # Deploy to Railway
    railway up
    
    if [ $? -eq 0 ]; then
        print_success "Backend deployed to Railway!"
        BACKEND_URL=$(railway status --json | jq -r '.deployments[0].url')
        echo "Backend URL: $BACKEND_URL"
    else
        print_error "Backend deployment failed!"
        exit 1
    fi
    
    cd ..
}

# Deploy frontend to Vercel
deploy_frontend() {
    print_status "Deploying frontend to Vercel..."
    
    cd frontend
    
    # Check if Vercel CLI is installed
    if ! command -v vercel &> /dev/null; then
        print_error "Vercel CLI not found. Install it with: npm install -g vercel"
        print_status "Then run: vercel login"
        exit 1
    fi
    
    # Set environment variable for API URL
    if [ ! -z "$BACKEND_URL" ]; then
        echo "NEXT_PUBLIC_API_URL=$BACKEND_URL" > .env.production
    fi
    
    # Deploy to Vercel
    vercel --prod
    
    if [ $? -eq 0 ]; then
        print_success "Frontend deployed to Vercel!"
    else
        print_error "Frontend deployment failed!"
        exit 1
    fi
    
    cd ..
}

# Main deployment flow
main() {
    check_requirements
    
    echo ""
    print_status "Choose deployment option:"
    echo "1) Deploy both backend and frontend"
    echo "2) Deploy backend only (Railway)"
    echo "3) Deploy frontend only (Vercel)"
    echo "4) Exit"
    
    read -p "Enter your choice (1-4): " choice
    
    case $choice in
        1)
            deploy_backend
            deploy_frontend
            ;;
        2)
            deploy_backend
            ;;
        3)
            deploy_frontend
            ;;
        4)
            print_status "Deployment cancelled."
            exit 0
            ;;
        *)
            print_error "Invalid choice. Please run the script again."
            exit 1
            ;;
    esac
    
    print_success "Deployment completed! 🎉"
}

# Run main function
main
