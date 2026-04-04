import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { MdVerified } from "react-icons/md";
import { VideoCard } from "../../components";
import { useAuth } from "../../context";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import "./Channel.css";

const LIMIT = 12;

const Channel = () => {
  const { channelName: routeChannelName } = useParams();
  const channelName = decodeURIComponent(routeChannelName || "");
  const { isAuthenticated, session, user } = useAuth();

  const [channel, setChannel] = useState(null);
  const [activeTab, setActiveTab] = useState("Videos");
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState("");
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [subscriptionSuccess, setSubscriptionSuccess] = useState(false);

  const shownIds = useRef([]);
  const loadMoreRef = useRef(null);

  const userDisplayName =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email?.split("@")[0] ||
    "My Channel";
  const isOwnChannelRoute = channelName.trim().toLowerCase() === "mine";
  const requestedChannelName = isOwnChannelRoute ? userDisplayName : channelName;

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

  const channelColors = generateColorHash(requestedChannelName || channel?.name);
  const channelInitials = getInitials(requestedChannelName || channel?.name);

  const fetchChannel = useCallback(
    async (append = false) => {
      if (!requestedChannelName.trim()) {
        setLoading(false);
        setError("Channel name is missing.");
        return;
      }

      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setError("");
        shownIds.current = [];
      }

      try {
        const data = await apiService.post(API_ENDPOINTS.CHANNEL, {
          channel_name: requestedChannelName,
          excluded_video_ids: append ? shownIds.current : [],
          limit: LIMIT,
        });

        const fetchedVideos = data?.videos || [];
        shownIds.current = [...shownIds.current, ...fetchedVideos.map((video) => video.id)];

        setChannel(data?.channel || null);
        setHasMore(Boolean(data?.has_more));
        setVideos((prev) => (append ? [...prev, ...fetchedVideos] : fetchedVideos));

        if (!append && isAuthenticated && session?.access_token) {
          try {
            const subscriptionData = await apiService
              .withAuth(session.access_token)
              .get(API_ENDPOINTS.SUBSCRIPTIONS);
            const subscribedChannels = subscriptionData?.channels || [];
            setIsSubscribed(subscribedChannels.includes(requestedChannelName));
          } catch (subscriptionError) {
            console.error("[Channel] Failed to fetch subscription state:", subscriptionError);
          }
        }
      } catch (err) {
        console.error("[Channel] Failed to fetch channel page:", err);
        if (isOwnChannelRoute) {
          setChannel({
            name: userDisplayName,
            verified: false,
            id: "mine",
          });
          setError("");
        } else {
          setChannel(null);
          setError("This channel has no videos yet.");
        }
        setVideos([]);
        setHasMore(false);
      } finally {
        if (append) {
          setLoadingMore(false);
        } else {
          setLoading(false);
        }
      }
    },
    [isAuthenticated, isOwnChannelRoute, requestedChannelName, session?.access_token, userDisplayName]
  );

  const handleSubscribe = async () => {
    if (!isAuthenticated || !session?.access_token || !requestedChannelName) return;

    setSubscriptionLoading(true);
    try {
      const client = apiService.withAuth(session.access_token);
      if (isSubscribed) {
        await client.delete(API_ENDPOINTS.SUBSCRIBE, { channel_name: requestedChannelName });
        setIsSubscribed(false);
      } else {
        await client.post(API_ENDPOINTS.SUBSCRIBE, { channel_name: requestedChannelName });
        setIsSubscribed(true);
      }

      setSubscriptionSuccess(true);
      window.dispatchEvent(new Event("yt:subscriptions-updated"));
      setTimeout(() => {
        setSubscriptionSuccess(false);
      }, 850);
    } catch (err) {
      console.error("[Channel] Subscribe toggle failed:", err);
    } finally {
      setSubscriptionLoading(false);
    }
  };

  useEffect(() => {
    fetchChannel(false);
  }, [fetchChannel]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    await fetchChannel(true);
  }, [loadingMore, hasMore, fetchChannel]);

  useEffect(() => {
    loadMoreRef.current = loadMore;
  }, [loadMore]);

  useEffect(() => {
    const handleScroll = () => {
      const nearBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 600;
      if (nearBottom) loadMoreRef.current?.();
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const tabs = ["Videos", "About"];

  const channelInfo = channel || {
    name: requestedChannelName || "Channel",
    verified: false,
    id: requestedChannelName,
  };

  if (loading) {
    return (
      <div className="channel-page channel-page--loading">
        <div className="loading-spinner" />
      </div>
    );
  }

  if (error && videos.length === 0) {
    return (
      <div className="channel-page">
        <div className="channel-page__empty-state">
          <h3>No videos</h3>
          <p>{error}</p>
          <Link to="/" className="channel-page__empty-link">
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="channel-page">
      <div
        className="channel-page__banner"
        style={{
          background: `linear-gradient(135deg, ${channelColors[0]} 0%, ${channelColors[1]} 100%)`,
        }}
      >
        <h2 className="channel-page__banner-text">{channelInfo.name}</h2>
      </div>

      <div className="channel-page__header">
        <div
          className="channel-page__avatar-fallback"
          style={{
            background: `linear-gradient(135deg, ${channelColors[0]} 0%, ${channelColors[1]} 100%)`,
          }}
          aria-label={channelInfo.name}
        >
          <span className="channel-page__avatar-initials">{channelInitials}</span>
        </div>
        <div className="channel-page__info">
          <h1 className="channel-page__name">
            {channelInfo.name}
            {channelInfo.verified && <MdVerified style={{ color: "#606060" }} />}
          </h1>
          <div className="channel-page__handle">
            @{channelInfo.name.toLowerCase().replace(/\s/g, "")}
          </div>
          <div className="channel-page__stats">
            <span>{videos.length} videos</span>
          </div>
          <p className="channel-page__description-text">
            Welcome to {channelInfo.name}! Subscribe for the latest videos on trending topics.
            New videos every week!
          </p>
          {isAuthenticated && (
            <button
              className={`channel-page__subscribe-btn ${isSubscribed ? "channel-page__subscribe-btn--subscribed" : ""} ${subscriptionLoading ? "channel-page__subscribe-btn--loading" : ""} ${subscriptionSuccess ? "channel-page__subscribe-btn--success" : ""}`}
              onClick={handleSubscribe}
              disabled={subscriptionLoading}
            >
              <span className="channel-page__subscribe-label">
                {isSubscribed ? "Subscribed" : "Subscribe"}
              </span>
            </button>
          )}
        </div>
      </div>

      <div className="channel-page__tabs">
        {tabs.map((tab) => (
          <button
            key={tab}
            className={`channel-page__tab ${
              activeTab === tab ? "channel-page__tab--active" : ""
            }`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="channel-page__videos">
        {activeTab === "Videos" ? (
          videos.length > 0 ? (
          videos.map((video) => <VideoCard key={video.id} video={video} />)
          ) : (
            <div className="channel-page__empty-state">
              {isOwnChannelRoute ? (
                <>
                  <h3>Your channel is ready</h3>
                  <p>
                    @{channelInfo.name.toLowerCase().replace(/\s/g, "")} is set up. Add your first upload
                    and your videos will appear here.
                  </p>
                  <div className="channel-page__setup-list">
                    <div className="channel-page__setup-item">
                      <strong>Profile</strong>
                      <span>Name and avatar are ready</span>
                    </div>
                    <div className="channel-page__setup-item">
                      <strong>Channel Handle</strong>
                      <span>@{channelInfo.name.toLowerCase().replace(/\s/g, "")}</span>
                    </div>
                    <div className="channel-page__setup-item">
                      <strong>Uploads</strong>
                      <span>0 videos published</span>
                    </div>
                  </div>
                  <Link to="/" className="channel-page__empty-link">
                    Explore Home Feed
                  </Link>
                </>
              ) : (
                <>
                  <h3>No videos</h3>
                  <p>This channel does not have any uploads in the database yet.</p>
                </>
              )}
            </div>
          )
        ) : (
          <div className="channel-page__empty-state">
            <h3>About</h3>
            <p>
              {channelInfo.name} is a derived channel page built from videos stored in the
              database.
            </p>
          </div>
        )}
      </div>

      {loadingMore && (
        <div className="channel-page__loading-more">
          <div className="loading-spinner" />
        </div>
      )}

      {!hasMore && videos.length > 0 && (
        <div className="channel-page__end-state">You&apos;ve reached the end</div>
      )}
    </div>
  );
};

export default Channel;
