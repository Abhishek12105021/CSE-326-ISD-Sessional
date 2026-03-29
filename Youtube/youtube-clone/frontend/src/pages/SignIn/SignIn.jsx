import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context';
import './SignIn.css';

function SignIn() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { signInWithGoogle, isAuthenticated, loading } = useAuth();
  const [error, setError] = useState(() => searchParams.get('auth_error') || null);
  const [isSigningIn, setIsSigningIn] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (!loading && isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, loading, navigate]);

  const handleGoogleSignIn = async () => {
    setError(null);
    setIsSigningIn(true);

    const result = await signInWithGoogle();

    if (!result.success) {
      setError(result.error);
      setIsSigningIn(false);
    }
    // On success, Supabase redirects to Google and back
  };

  if (loading) {
    return (
      <div className="signin-container">
        <div className="signin-card">
          <div className="signin-loading">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="signin-container">
      <div className="signin-card">
        <div className="signin-header">
          <svg className="youtube-logo" viewBox="0 0 90 20" preserveAspectRatio="xMidYMid meet">
            <g>
              <path d="M27.9727 3.12324C27.6435 1.89323 26.6768 0.926623 25.4468 0.597366C23.2197 2.24288e-07 14.285 0 14.285 0C14.285 0 5.35042 2.24288e-07 3.12323 0.597366C1.89323 0.926623 0.926623 1.89323 0.597366 3.12324C2.24288e-07 5.35042 0 10 0 10C0 10 2.24288e-07 14.6496 0.597366 16.8768C0.926623 18.1068 1.89323 19.0734 3.12323 19.4026C5.35042 20 14.285 20 14.285 20C14.285 20 23.2197 20 25.4468 19.4026C26.6768 19.0734 27.6435 18.1068 27.9727 16.8768C28.5701 14.6496 28.5701 10 28.5701 10C28.5701 10 28.5677 5.35042 27.9727 3.12324Z" fill="#FF0000"/>
              <path d="M11.4253 14.2854L18.8477 10.0004L11.4253 5.71533V14.2854Z" fill="white"/>
            </g>
            <g>
              <path d="M34.6024 19.4043L35.8917 3.34314H39.3481L40.6374 19.4043H38.4008L38.1989 15.7162H37.0413L36.8394 19.4043H34.6024ZM37.1878 13.6867L37.6201 6.57647L38.054 13.6867H37.1878Z" fill="white"/>
              <path d="M41.4697 19.4043V3.34314H45.1077V8.45486H46.3436V3.34314H49.9816V19.4043H46.3436V11.6115H45.1077V19.4043H41.4697Z" fill="white"/>
              <path d="M53.4997 19.4043V6.50034H51.2627V3.34314H59.3747V6.50034H57.1377V19.4043H53.4997Z" fill="white"/>
              <path d="M60.1401 19.4043V3.34314H63.7781V10.6468L65.7841 3.34314H69.4221L67.0031 11.9628L69.4221 19.4043H65.7841L63.7781 12.7831V19.4043H60.1401Z" fill="white"/>
            </g>
          </svg>
          <h1>Sign in</h1>
          <p>to continue to YouTube</p>
        </div>

        {error && (
          <div className="signin-error">
            {error}
          </div>
        )}

        <div className="signin-options">
          <button
            className="google-signin-btn"
            onClick={handleGoogleSignIn}
            disabled={isSigningIn}
          >
            <svg className="google-icon" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            {isSigningIn ? 'Signing in...' : 'Continue with Google'}
          </button>
        </div>

        <div className="signin-footer">
          <p>
            By signing in, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>
    </div>
  );
}

export default SignIn;
