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
    GUEST_RELOAD: '/api/guest/reload',
    GUEST_WATCH: '/api/guest/watch',

    // Feed
    FEED: '/api/feed',
    FEED_RELOAD: '/api/reload',
    TRENDING: '/api/trending',
    CATEGORIES: '/api/categories',

    // Video
    VIDEO_GET: '/api/get',
    WATCH: '/api/watch',
    WATCH_HISTORY: '/api/watch-history',

    // Likes / Dislikes
    LIKE: '/api/like',
    LIKES: '/api/likes',
    DISLIKE: '/api/dislike',

    // Subscriptions
    SUBSCRIBE: '/api/subscribe',
    SUBSCRIPTIONS: '/api/subscriptions',
    CHANNELS: '/api/channels',

    // Search
    SEARCH: '/api/search',
    SEARCH_RELOAD: '/api/reload-search',

    // Recommendations
    RECOMMEND: '/api/recommend',
    RECOMMEND_RELOAD: '/api/reload-recommend',

    // Health
    HEALTH: '/health',
};
