/**
 * Storage utilities - Guest session management
 */

const GUEST_STORAGE_KEY = 'youtube_clone_guest_id';

export const guestStorage = {
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
};

export default guestStorage;
