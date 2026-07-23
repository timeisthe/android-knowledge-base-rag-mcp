<script setup lang="ts">
import { computed } from 'vue'
import { data as articles } from '../../data/knowledge.data'

const categoryLabels: Record<string, string> = {
  'android-framework': 'Android 框架',
  architecture: '架构与设计',
  'computer-science': '计算机基础',
  compose: 'Jetpack Compose',
  'interview-topics': '面试专题',
  java: 'Java 基础',
  jetpack: 'Jetpack',
  kotlin: 'Kotlin',
  performance: '性能优化',
  'third-party-libs': '第三方库',
  uncategorized: '其他知识',
}

const categoryMarks: Record<string, string> = {
  'android-framework': 'AF',
  architecture: 'AR',
  'computer-science': 'CS',
  compose: 'CO',
  'interview-topics': 'IT',
  java: 'JV',
  jetpack: 'JP',
  kotlin: 'KT',
  performance: 'PF',
  'third-party-libs': 'LIB',
  uncategorized: 'KB',
}

const difficultyLabels: Record<string, string> = {
  easy: '入门',
  medium: '进阶',
  hard: '深入',
}

const categories = computed(() => {
  const grouped = new Map<string, typeof articles>()

  for (const article of articles) {
    const group = grouped.get(article.category) ?? []
    group.push(article)
    grouped.set(article.category, group)
  }

  return [...grouped.entries()].map(([key, items]) => ({
    key,
    label: categoryLabels[key] ?? key,
    mark: categoryMarks[key] ?? key.slice(0, 2).toUpperCase(),
    count: items.length,
    firstArticle: items[0],
    tags: [...new Set(items.flatMap((item) => item.tags))]
      .filter((tag) => tag !== key && tag !== '高频')
      .slice(0, 3),
  }))
})

const primaryArticle = computed(() => articles[0])
const recentArticles = computed(() => articles.slice(0, 6))
const tagCount = computed(() => new Set(articles.flatMap((article) => article.tags)).size)

function formatDate(value?: string): string {
  if (!value) return '持续更新'
  return value.replaceAll('-', '.')
}

function openSearch(): void {
  const trigger = document.querySelector<HTMLButtonElement>(
    '.VPNavBarSearch button, .DocSearch-Button, button[aria-label="搜索知识点"]',
  )
  trigger?.click()
}
</script>

<template>
  <main class="kb-home">
    <section class="kb-hero" aria-labelledby="knowledge-base-title">
      <div class="kb-hero__copy">
        <p class="kb-eyebrow">
          <span class="kb-eyebrow__dot" aria-hidden="true" />
          LOCAL-FIRST KNOWLEDGE BASE
        </p>
        <h1 id="knowledge-base-title">
          把知识整理成体系
          <span>随时检索，持续复习</span>
        </h1>
        <p class="kb-hero__description">
          面向 Android 学习与面试复习的个人知识库。内容由 Markdown 沉淀，
          通过本地搜索快速查阅，也可由 MCP 与 RAG 按需读取和维护。
        </p>

        <div class="kb-hero__actions">
          <a
            v-if="primaryArticle"
            class="kb-button kb-button--primary"
            :href="primaryArticle.url"
          >
            开始阅读
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 10h11m-4-4 4 4-4 4" />
            </svg>
          </a>
          <a v-else class="kb-button kb-button--primary" href="#knowledge-map">
            查看知识目录
          </a>
          <button class="kb-button kb-button--secondary" type="button" @click="openSearch">
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="9" cy="9" r="5.5" />
              <path d="m13 13 3.5 3.5" />
            </svg>
            搜索知识点
            <kbd>⌘ K</kbd>
          </button>
        </div>

        <ul class="kb-hero__principles" aria-label="知识库特性">
          <li><span aria-hidden="true">✓</span> Markdown 是唯一事实来源</li>
          <li><span aria-hidden="true">✓</span> 本地优先，内容自主可控</li>
          <li><span aria-hidden="true">✓</span> 首页随文章自动更新</li>
        </ul>
      </div>

      <aside class="kb-overview" aria-label="知识库概览">
        <div class="kb-overview__header">
          <div>
            <span class="kb-overview__label">KNOWLEDGE OVERVIEW</span>
            <strong>知识库概览</strong>
          </div>
          <span class="kb-status"><i aria-hidden="true" /> 可用</span>
        </div>

        <div class="kb-overview__stats">
          <div>
            <strong>{{ articles.length }}</strong>
            <span>篇文档</span>
          </div>
          <div>
            <strong>{{ categories.length }}</strong>
            <span>个主题</span>
          </div>
          <div>
            <strong>{{ tagCount }}</strong>
            <span>个标签</span>
          </div>
        </div>

        <div v-if="primaryArticle" class="kb-overview__latest">
          <span class="kb-overview__latest-label">最近更新</span>
          <a :href="primaryArticle.url">
            <span>{{ primaryArticle.title }}</span>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 10h11m-4-4 4 4-4 4" />
            </svg>
          </a>
          <div>
            <span>{{ categoryLabels[primaryArticle.category] ?? primaryArticle.category }}</span>
            <span>约 {{ primaryArticle.readingMinutes }} 分钟</span>
            <time :datetime="primaryArticle.updatedAt">{{ formatDate(primaryArticle.updatedAt) }}</time>
          </div>
        </div>

        <div v-else class="kb-overview__empty">
          还没有文章。通过 MCP 创建文档后，这里会自动出现最新内容。
        </div>

        <div class="kb-overview__pipeline" aria-label="内容工作流">
          <span>Markdown</span>
          <i aria-hidden="true">→</i>
          <span>VitePress</span>
          <i aria-hidden="true">→</i>
          <span>RAG / MCP</span>
        </div>
      </aside>
    </section>

    <section id="knowledge-map" class="kb-section kb-catalog">
      <div class="kb-section__heading">
        <div>
          <p class="kb-section__kicker">KNOWLEDGE MAP</p>
          <h2>按主题进入知识体系</h2>
          <p>目录由文章元数据自动生成，新增内容后无需手工维护首页入口。</p>
        </div>
        <button type="button" class="kb-text-button" @click="openSearch">
          搜索全部内容
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11m-4-4 4 4-4 4" /></svg>
        </button>
      </div>

      <div v-if="categories.length" class="kb-category-grid">
        <a
          v-for="category in categories"
          :key="category.key"
          class="kb-category-card"
          :href="category.firstArticle.url"
        >
          <span class="kb-category-card__mark">{{ category.mark }}</span>
          <span class="kb-category-card__body">
            <span class="kb-category-card__topline">
              <strong>{{ category.label }}</strong>
              <span>{{ category.count }} 篇</span>
            </span>
            <span class="kb-category-card__title">{{ category.firstArticle.title }}</span>
            <span v-if="category.tags.length" class="kb-category-card__tags">
              <em v-for="tag in category.tags" :key="tag">{{ tag }}</em>
            </span>
          </span>
          <svg class="kb-category-card__arrow" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M4 10h11m-4-4 4 4-4 4" />
          </svg>
        </a>
      </div>
      <div v-else class="kb-empty-state">
        <span class="kb-empty-state__icon">KB</span>
        <h3>知识库正在等待第一篇文章</h3>
        <p>通过 MCP 创建 Markdown 文档后，分类和入口会自动出现在这里。</p>
      </div>
    </section>

    <section id="latest" class="kb-section kb-latest">
      <div class="kb-section__heading">
        <div>
          <p class="kb-section__kicker">RECENTLY UPDATED</p>
          <h2>最近整理</h2>
          <p>从最近更新的知识点继续阅读，让复习路径保持连续。</p>
        </div>
      </div>

      <div v-if="recentArticles.length" class="kb-article-list">
        <a
          v-for="(article, index) in recentArticles"
          :key="article.url"
          class="kb-article-row"
          :href="article.url"
        >
          <span class="kb-article-row__index">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="kb-article-row__content">
            <span class="kb-article-row__meta">
              {{ categoryLabels[article.category] ?? article.category }}
              <i aria-hidden="true" />
              约 {{ article.readingMinutes }} 分钟
              <template v-if="article.difficulty">
                <i aria-hidden="true" />
                {{ difficultyLabels[article.difficulty] ?? article.difficulty }}
              </template>
            </span>
            <strong>{{ article.title }}</strong>
            <span>{{ article.description }}</span>
          </span>
          <time :datetime="article.updatedAt">{{ formatDate(article.updatedAt) }}</time>
          <svg class="kb-article-row__arrow" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M4 10h11m-4-4 4 4-4 4" />
          </svg>
        </a>
      </div>
    </section>

    <section id="workflow" class="kb-section kb-workflow">
      <div class="kb-workflow__intro">
        <p class="kb-section__kicker">HOW IT WORKS</p>
        <h2>一套内容，两种读取方式</h2>
        <p>人在网页中浏览，AI 通过向量检索按需读取；二者始终使用同一份 Markdown 内容。</p>
      </div>
      <ol class="kb-workflow__steps">
        <li>
          <span>01</span>
          <div><strong>沉淀</strong><p>把理解整理成结构化 Markdown。</p></div>
        </li>
        <li>
          <span>02</span>
          <div><strong>检索</strong><p>全文搜索与 RAG 分别服务人和 AI。</p></div>
        </li>
        <li>
          <span>03</span>
          <div><strong>迭代</strong><p>通过 MCP 安全更新文档和向量索引。</p></div>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.kb-home {
  color: var(--kb-ink);
  margin: 0 auto;
  max-width: 1240px;
  padding: 58px 32px 88px;
}

.kb-hero {
  align-items: center;
  display: grid;
  gap: 68px;
  grid-template-columns: minmax(0, 1.04fr) minmax(390px, 0.96fr);
  min-height: 590px;
  padding: 36px 0 76px;
}

.kb-eyebrow,
.kb-section__kicker {
  align-items: center;
  color: var(--kb-accent-dark);
  display: flex;
  font-size: 12px;
  font-weight: 750;
  gap: 9px;
  letter-spacing: 0.14em;
  margin: 0 0 20px;
}

.kb-eyebrow__dot {
  background: var(--kb-accent);
  border-radius: 50%;
  box-shadow: 0 0 0 5px rgba(var(--kb-accent-rgb), 0.1);
  height: 7px;
  width: 7px;
}

.kb-hero h1 {
  font-size: clamp(42px, 4.45vw, 58px);
  font-weight: 760;
  letter-spacing: -0.055em;
  line-height: 1.08;
  margin: 0;
  max-width: 720px;
}

.kb-hero h1 span {
  color: var(--kb-accent);
  display: block;
}

.kb-hero__description {
  color: var(--kb-muted);
  font-size: 17px;
  line-height: 1.9;
  margin: 28px 0 0;
  max-width: 640px;
}

.kb-hero__actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 34px;
}

.kb-button {
  align-items: center;
  border: 1px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  display: inline-flex;
  font-family: inherit;
  font-size: 14px;
  font-weight: 680;
  gap: 9px;
  justify-content: center;
  min-height: 48px;
  padding: 0 18px;
  text-decoration: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.kb-button:hover {
  transform: translateY(-2px);
}

.kb-button svg,
.kb-text-button svg,
.kb-category-card__arrow,
.kb-article-row__arrow,
.kb-overview__latest svg {
  fill: none;
  height: 18px;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.7;
  width: 18px;
}

.kb-button--primary {
  background: var(--kb-accent);
  box-shadow: 0 12px 24px rgba(var(--kb-accent-rgb), 0.18);
  color: white;
}

.kb-button--primary:hover {
  background: var(--kb-accent-dark);
  color: white;
}

.kb-button--secondary {
  background: var(--vp-c-bg);
  border-color: var(--kb-line);
  color: var(--kb-ink);
}

.kb-button--secondary:hover {
  border-color: rgba(var(--kb-accent-rgb), 0.35);
}

.kb-button kbd {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
  color: var(--kb-muted);
  font-family: inherit;
  font-size: 11px;
  font-weight: 650;
  margin-left: 4px;
  padding: 2px 6px;
}

.kb-hero__principles {
  color: var(--kb-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 9px 20px;
  list-style: none;
  margin: 24px 0 0;
  padding: 0;
}

.kb-hero__principles li {
  align-items: center;
  display: flex;
  gap: 6px;
}

.kb-hero__principles span {
  color: var(--kb-accent);
  font-weight: 800;
}

.kb-overview {
  background: var(--kb-overview-bg);
  border: 1px solid var(--kb-overview-border);
  border-radius: 24px;
  box-shadow: 0 28px 70px var(--kb-overview-shadow);
  overflow: hidden;
  padding: 26px;
  position: relative;
}

.kb-overview::before {
  background: radial-gradient(circle, var(--kb-overview-glow), transparent 68%);
  content: '';
  height: 230px;
  pointer-events: none;
  position: absolute;
  right: -80px;
  top: -90px;
  width: 230px;
}

.kb-overview__header,
.kb-overview__latest > div,
.kb-category-card__topline,
.kb-section__heading {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.kb-overview__header {
  border-bottom: 1px solid var(--kb-line);
  padding-bottom: 20px;
  position: relative;
}

.kb-overview__header > div {
  display: grid;
  gap: 3px;
}

.kb-overview__label {
  color: var(--kb-muted);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.kb-overview__header strong {
  font-size: 17px;
}

.kb-status {
  align-items: center;
  background: var(--kb-accent-soft);
  border-radius: 99px;
  color: var(--kb-accent-dark);
  display: inline-flex;
  font-size: 11px;
  font-weight: 650;
  gap: 6px;
  padding: 6px 10px;
}

.kb-status i {
  background: var(--kb-accent);
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(var(--kb-accent-rgb), 0.12);
  height: 6px;
  width: 6px;
}

.kb-overview__stats {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, 1fr);
  padding: 22px 0;
}

.kb-overview__stats > div {
  background: var(--kb-stat-bg);
  border: 1px solid var(--kb-stat-border);
  border-radius: 13px;
  display: grid;
  gap: 2px;
  padding: 14px;
}

.kb-overview__stats strong {
  font-size: 25px;
  letter-spacing: -0.04em;
}

.kb-overview__stats span {
  color: var(--kb-muted);
  font-size: 11px;
}

.kb-overview__latest {
  background: var(--kb-deep-bg);
  border-radius: 16px;
  color: white;
  padding: 18px;
}

.kb-overview__latest-label {
  color: rgba(255, 255, 255, 0.58);
  display: block;
  font-size: 10px;
  letter-spacing: 0.12em;
  margin-bottom: 9px;
}

.kb-overview__latest > a {
  align-items: center;
  color: white;
  display: flex;
  font-size: 15px;
  font-weight: 680;
  gap: 10px;
  justify-content: space-between;
  line-height: 1.45;
  text-decoration: none;
}

.kb-overview__latest > div {
  color: rgba(255, 255, 255, 0.55);
  font-size: 10px;
  gap: 10px;
  justify-content: flex-start;
  margin-top: 14px;
}

.kb-overview__latest > div span + span::before,
.kb-overview__latest time::before {
  content: '·';
  margin-right: 10px;
}

.kb-overview__empty,
.kb-empty-state {
  background: var(--vp-c-bg-soft);
  border: 1px dashed rgba(var(--kb-accent-rgb), 0.25);
  border-radius: 16px;
  color: var(--kb-muted);
  font-size: 13px;
  line-height: 1.7;
  padding: 20px;
}

.kb-overview__pipeline {
  align-items: center;
  color: var(--kb-muted);
  display: flex;
  font-size: 10px;
  gap: 8px;
  justify-content: center;
  margin-top: 18px;
}

.kb-overview__pipeline span {
  background: var(--kb-pipeline-bg);
  border: 1px solid var(--kb-line);
  border-radius: 7px;
  padding: 5px 8px;
  white-space: nowrap;
}

.kb-overview__pipeline i {
  color: var(--kb-accent);
  font-style: normal;
}

.kb-section {
  border-top: 1px solid var(--kb-line);
  padding: 84px 0;
  scroll-margin-top: 74px;
}

.kb-section__heading {
  gap: 28px;
  margin-bottom: 34px;
}

.kb-section__heading > div {
  max-width: 680px;
}

.kb-section__kicker {
  margin-bottom: 10px;
}

.kb-section h2,
.kb-workflow h2 {
  font-size: clamp(28px, 3vw, 40px);
  letter-spacing: -0.035em;
  line-height: 1.2;
  margin: 0;
}

.kb-section__heading p:last-child,
.kb-workflow__intro > p:last-child {
  color: var(--kb-muted);
  line-height: 1.75;
  margin: 12px 0 0;
}

.kb-text-button {
  align-items: center;
  background: transparent;
  border: 0;
  color: var(--kb-accent-dark);
  cursor: pointer;
  display: inline-flex;
  flex: 0 0 auto;
  font-family: inherit;
  font-size: 13px;
  font-weight: 680;
  gap: 7px;
  padding: 10px 0;
}

.kb-category-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.kb-category-card {
  align-items: center;
  background: var(--vp-c-bg);
  border: 1px solid var(--kb-line);
  border-radius: 17px;
  color: var(--kb-ink);
  display: grid;
  gap: 16px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  min-height: 136px;
  padding: 20px;
  text-decoration: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.kb-category-card:hover {
  border-color: rgba(var(--kb-accent-rgb), 0.36);
  box-shadow: 0 16px 35px rgba(var(--kb-accent-rgb), 0.08);
  color: var(--kb-ink);
  transform: translateY(-3px);
}

.kb-category-card__mark,
.kb-empty-state__icon {
  align-items: center;
  background: var(--kb-accent-soft);
  border: 1px solid rgba(var(--kb-accent-rgb), 0.13);
  border-radius: 13px;
  color: var(--kb-accent-dark);
  display: flex;
  font-size: 12px;
  font-weight: 800;
  height: 48px;
  justify-content: center;
  letter-spacing: 0.05em;
  width: 48px;
}

.kb-category-card__body {
  display: grid;
  min-width: 0;
}

.kb-category-card__topline {
  gap: 12px;
}

.kb-category-card__topline strong {
  font-size: 16px;
}

.kb-category-card__topline > span {
  color: var(--kb-muted);
  font-size: 11px;
}

.kb-category-card__title {
  color: var(--kb-muted);
  font-size: 12px;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-category-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 12px;
}

.kb-category-card__tags em {
  background: var(--vp-c-bg-soft);
  border-radius: 5px;
  color: var(--kb-muted);
  font-size: 9px;
  font-style: normal;
  padding: 3px 6px;
}

.kb-category-card__arrow {
  color: var(--kb-accent);
}

.kb-empty-state {
  align-items: center;
  background: var(--vp-c-bg-soft);
  border: 1px dashed rgba(var(--kb-accent-rgb), 0.25);
  border-radius: 16px;
  color: var(--kb-muted);
  display: flex;
  flex-direction: column;
  padding: 48px 24px;
  text-align: center;
}

.kb-empty-state h3 {
  color: var(--kb-ink);
  margin: 18px 0 6px;
}

.kb-empty-state p {
  margin: 0;
}

.kb-article-list {
  border-top: 1px solid var(--kb-line);
}

.kb-article-row {
  align-items: center;
  border-bottom: 1px solid var(--kb-line);
  color: var(--kb-ink);
  display: grid;
  gap: 20px;
  grid-template-columns: 42px minmax(0, 1fr) auto 20px;
  min-height: 138px;
  padding: 22px 8px;
  text-decoration: none;
  transition: background 0.2s ease, padding 0.2s ease;
}

.kb-article-row:hover {
  background: linear-gradient(90deg, rgba(var(--kb-accent-rgb), 0.055), transparent);
  color: var(--kb-ink);
  padding-left: 16px;
  padding-right: 16px;
}

.kb-article-row__index {
  color: rgba(var(--kb-accent-rgb), 0.6);
  font-size: 12px;
  font-weight: 750;
}

.kb-article-row__content {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.kb-article-row__meta {
  align-items: center;
  color: var(--kb-accent-dark);
  display: flex;
  font-size: 10px;
  font-weight: 650;
  gap: 7px;
}

.kb-article-row__meta i {
  background: rgba(var(--kb-accent-rgb), 0.35);
  border-radius: 50%;
  height: 3px;
  width: 3px;
}

.kb-article-row__content strong {
  font-size: 19px;
  letter-spacing: -0.015em;
}

.kb-article-row__content > span:last-child {
  color: var(--kb-muted);
  font-size: 12px;
  line-height: 1.65;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-article-row time {
  color: var(--kb-muted);
  font-size: 11px;
}

.kb-article-row__arrow {
  color: var(--kb-accent);
}

.kb-workflow {
  align-items: start;
  background: var(--kb-deep-bg);
  border: 0;
  border-radius: 24px;
  color: white;
  display: grid;
  gap: 56px;
  grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
  margin-top: 30px;
  padding: 52px;
}

.kb-workflow .kb-section__kicker {
  color: var(--kb-deep-text);
}

.kb-workflow__intro > p:last-child {
  color: rgba(255, 255, 255, 0.62);
}

.kb-workflow__steps {
  display: grid;
  gap: 0;
  list-style: none;
  margin: 0;
  padding: 0;
}

.kb-workflow__steps li {
  align-items: start;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  display: grid;
  gap: 17px;
  grid-template-columns: 38px minmax(0, 1fr);
  padding: 17px 0;
}

.kb-workflow__steps li:first-child {
  padding-top: 0;
}

.kb-workflow__steps li:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.kb-workflow__steps > li > span {
  color: var(--kb-deep-text);
  font-size: 11px;
  font-weight: 700;
}

.kb-workflow__steps strong {
  display: block;
  font-size: 15px;
  margin-bottom: 3px;
}

.kb-workflow__steps p {
  color: rgba(255, 255, 255, 0.58);
  font-size: 12px;
  margin: 0;
}

@media (max-width: 960px) {
  .kb-home {
    padding-top: 32px;
  }

  .kb-hero {
    gap: 44px;
    grid-template-columns: 1fr;
    padding-top: 24px;
  }

  .kb-overview {
    max-width: 680px;
  }

  .kb-workflow {
    gap: 38px;
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .kb-home {
    padding: 28px 20px 56px;
  }

  .kb-hero {
    min-height: auto;
    padding: 30px 0 64px;
  }

  .kb-hero h1 {
    font-size: 38px;
    letter-spacing: -0.045em;
  }

  .kb-hero__description {
    font-size: 15px;
    line-height: 1.8;
  }

  .kb-hero__actions,
  .kb-button {
    width: 100%;
  }

  .kb-hero__principles {
    align-items: flex-start;
    flex-direction: column;
  }

  .kb-overview {
    border-radius: 18px;
    padding: 18px;
  }

  .kb-overview__stats > div {
    padding: 11px;
  }

  .kb-overview__stats strong {
    font-size: 21px;
  }

  .kb-overview__latest > div {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .kb-overview__pipeline {
    display: grid;
    gap: 4px;
    grid-template-columns: auto 8px auto 8px auto;
  }

  .kb-overview__pipeline span {
    font-size: 8px;
    padding: 5px 6px;
  }

  .kb-overview__pipeline i {
    text-align: center;
  }

  .kb-section {
    padding: 62px 0;
  }

  .kb-section__heading {
    align-items: flex-start;
    flex-direction: column;
    margin-bottom: 26px;
  }

  .kb-category-grid {
    grid-template-columns: 1fr;
  }

  .kb-category-card {
    grid-template-columns: 48px minmax(0, 1fr);
    min-height: 120px;
    padding: 17px;
    position: relative;
  }

  .kb-category-card__body {
    padding-right: 22px;
  }

  .kb-category-card__topline {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }

  .kb-category-card__arrow {
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
  }

  .kb-article-row {
    gap: 9px 12px;
    grid-template-columns: 30px minmax(0, 1fr) 18px;
    padding: 22px 2px;
  }

  .kb-article-row time {
    display: none;
  }

  .kb-article-row__content > span:last-child {
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    display: -webkit-box;
    white-space: normal;
  }

  .kb-workflow {
    border-radius: 18px;
    margin-left: -4px;
    margin-right: -4px;
    padding: 32px 24px;
  }
}
</style>