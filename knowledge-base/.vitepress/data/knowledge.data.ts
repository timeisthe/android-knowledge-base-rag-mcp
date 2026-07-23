import { createContentLoader } from 'vitepress'

export interface KnowledgeArticle {
  category: string
  description: string
  difficulty?: string
  readingMinutes: number
  subcategory?: string
  tags: string[]
  title: string
  updatedAt?: string
  url: string
}

function buildDescription(source: string): string {
  const body = source
    .replace(/^---[\s\S]*?^---\s*/m, '')
    .replace(/^#{1,6}\s+.+$/gm, '')
    .replace(/```[\s\S]*?```/g, '')

  const paragraph = body
    .split(/\n\s*\n/)
    .map((part) => part.replace(/[`*_>#\[\]]/g, '').replace(/\s+/g, ' ').trim())
    .find((part) => part && !part.startsWith('- ') && !part.startsWith('|'))

  if (!paragraph) return '打开文章查看完整知识点。'
  return paragraph.length > 96 ? `${paragraph.slice(0, 96)}…` : paragraph
}

function estimateReadingMinutes(source: string): number {
  const content = source
    .replace(/^---[\s\S]*?^---\s*/m, '')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/[#>*_`|\[\]()-]/g, '')
    .replace(/\s+/g, '')

  return Math.max(1, Math.ceil(content.length / 500))
}

export default createContentLoader<KnowledgeArticle[]>(['**/*.md', '!index.md'], {
  includeSrc: true,
  render: false,
  transform(pages) {
    return pages
      .filter((page) => page.url !== '/')
      .map((page) => {
        const source = page.src ?? ''
        const segments = page.url.split('/').filter(Boolean)
        const title = page.frontmatter.title
          ?? source.match(/^#\s+(.+)$/m)?.[1]
          ?? segments.at(-1)
          ?? '未命名文章'

        return {
          category: page.frontmatter.category ?? segments[0] ?? 'uncategorized',
          description: page.frontmatter.description ?? buildDescription(source),
          difficulty: page.frontmatter.difficulty,
          readingMinutes: estimateReadingMinutes(source),
          subcategory: page.frontmatter.subcategory ?? segments[1],
          tags: Array.isArray(page.frontmatter.tags) ? page.frontmatter.tags : [],
          title,
          updatedAt: page.frontmatter.updated_at ?? page.frontmatter.created_at,
          url: page.url,
        }
      })
      .sort((a, b) => {
        const dateOrder = (b.updatedAt ?? '').localeCompare(a.updatedAt ?? '')
        return dateOrder || a.title.localeCompare(b.title, 'zh-CN')
      })
  },
})
