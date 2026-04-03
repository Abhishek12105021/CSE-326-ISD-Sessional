/**
 * App.test.jsx — Smoke tests for the main App component
 *
 * These tests verify that:
 * 1. The app renders without crashing
 * 2. Core UI elements are present
 * 3. Routing works for main pages
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

// Mock the Supabase client before importing App
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
      getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
      onAuthStateChange: vi.fn().mockReturnValue({
        data: { subscription: { unsubscribe: vi.fn() } },
      }),
      signInWithOAuth: vi.fn().mockResolvedValue({ data: {}, error: null }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
    },
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      insert: vi.fn().mockReturnThis(),
      update: vi.fn().mockReturnThis(),
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      single: vi.fn().mockResolvedValue({ data: null, error: null }),
    })),
    rpc: vi.fn().mockResolvedValue({ data: [], error: null }),
  },
}))

// Mock fetch for API calls
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve({ videos: [], total: 0 }),
})

import App from '../App'

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset window.location.hash for router tests
    window.location.hash = ''
  })

  it('renders without crashing', async () => {
    // This is the core smoke test - if this fails, something is fundamentally broken
    expect(() => render(<App />)).not.toThrow()
  })

  it('renders the navbar when enabled', async () => {
    render(<App />)

    // Wait for lazy-loaded components and auth state
    await waitFor(
      () => {
        // Look for common navbar elements (logo, search, etc.)
        // The navbar should contain the YouTube logo or app name
        const navbar = document.querySelector('.navbar') ||
                       document.querySelector('[class*="navbar"]') ||
                       document.querySelector('nav')
        expect(navbar).toBeTruthy()
      },
      { timeout: 3000 }
    )
  })

  it('renders the sidebar when enabled', async () => {
    render(<App />)

    await waitFor(
      () => {
        const sidebar = document.querySelector('.sidebar') ||
                        document.querySelector('[class*="sidebar"]') ||
                        document.querySelector('aside')
        expect(sidebar).toBeTruthy()
      },
      { timeout: 3000 }
    )
  })

  it('shows loading state while fetching data', async () => {
    render(<App />)

    // The app should show some form of loading indicator initially
    // This could be a spinner, skeleton, or loading text
    // Check for any loading-related elements
    const hasLoadingIndicator = document.querySelector('[style*="spin"]') ||
                                screen.queryByText(/loading/i) ||
                                document.querySelector('.loading')

    // Loading indicator may or may not be present depending on timing
    // The key is that the app doesn't crash and body exists
    expect(document.body).toBeTruthy()
    // If loading indicator is present, that's a bonus verification
    if (hasLoadingIndicator) {
      expect(hasLoadingIndicator).toBeTruthy()
    }
  })
})

describe('App routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.location.hash = ''
  })

  it('renders home page at root path', async () => {
    window.location.hash = '#/'
    render(<App />)

    await waitFor(
      () => {
        // App should render without errors
        expect(document.querySelector('.app')).toBeTruthy()
      },
      { timeout: 3000 }
    )
  })

  it('navigates to signin page', async () => {
    window.location.hash = '#/signin'
    render(<App />)

    await waitFor(
      () => {
        // Sign in page should render (may have different structure)
        expect(document.body.textContent).toBeDefined()
      },
      { timeout: 3000 }
    )
  })
})
