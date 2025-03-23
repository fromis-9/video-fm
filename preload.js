const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld(
  'api', {
    // Running the Python script
    runVideoFM: (config) => ipcRenderer.invoke('run-videofm', config),
    
    // File operations
    showInFolder: (filePath) => ipcRenderer.invoke('show-in-folder', filePath),
    openAppFolder: () => ipcRenderer.invoke('open-app-folder'),
    openVideo: (filePath) => ipcRenderer.invoke('open-video', filePath),
    
    // Process control
    stopProcess: () => ipcRenderer.invoke('stop-process'),
    
    // Input handling
    provideYoutubeUrl: (url) => ipcRenderer.invoke('provide-youtube-url', url),
    respondReplaceVideos: (response) => ipcRenderer.invoke('respond-replace-videos', response),
    provideApiKey: (key) => ipcRenderer.invoke('provide-api-key', key),
    provideSongNumber: (number) => ipcRenderer.invoke('provide-song-number', number),
    provideReplaceUrl: (url) => ipcRenderer.invoke('provide-replace-url', url),
    provideOverwriteResponse: (response) => ipcRenderer.invoke('provide-overwrite-response', response),
    
    // Event listeners
    onPythonOutput: (callback) => ipcRenderer.on('python-output', (event, data) => callback(data)),
    onPythonError: (callback) => ipcRenderer.on('python-error', (event, data) => callback(data)),
    onRequestYoutubeUrl: (callback) => ipcRenderer.on('request-youtube-url', (event, data) => callback(data)),
    onAskReplaceVideos: (callback) => ipcRenderer.on('ask-replace-videos', (event, data) => callback(data)),

    // External links
    openExternal: (url) => ipcRenderer.invoke('open-external', url),

    // Misc
    clearCache: () => ipcRenderer.invoke('clear-cache')
  }
);

// Expose path module for file path operations
contextBridge.exposeInMainWorld('path', {
  join: (...args) => require('path').join(...args),
  resolve: (...args) => require('path').resolve(...args),
  dirname: (path) => require('path').dirname(path)
});

// Make __dirname available to renderer
contextBridge.exposeInMainWorld('__dirname', __dirname);

// Log when preload script has completed - helpful for debugging
console.log('Preload script loaded successfully');