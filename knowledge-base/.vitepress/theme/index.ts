import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import './custom.css'
import ThemeSwitcher from './components/ThemeSwitcher.vue'

export default {
  extends: DefaultTheme,
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(ThemeSwitcher),
    }),
}
