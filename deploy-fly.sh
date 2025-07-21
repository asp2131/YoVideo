#!/bin/bash

# VideoThingy Fly.io Deployment Script
echo "🚀 Starting VideoThingy deployment to Fly.io..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if flyctl is installed
check_flyctl() {
    if ! command -v flyctl &> /dev/null; then
        print_error "flyctl is not installed. Installing it now..."
        
        # Install flyctl
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            if command -v brew &> /dev/null; then
                brew install flyctl
            else
                curl -L https://fly.io/install.sh | sh
                export PATH="$HOME/.fly/bin:$PATH"
            fi
        else
            # Linux
            curl -L https://fly.io/install.sh | sh
            export PATH="$HOME/.fly/bin:$PATH"
        fi
        
        if ! command -v flyctl &> /dev/null; then
            print_error "Failed to install flyctl. Please install it manually from https://fly.io/docs/hands-on/install-flyctl/"
            exit 1
        fi
    fi
    
    print_success "flyctl is installed!"
}

# Deploy backend to Fly.io
deploy_backend() {
    print_status "Deploying backend to Fly.io..."
    
    cd backend
    
    # Check if user is logged in
    if ! flyctl auth whoami &> /dev/null; then
        print_status "Please log in to Fly.io..."
        flyctl auth login
    fi
    
    # Check if app exists
    if ! flyctl apps list | grep -q "videothingy-backend"; then
        print_status "Creating new Fly.io app..."
        flyctl apps create videothingy-backend --org personal
    fi
    
    # Create volume for storage if it doesn't exist
    if ! flyctl volumes list | grep -q "videothingy_storage"; then
        print_status "Creating storage volume..."
        flyctl volumes create videothingy_storage --region ord --size 10
    fi
    
    # Set secrets (environment variables)
    print_status "Setting up environment variables..."
    print_warning "You'll need to set these secrets manually after deployment:"
    echo "  flyctl secrets set SUPABASE_URL=your_supabase_url"
    echo "  flyctl secrets set SUPABASE_KEY=your_supabase_anon_key"
    echo "  flyctl secrets set SUPABASE_SERVICE_KEY=your_supabase_service_key"
    echo "  flyctl secrets set REDIS_URL=redis://your_redis_url"
    echo ""
    
    # Deploy the app
    print_status "Deploying to Fly.io (this may take several minutes for large images)..."
    flyctl deploy --ha=false
    
    if [ $? -eq 0 ]; then
        print_success "Backend deployed to Fly.io!"
        BACKEND_URL="https://videothingy-backend.fly.dev"
        echo "Backend URL: $BACKEND_URL"
        
        # Open the app
        print_status "Opening app status..."
        flyctl status
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
    
    # Check if Vercel CLI is available
    if ! command -v vercel &> /dev/null && ! command -v npx &> /dev/null; then
        print_error "Neither vercel CLI nor npx is available. Please install Node.js and npm."
        exit 1
    fi
    
    # Set environment variable for API URL
    if [ ! -z "$BACKEND_URL" ]; then
        echo "NEXT_PUBLIC_API_URL=$BACKEND_URL" > .env.production
        print_status "Set frontend API URL to: $BACKEND_URL"
    fi
    
    # Deploy to Vercel using npx
    if command -v vercel &> /dev/null; then
        vercel --prod
    else
        npx vercel --prod
    fi
    
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
    check_flyctl
    
    echo ""
    print_status "Choose deployment option:"
    echo "1) Deploy both backend (Fly.io) and frontend (Vercel)"
    echo "2) Deploy backend only (Fly.io)"
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
    
    echo ""
    print_success "Deployment completed! 🎉"
    echo ""
    print_warning "Don't forget to set your environment variables:"
    echo "Backend: flyctl secrets set SUPABASE_URL=... SUPABASE_KEY=... etc."
    echo "Frontend: Set NEXT_PUBLIC_API_URL in Vercel dashboard"
}

# Run main function
main
