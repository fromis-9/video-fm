// Enable console logging for debugging
const DEBUG = true;
function debugLog(...args) {
  if (DEBUG) console.log("[RENDERER]", ...args);
}

debugLog("Renderer script starting...");

// Global variable to store video path when available
let currentVideoPath = null;

// Track log scroll position
let userScrolledLog = false;
let preventLogUpdates = false;

// DOM Elements - Check they exist after loading
let configForm;
let generateBtn;
let outputPanel;
let outputLog;
let progressBar;
let progressStatus;
let stopProcessBtn;
let toggleLogBtn;
let openFolderBtn;
let openVideoBtn;
let settingsBtn;
let settingsModal;
let lastfmApiKeyInput;
let youtubeApiKeyInput;
let toggleLastfmVisibility;
let toggleYoutubeVisibility;
let saveSettingsBtn;
let cancelSettingsBtn;

// YouTube URL modal elements
let youtubeUrlPrompt;
let youtubePromptText;
let youtubeUrlInput;
let submitYoutubeUrl;
let skipYoutubeUrl;

// Replace videos modal elements
let replaceVideosPrompt;
let yesReplace;
let noReplace;
let previewVideoBtn;

// API key modal elements
let apiKeyPrompt;
let newApiKeyInput;
let submitNewApiKey;
let cancelNewApiKey;
let toggleNewApiKeyVisibility;

// Replace song modal elements
let replaceSongPrompt;
let songListContainer;
let songNumberInput;
let submitSongNumber;
let cancelSongNumber;

// Replace song URL modal elements
let replaceSongUrlPrompt;
let replaceSongUrlText;
let replaceSongUrlInput;
let submitReplaceUrl;
let cancelReplaceUrl;

// Overwrite file prompt elements
let overwriteFilePrompt;
let yesOverwrite;
let noOverwrite;

// Initialize DOM elements after the document has loaded
document.addEventListener("DOMContentLoaded", () => {
  debugLog("Document loaded, initializing DOM elements...");

  try {
    // Main form elements
    configForm = document.getElementById("config-form");
    generateBtn = document.getElementById("generate-btn");
    outputPanel = document.getElementById("output-panel");
    outputLog = document.getElementById("output-log");
    progressBar = document.getElementById("progress-bar");
    progressStatus = document.querySelector(".progress-status");
    stopProcessBtn = document.getElementById("stop-process-btn");
    toggleLogBtn = document.getElementById("toggle-log-btn");
    openFolderBtn = document.getElementById("open-folder-btn");
    openVideoBtn = document.getElementById("open-video-btn");

    // Settings modal elements
    settingsBtn = document.getElementById("settings-btn");
    settingsModal = document.getElementById("settings-modal");
    lastfmApiKeyInput = document.getElementById("settings-lastfm-api-key");
    youtubeApiKeyInput = document.getElementById("settings-youtube-api-key");
    toggleLastfmVisibility = document.getElementById(
      "toggle-lastfm-visibility"
    );
    toggleYoutubeVisibility = document.getElementById(
      "toggle-youtube-visibility"
    );
    saveSettingsBtn = document.getElementById("save-settings");
    cancelSettingsBtn = document.getElementById("cancel-settings");

    // YouTube URL modal elements
    youtubeUrlPrompt = document.getElementById("youtube-url-prompt");
    youtubePromptText = document.getElementById("youtube-prompt-text");
    youtubeUrlInput = document.getElementById("youtube-url-input");
    submitYoutubeUrl = document.getElementById("submit-youtube-url");
    skipYoutubeUrl = document.getElementById("skip-youtube-url");

    // Replace videos modal elements
    replaceVideosPrompt = document.getElementById("replace-videos-prompt");
    yesReplace = document.getElementById("yes-replace");
    noReplace = document.getElementById("no-replace");
    previewVideoBtn = document.getElementById("preview-video");

    // API key modal elements
    apiKeyPrompt = document.getElementById("api-key-prompt");
    newApiKeyInput = document.getElementById("new-api-key-input");
    submitNewApiKey = document.getElementById("submit-new-api-key");
    cancelNewApiKey = document.getElementById("cancel-new-api-key");
    toggleNewApiKeyVisibility = document.getElementById(
      "toggle-new-api-key-visibility"
    );

    // Replace song modal elements
    replaceSongPrompt = document.getElementById("replace-song-prompt");
    songListContainer = document.getElementById("song-list-container");
    songNumberInput = document.getElementById("song-number-input");
    submitSongNumber = document.getElementById("submit-song-number");
    cancelSongNumber = document.getElementById("cancel-song-number");

    // Replace song URL modal elements
    replaceSongUrlPrompt = document.getElementById("replace-song-url-prompt");
    replaceSongUrlText = document.getElementById("replace-song-url-text");
    replaceSongUrlInput = document.getElementById("replace-song-url-input");
    submitReplaceUrl = document.getElementById("submit-replace-url");
    cancelReplaceUrl = document.getElementById("cancel-replace-url");

    // Overwrite file prompt elements
    overwriteFilePrompt = document.getElementById("overwrite-file-prompt");
    yesOverwrite = document.getElementById("yes-overwrite");
    noOverwrite = document.getElementById("no-overwrite");

    // Verify critical elements exist
    if (!configForm) throw new Error("Config form not found");
    if (!generateBtn) throw new Error("Generate button not found");
    if (!settingsBtn) throw new Error("Settings button not found");

    // Set up scroll detection for log
    if (outputLog) {
      outputLog.addEventListener("scroll", function () {
        // Check if user has scrolled up (not at the bottom)
        const isAtBottom =
          outputLog.scrollHeight - outputLog.clientHeight <=
          outputLog.scrollTop + 10;
        userScrolledLog = !isAtBottom;
      });
    }

    debugLog("All DOM elements initialized successfully");

    // Now set up event handlers
    setupEventHandlers();

    // Load saved data
    loadSavedData();
  } catch (error) {
    console.error("Error initializing DOM elements:", error);
    alert("Error initializing app. Check console for details.");
  }
});

// Set up all event handlers
function setupEventHandlers() {
  debugLog("Setting up event handlers...");

  try {
    // Listen for Python process output
    window.api.onPythonOutput((data) => {
      // Prevent log updates when hide button was clicked
      if (preventLogUpdates) return;

      // Always log data
      appendToLog(data);
      updateProgressBar(data);

      // Check for API quota error
      if (
        data.includes("API quota exceeded") &&
        data.includes("Enter new API key:")
      ) {
        debugLog("API quota exceeded, showing prompt");
        apiKeyPrompt.classList.remove("hidden");
      }

      // Load codec setting
      const codecSelection = document.getElementById("codec-selection");
      if (codecSelection) {
        const savedCodec = localStorage.getItem("selected-codec") || "libx264";
        codecSelection.value = savedCodec;

        // Save codec when changed
        codecSelection.addEventListener("change", () => {
          localStorage.setItem("selected-codec", codecSelection.value);
        });
      }

      // Add codec to config when generating video
      function handleFormSubmit(e) {
        e.preventDefault();

        // Get form values
        const config = {
          // Existing fields...
          codec: document.getElementById("codec-selection").value || "libx264",
        };
      }

      // Check for file overwrite prompt - using a more flexible pattern
      const overwriteMatch = data.match(
        /['"]?([^'"]+\.mp4)['"]? already exists\. Overwrite\? \[y\/N\]/
      );
      if (overwriteMatch) {
        debugLog("File overwrite prompt detected:", overwriteMatch[1]);
        // Extract filename from the match
        const fileName = overwriteMatch[1].split("/").pop(); // Get just the filename

        // Set the filename in the UI
        const fileNameElem = document.getElementById("overwrite-filename");
        if (fileNameElem) {
          fileNameElem.textContent = fileName;
        }

        // Show the overwrite prompt
        if (overwriteFilePrompt) {
          overwriteFilePrompt.classList.remove("hidden");
        }

        return;
      }

      // Check for song list and replacement prompt
      const songListMatch = data.match(
        /Current videos in compilation:([\s\S]*?)Enter the song number to replace \(1-(\d+)\):/
      );
      if (songListMatch) {
        debugLog("Song replacement prompt detected");

        // Extract song list and max number
        const songListText = songListMatch[1].trim();
        const maxSongs = parseInt(songListMatch[2]);

        // Populate the song list UI
        if (songListContainer) {
          songListContainer.innerHTML = "";

          // Extract individual songs from the list
          const songs = songListText
            .split("\n")
            .map((line) => line.trim())
            .filter((line) => line.match(/^\d+\./));

          songs.forEach((song) => {
            const songItem = document.createElement("div");
            songItem.className = "song-item";
            songItem.textContent = song;
            songListContainer.appendChild(songItem);
          });
        }

        // Update the input max attribute
        if (songNumberInput) {
          songNumberInput.max = maxSongs;
          songNumberInput.placeholder = `Enter song number (1-${maxSongs})`;
        }

        // Show the prompt
        if (replaceSongPrompt) {
          replaceSongPrompt.classList.remove("hidden");
        }

        return;
      }

      // Check for replacement URL prompt
      const replaceUrlMatch = data.match(/Enter the correct YouTube URL:/);
      if (replaceUrlMatch) {
        debugLog("Replace URL prompt detected");

        // Extract song information from previous messages if possible
        const songInfo = findReplacingSongInfo(data);

        if (replaceSongUrlText) {
          replaceSongUrlText.textContent = songInfo
            ? `Enter YouTube URL for: ${songInfo}`
            : "Enter the correct YouTube URL:";
        }

        if (replaceSongUrlPrompt) {
          replaceSongUrlPrompt.classList.remove("hidden");
        }

        return;
      }

      // Check for video completion
      if (
        data.includes("Video compilation complete") ||
        data.includes("Final video saved") ||
        data.includes("✨ Video compilation complete") ||
        data.includes("✨ Final video saved")
      ) {
        // Extract filename if possible
        const filenameMatch = data.match(
          /(?:Final video saved as:|Video compilation complete! Saved as:) ([\w.-]+\.mp4)/
        );
        if (filenameMatch && filenameMatch[1]) {
          const filename = filenameMatch[1];
          // Use path.join if available, otherwise use string concatenation
          const filePath = window.path
            ? window.path.join(__dirname, "..", filename)
            : `${__dirname}/../${filename}`; // Fallback

          debugLog("Video completed, path:", filePath);

          // Store the path globally
          currentVideoPath = filePath;

          // Set path on both buttons
          if (openVideoBtn) {
            openVideoBtn.setAttribute("data-path", filePath);
            openVideoBtn.classList.remove("hidden");
          }

          // Also set on preview button if it exists
          if (previewVideoBtn) {
            previewVideoBtn.setAttribute("data-path", filePath);
          }

          // Set progress to 100%
          progressBar.style.width = "100%";
          progressStatus.textContent = "Complete!";
        }
      }

      // Filter out download completion messages
      const isDownloadCompletion =
        data.includes("[download] 100%") ||
        data.includes("Destination:") ||
        data.includes("Downloaded") ||
        data.includes("ETA");

      // Only show log for actual errors, not download-related messages
      if (
        (data.toLowerCase().includes("error") &&
          !data.includes("[download]") &&
          !isDownloadCompletion) ||
        (data.includes("❌") &&
          !data.includes("download") &&
          !isDownloadCompletion)
      ) {
        showLogPanel();
      }
    });

    // Listen for Python process errors
    window.api.onPythonError((data) => {
      // Show log on error
      showLogPanel();
      appendToLog(`ERROR: ${data}`, "error");
    });

    // Listen for YouTube URL requests
    window.api.onRequestYoutubeUrl((prompt) => {
      debugLog("YouTube URL requested");
      youtubePromptText.textContent = prompt;
      youtubeUrlPrompt.classList.remove("hidden");
      youtubeUrlInput.value = "";
    });

    // In your window.api.onAskReplaceVideos handler:
    // Replace your existing onAskReplaceVideos event handler with this:
    window.api.onAskReplaceVideos(() => {
      debugLog("Replace videos question received");
      replaceVideosPrompt.classList.remove("hidden"); /*

      // Find the preview button
      const previewBtn = document.getElementById("preview-video");

      if (previewBtn) {
        // Clear existing event listeners by cloning the button
        const newPreviewBtn = previewBtn.cloneNode(true);
        previewBtn.parentNode.replaceChild(newPreviewBtn, previewBtn);

        // Add the event listener to the new button
        document
          .getElementById("preview-video")
          .addEventListener("click", () => {
            debugLog("Preview video button clicked");

            // Just use the same handler as the open button - directly call the API
            if (currentVideoPath) {
              window.api.openVideo(currentVideoPath);
            } else {
              // If we don't have a path, try to get it from the open button
              const openBtn = document.getElementById("open-video-btn");
              const path = openBtn ? openBtn.getAttribute("data-path") : null;

              if (path) {
                window.api.openVideo(path);
              } else {
                appendToLog(
                  "Cannot preview video: Video not yet created",
                  "error"
                );
              }
            }
          });
      }*/
    });

    // Form submission
    configForm.addEventListener("submit", handleFormSubmit);

    // Settings modal functionality
    settingsBtn.addEventListener("click", () => {
      debugLog("Settings button clicked");
      settingsModal.classList.remove("hidden");
    });

    cancelSettingsBtn.addEventListener("click", () => {
      debugLog("Cancel settings button clicked");
      settingsModal.classList.add("hidden");
      // Reset to saved values
      loadApiKeys();
    });

    saveSettingsBtn.addEventListener("click", () => {
      debugLog("Save settings button clicked");
      saveApiKeys();
      settingsModal.classList.add("hidden");
    });

    // Toggle password visibility
    toggleLastfmVisibility.addEventListener("click", () => {
      togglePasswordVisibility(lastfmApiKeyInput, toggleLastfmVisibility);
    });

    toggleYoutubeVisibility.addEventListener("click", () => {
      togglePasswordVisibility(youtubeApiKeyInput, toggleYoutubeVisibility);
    });

    // Toggle new API key visibility
    if (toggleNewApiKeyVisibility) {
      toggleNewApiKeyVisibility.addEventListener("click", () => {
        togglePasswordVisibility(newApiKeyInput, toggleNewApiKeyVisibility);
      });
    }

    // Clear cache button
    document.getElementById("clear-cache-btn").addEventListener("click", () => {
      if (
        confirm(
          "Are you sure you want to clear the cache? This will remove saved search results."
        )
      ) {
        window.api
          .clearCache()
          .then(() => {
            appendToLog("Cache cleared successfully", "success");
          })
          .catch((err) => {
            appendToLog(`Error clearing cache: ${err.message}`, "error");
          });
      }
    });

    // Open folder button
    openFolderBtn.addEventListener("click", () => {
      debugLog("Open folder button clicked");
      window.api
        .openAppFolder()
        .then((result) => {
          if (!result.success) {
            console.error("Failed to open app folder:", result.error);
          }
        })
        .catch((err) => {
          console.error("Error opening app folder:", err);
        });
    });

    // Open video button
    if (openVideoBtn) {
      openVideoBtn.addEventListener("click", () => {
        console.log("WORKING BUTTON - currentVideoPath:", currentVideoPath);
        console.log(
          "WORKING BUTTON - button path:",
          openVideoBtn.getAttribute("data-path")
        );
        debugLog("Open video button clicked");
        openCurrentVideo();
      });
    }

    // Preview video button
    if (previewVideoBtn) {
      previewVideoBtn.addEventListener("click", () => {
        debugLog(
          "Preview video button clicked, path:",
          previewVideoBtn.getAttribute("data-path")
        );
        openCurrentVideo(true);
      });
    }

    // Toggle log visibility with protection against interference with downloading status
    toggleLogBtn.addEventListener("click", () => {
      debugLog("Toggle log button clicked");

      if (outputLog.classList.contains("visible")) {
        // Closing the log
        outputLog.classList.remove("visible");
        outputLog.classList.add("hidden");
        toggleLogBtn.textContent = "Show Log";

        // Set flag to prevent log updates from reopening it
        preventLogUpdates = true;

        // Reset flag after a longer delay
        setTimeout(() => {
          preventLogUpdates = false;
        }, 2000); // Increase to 2 seconds
      } else {
        // Opening the log
        outputLog.classList.remove("hidden");
        outputLog.classList.add("visible");
        toggleLogBtn.textContent = "Hide Log";
        preventLogUpdates = false;
      }
    });

    // Stop process button
    stopProcessBtn.addEventListener("click", () => {
      debugLog("Stop process button clicked");
      window.api
        .stopProcess()
        .then(() => {
          resetUI();
          appendToLog("Process stopped by user", "warning");
          progressStatus.innerHTML = '<span class="warning">⚠️ Stopped</span>';
        })
        .catch((err) => {
          appendToLog(`Error stopping process: ${err.message}`, "error");
        });
    });

    // Submit YouTube URL
    submitYoutubeUrl.addEventListener("click", () => {
      debugLog("Submit YouTube URL button clicked");
      const url = youtubeUrlInput.value.trim();
      if (url) {
        window.api.provideYoutubeUrl(url);
        youtubeUrlPrompt.classList.add("hidden");
      }
    });

    // Skip providing YouTube URL
    skipYoutubeUrl.addEventListener("click", () => {
      debugLog("Skip YouTube URL button clicked");
      window.api.provideYoutubeUrl("");
      youtubeUrlPrompt.classList.add("hidden");
    });

    // Respond to "replace videos" question
    yesReplace.addEventListener("click", () => {
      debugLog("Yes replace button clicked");
      window.api.respondReplaceVideos("yes");
      replaceVideosPrompt.classList.add("hidden");
    });

    noReplace.addEventListener("click", () => {
      debugLog("No replace button clicked");
      window.api.respondReplaceVideos("no");
      replaceVideosPrompt.classList.add("hidden");
    });

    // Respond to file overwrite question
    if (yesOverwrite) {
      yesOverwrite.addEventListener("click", () => {
        debugLog("Yes overwrite button clicked");
        window.api.provideOverwriteResponse("y");
        overwriteFilePrompt.classList.add("hidden");
      });
    }

    if (noOverwrite) {
      noOverwrite.addEventListener("click", () => {
        debugLog("No overwrite button clicked");
        window.api.provideOverwriteResponse("n");
        overwriteFilePrompt.classList.add("hidden");
      });
    }

    // Submit new API key
    submitNewApiKey.addEventListener("click", () => {
      debugLog("Submit new API key button clicked");
      const newKey = newApiKeyInput.value.trim();
      if (newKey) {
        window.api
          .provideApiKey(newKey)
          .then(() => {
            // Update the saved API key in localStorage
            localStorage.setItem("youtube-api-key", newKey);
            youtubeApiKeyInput.value = newKey;
            apiKeyPrompt.classList.add("hidden");
          })
          .catch((err) => {
            appendToLog(`Error providing new API key: ${err.message}`, "error");
          });
      }
    });

    // Cancel new API key input
    cancelNewApiKey.addEventListener("click", () => {
      debugLog("Cancel new API key button clicked");
      apiKeyPrompt.classList.add("hidden");
      // This will likely cause the process to fail, but user chose to cancel
    });

    // Submit song number for replacement
    if (submitSongNumber) {
      submitSongNumber.addEventListener("click", () => {
        debugLog("Submit song number clicked");
        const songNum = songNumberInput.value.trim();
        if (songNum) {
          window.api
            .provideSongNumber(songNum)
            .then(() => {
              replaceSongPrompt.classList.add("hidden");
            })
            .catch((err) => {
              appendToLog(
                `Error providing song number: ${err.message}`,
                "error"
              );
            });
        }
      });
    }

    // Cancel song number selection
    if (cancelSongNumber) {
      cancelSongNumber.addEventListener("click", () => {
        debugLog("Cancel song number clicked");
        // Send a cancel signal to the process
        window.api
          .provideSongNumber("0")
          .then(() => {
            replaceSongPrompt.classList.add("hidden");
          })
          .catch((err) => {
            console.error("Error canceling song number:", err);
          });
      });
    }

    // Submit replacement YouTube URL
    if (submitReplaceUrl) {
      submitReplaceUrl.addEventListener("click", () => {
        debugLog("Submit replacement URL clicked");
        const url = replaceSongUrlInput.value.trim();
        if (url) {
          window.api
            .provideReplaceUrl(url)
            .then(() => {
              replaceSongUrlPrompt.classList.add("hidden");
            })
            .catch((err) => {
              appendToLog(
                `Error providing replacement URL: ${err.message}`,
                "error"
              );
            });
        }
      });
    }

    // Cancel replacement URL
    if (cancelReplaceUrl) {
      cancelReplaceUrl.addEventListener("click", () => {
        debugLog("Cancel replacement URL clicked");
        window.api
          .provideReplaceUrl("")
          .then(() => {
            replaceSongUrlPrompt.classList.add("hidden");
          })
          .catch((err) => {
            console.error("Error canceling replacement URL:", err);
          });
      });
    }

    // Add GitHub link handler
    const githubLink = document.getElementById("videoFmGithubLink");
    if (githubLink) {
      githubLink.addEventListener("click", (e) => {
        e.preventDefault();
        debugLog("GitHub link clicked");

        const githubUrl = "https://github.com/fromis-9/video-fm";

        // Use Electron's shell to open the URL in the default browser
        window.api
          .openExternal(githubUrl)
          .then(() => debugLog("GitHub page opened successfully"))
          .catch((err) => console.error("Error opening GitHub page:", err));
      });
    }

    debugLog("All event handlers set up successfully");
  } catch (error) {
    console.error("Error setting up event handlers:", error);
    alert("Error setting up event handlers. Check console for details.");
  }
}

// Helper function to open current video (used by both open and preview buttons)
function openCurrentVideo(isPreview = false) {
  // Try using the global path first
  if (currentVideoPath) {
    debugLog("Opening video from global path:", currentVideoPath);
    window.api
      .openVideo(currentVideoPath)
      .then(() => {
        debugLog("Video opened successfully");
      })
      .catch((err) => {
        console.error("Error opening video:", err);
        const msg = `Error ${isPreview ? "previewing" : "opening"} video: ${
          err.message
        }`;
        appendToLog(msg, "error");
      });
  } else {
    // Fallback to attribute on button
    const btn = isPreview ? previewVideoBtn : openVideoBtn;
    const videoPath = btn ? btn.getAttribute("data-path") : null;

    if (videoPath) {
      debugLog(
        `Opening video from ${
          isPreview ? "preview" : "open"
        } button attribute:`,
        videoPath
      );
      window.api
        .openVideo(videoPath)
        .then(() => {
          // Save to global path if it works
          currentVideoPath = videoPath;
          debugLog("Video opened and path saved");
        })
        .catch((err) => {
          console.error(
            `Error opening video from ${
              isPreview ? "preview" : "open"
            } button attribute:`,
            err
          );
          const msg = `Error ${isPreview ? "previewing" : "opening"} video: ${
            err.message
          }`;
          appendToLog(msg, "error");
        });
    } else {
      const msg = `Cannot ${
        isPreview ? "preview" : "open"
      } video: Video not yet created`;
      appendToLog(msg, "error");
    }
  }
}

// Handle form submission
async function handleFormSubmit(e) {
  e.preventDefault();
  debugLog("Form submitted");

  // Reset global video path
  currentVideoPath = null;

  // Reset user scrolled flag
  userScrolledLog = false;

  // Show output panel and reset state
  outputPanel.classList.remove("hidden");
  outputLog.classList.remove("visible");
  outputLog.classList.add("hidden");
  progressBar.style.width = "0";
  outputLog.textContent = "";
  progressStatus.textContent = "Processing...";

  // Remove any previous file info
  const existingFileInfo = document.querySelector(".file-info");
  if (existingFileInfo) {
    existingFileInfo.remove();
  }

  // Hide open video button
  if (openVideoBtn) {
    openVideoBtn.classList.add("hidden");
  }

  // Get form values
  const config = {
    username: document.getElementById("lastfm-username").value,
    year: document.getElementById("target-year").value,
    month: document.getElementById("target-month").value,
    numSongs: document.getElementById("num-songs").value,
    lastfmApiKey: lastfmApiKeyInput.value,
    youtubeApiKey: youtubeApiKeyInput.value,
    allowManualYoutube: document.getElementById("allow-manual-youtube").checked,
  };

  debugLog("Config:", config);

  // Disable the generate button while processing
  generateBtn.disabled = true;
  generateBtn.textContent = "Processing...";

  try {
    appendToLog("Starting video generation process...");
    debugLog("Calling API to run videofm");
    const result = await window.api.runVideoFM(config);

    if (result.success) {
      debugLog("Process completed successfully");
      progressStatus.innerHTML = '<span class="success">✓ Complete!</span>';
      appendToLog(`✅ ${result.message}`, "success");

      // If we have a file path, add button to open it
      if (result.filePath) {
        debugLog("File path received:", result.filePath);

        // Store path globally
        currentVideoPath = result.filePath;

        // Enable open video button
        if (openVideoBtn) {
          openVideoBtn.setAttribute("data-path", result.filePath);
          openVideoBtn.classList.remove("hidden");
        }

        // Also set on preview button if it exists
        if (previewVideoBtn) {
          previewVideoBtn.setAttribute("data-path", result.filePath);
        }

        // Add video action buttons with open video first, then show in folder
        const fileInfo = document.createElement("div");
        fileInfo.className = "file-info";
        fileInfo.innerHTML = `
          <p class="success">✓ Video saved!</p>
          <div class="video-actions">
            <button id="open-video-file" class="btn">Open Video</button>
            <button id="open-file-location" class="btn">Show in Folder</button>
          </div>
        `;
        outputPanel.appendChild(fileInfo);

        // Add click handlers
        document
          .getElementById("open-video-file")
          .addEventListener("click", () => {
            debugLog("Open video file button clicked");
            openCurrentVideo();
          });

        document
          .getElementById("open-file-location")
          .addEventListener("click", () => {
            debugLog("Open file location button clicked");
            window.api.showInFolder(result.filePath);
          });
      }
    } else {
      debugLog("Process failed:", result.error);
      progressStatus.innerHTML = '<span class="error">✗ Failed</span>';
      showLogPanel();
      appendToLog(`❌ Error: ${result.error}`, "error");
    }
  } catch (error) {
    debugLog("Error running process:", error.message);
    progressStatus.innerHTML = '<span class="error">✗ Failed</span>';
    showLogPanel();
    appendToLog(`❌ Error: ${error.message}`, "error");
  } finally {
    // Re-enable the generate button
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate Video";
  }
}

// Helper for password visibility toggle
function togglePasswordVisibility(input, button) {
  if (input.type === "password") {
    input.type = "text";
    button.textContent = "🔒";
  } else {
    input.type = "password";
    button.textContent = "👁️";
  }
}

// Helper to append text to log
function appendToLog(text, className = "") {
  const entry = document.createElement("div");
  entry.textContent = text;
  if (className) {
    entry.classList.add(className);
  }
  outputLog.appendChild(entry);

  // Only auto-scroll if user hasn't scrolled up
  if (!userScrolledLog) {
    outputLog.scrollTop = outputLog.scrollHeight;
  }
}

// Helper to show log panel when needed
function showLogPanel() {
  // Don't show log if updates are prevented
  if (preventLogUpdates) return;

  // Check if log is hidden first
  if (!outputLog.classList.contains("visible")) {
    // Make sure to remove hidden first then add visible
    outputLog.classList.remove("hidden");
    outputLog.classList.add("visible");
    if (toggleLogBtn) {
      toggleLogBtn.textContent = "Hide Log";
    }
  }
}

// Helper to reset UI to initial state
function resetUI() {
  debugLog("Resetting UI");

  // Hide output panel
  outputPanel.classList.add("hidden");

  // Reset progress bar
  progressBar.style.width = "0";

  // Clear log
  outputLog.textContent = "";
  outputLog.classList.remove("visible");
  outputLog.classList.add("hidden");

  // Reset log button text
  if (toggleLogBtn) {
    toggleLogBtn.textContent = "Show Log";
  }

  // Hide open video button
  if (openVideoBtn) {
    openVideoBtn.classList.add("hidden");
    openVideoBtn.removeAttribute("data-path");
  }

  // Reset global video path
  currentVideoPath = null;

  // Reset user scrolled flag
  userScrolledLog = false;

  // Reset prevention flag
  preventLogUpdates = false;

  // Remove any file info
  const fileInfo = document.querySelector(".file-info");
  if (fileInfo) {
    fileInfo.remove();
  }

  // Re-enable generate button
  generateBtn.disabled = false;
  generateBtn.textContent = "Generate Video";
}

// Song and song stage trackers for progress
let totalSongs = 0;
let processStage = "init"; // init, fetching, processing, merging
let currentSong = 0;
let lastStageProgress = 0;

// Helper to update progress bar based on log output
function updateProgressBar(text) {
  // Analyze text to determine stage and progress

  // Detect total songs
  const totalSongsMatch = text.match(/Processing your top (\d+) songs/);
  if (totalSongsMatch && totalSongsMatch[1]) {
    totalSongs = parseInt(totalSongsMatch[1]);
    processStage = "init";
    currentSong = 0;
    lastStageProgress = 5; // Start at 5%
    progressBar.style.width = "5%";
    debugLog(`Total songs: ${totalSongs}`);
  }

  // Detect song fetching stage
  if (
    text.includes("Fetching page") ||
    text.includes("Fetching from Last.fm")
  ) {
    processStage = "fetching";
    lastStageProgress = 10;
    progressBar.style.width = "10%";
    progressStatus.textContent = "Fetching data from Last.fm...";
  }

  // Detect song processing stage
  const songMatch = text.match(/Processing (\d+)\/(\d+):/);
  if (songMatch && songMatch[1] && songMatch[2]) {
    const songNumber = parseInt(songMatch[1]);
    currentSong = songNumber;

    // Only update if this is a new song
    if (processStage !== "processing" || songNumber !== currentSong) {
      processStage = "processing";

      // Calculate progress - allocate 85% to song processing (from 10% to 95%)
      // Each song gets an equal portion
      const songProgress = 10 + ((songNumber - 1) / totalSongs) * 85;
      lastStageProgress = songProgress;
      progressBar.style.width = `${songProgress}%`;
      progressStatus.textContent = `Processing song ${songNumber}/${totalSongs}`;
      debugLog(
        `Processing song ${songNumber}/${totalSongs}, progress: ${songProgress.toFixed(
          1
        )}%`
      );
    }
  }

  // Handle download progress indicators
  if (text.includes("[download]")) {
    // We're still in the current song's download stage
    // Just update status text, not the main progress bar
    const downloadMatch = text.match(/download\] (\d+\.\d+)% of/);
    if (downloadMatch && downloadMatch[1]) {
      const downloadPercent = parseFloat(downloadMatch[1]);
      progressStatus.textContent = `Song ${currentSong}/${totalSongs}: Downloading ${downloadPercent.toFixed(
        1
      )}%`;
    }
  }

  // Detect merging stage
  if (text.includes("Merging")) {
    processStage = "merging";
    lastStageProgress = 95;
    progressBar.style.width = "95%";
    progressStatus.textContent = "Creating final video...";

    // Set to 100% when complete
    if (
      text.includes("Video compilation complete") ||
      text.includes("Final video saved") ||
      text.includes("✨ Video compilation complete") ||
      text.includes("✨ Final video saved")
    ) {
      processStage = "complete";
      lastStageProgress = 100;
      progressBar.style.width = "100%";
      progressStatus.textContent = "Complete!";
    }
  }
}

// Helper function to find the song info being replaced
function findReplacingSongInfo(data) {
  // Look for recently mentioned song in the logs
  const lines = outputLog.textContent.split("\n");
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    if (line.includes("🔄 Replacing:")) {
      return line.replace("🔄 Replacing:", "").trim();
    }
  }
  return null;
}

// Save API keys to localStorage
function saveApiKeys() {
  debugLog("Saving API keys to localStorage");
  localStorage.setItem("lastfm-api-key", lastfmApiKeyInput.value);
  localStorage.setItem("youtube-api-key", youtubeApiKeyInput.value);
}

// Load API keys from localStorage
function loadApiKeys() {
  debugLog("Loading API keys from localStorage");
  const lastfmKey = localStorage.getItem("lastfm-api-key") || "";
  const youtubeKey = localStorage.getItem("youtube-api-key") || "";

  if (lastfmApiKeyInput) lastfmApiKeyInput.value = lastfmKey;
  if (youtubeApiKeyInput) youtubeApiKeyInput.value = youtubeKey;
}

// Load all saved data from localStorage
function loadSavedData() {
  debugLog("Loading saved data from localStorage");
  try {
    // Load API keys
    loadApiKeys();

    // Load other saved settings
    const username = localStorage.getItem("lastfm-username") || "";

    const allowManualSaved = localStorage.getItem("allow-manual-youtube");
    const allowManual =
      allowManualSaved === null ? false : allowManualSaved === "true";

    const usernameInput = document.getElementById("lastfm-username");
    const allowManualCheckbox = document.getElementById("allow-manual-youtube");

    if (usernameInput) usernameInput.value = username;
    if (allowManualCheckbox) allowManualCheckbox.checked = allowManual;

    debugLog("Saved data loaded successfully");
  } catch (error) {
    console.error("Error loading saved config:", error);
  }
}

// Save username and other settings when form is submitted
if (configForm) {
  configForm.addEventListener("submit", () => {
    try {
      const usernameInput = document.getElementById("lastfm-username");
      const allowManualCheckbox = document.getElementById(
        "allow-manual-youtube"
      );

      if (usernameInput) {
        localStorage.setItem("lastfm-username", usernameInput.value);
      }

      if (allowManualCheckbox) {
        localStorage.setItem(
          "allow-manual-youtube",
          allowManualCheckbox.checked
        );
      }

      debugLog("User settings saved to localStorage");
    } catch (error) {
      console.error("Error saving config:", error);
    }
  });
}

// Log that the renderer script has loaded
debugLog("Renderer script loaded successfully");
