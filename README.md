# video.fm

<img src="assets/icons/icon.png" alt="Video.fm logo" width="100"/>

A desktop application that automatically creates personalized music video compilations based on your Last.fm listening history. Transform your music taste into shareable video content with just a few clicks.

## Features

- **Last.fm Integration**: Seamlessly enter the user of any Last.fm account to access its full listening history
- **Custom Compilations**: Create video compilations of your top songs for any given date period
- **Smart Video Selection**: Automatically searches for related music videos
- **Video Editing**: Replace specific videos during the creation process
- **Cross-platform**: Compatible with both macOS and Windows

## Installation

### macOS
1. Download the latest `.dmg` file from the [Releases](https://github.com/yourusername/video-fm/releases) page or [videofm.app](https://videofm.app)
2. Open the DMG file and drag the application to your Applications folder
3. Right-click on the app and select "Open" to bypass macOS security warning on first launch
4. If you see a security warning, go to System Preferences → Security & Privacy → General and click "Open Anyway"

### Windows
1. Download the latest `.exe` installer from the [Releases](https://github.com/yourusername/video-fm/releases) page or [videofm.app](https://videofm.app)
2. Run the installer and follow the on-screen instructions
3. Launch the application from the Start menu or desktop shortcut
4. If SmartScreen shows a warning, click "More info" and "Run anyway"

## Usage

### Getting Started
1. Launch the video.fm application
2. Configure your API keys in the settings panel
3. Esnter your Last.fm username in the main field
4. Select the year and month for your compilation
5. Choose how many songs to include (1-50)
6. Check "Allow manual YouTube URL entry" if you want to provide specific video URLs from failed searches
7. Click "Generate" to start the compilation process

### Want hardware acceleration?
Look for the .py file in the program directory and edit the `SELECTED_CODEC` constant under `USER CONFIGURATION`

## API Keys

This application requires two API keys to function properly:

1. **Last.fm API Key**:
   - Register at [Last.fm API](https://www.last.fm/api/account/create)
   - Click on "Create API account" and fill out the application form:
   - Application name: video.fm (or your anything). You can skip the rest
   - After submitting, you'll receive your API key immediately on the confirmation page
   - Copy this API key and paste it into the settings section of video.fm (gear icon)

2. **YouTube API Key**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/) and sign in with your Google account
   - Click "Create Project" at the top of the page and name it (e.g., "video.fm")
   - Once your project is created, navigate to "APIs & Services" > "Library" in the left sidebar
   - Search for "YouTube Data API v3" and select it from the results
   - Click the "Enable" button to activate this API for your project
   - After enabling, go to "APIs & Services" > "Credentials" in the left sidebar
   - Click "Create Credentials" and select "API key" from the dropdown menu
   - Your new API key will be displayed - copy it to use in video.fm
   - Paste your API key into the video.fm settings screen (gear icon)

## System Requirements

- **Operating System**: macOS 10.13+ or Windows 10+
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Disk Space**: 500MB+ free space (varies based on compilation length)
- **Internet**: Good internet connection
- **Dependencies**: FFmpeg (automatically downloaded if not present)

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| No videos found | Verify your Last.fm username and time period |
| API quota exceeded | Get a new YouTube API key or wait next day |
| Low quality videos | Check your internet connection or manually provide URLs |
| Application crashes | Check console logs and ensure all dependencies are installed |
| Missing audio | Make sure FFmpeg is properly installed |
| File already exists. Replace y/N | Working on this, for now just try to delete or move video files you don't need |


## Privacy

- All API keys and user preferences are stored locally on your device
- No data is sent to our servers
- The application only communicates with Last.fm and YouTube APIs
- Your listening history remains private to your account
- Downloaded videos are stored temporarily and cleaned up after compilation

## Development

### Building from Source
```bash
# Clone repository
git clone https://github.com/yourusername/video-fm.git
cd video-fm

# Install dependencies
npm install

# Run in development mode
npm start

# Build for production
npm run package-mac    # For macOS
npm run package-win    # For Windows
```

### Contributing
Contributions are welcome! Please check out our [Contributing Guide](CONTRIBUTING.md) for more information.

## License

[MIT License](LICENSE)

## Roadmap

- [ ] Spotify integration
- [ ] Custom video intro/outro options
- [ ] Additional video effects and transitions
- [ ] Year in review compilation feature
- [ ] Artist-specific compilations
- [ ] Export to various quality settings
- [ ] More

## Credits

- Last.fm for the listening history API
- Uses yt-dlp for video downloading
- FFmpeg for media processing
- Electron for the application framework

## Contact

- Discord: @fromis_09