/**
 * Auth Service - Authentication-related API calls
 */

import { apiService } from './api.service';
import { API_ENDPOINTS } from '../config';

export const authService = {
  async getProfile(token) {
    const response = await apiService.withAuth(token).get(API_ENDPOINTS.AUTH_PROFILE);
    if (!response.ok) {
      throw new Error('Failed to fetch profile');
    }
    return response.json();
  },

  async updateProfile(token, updates) {
    const response = await apiService.withAuth(token).put(API_ENDPOINTS.AUTH_PROFILE, updates);
    if (!response.ok) {
      throw new Error('Failed to update profile');
    }
    return response.json();
  },

  async migrateGuestData(token, guestUuid) {
    const response = await apiService.withAuth(token).post(API_ENDPOINTS.AUTH_MIGRATE_GUEST, {
      guest_uuid: guestUuid,
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Migration failed');
    }
    return response.json();
  },

  async logout(token) {
    const response = await apiService.withAuth(token).post(API_ENDPOINTS.AUTH_LOGOUT, {});
    return response.json();
  },

  async logoutAll(token) {
    const response = await apiService.withAuth(token).post(API_ENDPOINTS.AUTH_LOGOUT_ALL, {});
    return response.json();
  },
};

export default authService;
