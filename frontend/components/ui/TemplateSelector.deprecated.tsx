import { useState } from 'react';
import Image from 'next/image';

interface Template {
  id: string;
  name: string;
  description: string;
  thumbnailUrl: string;
  category: string;
}

interface TemplateSelectorProps {
  onTemplateSelect: (templateId: string) => void;
  selectedTemplateId?: string;
  className?: string;
}

export default function TemplateSelector({
  onTemplateSelect,
  selectedTemplateId,
  className = ''
}: TemplateSelectorProps) {
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Sample template data - in a real app, this would come from an API
  const templates: Template[] = [
    {
      id: 'minimal-1',
      name: 'Minimal Clean',
      description: 'Simple, clean design with minimal distractions',
      thumbnailUrl: '',
      category: 'minimal'
    },
    {
      id: 'social-1',
      name: 'Social Media Basic',
      description: 'Optimized for social media feeds with captions',
      thumbnailUrl: '',
      category: 'social'
    },
    {
      id: 'social-2',
      name: 'TikTok Style',
      description: 'Vertical format with animated captions',
      thumbnailUrl: '',
      category: 'social'
    },
    {
      id: 'professional-1',
      name: 'Corporate Presentation',
      description: 'Professional design for business presentations',
      thumbnailUrl: '',
      category: 'professional'
    },
    {
      id: 'tutorial-1',
      name: 'Tutorial Layout',
      description: 'Perfect for educational content and how-to videos',
      thumbnailUrl: '',
      category: 'tutorial'
    },
    {
      id: 'custom-1',
      name: 'Custom Template',
      description: 'Your custom saved template',
      thumbnailUrl: '',
      category: 'custom'
    }
  ];

  // Get unique categories
  const categories = ['all', ...new Set(templates.map(t => t.category))];

  // Filter templates based on category and search query
  const filteredTemplates = templates.filter(template => {
    const matchesCategory = activeCategory === 'all' || template.category === activeCategory;
    const matchesSearch = template.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          template.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className={`${className}`}>
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Select a Template</h3>
        
        {/* Search and filter */}
        <div className="flex flex-col sm:flex-row gap-4 mb-4">
          <div className="flex-grow">
            <input
              type="text"
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex-shrink-0">
            <select
              value={activeCategory}
              onChange={(e) => setActiveCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category.charAt(0).toUpperCase() + category.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>
        
        {/* Template grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className={`border rounded-lg overflow-hidden cursor-pointer transition-all ${
                selectedTemplateId === template.id
                  ? 'border-blue-500 ring-2 ring-blue-500'
                  : 'border-gray-200 hover:border-blue-300'
              }`}
              onClick={() => onTemplateSelect(template.id)}
            >
              <div className="relative h-32 bg-gray-100">
                {template.thumbnailUrl ? (
                  <Image
                    src={template.thumbnailUrl}
                    alt={template.name}
                    fill
                    className="object-cover"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full bg-gray-200">
                    <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                  </div>
                )}
                <div className="absolute top-2 right-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                    {template.category}
                  </span>
                </div>
              </div>
              <div className="p-3">
                <h4 className="font-medium text-gray-900">{template.name}</h4>
                <p className="text-sm text-gray-500 mt-1">{template.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Template preview */}
      {selectedTemplateId && (
        <div className="mt-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Template Preview</h3>
          <div className="bg-gray-100 rounded-lg p-4">
            <div className="aspect-video bg-gray-200 rounded-lg flex items-center justify-center">
              <div className="text-center">
                <p className="text-gray-500 mb-2">Preview of selected template</p>
                <p className="text-sm text-gray-400">
                  {templates.find(t => t.id === selectedTemplateId)?.name}
                </p>
              </div>
            </div>
            <div className="mt-4">
              <h4 className="font-medium text-gray-900 mb-2">Template Settings</h4>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Caption Style
                  </label>
                  <select className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option>Default</option>
                    <option>Minimal</option>
                    <option>Bold</option>
                    <option>Animated</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Color Scheme
                  </label>
                  <div className="flex space-x-2">
                    <button className="w-8 h-8 bg-blue-500 rounded-full"></button>
                    <button className="w-8 h-8 bg-red-500 rounded-full"></button>
                    <button className="w-8 h-8 bg-green-500 rounded-full"></button>
                    <button className="w-8 h-8 bg-purple-500 rounded-full"></button>
                    <button className="w-8 h-8 bg-yellow-500 rounded-full"></button>
                    <button className="w-8 h-8 bg-gray-800 rounded-full"></button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Animation Speed
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="2"
                    step="0.1"
                    defaultValue="1"
                    className="w-full"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
