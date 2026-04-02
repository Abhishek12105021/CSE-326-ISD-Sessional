/**
 * Format utilities for views, dates, etc.
 */

export function formatViewCount(views) {
  if (typeof views === "string") {
    return views; // Already formatted
  }

  if (views >= 1000000000) {
    return `${(views / 1000000000).toFixed(1)}B views`;
  }
  if (views >= 1000000) {
    return `${(views / 1000000).toFixed(1)}M views`;
  }
  if (views >= 1000) {
    return `${(views / 1000).toFixed(1)}K views`;
  }
  return `${views} views`;
}

export function formatSubscriberCount(count) {
  if (typeof count === "string") {
    return count;
  }

  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M subscribers`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K subscribers`;
  }
  return `${count} subscribers`;
}

export function formatDuration(seconds) {
  if (typeof seconds === "string") {
    return seconds;
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

function parseUtcDate(dateInput) {
  if (!dateInput) return null;
  if (dateInput instanceof Date) return dateInput;
  if (typeof dateInput !== "string") return new Date(dateInput);

  const value = dateInput.trim();
  // Treat timezone-less ISO values from DB as UTC to avoid local-time misinterpretation.
  const isIsoWithoutTimezone =
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value);
  const normalized = isIsoWithoutTimezone ? `${value}Z` : value;

  return new Date(normalized);
}

export function formatTimeAgo(dateInput, nowInput = new Date()) {
  if (!dateInput) return "";

  const now = nowInput instanceof Date ? nowInput : new Date(nowInput);
  const past = parseUtcDate(dateInput);
  if (!past) return "";

  // If input is already pre-formatted text (or invalid), keep it unchanged.
  if (Number.isNaN(past.getTime())) {
    return typeof dateInput === "string" ? dateInput : "";
  }

  const diffInSeconds = Math.floor((now.getTime() - past.getTime()) / 1000);
  if (diffInSeconds <= 0) return "just now";

  if (diffInSeconds < 60) {
    return "just now";
  }

  if (diffInSeconds < 3600) {
    const minutes = Math.floor(diffInSeconds / 60);
    return `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`;
  }

  if (diffInSeconds < 86400) {
    const hours = Math.floor(diffInSeconds / 3600);
    return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  }

  const diffInDays = Math.floor(diffInSeconds / 86400);
  if (diffInDays < 7) {
    return `${diffInDays} ${diffInDays === 1 ? "day" : "days"} ago`;
  }

  if (diffInDays < 30) {
    const weeks = Math.floor(diffInDays / 7);
    return `${weeks} ${weeks === 1 ? "week" : "weeks"} ago`;
  }

  let months =
    (now.getUTCFullYear() - past.getUTCFullYear()) * 12 +
    (now.getUTCMonth() - past.getUTCMonth());
  if (now.getUTCDate() < past.getUTCDate()) {
    months -= 1;
  }
  months = Math.max(1, months);

  if (months < 12) {
    return `${months} ${months === 1 ? "month" : "months"} ago`;
  }

  const years = Math.floor(months / 12);
  return `${years} ${years === 1 ? "year" : "years"} ago`;
}

export function formatDateTimeForTimezone(
  dateInput,
  { mode = "client", locale } = {},
) {
  if (!dateInput) return "";

  const utcDate = parseUtcDate(dateInput);
  if (!utcDate || Number.isNaN(utcDate.getTime())) {
    return typeof dateInput === "string" ? dateInput : "";
  }

  const formatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  };

  if (mode === "gmt+6") {
    return new Intl.DateTimeFormat(locale, {
      ...formatOptions,
      timeZone: "Asia/Dhaka",
    }).format(utcDate);
  }

  return new Intl.DateTimeFormat(locale, formatOptions).format(utcDate);
}
