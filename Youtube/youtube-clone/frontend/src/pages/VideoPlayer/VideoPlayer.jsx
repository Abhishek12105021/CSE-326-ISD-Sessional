import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import {
  AiOutlineLike,
  AiOutlineDislike,
  AiFillLike,
  AiFillDislike,
} from "react-icons/ai";
import {
  RiShareForwardLine,
  RiScissorsFill,
  RiDownloadLine,
} from "react-icons/ri";
import { BsThreeDots, BsSortDown } from "react-icons/bs";
import { MdVerified } from "react-icons/md";
import { BiChevronDown } from "react-icons/bi";
import { comments } from "../../data/sampleData";
import { useAuth } from "../../context";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import { guestStorage } from "../../utils";
import "./VideoPlayer.css";

const VideoPlayer = () => {
  const { id } = useParams(); // UUID
  const { isAuthenticated, session, guestId } = useAuth();

  const [video, setVideo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recommendations, setRecommendations] = useState([]);
  const [loadingMoreRecs, setLoadingMoreRecs] = useState(false);
  const [hasMoreRecs, setHasMoreRecs] = useState(true);
  const [isLiked, setIsLiked] = useState(false);
  const [isDisliked, setIsDisliked] = useState(false);
  const [likeCount, setLikeCount] = useState(0);
  const [dislikeCount, setDislikeCount] = useState(0);
  const [reactionPending, setReactionPending] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [showFullDescription, setShowFullDescription] = useState(false);
  const [expandedReplies, setExpandedReplies] = useState({});

  // watchId: null = not started | 'pending' = INSERT in flight | uuid = INSERT done
  // watchVideoId: tracks which video the current watchId belongs to (guards fast navigation)
  const watchId = useRef(null);
  const watchVideoId = useRef(null);
  const watchStartTime = useRef(Date.now());
  const shownRecIds = useRef(new Set());

  // Refs so cleanup always reads fresh auth state (avoids stale closures)
  const sessionRef = useRef(session);
  const isAuthRef = useRef(isAuthenticated);
  const guestIdRef = useRef(guestId);
  useEffect(() => {
    sessionRef.current = session;
    isAuthRef.current = isAuthenticated;
    guestIdRef.current = guestId;
  });

  const authClient =
    isAuthenticated && session?.access_token
      ? apiService.withAuth(session.access_token)
      : null;

  // Fetch video metadata
  useEffect(() => {
    setLoading(true);
    setVideo(null);
    apiService
      .post(API_ENDPOINTS.VIDEO_GET, { video_uuid: id })
      .then((data) => {
        setVideo(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("[VideoPlayer] Failed to fetch video:", err);
        setLoading(false);
      });
  }, [id]);

  // Initialize reaction counters from fetched video metadata.
  useEffect(() => {
    if (!video) {
      setLikeCount(0);
      setDislikeCount(0);
      return;
    }

    setLikeCount(Number(video.likes) || 0);
    setDislikeCount(Number(video.dislikes) || 0);
  }, [video]);

  // Watch tracking: INSERT on video start, UPDATE on leave.
  //
  // WHY 'pending' sentinel:
  //   React StrictMode mounts → cleanups → remounts effects synchronously.
  //   The INSERT is async (fetch), so it hasn't resolved yet when StrictMode's
  //   cleanup fires. Without the sentinel, Mount 2 sees watchId=null and fires
  //   a second INSERT → two rows in the DB.
  //
  //   By setting watchId='pending' SYNCHRONOUSLY before the async call:
  //   - Mount 1 sets 'pending', starts INSERT async
  //   - StrictMode cleanup sees 'pending' → skips UPDATE (INSERT not done yet)
  //   - Mount 2 sees watchVideoId===id && watchId!==null → skips INSERT entirely
  //   - INSERT resolves → watchId = real uuid
  //   - Real navigation cleanup → watchId is real uuid → sends UPDATE ✓
  useEffect(() => {
    if (!id) return;

    // StrictMode re-mount guard: INSERT already initiated for THIS video — skip
    if (watchVideoId.current === id && watchId.current !== null) {
      return () => {
        const duration = Math.floor(
          (Date.now() - watchStartTime.current) / 1000,
        );
        // Always update localStorage for guest users — independent of INSERT state
        if (!isAuthRef.current) {
          guestStorage.updateWatchDuration(id, duration);
        }
        // Only send backend UPDATE if INSERT has resolved (watch_id is a real uuid)
        if (!watchId.current || watchId.current === "pending") return;
        const payload = {
          video_uuid: id,
          watch_id: watchId.current,
          watch_duration_seconds: duration,
        };
        if (isAuthRef.current && sessionRef.current?.access_token) {
          apiService
            .withAuth(sessionRef.current.access_token)
            .post(API_ENDPOINTS.WATCH, payload)
            .catch(() => {});
        } else {
          apiService
            .post(API_ENDPOINTS.GUEST_WATCH, {
              ...payload,
              guest_uuid: guestIdRef.current,
            })
            .catch(() => {});
        }
        watchId.current = null;
        watchVideoId.current = null;
        localStorage.removeItem("yt_current_watch");
      };
    }

    // New video — set sentinel SYNCHRONOUSLY before async INSERT
    watchVideoId.current = id;
    watchId.current = "pending";
    watchStartTime.current = Date.now();

    (async () => {
      try {
        let data;
        if (isAuthRef.current && sessionRef.current?.access_token) {
          data = await apiService
            .withAuth(sessionRef.current.access_token)
            .post(API_ENDPOINTS.WATCH, { video_uuid: id });
        } else {
          data = await apiService.post(API_ENDPOINTS.GUEST_WATCH, {
            video_uuid: id,
            guest_uuid: guestIdRef.current,
          });
        }
        // Guard: only commit if user hasn't already navigated to a different video
        if (watchVideoId.current === id) {
          watchId.current = data?.watch_id ?? null;
          localStorage.setItem(
            "yt_current_watch",
            JSON.stringify({
              videoId: id,
              watch_id: data?.watch_id,
              startTime: watchStartTime.current,
            }),
          );
        }
      } catch (err) {
        console.error("[VideoPlayer] Watch insert failed:", err);
        if (watchVideoId.current === id) watchId.current = null;
      }
    })();

    return () => {
      const duration = Math.floor((Date.now() - watchStartTime.current) / 1000);
      // Always update localStorage for guest users — independent of INSERT state
      if (!isAuthRef.current) {
        guestStorage.updateWatchDuration(id, duration);
      }
      // Only send backend UPDATE if INSERT has resolved (watch_id is a real uuid)
      if (!watchId.current || watchId.current === "pending") return;
      const payload = {
        video_uuid: id,
        watch_id: watchId.current,
        watch_duration_seconds: duration,
      };
      if (isAuthRef.current && sessionRef.current?.access_token) {
        apiService
          .withAuth(sessionRef.current.access_token)
          .post(API_ENDPOINTS.WATCH, payload)
          .catch(() => {});
      } else {
        apiService
          .post(API_ENDPOINTS.GUEST_WATCH, {
            ...payload,
            guest_uuid: guestIdRef.current,
          })
          .catch(() => {});
      }
      watchId.current = null;
      watchVideoId.current = null;
      localStorage.removeItem("yt_current_watch");
    };
  }, [id]);

  // Guest-only: save to localStorage watch history for feed personalization
  // Authenticated users' history is tracked server-side via the watch endpoint
  useEffect(() => {
    if (!video || isAuthenticated) return;
    guestStorage.addToWatchHistory({
      videoId: id,
      title: video.title,
      channelName: video.channel?.name,
      thumbnail: video.thumbnail,
    });
  }, [video, id, isAuthenticated]);

  // Fetch recommendations
  useEffect(() => {
    if (!id) return;
    shownRecIds.current = new Set([id]);
    apiService
      .post(`${API_ENDPOINTS.RECOMMEND}?video_id=${id}&limit=15`)
      .then((data) => {
        const recs = data?.videos || [];
        recs.forEach((v) => shownRecIds.current.add(v.id));
        setRecommendations(recs);
        setHasMoreRecs(recs.length >= 15);
      })
      .catch((err) =>
        console.error("[VideoPlayer] Recommendations failed:", err),
      );
  }, [id]);

  // Load more recommendations on sidebar scroll
  const loadMoreRecs = useCallback(async () => {
    if (loadingMoreRecs || !hasMoreRecs) return;
    setLoadingMoreRecs(true);
    try {
      const data = await apiService.post(API_ENDPOINTS.RECOMMEND_RELOAD, {
        video_id: id,
        excluded_video_ids: Array.from(shownRecIds.current),
        limit: 15,
      });
      const recs = data?.videos || [];
      recs.forEach((v) => shownRecIds.current.add(v.id));
      setRecommendations((prev) => [...prev, ...recs]);
      setHasMoreRecs(recs.length >= 15);
    } catch (err) {
      console.error("[VideoPlayer] Load more recs failed:", err);
    } finally {
      setLoadingMoreRecs(false);
    }
  }, [id, loadingMoreRecs, hasMoreRecs]);

  useEffect(() => {
    const handleScroll = () => {
      const nearBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 600;
      if (nearBottom) loadMoreRecs();
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [loadMoreRecs]);

  // Check subscription state on mount (authenticated only)
  useEffect(() => {
    if (!authClient || !video) return;
    authClient
      .get(API_ENDPOINTS.SUBSCRIPTIONS)
      .then((data) => {
        const channels = data?.channels || [];
        setIsSubscribed(channels.includes(video.channel?.name));
      })
      .catch(() => {});
  }, [video, isAuthenticated, session]);

  // Initialize like/dislike state from server for authenticated users
  useEffect(() => {
    if (!id) return;

    if (!isAuthenticated || !session?.access_token) {
      setIsLiked(false);
      setIsDisliked(false);
      return;
    }

    let cancelled = false;
    const client = apiService.withAuth(session.access_token);

    (async () => {
      const [likesResult, dislikesResult] = await Promise.allSettled([
        client.get(`${API_ENDPOINTS.LIKES}?limit=500`),
        client.get(`${API_ENDPOINTS.DISLIKES}?limit=500`),
      ]);

      if (cancelled) return;

      const likedVideos =
        likesResult.status === "fulfilled"
          ? likesResult.value?.videos || []
          : [];
      const dislikedVideos =
        dislikesResult.status === "fulfilled"
          ? dislikesResult.value?.videos || []
          : [];

      const liked = likedVideos.some((v) => v.id === id);
      const disliked = dislikedVideos.some((v) => v.id === id);

      // In case of inconsistent server state, prefer showing liked.
      setIsLiked(liked);
      setIsDisliked(disliked && !liked);
    })().catch((err) => {
      if (!cancelled) {
        console.error(
          "[VideoPlayer] Failed to fetch like/dislike status:",
          err,
        );
      }
    });

    return () => {
      cancelled = true;
    };
  }, [id, isAuthenticated, session]);

  // Like toggle
  const handleLike = async () => {
    if (!authClient || reactionPending) return;

    const prev = {
      isLiked,
      isDisliked,
      likeCount,
      dislikeCount,
    };

    const nextIsLiked = !isLiked;
    const nextLikeCount = Math.max(0, likeCount + (isLiked ? -1 : 1));
    const shouldClearDislike = !isLiked && isDisliked;
    const nextDislikeCount = shouldClearDislike
      ? Math.max(0, dislikeCount - 1)
      : dislikeCount;

    // Optimistic UI update: instant feedback while request is in-flight.
    setIsLiked(nextIsLiked);
    setLikeCount(nextLikeCount);
    if (shouldClearDislike) {
      setIsDisliked(false);
      setDislikeCount(nextDislikeCount);
    }

    setReactionPending(true);

    try {
      const data = isLiked
        ? await authClient.delete(API_ENDPOINTS.LIKE, { video_uuid: id })
        : await authClient.post(API_ENDPOINTS.LIKE, { video_uuid: id });

      // Respect authoritative state from API if present.
      if (typeof data?.is_liked === "boolean") {
        setIsLiked(data.is_liked);
      }
      if (data?.is_liked && shouldClearDislike) {
        setIsDisliked(false);
      }
    } catch (err) {
      console.error("[VideoPlayer] Like toggle failed:", err);
      // Roll back optimistic changes on failure.
      setIsLiked(prev.isLiked);
      setIsDisliked(prev.isDisliked);
      setLikeCount(prev.likeCount);
      setDislikeCount(prev.dislikeCount);
    } finally {
      setReactionPending(false);
    }
  };

  // Dislike toggle
  const handleDislike = async () => {
    if (!authClient || reactionPending) return;

    const prev = {
      isLiked,
      isDisliked,
      likeCount,
      dislikeCount,
    };

    const nextIsDisliked = !isDisliked;
    const nextDislikeCount = Math.max(0, dislikeCount + (isDisliked ? -1 : 1));
    const shouldClearLike = !isDisliked && isLiked;
    const nextLikeCount = shouldClearLike
      ? Math.max(0, likeCount - 1)
      : likeCount;

    // Optimistic UI update: instant feedback while request is in-flight.
    setIsDisliked(nextIsDisliked);
    setDislikeCount(nextDislikeCount);
    if (shouldClearLike) {
      setIsLiked(false);
      setLikeCount(nextLikeCount);
    }

    setReactionPending(true);

    try {
      const data = isDisliked
        ? await authClient.delete(API_ENDPOINTS.DISLIKE, { video_uuid: id })
        : await authClient.post(API_ENDPOINTS.DISLIKE, { video_uuid: id });

      // Respect authoritative state from API if present.
      if (typeof data?.is_disliked === "boolean") {
        setIsDisliked(data.is_disliked);
      }
      if (data?.is_disliked && shouldClearLike) {
        setIsLiked(false);
      }
    } catch (err) {
      console.error("[VideoPlayer] Dislike toggle failed:", err);
      // Roll back optimistic changes on failure.
      setIsLiked(prev.isLiked);
      setIsDisliked(prev.isDisliked);
      setLikeCount(prev.likeCount);
      setDislikeCount(prev.dislikeCount);
    } finally {
      setReactionPending(false);
    }
  };

  // Subscribe toggle
  const handleSubscribe = async () => {
    if (!authClient || !video) return;
    try {
      if (isSubscribed) {
        await authClient.delete(API_ENDPOINTS.SUBSCRIBE, {
          channel_name: video.channel?.name,
        });
        setIsSubscribed(false);
      } else {
        await authClient.post(API_ENDPOINTS.SUBSCRIBE, {
          channel_name: video.channel?.name,
        });
        setIsSubscribed(true);
      }
    } catch (err) {
      console.error("[VideoPlayer] Subscribe toggle failed:", err);
    }
  };

  const toggleReplies = (commentId) => {
    setExpandedReplies((prev) => ({ ...prev, [commentId]: !prev[commentId] }));
  };

  const generateColorHash = (value) => {
    const str = value || "Channel";
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
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

  const getInitials = (name) => {
    const normalized = (name || "C").trim();
    if (!normalized) return "C";
    return normalized
      .split(" ")
      .filter(Boolean)
      .map((part) => part[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const getHqThumbnail = (thumbnailUrl) => {
    if (!thumbnailUrl) return "";
    return thumbnailUrl.replace(
      /\/(default|mqdefault|hqdefault|sddefault|maxresdefault)\.jpg$/,
      "/hqdefault.jpg",
    );
  };

  const channelColors = generateColorHash(video?.channel?.name);
  const channelInitials = getInitials(video?.channel?.name);

  if (loading) {
    return (
      <div
        className="video-player-page"
        style={{
          justifyContent: "center",
          alignItems: "center",
          display: "flex",
          minHeight: "60vh",
        }}
      >
        <div className="loading-spinner" />
      </div>
    );
  }

  if (!video) {
    return (
      <div
        className="video-player-page"
        style={{ padding: "48px", textAlign: "center", color: "#606060" }}
      >
        <h3>Video not found</h3>
      </div>
    );
  }

  return (
    <div className="video-player-page">
      {/* Primary Column */}
      <div className="video-player-page__primary">
        {/* Plain iframe — matches mock.html exactly, video_id is the YouTube ID */}
        <div className="video-player__player-container">
          <iframe
            width="100%"
            height="100%"
            src={`https://www.youtube.com/embed/${video.video_id}`}
            title={video.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerPolicy="strict-origin-when-cross-origin"
            allowFullScreen
            style={{ display: "block", border: 0 }}
          />
        </div>

        {/* Video Info */}
        <div className="video-player__info">
          <h1 className="video-player__title">{video.title}</h1>

          <div className="video-player__actions-row">
            {/* Channel Info */}
            <div className="video-player__channel-info">
              <Link to={`/channel/${video.channel?.id}`}>
                <div
                  className="video-player__channel-avatar-fallback"
                  style={{
                    background: `linear-gradient(135deg, ${channelColors[0]} 0%, ${channelColors[1]} 100%)`,
                  }}
                  aria-label={video.channel?.name}
                >
                  <span className="video-player__channel-avatar-initials">
                    {channelInitials}
                  </span>
                </div>
              </Link>
              <div className="video-player__channel-text">
                <Link
                  to={`/channel/${video.channel?.id}`}
                  className="video-player__channel-name"
                >
                  {video.channel?.name}
                  {video.channel?.verified && (
                    <MdVerified style={{ color: "#606060" }} />
                  )}
                </Link>
                <span className="video-player__channel-subs">
                  {video.channel?.subscribers || ""}
                </span>
              </div>
              {isAuthenticated && (
                <button
                  className={`video-player__subscribe-btn ${isSubscribed ? "video-player__subscribe-btn--subscribed" : ""}`}
                  onClick={handleSubscribe}
                >
                  {isSubscribed ? "Subscribed" : "Subscribe"}
                </button>
              )}
            </div>

            {/* Action Buttons */}
            <div className="video-player__action-buttons">
              <div className="video-player__action-btn--like-dislike">
                <button
                  className="video-player__like-btn"
                  onClick={handleLike}
                  disabled={!isAuthenticated || reactionPending}
                  title={!isAuthenticated ? "Sign in to like" : ""}
                >
                  {isLiked ? <AiFillLike /> : <AiOutlineLike />}
                  {likeCount.toLocaleString()}
                </button>
                <button
                  className="video-player__dislike-btn"
                  onClick={handleDislike}
                  disabled={!isAuthenticated || reactionPending}
                  title={!isAuthenticated ? "Sign in to dislike" : ""}
                >
                  {isDisliked ? <AiFillDislike /> : <AiOutlineDislike />}
                  {dislikeCount.toLocaleString()}
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
              <button
                className="video-player__action-btn"
                style={{ padding: "8px 12px" }}
              >
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
            className={`video-player__description-text ${!showFullDescription ? "video-player__description-text--collapsed" : ""}`}
          >
            {video.description}
          </p>
          <p className="video-player__show-more">
            {showFullDescription ? "Show less" : "...more"}
          </p>
        </div>

        {/* Comments Section (static sample data — no comments API) */}
        <div className="comments-section">
          <div className="comments-section__header">
            <span className="comments-section__count">
              {comments.length} Comments
            </span>
            <button className="comments-section__sort">
              <BsSortDown /> Sort by
            </button>
          </div>

          <div className="comment-input">
            <img
              className="comment-input__avatar"
              src="https://ui-avatars.com/api/?name=U&background=8B5CF6&color=fff&size=40"
              alt="Your avatar"
            />
            <input
              className="comment-input__field"
              placeholder="Add a comment..."
            />
          </div>

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
        {recommendations.map((rec) => (
          <Link
            key={rec.id}
            to={`/video/${rec.id}`}
            className="recommendation-card"
          >
            <div className="recommendation-card__thumbnail-container">
              <img
                className="recommendation-card__thumbnail"
                src={getHqThumbnail(rec.thumbnail)}
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
                {rec.channel?.name}
                {rec.channel?.verified && (
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
        {loadingMoreRecs && (
          <div style={{ textAlign: "center", padding: "16px" }}>
            <div className="loading-spinner" />
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoPlayer;
