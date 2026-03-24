import React from "react";
import { Link } from "react-router-dom";
import { MdVerified } from "react-icons/md";
import "./VideoCard.css";

const VideoCard = ({ video }) => {
  return (
    <div className="video-card">
      <Link to={`/video/${video.id}`}>
        <div className="video-card__thumbnail-container">
          <img
            className="video-card__thumbnail"
            src={video.thumbnail}
            alt={video.title}
            loading="lazy"
          />
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
          <img
            className="video-card__avatar"
            src={video.channel.avatar}
            alt={video.channel.name}
          />
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
