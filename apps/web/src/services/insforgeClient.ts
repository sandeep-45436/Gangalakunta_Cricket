/**
 * InsForge SDK client — browser/frontend side.
 * Uses only the public anon key (VITE_INSFORGE_ANON_KEY).
 * Never use the server-side API_KEY here.
 */
import { createClient } from '@insforge/sdk'

const insforgeUrl = import.meta.env.VITE_INSFORGE_URL as string
const insforgeAnonKey = import.meta.env.VITE_INSFORGE_ANON_KEY as string

if (!insforgeUrl || !insforgeAnonKey) {
  throw new Error(
    'Missing InsForge env vars. Check VITE_INSFORGE_URL and VITE_INSFORGE_ANON_KEY in apps/web/.env'
  )
}

export const insforge = createClient({
  baseUrl: insforgeUrl,
  anonKey: insforgeAnonKey,
})
