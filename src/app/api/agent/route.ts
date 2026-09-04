import { NextResponse } from 'next/server'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const SNAPSHOT = path.join(process.cwd(), 'agent', 'data', 'snapshot.json')

export async function GET() {
  try {
    const raw = await readFile(SNAPSHOT, 'utf8')
    return NextResponse.json(JSON.parse(raw), {
      headers: { 'Cache-Control': 'no-store' },
    })
  } catch {
    return NextResponse.json(
      {
        ts: null,
        ledger: null,
        open_trades: [],
        recent_trades: [],
        judgments: [],
        note: 'Agent snapshot not written yet. Start: bash agent/start.sh',
      },
      { status: 200 }
    )
  }
}
