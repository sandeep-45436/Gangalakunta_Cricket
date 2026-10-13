/**
 * HealthCheck component.
 * Calls the FastAPI health endpoints and displays their status.
 * Used on the home screen to confirm end-to-end connectivity.
 */
import { useEffect, useState } from 'react'
import { apiClient, type HealthResponse } from '../services/apiClient'

interface CheckState {
  status: 'loading' | 'ok' | 'error'
  detail?: string
}

function StatusBadge({ state }: { state: CheckState }) {
  const colors: Record<CheckState['status'], string> = {
    loading: '#888',
    ok: '#22c55e',
    error: '#ef4444',
  }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 12,
        background: colors[state.status],
        color: '#fff',
        fontWeight: 600,
        fontSize: 13,
      }}
    >
      {state.status === 'loading' ? '…' : state.status}
    </span>
  )
}

export function HealthCheck() {
  const [api, setApi] = useState<CheckState>({ status: 'loading' })
  const [db, setDb] = useState<CheckState>({ status: 'loading' })
  const [storage, setStorage] = useState<CheckState>({ status: 'loading' })

  useEffect(() => {
    apiClient
      .health()
      .then((r: HealthResponse) =>
        setApi({ status: r.status === 'ok' ? 'ok' : 'error', detail: r.service })
      )
      .catch((e: unknown) => setApi({ status: 'error', detail: String(e) }))

    apiClient
      .healthDb()
      .then((r: HealthResponse) => setDb({ status: r.status === 'ok' ? 'ok' : 'error', detail: r.db }))
      .catch((e: unknown) => setDb({ status: 'error', detail: String(e) }))

    apiClient
      .healthStorage()
      .then((r: HealthResponse) =>
        setStorage({ status: r.status === 'ok' ? 'ok' : 'error', detail: r.storage })
      )
      .catch((e: unknown) => setStorage({ status: 'error', detail: String(e) }))
  }, [])

  return (
    <div
      style={{
        fontFamily: 'system-ui, sans-serif',
        maxWidth: 480,
        margin: '0 auto',
        padding: 24,
      }}
    >
      <h2 style={{ marginBottom: 8 }}>🏏 Cricket Highlights</h2>
      <p style={{ color: '#666', marginBottom: 24 }}>Phase 0 — System Connectivity</p>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '6px 12px', borderBottom: '1px solid #e5e7eb' }}>Service</th>
            <th style={{ textAlign: 'left', padding: '6px 12px', borderBottom: '1px solid #e5e7eb' }}>Status</th>
            <th style={{ textAlign: 'left', padding: '6px 12px', borderBottom: '1px solid #e5e7eb' }}>Detail</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={{ padding: '8px 12px' }}>API</td>
            <td style={{ padding: '8px 12px' }}><StatusBadge state={api} /></td>
            <td style={{ padding: '8px 12px', color: '#666', fontSize: 13 }}>{api.detail ?? ''}</td>
          </tr>
          <tr style={{ background: '#f9fafb' }}>
            <td style={{ padding: '8px 12px' }}>Database</td>
            <td style={{ padding: '8px 12px' }}><StatusBadge state={db} /></td>
            <td style={{ padding: '8px 12px', color: '#666', fontSize: 13 }}>{db.detail ?? ''}</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px' }}>Storage</td>
            <td style={{ padding: '8px 12px' }}><StatusBadge state={storage} /></td>
            <td style={{ padding: '8px 12px', color: '#666', fontSize: 13 }}>{storage.detail ?? ''}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
