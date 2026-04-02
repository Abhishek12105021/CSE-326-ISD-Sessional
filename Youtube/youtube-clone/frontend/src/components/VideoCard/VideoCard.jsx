import React, { useState } from "react";
import { Link } from "react-router-dom";
import { MdVerified } from "react-icons/md";
import "./VideoCard.css";

const VideoCard = ({ video }) => {
  const [thumbnailError, setThumbnailError] = useState(false);
  const [currentThumbnailQuality, setCurrentThumbnailQuality] = useState(0);

  // Try multiple quality levels with fallback
  const getThumbnailWithFallback = (thumbnailUrl) => {
    if (!thumbnailUrl) return null;
    
    // Quality levels to try (from best to worst)
    const qualityLevels = [
      "/maxresdefault.jpg",
      "/sddefault.jpg",
      "/hqdefault.jpg",
      "/mqdefault.jpg",
      "/default.jpg",
    ];

    // Extract base URL (everything before the quality suffix)
    const baseUrl = thumbnailUrl.replace(
      /\/(default|mqdefault|hqdefault|sddefault|maxresdefault)\.jpg$/,
      ""
    );

    return baseUrl + qualityLevels[currentThumbnailQuality];
  };

  const handleThumbnailError = () => {
    if (currentThumbnailQuality < 4) {
      // Try next lower quality
      setCurrentThumbnailQuality(currentThumbnailQuality + 1);
    } else {
      // All quality levels exhausted
      setThumbnailError(true);
    }
  };

  // Generate a unique color based on channel name
  const generateColorHash = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    // Modern gradient colors
    const colors = [
      ["#FF6B6B", "#FFE66D"],
      ["#4ECDC4", "#44A08D"],
      ["#95E1D3", "#38A169"],
      ["#FA8072", "#FFB347"],
      ["#87CEEB", "#4169E1"],
      ["#DDA0DD", "#BA55D3"],
      ["#20B2AA", "#00CED1"],
      ["#FF69B4", "#FF1493"],
    ];
    return colors[Math.abs(hash) % colors.length];
  };

  // Get channel initials
  const getInitials = (name) => {
    return name
      .split(" ")
      .map((word) => word[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const colors = generateColorHash(video.channel.name);
  const initials = getInitials(video.channel.name);
  const thumbnailUrl = getThumbnailWithFallback(video.thumbnail);

  return (
    <div className="video-card">
      <Link to={`/video/${video.id}`}>
        <div className="video-card__thumbnail-container">
          {!thumbnailError ? (
            <img
              className="video-card__thumbnail"
              src={thumbnailUrl}
              alt={video.title}
              loading="lazy"
              onError={handleThumbnailError}
            />
          ) : (
            <div className="video-card__thumbnail-placeholder">
              <span className="video-card__thumbnail-placeholder-text">
                No Thumbnail
              </span>
            </div>
          )}
          <span
            className={`video-card__duration ${
              video.duration === "LIVE" ? "video-card__duration--live" : ""
            }`}
          >
            {video.duration}
          </span>
        </div>
      </Link>
      <div className="video-card__info">
        <Link to={`/channel/${video.channel.id}`}>
          <div
            className="video-card__avatar-fallback"
            style={{
              background: `linear-gradient(135deg, ${colors[0]} 0%, ${colors[1]} 100%)`,
            }}
          >
            <span className="video-card__avatar-initials">{initials}</span>
          </div>
        </Link>
        <div className="video-card__details">
          <Link to={`/video/${video.id}`} style={{ textDecoration: "none" }}>
            <h3 className="video-card__title">{video.title}</h3>
          </Link>
          <Link
            to={`/channel/${video.channel.id}`}
            className="video-card__channel"
            style={{ textDecoration: "none" }}
          >
            {video.channel.name}
            {video.channel.verified && (
              <MdVerified className="video-card__verified" />
            )}
          </Link>
          <div className="video-card__meta">
            <span>{video.views}</span>
            <span>{video.timestamp}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoCard;
