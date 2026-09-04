'use client'

import { useQuery } from '@tanstack/react-query'

export type AgentSnapshot = {
  ts: string | null
  mode?: string
  signer?: string
  funder?: string
  holds?: number
  arbs_seen?: number
  note?: string
  ledger: {
    cash: number
    starting_cash: number
    reserved_notional: number
    equity: number
    fees_paid: number
    realized_pnl: number
    open: number
  } | null
  open_trades: Array<Record<string, unknown>>
  recent_trades: Array<Record<string, unknown>>
  judgments: Array<{
    market_id: string
    question: string
    action: string
    reasoning: string
    implied_yes: number
    edge_after_fees: number
    kelly_fraction: number
    pair_cost: number
  }>
}

async function fetchSnapshot(): Promise<AgentSnapshot> {
  const res = await fetch('/api/agent', { cache: 'no-store' })
  if (!res.ok) throw new Error(`agent ${res.status}`)
  return res.json()
}

async function fetchMarkets() {
  const res = await fetch('/api/markets?limit=40&active=true', { cache: 'no-store' })
  if (!res.ok) return []
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export function useLiveData() {
  const agent = useQuery({
    queryKey: ['agent-snapshot'],
    queryFn: fetchSnapshot,
    refetchInterval: 10_000,
  })
  const markets = useQuery({
    queryKey: ['markets'],
    queryFn: fetchMarkets,
    refetchInterval: 30_000,
  })
  return { agent, markets }
}
