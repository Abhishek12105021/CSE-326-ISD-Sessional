import { useState } from "react";
import { useParams } from "react-router-dom";
import { MdVerified } from "react-icons/md";
import { VideoCard } from "../../components";
import { videos } from "../../data/sampleData";
import "./Channel.css";

const Channel = () => {
  const { channelId } = useParams();
  const [activeTab, setActiveTab] = useState("Videos");

  // Find channel info from videos data
  const channelVideo = videos.find((v) => v.channel.id === channelId);
  const channelInfo = channelVideo?.channel || {
    name: "Your Channel",
    avatar: "https://ui-avatars.com/api/?name=MK&background=8B5CF6&color=fff&size=128",
    verified: false,
    subscribers: "0",
    id: channelId,
  };

  const channelVideos = videos.filter((v) => v.channel.id === channelId);

  const tabs = ["Home", "Videos", "Shorts", "Live", "Playlists", "Community", "About"];

  return (
    <div className="channel-page">
      {/* Banner */}
      <div className="channel-page__banner">
        <img
          src={`https://picsum.photos/seed/${channelId}-banner/1200/200`}
          alt="Channel banner"
        />
      </div>

      {/* Channel Header */}
      <div className="channel-page__header">
        <img
          className="channel-page__avatar"
          src={channelInfo.avatar.replace("size=36", "size=128")}
          alt={channelInfo.name}
        />
        <div className="channel-page__info">
          <h1 className="channel-page__name">
            {channelInfo.name}
            {channelInfo.verified && <MdVerified style={{ color: "#606060" }} />}
          </h1>
          <div className="channel-page__handle">
            @{channelInfo.name.toLowerCase().replace(/\s/g, "")}
          </div>
          <div className="channel-page__stats">
            <span>{channelInfo.subscribers} subscribers</span>
            <span>{channelVideos.length} videos</span>
          </div>
          <p className="channel-page__description-text">
            Welcome to {channelInfo.name}! Subscribe for the latest videos on trending topics.
            New videos every week!
          </p>
          <button className="channel-page__subscribe-btn">Subscribe</button>
        </div>
      </div>

      {/* Tabs */}
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

      {/* Tab Content */}
      {activeTab === "Videos" || activeTab === "Home" ? (
        <>
          {channelVideos.length > 0 ? (
            <div className="channel-page__videos">
              {channelVideos.map((video) => (
                <VideoCard key={video.id} video={video} />
              ))}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "48px", color: "#606060" }}>
              <h3>This channel doesn&apos;t have any videos yet</h3>
            </div>
          )}
        </>
      ) : (
        <div style={{ textAlign: "center", padding: "48px", color: "#606060" }}>
          <h3>{activeTab}</h3>
          <p>This section is coming soon!</p>
        </div>
      )}
    </div>
  );
};

export default Channel;
