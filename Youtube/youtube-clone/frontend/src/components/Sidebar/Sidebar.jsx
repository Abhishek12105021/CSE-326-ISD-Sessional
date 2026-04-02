import React from "react";
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
import "./Sidebar.css";

const Sidebar = ({ isCollapsed }) => {
  const location = useLocation();

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
    { icon: <MdOutlineVideoLibrary />, text: "Your channel", path: "/channel/you" },
    { icon: <MdOutlineHistory />, text: "History", path: "/history" },
    { icon: <AiOutlinePlaySquare />, text: "Playlists", path: "/playlists" },
    { icon: <MdOutlineWatchLater />, text: "Watch later", path: "/watchlater" },
    { icon: <AiOutlineLike />, text: "Liked videos", path: "/liked" },
  ];

  const subscriptions = [
    {
      name: "Tech Academy",
      avatar: "https://ui-avatars.com/api/?name=Tech+A&background=random&size=24",
      id: "ch1",
    },
    {
      name: "ChillBeats",
      avatar: "https://ui-avatars.com/api/?name=Chill+B&background=random&size=24",
      id: "ch2",
    },
    {
      name: "Sports Central",
      avatar: "https://ui-avatars.com/api/?name=Sports+C&background=random&size=24",
      id: "ch3",
    },
    {
      name: "GameMaster Pro",
      avatar: "https://ui-avatars.com/api/?name=Game+M&background=random&size=24",
      id: "ch4",
    },
    {
      name: "Dev Simplified",
      avatar: "https://ui-avatars.com/api/?name=Dev+S&background=random&size=24",
      id: "ch7",
    },
  ];

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

      <hr className="sidebar__hr" />

      {/* Subscriptions */}
      <div className="sidebar__section">
        <div className="sidebar__section-title">Subscriptions</div>
        {subscriptions.map((sub) => (
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
      </div>

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
