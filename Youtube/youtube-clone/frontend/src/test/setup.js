/**
 * Vitest test setup file
 * Runs before each test file
 */

import '@testing-library/jest-dom'

// Mock window.matchMedia (used by some UI components)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock IntersectionObserver (used by lazy loading)
class IntersectionObserverMock {
  constructor(callback) {
    this.callback = callback
  }
  observe() { return null }
  unobserve() { return null }
  disconnect() { return null }
}
window.IntersectionObserver = IntersectionObserverMock

// Mock ResizeObserver
class ResizeObserverMock {
  observe() { return null }
  unobserve() { return null }
  disconnect() { return null }
}
window.ResizeObserver = ResizeObserverMock

// Suppress React Router console warnings in tests
const originalError = console.error
console.error = (...args) => {
  if (
    typeof args[0] === 'string' &&
    args[0].includes('React Router')
  ) {
    return
  }
  originalError.call(console, ...args)
}
