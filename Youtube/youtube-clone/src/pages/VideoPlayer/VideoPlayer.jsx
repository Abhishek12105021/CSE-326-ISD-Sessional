import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  AiOutlineLike,
  AiOutlineDislike,
  AiFillLike,
} from "react-icons/ai";
import {
  RiShareForwardLine,
  RiScissorsFill,
  RiDownloadLine,
} from "react-icons/ri";
import {
  BsThreeDots,
  BsPlayFill,
  BsSortDown,
} from "react-icons/bs";
import { MdVerified } from "react-icons/md";
import { BiChevronDown } from "react-icons/bi";
import { videos, comments } from "../../data/sampleData";
import "./VideoPlayer.css";

const VideoPlayer = () => {
  const { id } = useParams();
  const video = videos.find((v) => v.id === id) || videos[0];
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLiked, setIsLiked] = useState(false);
  const [showFullDescription, setShowFullDescription] = useState(false);
  const [expandedReplies, setExpandedReplies] = useState({});

  const recommendedVideos = videos.filter((v) => v.id !== id).slice(0, 10);

  const toggleReplies = (commentId) => {
    setExpandedReplies((prev) => ({
      ...prev,
      [commentId]: !prev[commentId],
    }));
  };

  return (
    <div className="video-player-page">
      {/* Primary Column */}
      <div className="video-player-page__primary">
        {/* Video Player */}
        <div className="video-player__player-container">
          <img src={video.thumbnail} alt={video.title} />
          <div className="video-player__play-overlay">
            <BsPlayFill />
          </div>
        </div>
        <div className="video-player__progress-bar">
          <div className="video-player__progress" />
        </div>

        {/* Video Info */}
        <div className="video-player__info">
          <h1 className="video-player__title">{video.title}</h1>

          <div className="video-player__actions-row">
            {/* Channel Info */}
            <div className="video-player__channel-info">
              <Link to={`/channel/${video.channel.id}`}>
                <img
                  className="video-player__channel-avatar"
                  src={video.channel.avatar}
                  alt={video.channel.name}
                />
              </Link>
              <div className="video-player__channel-text">
                <Link
                  to={`/channel/${video.channel.id}`}
                  className="video-player__channel-name"
                >
                  {video.channel.name}
                  {video.channel.verified && <MdVerified style={{ color: "#606060" }} />}
                </Link>
                <span className="video-player__channel-subs">
                  {video.channel.subscribers} subscribers
                </span>
              </div>
              <button
                className={`video-player__subscribe-btn ${
                  isSubscribed ? "video-player__subscribe-btn--subscribed" : ""
                }`}
                onClick={() => setIsSubscribed(!isSubscribed)}
              >
                {isSubscribed ? "Subscribed" : "Subscribe"}
              </button>
            </div>

            {/* Action Buttons */}
            <div className="video-player__action-buttons">
              <div className="video-player__action-btn--like-dislike">
                <button
                  className="video-player__like-btn"
                  onClick={() => setIsLiked(!isLiked)}
                >
                  {isLiked ? <AiFillLike /> : <AiOutlineLike />}
                  {video.likes}
                </button>
                <button className="video-player__dislike-btn">
                  <AiOutlineDislike />
                </button>
              </div>
              <button className="video-player__action-btn">
                <RiShareForwardLine /> Share
              </button>
              <button className="video-player__action-btn">
                <RiDownloadLine /> Download
              </button>
              <button className="video-player__action-btn">
                <RiScissorsFill /> Clip
              </button>
              <button className="video-player__action-btn" style={{ padding: "8px 12px" }}>
                <BsThreeDots />
              </button>
            </div>
          </div>
        </div>

        {/* Description */}
        <div
          className="video-player__description"
          onClick={() => setShowFullDescription(!showFullDescription)}
        >
          <div className="video-player__description-meta">
            <span>{video.views}</span>
            <span>{video.timestamp}</span>
          </div>
          <p
            className={`video-player__description-text ${
              !showFullDescription
                ? "video-player__description-text--collapsed"
                : ""
            }`}
          >
            {video.description}
          </p>
          <p className="video-player__show-more">
            {showFullDescription ? "Show less" : "...more"}
          </p>
        </div>

        {/* Comments Section */}
        <div className="comments-section">
          <div className="comments-section__header">
            <span className="comments-section__count">
              {comments.length} Comments
            </span>
            <button className="comments-section__sort">
              <BsSortDown /> Sort by
            </button>
          </div>

          {/* Comment Input */}
          <div className="comment-input">
            <img
              className="comment-input__avatar"
              src="https://ui-avatars.com/api/?name=MK&background=8B5CF6&color=fff&size=40"
              alt="Your avatar"
            />
            <input
              className="comment-input__field"
              placeholder="Add a comment..."
            />
          </div>

          {/* Comments */}
          {comments.map((comment) => (
            <div key={comment.id}>
              <div className="comment">
                <img
                  className="comment__avatar"
                  src={comment.avatar}
                  alt={comment.user}
                />
                <div className="comment__content">
                  <div className="comment__header">
                    <span className="comment__author">@{comment.user}</span>
                    <span className="comment__time">{comment.timestamp}</span>
                  </div>
                  <p className="comment__text">{comment.text}</p>
                  <div className="comment__actions">
                    <button className="comment__action-btn">
                      <AiOutlineLike /> {comment.likes}
                    </button>
                    <button className="comment__action-btn">
                      <AiOutlineDislike />
                    </button>
                    <button className="comment__action-btn">Reply</button>
                  </div>
                  {comment.replies?.length > 0 && (
                    <button
                      className="comment__replies-toggle"
                      onClick={() => toggleReplies(comment.id)}
                    >
                      <BiChevronDown />
                      {comment.replies.length}{" "}
                      {comment.replies.length === 1 ? "reply" : "replies"}
                    </button>
                  )}
                </div>
              </div>
              {expandedReplies[comment.id] &&
                comment.replies?.map((reply) => (
                  <div className="comment__replies" key={reply.id}>
                    <div className="comment">
                      <img
                        className="comment__avatar"
                        src={reply.avatar}
                        alt={reply.user}
                        style={{ width: 24, height: 24 }}
                      />
                      <div className="comment__content">
                        <div className="comment__header">
                          <span className="comment__author">@{reply.user}</span>
                          <span className="comment__time">
                            {reply.timestamp}
                          </span>
                        </div>
                        <p className="comment__text">{reply.text}</p>
                        <div className="comment__actions">
                          <button className="comment__action-btn">
                            <AiOutlineLike /> {reply.likes}
                          </button>
                          <button className="comment__action-btn">
                            <AiOutlineDislike />
                          </button>
                          <button className="comment__action-btn">Reply</button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          ))}
        </div>
      </div>

      {/* Secondary Column - Recommendations */}
      <div className="video-player-page__secondary">
        {recommendedVideos.map((rec) => (
          <Link
            key={rec.id}
            to={`/video/${rec.id}`}
            className="recommendation-card"
          >
            <div className="recommendation-card__thumbnail-container">
              <img
                className="recommendation-card__thumbnail"
                src={rec.thumbnail}
                alt={rec.title}
                loading="lazy"
              />
              <span className="recommendation-card__duration">
                {rec.duration}
              </span>
            </div>
            <div className="recommendation-card__info">
              <h4 className="recommendation-card__title">{rec.title}</h4>
              <span className="recommendation-card__channel-name">
                {rec.channel.name}
                {rec.channel.verified && (
                  <MdVerified style={{ fontSize: 14 }} />
                )}
              </span>
              <div className="recommendation-card__meta">
                <span>{rec.views}</span>
                <span>{rec.timestamp}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default VideoPlayer;
