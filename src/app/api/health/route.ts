import { NextResponse } from 'next/server'
import { access } from 'node:fs/promises'
import path from 'node:path'

export async function GET() {
  const snapshot = path.join(process.cwd(), 'agent', 'data', 'snapshot.json')
  let agentSnapshot = false
  try {
    await access(snapshot)
    agentSnapshot = true
  } catch {
    agentSnapshot = false
  }
  return NextResponse.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    agentSnapshot,
  })
}
