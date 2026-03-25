/**
 * Storage utilities - Guest session management (localStorage-based)
 */

const GUEST_STORAGE_KEY = 'youtube_clone_guest_id';
const REGION_STORAGE_KEY = 'youtube_clone_region';
const WATCH_HISTORY_KEY = 'youtube_clone_watch_history';
const DEFAULT_REGION = 'US';
const MAX_HISTORY_ITEMS = 100;

export const guestStorage = {
  // Guest ID management
  getGuestId() {
    let guestId = localStorage.getItem(GUEST_STORAGE_KEY);
    if (!guestId) {
      guestId = crypto.randomUUID();
      localStorage.setItem(GUEST_STORAGE_KEY, guestId);
    }
    return guestId;
  },

  clearGuestId() {
    localStorage.removeItem(GUEST_STORAGE_KEY);
  },

  hasGuestId() {
    return !!localStorage.getItem(GUEST_STORAGE_KEY);
  },

  getRawGuestId() {
    return localStorage.getItem(GUEST_STORAGE_KEY);
  },

  // Region management
  getRegion() {
    return localStorage.getItem(REGION_STORAGE_KEY) || DEFAULT_REGION;
  },

  setRegion(region) {
    localStorage.setItem(REGION_STORAGE_KEY, region);
  },

  // Watch history management
  getWatchHistory() {
    try {
      const history = localStorage.getItem(WATCH_HISTORY_KEY);
      return history ? JSON.parse(history) : [];
    } catch {
      return [];
    }
  },

  addToWatchHistory(video) {
    const history = this.getWatchHistory();

    // Remove if already exists (to move to top)
    const filtered = history.filter(v => v.videoId !== video.videoId);

    // Add to beginning
    const newHistory = [
      {
        videoId: video.videoId,
        title: video.title,
        channelName: video.channelName,
        thumbnail: video.thumbnail,
        watchedAt: new Date().toISOString(),
        watchDuration: video.watchDuration || 0,
      },
      ...filtered
    ].slice(0, MAX_HISTORY_ITEMS); // Keep only last 100 items

    localStorage.setItem(WATCH_HISTORY_KEY, JSON.stringify(newHistory));
    return newHistory;
  },

  removeFromWatchHistory(videoId) {
    const history = this.getWatchHistory();
    const filtered = history.filter(v => v.videoId !== videoId);
    localStorage.setItem(WATCH_HISTORY_KEY, JSON.stringify(filtered));
    return filtered;
  },

  clearWatchHistory() {
    localStorage.removeItem(WATCH_HISTORY_KEY);
  },

  // Clear all guest data
  clearAllGuestData() {
    localStorage.removeItem(GUEST_STORAGE_KEY);
    localStorage.removeItem(REGION_STORAGE_KEY);
    localStorage.removeItem(WATCH_HISTORY_KEY);
  },
};

export default guestStorage;
