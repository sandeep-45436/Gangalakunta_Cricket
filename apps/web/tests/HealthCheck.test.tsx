/**
 * HealthCheck component tests.
 * Mocks the apiClient so no real network calls are made.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { HealthCheck } from '../src/components/HealthCheck'

// Mock the API client module
vi.mock('../src/services/apiClient', () => ({
  apiClient: {
    health: vi.fn(),
    healthDb: vi.fn(),
    healthStorage: vi.fn(),
  },
}))

// Mock the InsForge client to avoid env var requirement in tests
vi.mock('../src/services/insforgeClient', () => ({
  insforge: {},
}))

import { apiClient } from '../src/services/apiClient'

describe('HealthCheck', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows ok status when all services respond successfully', async () => {
    vi.mocked(apiClient.health).mockResolvedValue({ status: 'ok', service: 'cricket-api' })
    vi.mocked(apiClient.healthDb).mockResolvedValue({ status: 'ok', db: 'connected' })
    vi.mocked(apiClient.healthStorage).mockResolvedValue({ status: 'ok', storage: 'reachable' })

    render(<HealthCheck />)

    await waitFor(() => {
      const badges = screen.getAllByText('ok')
      expect(badges).toHaveLength(3)
    })
  })

  it('shows error when API is unreachable', async () => {
    vi.mocked(apiClient.health).mockRejectedValue(new Error('Network error'))
    vi.mocked(apiClient.healthDb).mockResolvedValue({ status: 'ok', db: 'connected' })
    vi.mocked(apiClient.healthStorage).mockResolvedValue({ status: 'ok', storage: 'reachable' })

    render(<HealthCheck />)

    await waitFor(() => {
      expect(screen.getByText('error')).toBeInTheDocument()
    })
  })

  it('renders service names in the table', () => {
    vi.mocked(apiClient.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(apiClient.healthDb).mockResolvedValue({ status: 'ok' })
    vi.mocked(apiClient.healthStorage).mockResolvedValue({ status: 'ok' })

    render(<HealthCheck />)

    expect(screen.getByText('API')).toBeInTheDocument()
    expect(screen.getByText('Database')).toBeInTheDocument()
    expect(screen.getByText('Storage')).toBeInTheDocument()
  })
})
