import http from 'k6/http'
import { check, sleep } from 'k6'

export const options = {
  scenarios: {
    pilot_smoke: {
      executor: 'constant-vus',
      vus: Number(__ENV.LOAD_VUS || 10),
      duration: __ENV.LOAD_DURATION || '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<750'],
    checks: ['rate>0.99'],
  },
}

const baseUrl = __ENV.BASE_URL || 'https://caddy'

export default function () {
  const page = http.get(`${baseUrl}/`, { responseCallback: http.expectedStatuses(200) })
  check(page, { 'frontend available': (response) => response.status === 200 })
  const health = http.get(`${baseUrl}/api/v1/health/live`, {
    responseCallback: http.expectedStatuses(200),
  })
  check(health, { 'API healthy': (response) => response.status === 200 })
  sleep(1)
}
