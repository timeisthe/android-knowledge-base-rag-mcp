<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

interface ThemeOption {
  id: string
  label: string
  swatch: string
  isDark: boolean
}

const themes: ThemeOption[] = [
  { id: 'green',      label: '亮绿',  swatch: '#16864b', isDark: false },
  { id: 'paper',      label: '纸皮',  swatch: '#8b7355', isDark: false },
  { id: 'green-dark', label: '暗绿',  swatch: '#52dd91', isDark: true  },
  { id: 'teal-dark',  label: '暗青',  swatch: '#2dd4bf', isDark: true  },
]

const current = ref('green')
const open = ref(false)
const root = ref<HTMLElement>()

function applyTheme(themeId: string) {
  const rootEl = document.documentElement
  const opt = themes.find(t => t.id === themeId) ?? themes[0]

  rootEl.setAttribute('data-theme', opt.id)

  if (opt.isDark) {
    rootEl.classList.add('dark')
  } else {
    rootEl.classList.remove('dark')
  }

  // 同步 VitePress 内部的暗色状态
  try {
    localStorage.setItem('vueuse-color-scheme', opt.isDark ? 'dark' : 'light')
    localStorage.setItem('is-dark', opt.isDark ? 'true' : 'false')
  } catch {}

  localStorage.setItem('kb-theme', opt.id)
  current.value = opt.id

  // 更新 meta theme-color
  const metas = document.querySelectorAll('meta[name="theme-color"]')
  if (metas.length > 0) {
    const darkColors: Record<string, string> = { 'green-dark': '#0e1410', 'teal-dark': '#0a0f1a' }
    const lightColors: Record<string, string> = { green: '#16864b', paper: '#8b7355' }
    metas[0].setAttribute('content', darkColors[opt.id] ?? lightColors[opt.id] ?? '#16864b')
  }
}

function selectTheme(themeId: string) {
  applyTheme(themeId)
  open.value = false
}

function toggleDropdown() {
  open.value = !open.value
}

function handleClickOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => {
  const saved = localStorage.getItem('kb-theme') || 'green'
  applyTheme(saved)
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div ref="root" class="theme-switcher">
    <button
      class="ts-btn"
      :class="{ 'ts-btn--active': open }"
      aria-label="选择主题"
      @click="toggleDropdown"
    >
      <span
        class="ts-swatch"
        :style="{ background: themes.find(t => t.id === current)?.swatch ?? '#16864b' }"
      />
      <svg class="ts-chevron" viewBox="0 0 20 20" aria-hidden="true">
        <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <Transition name="ts-pop">
      <div v-if="open" class="ts-dropdown" role="menu">
        <p class="ts-title">主题颜色</p>
        <button
          v-for="t in themes"
          :key="t.id"
          class="ts-option"
          :class="{ 'ts-option--current': t.id === current }"
          role="menuitem"
          @click="selectTheme(t.id)"
        >
          <span class="ts-swatch" :style="{ background: t.swatch }" />
          <span class="ts-label">{{ t.label }}</span>
          <svg v-if="t.id === current" class="ts-check" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M5 10l3.5 3.5L15 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.theme-switcher {
  display: inline-flex;
  position: relative;
  align-items: center;
  margin-left: 8px;
}

.ts-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  padding: 6px 8px;
  height: 36px;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.ts-btn:hover {
  background: var(--vp-c-bg-soft);
  border-color: var(--vp-c-brand-1);
}

.ts-btn--active {
  border-color: var(--vp-c-brand-1);
  background: var(--vp-c-bg-soft);
}

.ts-swatch {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 0 0 1px var(--vp-c-divider);
  flex-shrink: 0;
}

.ts-chevron {
  width: 14px;
  height: 14px;
  color: var(--vp-c-text-2);
  transition: transform 0.2s ease;
}

.ts-btn--active .ts-chevron {
  transform: rotate(180deg);
}

.ts-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 50;
  min-width: 152px;
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
  padding: 6px;
}

.ts-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--vp-c-text-3);
  padding: 6px 10px 4px;
  margin: 0;
  text-transform: uppercase;
}

.ts-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 0;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  padding: 7px 10px;
  font-size: 13px;
  font-weight: 550;
  color: var(--vp-c-text-1);
  transition: background 0.15s ease;
}

.ts-option:hover {
  background: var(--vp-c-bg-soft);
}

.ts-option--current {
  color: var(--vp-c-brand-1);
  font-weight: 650;
}

.ts-label {
  flex: 1;
  text-align: left;
}

.ts-check {
  width: 16px;
  height: 16px;
  color: var(--vp-c-brand-1);
}

.ts-pop-enter-active,
.ts-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.ts-pop-enter-from,
.ts-pop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
