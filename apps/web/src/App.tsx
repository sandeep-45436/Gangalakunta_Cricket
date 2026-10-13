import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './features/auth/AuthContext'
import { ProtectedRoute } from './features/auth/ProtectedRoute'
import { SignInPage } from './features/auth/SignInPage'
import { SignUpPage } from './features/auth/SignUpPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { TeamsPage } from './features/teams/TeamsPage'
import { CreateTeamPage } from './features/teams/CreateTeamPage'
import { TeamDetailPage } from './features/teams/TeamDetailPage'
import { PlayersPage } from './features/players/PlayersPage'
import { CreatePlayerPage } from './features/players/CreatePlayerPage'
import { PlayerHighlightsPage } from './features/players/PlayerHighlightsPage'
import { MatchesPage } from './features/matches/MatchesPage'
import { CreateMatchPage } from './features/matches/CreateMatchPage'
import { MatchDetailPage } from './features/matches/MatchDetailPage'
import { ScoringPage } from './features/scoring/ScoringPage'
import { RecordingPage } from './features/recording/RecordingPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/sign-in" element={<SignInPage />} />
          <Route path="/signin" element={<Navigate to="/sign-in" replace />} />
          <Route path="/sign-up" element={<SignUpPage />} />
          <Route path="/signup" element={<Navigate to="/sign-up" replace />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/teams" element={<TeamsPage />} />
            <Route path="/teams/new" element={<CreateTeamPage />} />
            <Route path="/teams/:teamId" element={<TeamDetailPage />} />
            <Route path="/players" element={<PlayersPage />} />
            <Route path="/players/new" element={<CreatePlayerPage />} />
            <Route path="/players/:playerId/highlights" element={<PlayerHighlightsPage />} />
            <Route path="/matches" element={<MatchesPage />} />
            <Route path="/matches/new" element={<CreateMatchPage />} />
            <Route path="/matches/:matchId" element={<MatchDetailPage />} />
            <Route path="/matches/:matchId/score" element={<ScoringPage />} />
            <Route path="/matches/:matchId/record" element={<RecordingPage />} />
          </Route>


          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
