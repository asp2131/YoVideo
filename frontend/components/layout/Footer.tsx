import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 py-6 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-center">
          <div className="mb-4 md:mb-0">
            <p className="text-sm text-gray-500">© {new Date().getFullYear()} OpusClip. All rights reserved.</p>
          </div>
          <div className="flex space-x-6">
            <Link href="/terms" className="text-sm text-gray-500 hover:text-blue-600">
              Terms of Service
            </Link>
            <Link href="/privacy" className="text-sm text-gray-500 hover:text-blue-600">
              Privacy Policy
            </Link>
            <Link href="/contact" className="text-sm text-gray-500 hover:text-blue-600">
              Contact
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
