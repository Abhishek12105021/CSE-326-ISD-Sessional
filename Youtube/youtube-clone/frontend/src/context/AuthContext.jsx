import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import { guestStorage } from '../utils';
import { authService } from '../services';
import { API_BASE_URL } from '../config';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [guestId, setGuestId] = useState(null);
  const [region, setRegion] = useState(() => guestStorage.getRegion());

  // Initialize auth state
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);

      if (!session?.user) {
        setGuestId(guestStorage.getGuestId());
      }

      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        setSession(session);
        setUser(session?.user ?? null);

        if (event === 'SIGNED_IN' && session?.user) {
          const previousGuestId = guestStorage.getRawGuestId();

          if (previousGuestId) {
            // Clear guest data (managed via localStorage)
            guestStorage.clearGuestId();
          }

          setGuestId(null);
        } else if (event === 'SIGNED_OUT') {
          setGuestId(guestStorage.getGuestId());
        }
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  // API helper with auth
  const authFetch = useCallback(async (endpoint, options = {}) => {
    const accessToken = session?.access_token;

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
        ...options.headers,
      },
    });

    return response;
  }, [session]);

  // Sign in with Google
  const signInWithGoogle = async () => {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}`,
        queryParams: {
          access_type: 'offline',
          prompt: 'consent',
        },
      },
    });

    if (error) {
      console.error('Google sign in error:', error);
      return { success: false, error: error.message };
    }

    return { success: true, data };
  };

  // Sign out
  const signOut = async (scope = 'local') => {
    const { error } = await supabase.auth.signOut({ scope });

    if (error) {
      console.error('Sign out error:', error);
      return { success: false, error: error.message };
    }

    return { success: true };
  };

  // Sign out from all devices
  const signOutAll = async () => {
    return signOut('global');
  };

  // Get user profile from backend
  const getProfile = async () => {
    if (!session?.access_token) throw new Error('Not authenticated');
    return authService.getProfile(session.access_token);
  };

  // Update user profile
  const updateProfile = async (updates) => {
    if (!session?.access_token) throw new Error('Not authenticated');
    return authService.updateProfile(session.access_token, updates);
  };

  // Update region for both guest and authenticated users
  const updateRegion = useCallback(async (newRegion) => {
    // Always store in localStorage for persistence (works for both guest and auth users)
    guestStorage.setRegion(newRegion);
    setRegion(newRegion);

    // For authenticated users, also update on server
    if (session?.access_token) {
      try {
        await authService.updateProfile(session.access_token, { region: newRegion });
      } catch (error) {
        console.error('Failed to update region on server:', error);
      }
    }

    return { success: true };
  }, [session]);

  const value = {
    user,
    session,
    loading,
    isAuthenticated: !!user,
    guestId,
    region,
    signInWithGoogle,
    signOut,
    signOutAll,
    getProfile,
    updateProfile,
    updateRegion,
    authFetch,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
