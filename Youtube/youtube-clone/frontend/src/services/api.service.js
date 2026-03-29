/**
 * Base API Service - HTTP client wrapper
 */

import { API_BASE_URL } from '../config';

class ApiService {
  constructor(baseURL = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;

    const config = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    const response = await fetch(url, config);

    if (!response.ok) {
      let errorDetail = response.statusText;
      try {
        const errBody = await response.json();
        errorDetail = errBody.detail || errorDetail;
      } catch (_) {}
      throw new Error(`API ${response.status}: ${errorDetail}`);
    }

    // Return parsed JSON (or null for 204 No Content)
    if (response.status === 204) return null;
    return response.json();
  }

  async get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  async post(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'DELETE',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  // Create authenticated request with token
  withAuth(token) {
    return {
      get: (endpoint, options = {}) =>
        this.get(endpoint, {
          ...options,
          headers: { ...options.headers, Authorization: `Bearer ${token}` },
        }),
      post: (endpoint, data, options = {}) =>
        this.post(endpoint, data, {
          ...options,
          headers: { ...options.headers, Authorization: `Bearer ${token}` },
        }),
      put: (endpoint, data, options = {}) =>
        this.put(endpoint, data, {
          ...options,
          headers: { ...options.headers, Authorization: `Bearer ${token}` },
        }),
      delete: (endpoint, data, options = {}) =>
        this.delete(endpoint, data, {
          ...options,
          headers: { ...options.headers, Authorization: `Bearer ${token}` },
        }),
    };
  }
}

export const apiService = new ApiService();
export default ApiService;
