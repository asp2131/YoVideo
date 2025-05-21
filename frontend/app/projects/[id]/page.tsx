import MainLayout from '../../../components/layout/MainLayout';
import Link from 'next/link';
import Image from 'next/image';

interface ProjectDetailPageProps {
  params: {
    id: string;
  };
}

export default function ProjectDetailPage({ params }: ProjectDetailPageProps) {
  const { id } = params;
  
  // In a real app, we would fetch project data based on the ID
  // For now, we'll use mock data
  const project = {
    id,
    title: 'Social Media Promo',
    date: 'May 18, 2025',
    duration: '1:30',
    status: 'draft',
    videoUrl: '',
    thumbnailUrl: '',
  };

  return (
    <MainLayout>
      <div className="py-8">
        <div className="mb-6">
          <Link href="/projects" className="text-blue-600 hover:text-blue-800 flex items-center">
            <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
            </svg>
            Back to Projects
          </Link>
        </div>

        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">{project.title}</h1>
          <div className="flex space-x-3">
            <button className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg">
              Save Changes
            </button>
            <button className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg">
              Export Video
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Project Details</h2>
              <div className="space-y-4">
                <div>
                  <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
                    Title
                  </label>
                  <input
                    type="text"
                    id="title"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    defaultValue={project.title}
                  />
                </div>
                <div>
                  <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-1">
                    Status
                  </label>
                  <select
                    id="status"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    defaultValue={project.status}
                  >
                    <option value="draft">Draft</option>
                    <option value="processing">Processing</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="created" className="block text-sm font-medium text-gray-700 mb-1">
                    Created
                  </label>
                  <input
                    type="text"
                    id="created"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm bg-gray-50"
                    value={project.date}
                    disabled
                  />
                </div>
              </div>
            </div>

            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Video Settings</h2>
              <div className="space-y-4">
                <div>
                  <label htmlFor="aspect-ratio" className="block text-sm font-medium text-gray-700 mb-1">
                    Aspect Ratio
                  </label>
                  <select
                    id="aspect-ratio"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  >
                    <option value="16:9">16:9 (Landscape)</option>
                    <option value="9:16">9:16 (Portrait)</option>
                    <option value="1:1">1:1 (Square)</option>
                    <option value="4:5">4:5 (Instagram)</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="template" className="block text-sm font-medium text-gray-700 mb-1">
                    Template
                  </label>
                  <select
                    id="template"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  >
                    <option value="none">None</option>
                    <option value="social">Social Media</option>
                    <option value="professional">Professional</option>
                    <option value="minimal">Minimal</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="quality" className="block text-sm font-medium text-gray-700 mb-1">
                    Export Quality
                  </label>
                  <select
                    id="quality"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  >
                    <option value="high">High (1080p)</option>
                    <option value="medium">Medium (720p)</option>
                    <option value="low">Low (480p)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Main content area */}
          <div className="lg:col-span-2">
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Video Upload</h2>
              {project.videoUrl ? (
                <div className="relative aspect-video bg-gray-100 rounded-lg overflow-hidden">
                  {/* Video player would go here */}
                  <div className="flex items-center justify-center h-full bg-gray-200">
                    <svg className="w-16 h-16 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  </div>
                </div>
              ) : (
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                  </svg>
                  <div className="mt-4 flex text-sm text-gray-600 justify-center">
                    <label htmlFor="file-upload" className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none">
                      <span>Upload a video</span>
                      <input id="file-upload" name="file-upload" type="file" className="sr-only" accept="video/*" />
                    </label>
                    <p className="pl-1">or drag and drop</p>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">MP4, MOV, or AVI up to 500MB</p>
                </div>
              )}
            </div>

            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Clip Editor</h2>
              <div className="bg-gray-100 p-4 rounded-lg text-center">
                <p className="text-gray-500">Upload a video to start editing clips</p>
              </div>
            </div>

            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Captions</h2>
              <div className="bg-gray-100 p-4 rounded-lg text-center">
                <p className="text-gray-500">Transcription will appear here after video processing</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
