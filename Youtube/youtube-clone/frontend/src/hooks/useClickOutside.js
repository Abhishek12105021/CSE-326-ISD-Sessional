/**
 * useClickOutside - Detect clicks outside a referenced element
 */

import { useEffect } from 'react';

export function useClickOutside(ref, handler, enabled = true) {
  useEffect(() => {
    if (!enabled) return;

    const handleClickOutside = (event) => {
      if (ref.current && !ref.current.contains(event.target)) {
        handler(event);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [ref, handler, enabled]);
}

export default useClickOutside;
