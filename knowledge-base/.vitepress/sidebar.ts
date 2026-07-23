import { readdirSync, readFileSync } from 'node:fs'
import { basename, join, relative, sep } from 'node:path'
import type { DefaultTheme } from 'vitepress'

const labels: Record<string, string> = {
  'android-framework': 'Android 框架核心',
  'computer-science': '计算机基础',
  'four-components': '四大组件',
  'view-system': 'View 体系',
  jetpack: 'Jetpack 组件',
  compose: 'Jetpack Compose',
  'third-party-libs': '常用第三方库',
  networking: '网络库',
  'image-loading': '图片加载',
  'dependency-injection': '依赖注入',
  reactive: '响应式与异步',
  serialization: '序列化',
  java: 'Java 基础',
  jvm: 'JVM',
  concurrency: '并发编程',
  kotlin: 'Kotlin',
  coroutines: '协程',
  architecture: '架构与设计',
  performance: '性能优化',
  'interview-topics': '面试专题',
}

const topLevelOrder = [
  'computer-science',
  'android-framework',
  'jetpack',
  'compose',
  'third-party-libs',
  'java',
  'kotlin',
  'architecture',
  'performance',
  'interview-topics',
]

function titleFromMarkdown(filePath: string): string {
  const source = readFileSync(filePath, 'utf8')
  const frontmatterTitle = source.match(/^---[\s\S]*?^title:\s*["']?(.+?)["']?\s*$[\s\S]*?^---/m)
  if (frontmatterTitle?.[1]) return frontmatterTitle[1]

  const heading = source.match(/^#\s+(.+)$/m)
  return heading?.[1] ?? basename(filePath, '.md')
}

function sortEntries(a: string, b: string): number {
  const aIndex = topLevelOrder.indexOf(a)
  const bIndex = topLevelOrder.indexOf(b)
  if (aIndex >= 0 || bIndex >= 0) {
    return (aIndex < 0 ? Number.MAX_SAFE_INTEGER : aIndex)
      - (bIndex < 0 ? Number.MAX_SAFE_INTEGER : bIndex)
  }
  return a.localeCompare(b, 'zh-CN')
}

export function generateSidebar(root: string): DefaultTheme.SidebarItem[] {
  function walk(directory: string): DefaultTheme.SidebarItem[] {
    return readdirSync(directory, { withFileTypes: true })
      .filter((entry) => !entry.name.startsWith('.') && entry.name !== 'index.md')
      .sort((a, b) => sortEntries(a.name, b.name))
      .flatMap((entry): DefaultTheme.SidebarItem[] => {
        const absolutePath = join(directory, entry.name)

        if (entry.isDirectory()) {
          const items = walk(absolutePath)
          if (items.length === 0) return []
          return [{
            text: labels[entry.name] ?? entry.name,
            collapsed: relative(root, absolutePath).includes(sep),
            items,
          }]
        }

        if (!entry.isFile() || !entry.name.endsWith('.md')) return []
        const link = `/${relative(root, absolutePath).split(sep).join('/').replace(/\.md$/, '')}`
        return [{ text: titleFromMarkdown(absolutePath), link }]
      })
  }

  return walk(root)
}
