// Script to check Supabase storage configuration using service key
const { createClient } = require('@supabase/supabase-js');
const { exec } = require('child_process');

// Get environment variables from .zshrc
function getEnvVar(varName) {
  return new Promise((resolve, reject) => {
    exec(`source ~/.zshrc && echo $${varName}`, (error, stdout, stderr) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(stdout.trim());
    });
  });
}

async function checkSupabaseStorage() {
  try {
    // Get Supabase URL and service key from environment variables
    const supabaseUrl = await getEnvVar('SUPABASE_URL');
    const supabaseServiceKey = await getEnvVar('SUPABASE_SERVICE_KEY');
    
    if (!supabaseUrl || !supabaseServiceKey) {
      console.error('Missing Supabase environment variables');
      return;
    }
    
    console.log(`Using Supabase URL: ${supabaseUrl}`);
    console.log('Service key available: Yes');
    
    const supabase = createClient(supabaseUrl, supabaseServiceKey);
    
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
      console.log('The "source-videos" bucket does not exist.');
    } else {
      console.log('The "source-videos" bucket exists:', sourceVideosBucket);
      
      // List files in the bucket
      console.log('Listing files in source-videos bucket...');
      const { data: files, error: filesError } = await supabase
        .storage
        .from('source-videos')
        .list();
        
      if (filesError) {
        console.error('Error listing files:', filesError);
      } else {
        console.log('Files in source-videos bucket:', files);
      }
    }
  } catch (err) {
    console.error('Unexpected error:', err);
  }
}

checkSupabaseStorage();
