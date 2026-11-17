import { Hono } from 'hono'
import { renderer } from './renderer'
import { Dashboard } from './components/Dashboard'
import { getGcpAccessToken } from './gcp-auth'

type Bindings = {
  AGENT_RUNTIME_API_URL?: string
  GCP_SA_KEY_JSON?: string
}

const app = new Hono<{ Bindings: Bindings }>()

app.all('/api/adk/*', async (c) => {
  const url = new URL(c.req.url)
  const subPath = url.pathname.replace(/^\/api\/adk/, '')
  const baseUrl = (c.env?.AGENT_RUNTIME_API_URL || 'http://localhost:8000').replace(/\/$/, '')
  const targetUrl = `${baseUrl}${subPath}${url.search}`

  const headers = new Headers()
  const contentType = c.req.header('content-type')
  if (contentType) headers.set('content-type', contentType)
  const accept = c.req.header('accept')
  if (accept) headers.set('accept', accept)

  if (c.env?.GCP_SA_KEY_JSON) {
    const token = await getGcpAccessToken(c.env.GCP_SA_KEY_JSON)
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(targetUrl, {
    method: c.req.method,
    headers,
    body: ['GET', 'HEAD'].includes(c.req.method) ? undefined : c.req.raw.body,
  })

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  })
})

app.use(renderer)

app.get('/', async (c) => {
  return c.render(
    <main class="app-layout">
      <Dashboard />
    </main>
  )
})

export default app
