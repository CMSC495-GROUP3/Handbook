import client from './client'
import type { CoverageReport } from '../types'

/** Refused and repeated questions over the last `days` days. */
export async function getCoverageReport(days: number): Promise<CoverageReport> {
  const response = await client.get<CoverageReport>('/api/reports/gaps', { params: { days } })
  return response.data
}
