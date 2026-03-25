import React, { useState, useRef } from 'react';
import { MdPublic } from 'react-icons/md';
import { useClickOutside } from '../../hooks';
import './RegionSelector.css';

const REGIONS = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'JP', name: 'Japan' },
  { code: 'KR', name: 'South Korea' },
  { code: 'IN', name: 'India' },
  { code: 'MX', name: 'Mexico' },
  { code: 'RU', name: 'Russia' },
];

const RegionSelector = ({ currentRegion, onRegionChange, disabled }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useClickOutside(dropdownRef, () => setIsOpen(false), isOpen);

  const selectedRegion = REGIONS.find(r => r.code === currentRegion) || REGIONS[0];

  const handleSelect = (regionCode) => {
    onRegionChange(regionCode);
    setIsOpen(false);
  };

  return (
    <div className="region-selector" ref={dropdownRef}>
      <button
        className="region-selector__btn"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        aria-label="Select region"
        title={`Region: ${selectedRegion.name}`}
      >
        <MdPublic className="region-selector__icon" />
        <span className="region-selector__code">{selectedRegion.code}</span>
      </button>

      {isOpen && (
        <div className="region-selector__dropdown">
          <div className="region-selector__header">
            <span>Select your region</span>
          </div>
          <div className="region-selector__list">
            {REGIONS.map((region) => (
              <button
                key={region.code}
                className={`region-selector__item ${
                  region.code === currentRegion ? 'region-selector__item--active' : ''
                }`}
                onClick={() => handleSelect(region.code)}
              >
                <span className="region-selector__item-code">{region.code}</span>
                <span className="region-selector__item-name">{region.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default RegionSelector;
