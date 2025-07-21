# VideoThingy Deployment Guide

This guide will help you deploy your video transcription and caption overlay application to production.

## Architecture Overview

- **Backend**: Python FastAPI application with video processing capabilities
- **Frontend**: Next.js React application with modern UI
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage for video files

## Deployment Options

### Option 1: Automated Deployment (Recommended)

Use the provided deployment script:

```bash
./deploy.sh
```

### Option 2: Manual Deployment

#### Backend Deployment (Railway)

1. **Install Railway CLI**:
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. **Deploy Backend**:
   ```bash
   cd backend
   railway up
   ```

3. **Set Environment Variables** in Railway dashboard:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   SUPABASE_SERVICE_KEY=your_supabase_service_key
   REDIS_URL=redis://localhost:6379  # Railway will provide this
   ```

#### Frontend Deployment (Vercel)

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   vercel login
   ```

2. **Deploy Frontend**:
   ```bash
   cd frontend
   vercel --prod
   ```

3. **Set Environment Variables** in Vercel dashboard:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-url.railway.app
   ```

## Alternative Deployment Platforms

### Backend Alternatives

#### Render
- Uses the provided `render.yaml` configuration
- Automatic deployments from Git
- Built-in PostgreSQL and Redis add-ons

#### Heroku
```bash
# Install Heroku CLI and login
heroku create videothingy-backend
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
git push heroku main
```

#### AWS/GCP/Azure
- Use the provided `Dockerfile` for containerized deployment
- Configure environment variables in your cloud platform
- Set up managed database and Redis instances

### Frontend Alternatives

#### Netlify
```bash
# Install Netlify CLI
npm install -g netlify-cli
netlify login
netlify deploy --prod --dir=.next
```

#### AWS Amplify
- Connect your GitHub repository
- Configure build settings:
  - Build command: `npm run build`
  - Publish directory: `.next`

## Environment Variables

### Backend (.env)
```
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
REDIS_URL=redis://localhost:6379
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=https://your-backend-url.com
```

## Pre-Deployment Checklist

- [ ] Supabase project created and configured
- [ ] Database tables created (use migrations in `/supabase` folder)
- [ ] Storage bucket configured in Supabase
- [ ] Environment variables set for both frontend and backend
- [ ] CORS origins updated in backend for production domains
- [ ] Test the application locally with production environment variables

## Post-Deployment Steps

1. **Test the deployed application**:
   - Upload a test video
   - Verify transcription works
   - Check caption overlay functionality
   - Test download features

2. **Monitor logs**:
   - Backend: Check Railway/Render logs for errors
   - Frontend: Check Vercel/Netlify function logs

3. **Set up monitoring** (optional):
   - Add error tracking (Sentry)
   - Set up uptime monitoring
   - Configure alerts for failures

## Troubleshooting

### Common Issues

1. **CORS Errors**:
   - Ensure frontend domain is added to CORS origins in backend
   - Check that API URL is correctly set in frontend environment

2. **File Upload Issues**:
   - Verify Supabase storage bucket permissions
   - Check file size limits in deployment platform

3. **Video Processing Timeouts**:
   - Increase timeout limits in deployment platform
   - Consider using background job processing for large files

4. **Database Connection Issues**:
   - Verify Supabase credentials
   - Check database connection limits

### Getting Help

- Check deployment platform documentation
- Review application logs for specific error messages
- Test locally with production environment variables first

## Scaling Considerations

For high-traffic scenarios:

1. **Backend Scaling**:
   - Use horizontal scaling with load balancers
   - Implement Redis for session management
   - Consider separating video processing to dedicated workers

2. **Storage Optimization**:
   - Implement CDN for video delivery
   - Use video compression for faster uploads
   - Set up automatic cleanup of old files

3. **Database Optimization**:
   - Add database indexes for frequently queried fields
   - Consider read replicas for heavy read workloads
   - Implement connection pooling
