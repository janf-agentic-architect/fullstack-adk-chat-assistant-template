import { Hono } from 'hono'
import { renderer } from './renderer'
import { Dashboard } from './components/Dashboard'

const app = new Hono()

app.use(renderer)

app.get('/', async (c) => {
  return c.render(
    <main class="app-layout">
      <Dashboard />
    </main>
  )
})

export default app
