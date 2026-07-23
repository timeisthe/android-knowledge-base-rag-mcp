import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { h } from 'vue'
import './custom.css'
import ThemeSwitcher from './components/ThemeSwitcher.vue'

function scrollToHash(to: string): void {
  if (typeof window === 'undefined') return

  const hash = new URL(to, window.location.origin).hash
  if (!hash) return

  const targetId = decodeURIComponent(hash.slice(1))
  const restore = () => {
    const target = document.getElementById(targetId)
    if (!target) return

    const root = document.documentElement
    const previousBehavior = root.style.scrollBehavior
    root.style.scrollBehavior = 'auto'
    target.scrollIntoView({ block: 'start' })
    root.style.scrollBehavior = previousBehavior
  }

  // VitePress may reset scroll after hydration. Retry briefly after the first paint.
  requestAnimationFrame(restore)
  window.setTimeout(restore, 80)
  window.setTimeout(restore, 240)
}

const theme: Theme = {
  extends: DefaultTheme,
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(ThemeSwitcher),
    }),
  enhanceApp(context) {
    context.router.onAfterRouteChange = scrollToHash

    if (typeof window !== 'undefined') {
      const restoreInitialHash = () => scrollToHash(window.location.href)
      window.addEventListener('load', restoreInitialHash, { once: true })
      restoreInitialHash()
    }
  },
}

export default theme
