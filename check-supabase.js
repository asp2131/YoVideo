// Simple script to check Supabase storage configuration
const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = 'https://whwbduaefolbnfdrcfuo.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indod2JkdWFlZm9sYm5mZHJjZnVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcxNTU2MzQsImV4cCI6MjA2MjczMTYzNH0.dVMinX4X2mH_SVsGcokMHEGd1mDOb4pNO7o6wj_XLMU';

const supabase = createClient(supabaseUrl, supabaseKey);

async function checkSupabaseStorage() {
  try {
    console.log('Checking Supabase storage buckets...');
    const { data: buckets, error } = await supabase.storage.listBuckets();
    
    if (error) {
      console.error('Error listing buckets:', error);
      return;
    }
    
    console.log('Available buckets:', buckets.map(b => b.name));
    
    // Check if source-videos bucket exists
    const sourceVideosBucket = buckets.find(b => b.name === 'source-videos');
    if (!sourceVideosBucket) {
      console.log('The "source-videos" bucket does not exist. Creating it...');
      const { data: newBucket, error: createError } = await supabase.storage.createBucket('source-videos', {
        public: false
      });
      
      if (createError) {
        console.error('Error creating source-videos bucket:', createError);
      } else {
        console.log('Successfully created source-videos bucket:', newBucket);
      }
    } else {
      console.log('The "source-videos" bucket exists:', sourceVideosBucket);
    }
  } catch (err) {
    console.error('Unexpected error:', err);
  }
}

checkSupabaseStorage();
