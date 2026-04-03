import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  AiOutlineHome,
  AiFillHome,
  AiOutlineLike,
  AiOutlineClockCircle,
  AiOutlineFire,
  AiOutlinePlaySquare,
} from "react-icons/ai";
import {
  MdOutlineSubscriptions,
  MdSubscriptions,
  MdOutlineVideoLibrary,
  MdOutlineWatchLater,
  MdOutlineHistory,
  MdOutlineSportsEsports,
  MdOutlineNewspaper,
  MdOutlinePodcasts,
  MdOutlineMusicNote,
  MdOutlineMovie,
  MdOutlineLiveTv,
  MdOutlineSchool,
  MdOutlineFeedback,
  MdOutlineHelp,
  MdOutlineFlag,
  MdOutlineSettings,
} from "react-icons/md";
import { SiYoutubeshorts } from "react-icons/si";
import { BiTrendingUp } from "react-icons/bi";
import { useAuth } from "../../context";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import "./Sidebar.css";

const Sidebar = ({ isCollapsed }) => {
  const SUBSCRIPTION_COLLAPSED_LIMIT = 6;
  const location = useLocation();
  const { isAuthenticated, session } = useAuth();
  const [subscribedChannels, setSubscribedChannels] = useState([]);
  const [showAllSubscriptions, setShowAllSubscriptions] = useState(false);

  const loadSubscriptions = useCallback(async () => {
    if (!isAuthenticated || !session?.access_token) {
      setSubscribedChannels([]);
      return;
    }

    try {
      const data = await apiService
        .withAuth(session.access_token)
        .get(API_ENDPOINTS.SUBSCRIPTIONS);

      const channels = Array.isArray(data?.channels) ? data.channels : [];
      const uniqueChannels = Array.from(
        new Set(
          channels
            .map((name) => (name || "").trim())
            .filter(Boolean)
        )
      );

      setSubscribedChannels(uniqueChannels);
    } catch (error) {
      console.error("[Sidebar] Failed to load subscriptions:", error);
      setSubscribedChannels([]);
    }
  }, [isAuthenticated, session?.access_token]);

  const isActive = (path) => location.pathname === path;

  const mainLinks = [
    {
      icon: isActive("/") ? <AiFillHome /> : <AiOutlineHome />,
      text: "Home",
      path: "/",
    },
    {
      icon: <SiYoutubeshorts />,
      text: "Shorts",
      path: "/shorts",
    },
    {
      icon: isActive("/subscriptions") ? (
        <MdSubscriptions />
      ) : (
        <MdOutlineSubscriptions />
      ),
      text: "Subscriptions",
      path: "/subscriptions",
    },
  ];

  const youLinks = [
    { icon: <MdOutlineVideoLibrary />, text: "Your channel", path: "/channel/mine" },
    { icon: <MdOutlineHistory />, text: "History", path: "/history" },
    { icon: <AiOutlinePlaySquare />, text: "Playlists", path: "/playlists" },
    { icon: <MdOutlineWatchLater />, text: "Watch later", path: "/watchlater" },
    { icon: <AiOutlineLike />, text: "Liked videos", path: "/liked" },
  ];

  useEffect(() => {
    let cancelled = false;

    loadSubscriptions().catch(() => {
      if (!cancelled) {
        setSubscribedChannels([]);
      }
    });

    const handleSubscriptionsUpdated = () => {
      loadSubscriptions().catch(() => {
        if (!cancelled) {
          setSubscribedChannels([]);
        }
      });
    };

    window.addEventListener("yt:subscriptions-updated", handleSubscriptionsUpdated);

    return () => {
      cancelled = true;
      window.removeEventListener("yt:subscriptions-updated", handleSubscriptionsUpdated);
    };
  }, [loadSubscriptions]);

  const subscriptions = useMemo(
    () =>
      subscribedChannels.map((name) => ({
        id: name,
        name,
        avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&size=24&background=random&color=fff&rounded=true&bold=true`,
      })),
    [subscribedChannels]
  );

  useEffect(() => {
    if (subscriptions.length <= SUBSCRIPTION_COLLAPSED_LIMIT) {
      setShowAllSubscriptions(false);
    }
  }, [subscriptions.length]);

  const visibleSubscriptions = showAllSubscriptions
    ? subscriptions
    : subscriptions.slice(0, SUBSCRIPTION_COLLAPSED_LIMIT);

  const exploreLinks = [
    { icon: <AiOutlineFire />, text: "Trending", path: "/trending" },
    { icon: <MdOutlineMusicNote />, text: "Music", path: "/music" },
    { icon: <MdOutlineMovie />, text: "Movies", path: "/movies" },
    { icon: <MdOutlineLiveTv />, text: "Live", path: "/live" },
    { icon: <MdOutlineSportsEsports />, text: "Gaming", path: "/gaming" },
    { icon: <MdOutlineNewspaper />, text: "News", path: "/news" },
    { icon: <MdOutlinePodcasts />, text: "Podcasts", path: "/podcasts" },
    { icon: <MdOutlineSchool />, text: "Learning", path: "/learning" },
  ];

  const moreLinks = [
    { icon: <MdOutlineSettings />, text: "Settings", path: "/settings" },
    { icon: <MdOutlineFlag />, text: "Report history", path: "/report" },
    { icon: <MdOutlineHelp />, text: "Help", path: "/help" },
    { icon: <MdOutlineFeedback />, text: "Send feedback", path: "/feedback" },
  ];

  return (
    <aside className={`sidebar ${isCollapsed ? "sidebar--collapsed" : ""}`}>
      {/* Main Links */}
      <div className="sidebar__section">
        {mainLinks.map((link) => (
          <Link
            key={link.text}
            to={link.path}
            className={`sidebar__link ${
              isActive(link.path) ? "sidebar__link--active" : ""
            }`}
          >
            <span className="sidebar__link-icon">{link.icon}</span>
            <span className="sidebar__link-text">{link.text}</span>
          </Link>
        ))}
      </div>

      <hr className="sidebar__hr" />

      {/* You Section */}
      <div className="sidebar__section">
        <div className="sidebar__section-title">You &gt;</div>
        {youLinks.map((link) => (
          <Link
            key={link.text}
            to={link.path}
            className={`sidebar__link ${
              isActive(link.path) ? "sidebar__link--active" : ""
            }`}
          >
            <span className="sidebar__link-icon">{link.icon}</span>
            <span className="sidebar__link-text">{link.text}</span>
          </Link>
        ))}
      </div>

      {subscriptions.length > 0 && (
        <>
          <hr className="sidebar__hr" />

          {/* Subscriptions */}
          <div className="sidebar__section">
            <div className="sidebar__section-title">Subscriptions</div>
            {visibleSubscriptions.map((sub) => (
              <Link
                key={sub.id}
                to={`/channel/${encodeURIComponent(sub.name)}`}
                className="sidebar__link"
              >
                <img
                  className="sidebar__sub-avatar"
                  src={sub.avatar}
                  alt={sub.name}
                />
                <span className="sidebar__link-text">{sub.name}</span>
              </Link>
            ))}

            {subscriptions.length > SUBSCRIPTION_COLLAPSED_LIMIT && (
              <button
                type="button"
                className="sidebar__subscriptions-toggle"
                onClick={() => setShowAllSubscriptions((prev) => !prev)}
              >
                <span className="sidebar__link-icon">
                  {showAllSubscriptions ? "˄" : "˅"}
                </span>
                <span className="sidebar__link-text">
                  {showAllSubscriptions
                    ? "Show less"
                    : `Show ${subscriptions.length - SUBSCRIPTION_COLLAPSED_LIMIT} more`}
                </span>
              </button>
            )}
          </div>
        </>
      )}

      <hr className="sidebar__hr" />

      {/* Explore */}
      <div className="sidebar__section">
        <div className="sidebar__section-title">Explore</div>
        {exploreLinks.map((link) => (
          <Link
            key={link.text}
            to={link.path}
            className={`sidebar__link ${
              isActive(link.path) ? "sidebar__link--active" : ""
            }`}
          >
            <span className="sidebar__link-icon">{link.icon}</span>
            <span className="sidebar__link-text">{link.text}</span>
          </Link>
        ))}
      </div>

      <hr className="sidebar__hr" />

      {/* More from YouTube */}
      <div className="sidebar__section">
        {moreLinks.map((link) => (
          <Link
            key={link.text}
            to={link.path}
            className="sidebar__link"
          >
            <span className="sidebar__link-icon">{link.icon}</span>
            <span className="sidebar__link-text">{link.text}</span>
          </Link>
        ))}
      </div>

      <div className="sidebar__section" style={{ padding: "16px 24px", fontSize: "12px", color: "#909090" }}>
        <span className="sidebar__link-text">© 2026 YouTube Clone</span>
      </div>
    </aside>
  );
};

export default Sidebar;
