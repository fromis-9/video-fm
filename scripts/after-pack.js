const fs = require('fs');
const path = require('path');

module.exports = async function afterPack(context) {
  console.log('Running after-pack script...');
  
  // Only run on macOS and Linux
  if (context.electronPlatformName === 'win32') {
    console.log('Skipping permission fixes on Windows');
    return;
  }
  
  const appOutDir = context.appOutDir;
  console.log('App output directory:', appOutDir);
  
  // Define files that need executable permissions based on platform
  let executableFiles = [];
  
  if (context.electronPlatformName === 'darwin') {
    executableFiles = [
      'video.fm.app/Contents/Resources/extraResources/videofm',
      'video.fm.app/Contents/Resources/extraResources/bin/ffmpeg',
      'video.fm.app/Contents/Resources/extraResources/bin/ffprobe'
    ];
  } else {
    // Linux paths
    executableFiles = [
      'resources/extraResources/videofm',
      'resources/extraResources/bin/ffmpeg',
      'resources/extraResources/bin/ffprobe'
    ];
  }
  
  for (const filePath of executableFiles) {
    const fullPath = path.join(appOutDir, filePath);
    
    try {
      if (fs.existsSync(fullPath)) {
        console.log(`Setting executable permissions for: ${filePath}`);
        fs.chmodSync(fullPath, 0o755);
        console.log(`✅ Permissions set for: ${filePath}`);
      } else {
        console.log(`⚠️ File not found: ${filePath}`);
      }
    } catch (error) {
      console.error(`❌ Failed to set permissions for ${filePath}:`, error.message);
    }
  }
  
  console.log('After-pack script completed');
}; 