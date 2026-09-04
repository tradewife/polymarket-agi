'use client'

import { useLiveData } from '@/hooks/useLiveData'

function usd(n: number | null | undefined, d = 2) {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  })
}

function cents(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}¢`
}

export default function DashboardPage() {
  const { agent, markets } = useLiveData()
  const snap = agent.data
  const ledger = snap?.ledger

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-8">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">PolyAgent</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            One loop. Paper book. HOLD unless a YES+NO pair costs less than $1 after fees.
          </p>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          <div>mode {snap?.mode ?? '—'}</div>
          <div>{snap?.ts ? new Date(snap.ts).toLocaleString() : 'no snapshot yet'}</div>
        </div>
      </header>

      <section className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ['Cash', usd(ledger?.cash)],
          ['In market', usd(ledger?.reserved_notional)],
          ['Equity', usd(ledger?.equity)],
          ['Realized', usd(ledger?.realized_pnl)],
          ['Fees paid', usd(ledger?.fees_paid, 4)],
          ['Open tickets', String(ledger?.open ?? 0)],
          ['Holds this scan', String(snap?.holds ?? '—')],
          ['Arbs seen', String(snap?.arbs_seen ?? '—')],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border bg-card/40 p-3">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className="mt-1 font-mono text-lg">{value}</div>
          </div>
        ))}
      </section>

      {snap?.funder && (
        <p className="mb-8 text-xs text-muted-foreground">
          Signer {snap.signer} · funder {snap.funder} (PolyUSD here if you ever go live)
        </p>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Open paper trades
        </h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Market</th>
                <th className="px-3 py-2">Side</th>
                <th className="px-3 py-2">Price</th>
                <th className="px-3 py-2">Size</th>
                <th className="px-3 py-2">Fee</th>
                <th className="px-3 py-2">Debit</th>
              </tr>
            </thead>
            <tbody>
              {(snap?.open_trades ?? []).length === 0 && (
                <tr>
                  <td className="px-3 py-4 text-muted-foreground" colSpan={6}>
                    None. That is expected: the reasoner HOLDs without independent p_true.
                  </td>
                </tr>
              )}
              {(snap?.open_trades ?? []).map((t) => (
                <tr key={String(t.id)} className="border-t border-border/60">
                  <td className="max-w-md truncate px-3 py-2">{String(t.question)}</td>
                  <td className="px-3 py-2 font-mono">{String(t.outcome)}</td>
                  <td className="px-3 py-2 font-mono">{cents(Number(t.price))}</td>
                  <td className="px-3 py-2 font-mono">{Number(t.size).toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono">{usd(Number(t.fee ?? 0), 4)}</td>
                  <td className="px-3 py-2 font-mono">{usd(Number(t.cash_debit ?? t.notional))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Latest judgments
        </h2>
        <div className="space-y-2">
          {(snap?.judgments ?? []).slice(0, 12).map((j) => (
            <div key={j.market_id} className="rounded-lg border border-border bg-card/30 px-3 py-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-sm">{j.question}</span>
                <span className="font-mono text-xs">
                  {j.action} · book {cents(j.implied_yes)} · pair {j.pair_cost.toFixed(3)}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{j.reasoning}</p>
            </div>
          ))}
          {agent.isLoading && <p className="text-sm text-muted-foreground">Loading snapshot…</p>}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Live markets (Gamma)
        </h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Question</th>
                <th className="px-3 py-2">YES</th>
                <th className="px-3 py-2">NO</th>
                <th className="px-3 py-2">Vol</th>
              </tr>
            </thead>
            <tbody>
              {(markets.data ?? []).slice(0, 20).map((m: { id: string; title: string; yesPrice: number; noPrice: number; volume: number }) => (
                <tr key={m.id} className="border-t border-border/60">
                  <td className="max-w-lg truncate px-3 py-2">{m.title}</td>
                  <td className="px-3 py-2 font-mono">{cents(m.yesPrice)}</td>
                  <td className="px-3 py-2 font-mono">{cents(m.noPrice)}</td>
                  <td className="px-3 py-2 font-mono">{usd(m.volume, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
