import MainLayout from '../../components/layout/MainLayout';
import Image from 'next/image';
import Link from 'next/link';

interface Project {
  id: string;
  title: string;
  date: string;
  thumbnailUrl: string;
  duration?: string;
  status?: 'draft' | 'processing' | 'completed';
}

export default function ProjectsPage() {
  // Sample project data - in a real app, this would come from an API
  const projects: Project[] = [
    { 
      id: '1', 
      title: 'Social Media Promo', 
      date: 'May 18, 2025', 
      thumbnailUrl: '', 
      duration: '1:30',
      status: 'completed'
    },
    { 
      id: '2', 
      title: 'Product Demo', 
      date: 'May 15, 2025', 
      thumbnailUrl: '', 
      duration: '2:45',
      status: 'processing'
    },
    { 
      id: '3', 
      title: 'Tutorial Video', 
      date: 'May 10, 2025', 
      thumbnailUrl: '', 
      duration: '5:20',
      status: 'draft'
    },
  ];

  return (
    <MainLayout>
      <div className="py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">All Projects</h1>
          <button className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
            </svg>
            New Project
          </button>
        </div>

        {/* Filter and sort options */}
        <div className="bg-gray-50 p-4 rounded-lg mb-6 flex flex-wrap gap-4">
          <div className="flex-grow">
            <label htmlFor="filter" className="block text-sm font-medium text-gray-700 mb-1">Filter by</label>
            <select id="filter" className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm">
              <option value="all">All Projects</option>
              <option value="draft">Drafts</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
            </select>
          </div>
          <div className="flex-grow">
            <label htmlFor="sort" className="block text-sm font-medium text-gray-700 mb-1">Sort by</label>
            <select id="sort" className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm">
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="a-z">A-Z</option>
              <option value="z-a">Z-A</option>
            </select>
          </div>
          <div className="flex-grow">
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-1">Search</label>
            <input
              type="text"
              id="search"
              placeholder="Search projects..."
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
          </div>
        </div>

        {/* Project list */}
        <div className="bg-white shadow overflow-hidden rounded-md">
          <ul role="list" className="divide-y divide-gray-200">
            {projects.map((project) => (
              <li key={project.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 h-12 w-12 bg-gray-200 rounded overflow-hidden relative">
                      {project.thumbnailUrl ? (
                        <Image 
                          src={project.thumbnailUrl} 
                          alt={project.title} 
                          fill 
                          className="object-cover" 
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full">
                          <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                          </svg>
                        </div>
                      )}
                    </div>
                    <div className="ml-4">
                      <h2 className="text-lg font-medium text-gray-900">{project.title}</h2>
                      <div className="flex items-center text-sm text-gray-500">
                        <span>{project.date}</span>
                        {project.duration && (
                          <>
                            <span className="mx-2">•</span>
                            <span>{project.duration}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center">
                    {project.status && (
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium mr-4 ${
                        project.status === 'completed' ? 'bg-green-100 text-green-800' : 
                        project.status === 'processing' ? 'bg-yellow-100 text-yellow-800' : 
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
                      </span>
                    )}
                    <div className="flex space-x-2">
                      <Link 
                        href={`/projects/${project.id}`} 
                        className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        Edit
                      </Link>
                      <button className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </MainLayout>
  );
}
