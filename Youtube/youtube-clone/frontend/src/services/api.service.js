/**
 * Base API Service - HTTP client wrapper
 */

import { API_BASE_URL } from "../config";
import { formatDateTimeForTimezone, formatTimeAgo } from "../utils";

function normalizeTimestamps(payload) {
  if (Array.isArray(payload)) {
    return payload.map(normalizeTimestamps);
  }

  if (!payload || typeof payload !== "object") {
    return payload;
  }

  const normalized = {};
  for (const [key, value] of Object.entries(payload)) {
    normalized[key] = normalizeTimestamps(value);
  }

  if (
    typeof normalized.publish_time_raw === "string" &&
    normalized.publish_time_raw.trim()
  ) {
    normalized.timestamp = formatTimeAgo(normalized.publish_time_raw);
  }

  if (
    typeof normalized.started_at === "string" &&
    normalized.started_at.trim()
  ) {
    normalized.started_at_local = formatDateTimeForTimezone(
      normalized.started_at,
      { mode: "client" },
    );
    normalized.started_at_gmt6 = formatDateTimeForTimezone(
      normalized.started_at,
      { mode: "gmt+6" },
    );
  }

  if (typeof normalized.ended_at === "string" && normalized.ended_at.trim()) {
    normalized.ended_at_local = formatDateTimeForTimezone(normalized.ended_at, {
      mode: "client",
    });
    normalized.ended_at_gmt6 = formatDateTimeForTimezone(normalized.ended_at, {
      mode: "gmt+6",
    });
  }

  return normalized;
}

class ApiService {
  constructor(baseURL = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;

    const config = {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    };

    const response = await fetch(url, config);

    if (!response.ok) {
      let errorDetail = response.statusText;
      try {
        const errBody = await response.json();
        errorDetail = errBody.detail || errorDetail;
      } catch {
        // Ignore JSON parse errors for non-JSON error responses
      }
      throw new Error(`API ${response.status}: ${errorDetail}`);
    }

    // Return parsed JSON (or null for 204 No Content)
    if (response.status === 204) return null;
    const data = await response.json();
    return normalizeTimestamps(data);
  }

  async get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: "GET" });
  }

  async post(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async put(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async delete(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: "DELETE",
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
