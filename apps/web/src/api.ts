export type Theme = 'light' | 'dark'
export type Accent = {preset: 'forest' | 'ocean'; revision: number}
export interface SettingsRecord {
  version: 1
  revision: number
  theme: Theme
}
export interface Account {
  address: string
  status: 'available' | 'unavailable'
  source: string
  observedAt: string | null
  checkedAt: string
  message: string
  positions: {
    conditionId?: string
    endDate?: string
    market: string
    outcome: string
    shares: string
    markedValue?: string
    status?: 'OPEN' | 'REDEEMABLE'
  }[]
  concentration?: {conditionId: string; market: string; marketCount: number; percent: string; tied: boolean} | null
  complete: boolean
  nextCursor: string | null
  lastSuccessful?: Pick<Account, 'source' | 'observedAt' | 'positions' | 'complete'>
}
export interface Leader {
  id: string
  name: string
  handle: string
  category: string
  description: string
  pnl: string
  volume: string
  markets: number
  win_rate: number
  history: number[]
  color: string
  market: string
}
export interface ScenarioPolicy {
  version: number
  fee_bps: number
  delay_seconds: number
  max_age_seconds: number
  max_slippage_cents: number
  lot_shares: number
}

export interface ScenarioLimits {
  min_allocation: string
  max_allocation: string
  min_order_size: string
  max_order_size: string
}

export interface Directory {
  leaders: Leader[]
  policy: ScenarioPolicy
  limits: ScenarioLimits
}

export interface Signal {
  id: string
  market: string
  side: string
  status: string
  reason: string
  requested: string | null
  filled: string
  quantity: string
  price: string | null
  fee: string
  observed_at: string
  decided_at: string
}
export interface Run {
  id: string
  leader_id: string
  leader_name: string
  status: 'running' | 'paused' | 'completed' | 'stopped'
  revision: number
  capital: string
  order_size: string
  cash: string
  quantity: string
  cost_basis: string
  fees: string
  realized_pnl: string
  marked_value: string | null
  marked_net_result: string | null
  liquidation_value: string | null
  events: Signal[]
  cursor: number
  total_steps: number
  source: 'scenario'
  market: string
  observation_start: string
  remaining_steps: number
}
export interface Workspace {
  accent: Accent
  savedWallets: { address: string; label: string }[]
  accountRevision: number
  settings: SettingsRecord
  account: Account | null
  run: Run | null
}
export async function apiResponse(path: string, method = 'GET', body?: unknown): Promise<Response> {
  const options: RequestInit = { method, cache: 'no-store', credentials: 'same-origin' }
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' }
    options.body = JSON.stringify(body)
  }
  const response = await fetch('/api/v1/' + path, options)
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    throw new Error(result.error || 'Request failed (' + response.status + '). Try again.')
  }
  return response
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  return (await apiResponse(path, method, body)).json()
}
export const money = (value: number | string, digits = 2) =>
  Number(value).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
export const signed = (value: number | string, digits = 0) =>
  (Number(value) > 0 ? '+' : '') + money(value, digits)
export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'The request could not be completed.'

export function validBuyBudget(value: string | null): value is string {
  return value !== null && /^\d+(?:\.\d{1,2})?$/.test(value) && Number(value) >= 1 && Number(value) <= 1000
}
