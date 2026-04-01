import React, { useState, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AiOutlineMenu,
  AiOutlineSearch,
  AiOutlineBell,
  AiOutlineVideoCameraAdd,
} from "react-icons/ai";
import { BsYoutube, BsMic } from "react-icons/bs";
import { FaUserCircle } from "react-icons/fa";
import { useAuth } from "../../context";
import { useClickOutside } from "../../hooks";
import "./Navbar.css";

const Navbar = ({ toggleSidebar }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [showUserMenu, setShowUserMenu] = useState(false);
  const navigate = useNavigate();
  const userMenuRef = useRef(null);
  const { user, isAuthenticated, signOut, loading } = useAuth();

  // Close menu on click outside
  useClickOutside(userMenuRef, () => setShowUserMenu(false), showUserMenu);

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    setShowUserMenu(false);
    navigate("/");
  };

  // Get user display info
  const getUserAvatar = () => {
    if (user?.user_metadata?.avatar_url) {
      return user.user_metadata.avatar_url;
    }
    const name = user?.user_metadata?.full_name || user?.email || "User";
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=8B5CF6&color=fff&size=32`;
  };

  const getUserName = () => {
    return (
      user?.user_metadata?.full_name || user?.email?.split("@")[0] || "User"
    );
  };

  return (
    <nav className="navbar">
      {/* Left Section */}
      <div className="navbar__left">
        <button className="navbar__hamburger" onClick={toggleSidebar}>
          <AiOutlineMenu />
        </button>
        <Link to="/" className="navbar__logo">
          <BsYoutube className="navbar__logo-icon" />
          <span className="navbar__logo-text">YouTube</span>
        </Link>
      </div>

      {/* Center Section - Search */}
      <div className="navbar__center">
        <form className="navbar__search" onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="Search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </form>
        <button className="navbar__search-btn" onClick={handleSearch}>
          <AiOutlineSearch />
        </button>
        <button className="navbar__voice-btn">
          <BsMic />
        </button>
      </div>

      {/* Right Section */}
      <div className="navbar__right">
        <button className="navbar__icon-btn">
          <AiOutlineVideoCameraAdd />
        </button>
        <button className="navbar__icon-btn">
          <AiOutlineBell />
          <span className="navbar__notification-count">9+</span>
        </button>

        {loading ? (
          <div className="navbar__avatar-loading" />
        ) : isAuthenticated ? (
          <div className="navbar__user-menu" ref={userMenuRef}>
            <button
              className="navbar__avatar-btn"
              onClick={() => setShowUserMenu(!showUserMenu)}
              aria-label="Account menu"
            >
              <img
                className="navbar__avatar"
                src={getUserAvatar()}
                alt="User avatar"
              />
            </button>

            {showUserMenu && (
              <div className="navbar__dropdown">
                <div className="navbar__dropdown-header">
                  <img
                    className="navbar__dropdown-avatar"
                    src={getUserAvatar()}
                    alt=""
                  />
                  <div className="navbar__dropdown-info">
                    <p className="navbar__dropdown-name">{getUserName()}</p>
                    <p className="navbar__dropdown-email">{user?.email}</p>
                  </div>
                </div>

                <div className="navbar__dropdown-divider" />

                <button
                  className="navbar__dropdown-item"
                  onClick={() => {
                    navigate("/channel/mine");
                    setShowUserMenu(false);
                  }}
                >
                  Your channel
                </button>
                <button
                  className="navbar__dropdown-item"
                  onClick={() => {
                    navigate("/history");
                    setShowUserMenu(false);
                  }}
                >
                  History
                </button>
                <button
                  className="navbar__dropdown-item"
                  onClick={() => {
                    navigate("/settings");
                    setShowUserMenu(false);
                  }}
                >
                  Settings
                </button>

                <div className="navbar__dropdown-divider" />

                <button
                  className="navbar__dropdown-item navbar__dropdown-item--danger"
                  onClick={handleSignOut}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link to="/signin" className="navbar__signin-btn">
            <FaUserCircle className="navbar__signin-icon" />
            <span>Sign in</span>
          </Link>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
