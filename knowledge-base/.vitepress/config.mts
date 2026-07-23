import { defineConfig } from 'vitepress'
import { fileURLToPath, URL } from 'node:url'
import { generateSidebar } from './sidebar'

const knowledgeRoot = fileURLToPath(new URL('..', import.meta.url))

export default defineConfig({
  lang: 'zh-CN',
  title: 'Android 知识库',
  description: '面向 Android 学习与面试复习的本地优先知识库',
  cleanUrls: true,
  lastUpdated: true,
  head: [
    ['meta', { name: 'theme-color', content: '#3ddc84' }],
  ],
  markdown: {
    lineNumbers: true,
  },
  themeConfig: {
    logo: {
      src: '/android-robot.svg',
      alt: 'Android 知识库',
    },
    nav: [
      { text: '首页', link: '/' },
      { text: '知识目录', link: '/#knowledge-map' },
      { text: '最近更新', link: '/#latest' },
      { text: '工作方式', link: '/#workflow' },
    ],
    sidebar: generateSidebar(knowledgeRoot),
    outline: {
      level: [2, 3],
      label: '本页目录',
    },
    search: {
      provider: 'local',
      options: {
        miniSearch: {
          searchOptions: {
            fuzzy: 0.2,
            prefix: true,
          },
        },
        translations: {
          button: {
            buttonText: '搜索知识点',
            buttonAriaLabel: '搜索知识点',
          },
          modal: {
            displayDetails: '显示详细列表',
            resetButtonTitle: '清除搜索条件',
            backButtonTitle: '关闭搜索',
            noResultsText: '没有找到相关知识点',
            footer: {
              selectText: '选择',
              navigateText: '切换',
              closeText: '关闭',
            },
          },
        },
      },
    },
    socialLinks: [],
    footer: {
      message: '本地优先 · Markdown 驱动 · RAG 按需检索 · MCP 安全编辑',
      copyright: 'Android Knowledge Base',
    },
    darkModeSwitchLabel: '切换深色模式',
    lightModeSwitchTitle: '切换浅色模式',
    darkModeSwitchTitle: '切换深色模式',
    sidebarMenuLabel: '知识目录',
    returnToTopLabel: '返回顶部',
    lastUpdated: {
      text: '最后更新',
      formatOptions: {
        dateStyle: 'medium',
        timeStyle: 'short',
      },
    },
    docFooter: {
      prev: '上一篇',
      next: '下一篇',
    },
  },
})
