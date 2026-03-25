/**
 * Guest Service - Guest session management API calls
 */

import { apiService } from './api.service';
import { API_ENDPOINTS } from '../config';

export const guestService = {
  async createSession(guestUuid, options = {}) {
    const response = await apiService.post(API_ENDPOINTS.GUEST_SESSION, {
      guest_uuid: guestUuid,
      region: options.region,
      language: options.language,
      device_type: options.device_type,
    });
    return response.json();
  },

  async updateSession(guestUuid, updates) {
    const response = await apiService.post(API_ENDPOINTS.GUEST_SESSION, {
      guest_uuid: guestUuid,
      ...updates,
    });
    return response.json();
  },

  async getSession(guestUuid) {
    const response = await apiService.get(`${API_ENDPOINTS.GUEST_SESSION}/${guestUuid}`);
    if (!response.ok) {
      return null;
    }
    return response.json();
  },

  async addToHistory(guestUuid, videoId) {
    const response = await apiService.post(API_ENDPOINTS.GUEST_HISTORY, {
      guest_uuid: guestUuid,
      video_id: videoId,
    });
    return response.json();
  },

  async getHistory(guestUuid) {
    const response = await apiService.get(`${API_ENDPOINTS.GUEST_HISTORY}/${guestUuid}`);
    if (!response.ok) {
      return [];
    }
    return response.json();
  },
};

export default guestService;
