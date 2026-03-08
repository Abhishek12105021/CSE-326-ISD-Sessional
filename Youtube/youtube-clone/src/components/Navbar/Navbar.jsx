import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AiOutlineMenu,
  AiOutlineSearch,
  AiOutlineBell,
  AiOutlineVideoCameraAdd,
} from "react-icons/ai";
import { BsYoutube, BsMic } from "react-icons/bs";
import "./Navbar.css";

const Navbar = ({ toggleSidebar }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
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
        <img
          className="navbar__avatar"
          src="https://ui-avatars.com/api/?name=MK&background=8B5CF6&color=fff&size=32"
          alt="User avatar"
        />
      </div>
    </nav>
  );
};

export default Navbar;
