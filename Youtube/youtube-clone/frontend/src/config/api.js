/**
 * API Configuration
 */

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  // Auth
  AUTH_PROFILE: '/api/auth/profile',
  AUTH_LOGOUT: '/api/auth/logout',
  AUTH_LOGOUT_ALL: '/api/auth/logout-all',

  // Guest
  GUEST_SESSION: '/api/guest/session',
  GUEST_FEED: '/api/guest/feed',
  GUEST_WATCH: '/api/guest/watch',

  // Feed
  FEED: '/api/feed',
  TRENDING: '/api/trending',
  CATEGORIES: '/api/categories',

  // Health
  HEALTH: '/health',
};
