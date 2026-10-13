/**
 * InsForge SDK client — browser/frontend side.
 * Uses only the public anon key (VITE_INSFORGE_ANON_KEY or runtime window.__CRICKET_CONFIG__).
 * Never use the server-side API_KEY here.
 */
import { createClient } from '@insforge/sdk'

declare global {
  interface Window {
    __CRICKET_CONFIG__?: {
      insforgeUrl?: string
      insforgeAnonKey?: string
    }
  }
}

const runtimeCfg = typeof window !== 'undefined' ? window.__CRICKET_CONFIG__ : undefined

const insforgeUrl = (
  runtimeCfg?.insforgeUrl ||
  import.meta.env.VITE_INSFORGE_URL ||
  'https://asp6i95i.ap-southeast.insforge.app'
) as string

const insforgeAnonKey = (
  runtimeCfg?.insforgeAnonKey ||
  import.meta.env.VITE_INSFORGE_ANON_KEY ||
  ''
) as string

if (!insforgeUrl || !insforgeAnonKey) {
  console.warn(
    'Missing InsForge env vars. Check VITE_INSFORGE_URL and VITE_INSFORGE_ANON_KEY in Vercel Environment Variables or apps/web/.env'
  )
}

export const insforge = createClient({
  baseUrl: insforgeUrl,
  anonKey: insforgeAnonKey || 'missing-anon-key',
})
