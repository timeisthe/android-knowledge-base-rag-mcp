---
category: 简历解释
created_at: '2026-07-23'
difficulty: advanced
source_project: changli-planet-app
subcategory: Android 项目
tags:
- Android
- 简历解释
- 动态换肤
- AssetManager
- LayoutInflater.Factory2
- Observer
- WeakReference
- Compose
- StateFlow
- CompositionLocal
- 协程
- 项目深挖
title: Android View/Compose 混合架构动态换肤框架：简历解释与追问
updated_at: '2026-07-23'
---

# Android View/Compose 混合架构动态换肤框架：简历解释与追问

## 1. 核心思路

这套换肤框架可以归结为四个问题：

```text
资源从哪里来？
    AssetManager + 外部皮肤 APK

资源如何对应？
    resourceType + resourceName

哪些 UI 需要更新？
    Factory2 属性采集 + SkinSupportable

什么时候更新？
    View Observer + Compose StateFlow
```

完整调用链是：

```text
用户选择皮肤
    → 下载或读取缓存中的皮肤 APK
    → AssetManager 加载外部资源
    → SkinManager 发布当前皮肤
    → View Observer 执行 applySkin
    → Compose StateFlow 触发重组
```

后面的实现都围绕这四个问题展开。

---

## 2. 第一个问题：资源从哪里来？

### 2.1 资源载体

皮肤以独立 APK 文件作为资源载体。皮肤 APK 不负责运行业务代码，主要提供与宿主约定好的资源，例如：

```text
color/main_color
color/text_primary
drawable/button_background
drawable/card_background
```

资源可能来自两个位置：

1. 已下载到应用私有目录的缓存文件。
2. 首次内置在宿主 assets 中的皮肤文件。

`SkinFileHelper.getSkinFile()` 先检查 `files/skin_cache`。缓存文件存在且非空时直接复用；缓存不存在时尝试从 assets 复制到缓存目录。

服务端皮肤由 `SkinSelectionViewModel` 调用 `SkinRepository` 下载，再通过 `SkinFileHelper.saveStreamToCache()` 写入相同目录。MMKV 记录已下载状态和当前皮肤名称。

### 2.2 为什么需要 AssetManager

普通的 `context.resources` 只关联宿主当前的资源路径。为了读取外部皮肤 APK，需要为它创建一套独立的资源访问环境。

`SkinResourcesHelper.loadSkinResources()` 的执行过程是：

1. 检查皮肤文件是否存在。
2. 调用 `PackageManager.getPackageArchiveInfo()` 读取皮肤 APK 的包名。
3. 反射创建新的 `AssetManager`。
4. 反射调用 `addAssetPath(skinPath)`，把皮肤 APK 加入该 AssetManager 的资源搜索路径。
5. 使用宿主的 `displayMetrics` 和 `configuration` 构造新的 `Resources`。
6. 返回皮肤 `Resources` 和皮肤包名。

伪代码如下：

```kotlin
val packageInfo = packageManager.getPackageArchiveInfo(skinPath, 0)
val skinPackageName = packageInfo.packageName

val assetManager = AssetManager::class.java.newInstance()
val addAssetPath = AssetManager::class.java.getMethod(
    "addAssetPath",
    String::class.java
)
addAssetPath.invoke(assetManager, skinPath)

val skinResources = Resources(
    assetManager,
    context.resources.displayMetrics,
    context.resources.configuration
)
```

最终 `SkinManager` 同时保存：

```kotlin
var appResources: Resources
var skinResources: Resources?
var skinPackageName: String?
```

- `appResources`：宿主默认资源，用于资源信息解析和回退。
- `skinResources`：当前外部皮肤资源。
- `skinPackageName`：调用 `getIdentifier()` 时指定资源所属包。

切回默认皮肤时，将 `skinResources` 和 `skinPackageName` 置空，后续资源查找自然回到宿主资源。

### 2.3 协程、缓存与启动恢复

资源文件读取和 `Resources` 构建在 `Dispatchers.IO` 中执行，避免阻塞主线程。加载完成后再切换到主线程通知 View。

MMKV 保存当前皮肤名称。应用启动时，`PlanetApplication` 读取缓存；如果不是默认皮肤，就重新调用 `SkinManager.setSkin()` 恢复皮肤资源环境。

因此资源链路可以概括为：

```text
Retrofit / assets
    → files/skin_cache
    → AssetManager.addAssetPath
    → 独立 Resources
    → SkinManager
```

---

## 3. 第二个问题：资源如何对应？

### 3.1 映射协议

宿主 APK 和皮肤 APK 会分别编译自己的资源表。即使都声明了 `R.color.main_color`，编译后的整数资源 ID 也不保证相同。

因此框架不把资源 ID 作为跨 APK 协议，而是使用：

```text
resourceType + resourceName
```

例如：

```text
color/main_color
drawable/button_background
```

资源查找流程是：

```text
宿主资源 ID
    → getResourceEntryName() 获得资源名称
    → getResourceTypeName() 获得资源类型
    → skinResources.getIdentifier(name, type, skinPackageName)
    → 获得皮肤包中的资源 ID
```

对应逻辑：

```kotlin
val resName = appResources.getResourceEntryName(originalResId)
val resType = appResources.getResourceTypeName(originalResId)

val skinResId = skinResources?.getIdentifier(
    resName,
    resType,
    skinPackageName
) ?: 0
```

这相当于让宿主和皮肤包遵守一套资源命名契约：皮肤只要提供同名、同类型资源，就能覆盖宿主资源。

### 3.2 资源回退

皮肤包可以只包含需要变化的资源，不要求复制宿主的全部资源。

查找结果分为三种情况：

1. 找到同名皮肤资源：使用皮肤资源。
2. 没有找到：使用宿主原始资源。
3. 查找或解析发生异常：捕获异常并回退宿主资源。

以文字颜色为例：

```kotlin
val color = if (skinResId != 0) {
    skinResources.getColor(skinResId, null)
} else {
    appResources.getColor(originalResId, view.context.theme)
}

textView.setTextColor(color)
```

回退机制保证增量皮肤可以工作，也避免皮肤包漏资源时出现空背景、透明文字或崩溃。

### 3.3 Drawable 的映射

背景资源不仅可能是颜色，还可能是带圆角、描边和渐变的 Drawable XML。

处理顺序是：

1. 皮肤包有同名 Drawable：整体替换。
2. 没有同名 Drawable：检查宿主 Drawable 是否为 XML。
3. 解析 `solid`、`stroke`、`gradient` 中引用的颜色资源。
4. 根据颜色名称在皮肤包中查找同名颜色。
5. 对原 Drawable 执行 `mutate()`，再通过 `GradientDrawable.setColor()` 或 tint 替换颜色。
6. 无法处理时回退宿主 Drawable。

这样可以只替换 Drawable 内部的颜色，同时保留圆角、尺寸、描边宽度等原有结构。

### 3.4 Compose 资源映射

`SkinComposeHelper.getSkinColor()` 使用相同的名称和类型映射逻辑，将皮肤资源中的 Android Color Int 转换为 Compose `Color`。

当前项目的 Compose 主路径主要通过皮肤名称选择 `SkinColors` 主题 Token；需要直接访问外部皮肤颜色的组件，可以使用 `SkinComposeHelper` 完成同名资源查找。

---

## 4. 第三个问题：哪些 UI 需要更新？

这个问题需要分别处理传统 View 和 Compose。

### 4.1 View：Factory2 发现可换肤控件

在 `FullScreenActivity.super.onCreate()` 之前设置 `LayoutInflater.Factory2`，拦截 XML 布局创建过程。

当 XML 中出现 TextView、MaterialCardView、ConstraintLayout、TabLayout 等控件时，Factory2 将它们替换为对应的可换肤实现，例如：

```text
TextView
    → SkinTextView

MaterialCardView
    → SkinMaterialCardView

ConstraintLayout
    → SkinConstraintLayout

TabLayout
    → SkinTabLayout
```

Factory2 解决的是“哪些 XML View 要进入换肤体系”。业务页面不需要逐个保存控件并手动注册换肤属性。

### 4.2 SkinAttributeProvider：采集哪些属性

不同控件支持的属性不同：

- TextView：`textColor`、`background`
- EditText：`textColor`、`hintTextColor`、`background`
- MaterialButton：`textColor`、`background`、`strokeColor`
- MaterialCardView：`cardBackgroundColor`
- TabLayout：普通文字颜色、选中文字颜色、背景
- 普通 View 和布局：`background`

每个可换肤控件实现 `SkinAttributeProvider`，在初始化时通过 `withStyledAttributes()` 从 `AttributeSet` 中读取资源引用。

这里保存的是资源 ID，而不是已经解析完成的颜色值：

```kotlin
val textColorResId = getResourceId(index, 0)
delegate.setAttr("tv_text_color", textColorResId)
```

保存资源引用后，皮肤切换时才能重新按照资源名称查找新值。

### 4.3 SkinSupportable：统一刷新协议

所有需要响应换肤的 View 实现：

```kotlin
interface SkinSupportable {
    fun applySkin()
}
```

`SkinSupportable` 只定义统一入口，不关心控件具体有哪些属性。

各控件内部持有 `SkinDelegate`，并把实际更新工作交给 Delegate：

```kotlin
override fun applySkin() {
    delegate.applySkin()
}
```

`SkinDelegate` 保存：

- View 的弱引用。
- 属性名称到宿主资源 ID 的映射。
- 不同属性类型对应的应用逻辑。

它根据属性标识执行：

```text
tv_text_color
    → TextView.setTextColor()

view_background
    → View.setBackground()

card_background_color
    → MaterialCardView.setCardBackgroundColor()

tab_text_color
    → TabLayout.setTabTextColors()
```

Factory2 负责发现 View，`SkinAttributeProvider` 负责采集属性，`SkinSupportable` 负责统一刷新入口，`SkinDelegate` 负责复用具体换肤逻辑。

### 4.4 Compose：主题树中的消费者

Compose 不通过 Factory2 发现组件。

需要换肤的 Compose 页面由 `AppSkinTheme` 包裹，子组件统一从：

```kotlin
AppTheme.colors
```

读取 `SkinColors`。

因此 Compose 中“哪些 UI 需要更新”由状态读取关系决定：读取了 `AppTheme.colors` 或相关 Compose State 的组件，会在主题状态变化时参与重组。

---

## 5. 第四个问题：什么时候更新？

### 5.1 SkinManager 是统一状态中心

皮肤资源加载成功后，`SkinManager` 更新：

1. `skinResources`
2. `skinPackageName`
3. MMKV 中的当前皮肤名称
4. `currentSkinName: StateFlow<String>`

随后分别驱动 View 和 Compose 两条刷新链。

```text
SkinManager
    ├── notifyObservers() → 传统 View
    └── currentSkinName   → Compose
```

### 5.2 View：Observer 通知存量控件

可换肤 View 在：

```text
onAttachedToWindow
    → SkinManager.attach(this)

onDetachedFromWindow
    → SkinManager.detach(this)
```

`SkinManager` 保存 `WeakReference<SkinSupportable>`。皮肤加载完成后回到主线程调用 `notifyObservers()`：

1. 遍历观察者列表。
2. 引用仍然有效时调用 `applySkin()`。
3. 引用已经失效时移除该条目。

主动 detach 用于及时减少无效观察者；弱引用负责兜底，避免全局单例强引用短生命周期 View。Delegate 对实际 View 也使用弱引用。

View 的两个更新时间点是：

- 已存在的 View：收到 Observer 通知后重新执行 `applySkin()`。
- 新创建的 View：初始化时立即执行 `applySkin()`，读取当前皮肤。

因此切换后进入的新页面也能使用当前皮肤。

### 5.3 Compose：StateFlow 触发主题重组

`AppSkinTheme` 订阅：

```kotlin
val currentSkinName by SkinManager.currentSkinName.collectAsState()
```

皮肤名称改变后：

1. `collectAsState()` 更新 Compose State。
2. `AppSkinTheme` 重新选择对应的 `SkinColors`。
3. `CompositionLocalProvider` 提供新的主题 Token。
4. 主题作用域内使用 `AppTheme.colors` 的组件重新执行组合。

完整链路：

```text
MutableStateFlow.value 更新
    → collectAsState 感知变化
    → AppSkinTheme 重组
    → CompositionLocalProvider 提供新值
    → Compose 子树刷新
```

`StateFlow` 负责状态发布和触发，`CompositionLocal` 负责在 Compose 树内向下提供主题数据，两者职责不同。

### 5.4 为什么能够跨技术栈同步

View 和 Compose 没有直接互相通知，而是共享同一个 `SkinManager`：

- View 使用命令式 Observer。
- Compose 使用响应式 StateFlow。
- 两条链读取同一份当前皮肤状态和资源环境。

皮肤切换时既不调用 `Activity.recreate()`，也不需要重启进程。存量 View 重新绑定属性，Compose 根据 State 重组，从而在当前页面完成跨技术栈实时换肤。

---

## 6. 四个问题之间的关系

| 问题 | 核心组件 | 最终产物 |
|---|---|---|
| 资源从哪里来 | Retrofit、SkinFileHelper、AssetManager、Resources | 可访问外部 APK 的皮肤 Resources |
| 资源如何对应 | resourceType、resourceName、getIdentifier、Fallback | 宿主属性对应的皮肤资源 |
| 哪些 UI 更新 | Factory2、SkinAttributeProvider、SkinSupportable、SkinDelegate | 可被重新绑定资源的 UI |
| 什么时候更新 | SkinManager、Observer、StateFlow、CompositionLocal | View 刷新和 Compose 重组 |

四者缺一不可：

```text
没有资源来源
    → 无法获得皮肤资源

没有映射协议
    → 不知道宿主属性对应哪个皮肤资源

没有 UI 采集
    → 不知道需要修改哪些对象和属性

没有更新时机
    → 皮肤加载完成后界面不会变化
```

---

## 7. 适当补充

### 7.1 协程与性能

- 下载、文件读取和 Resources 构建在 IO 线程执行。
- UI 属性应用和 Observer 通知回到主线程。
- 已下载皮肤复用本地缓存。
- View 只刷新已注册的可换肤控件，不依赖 Activity 重建。
- Compose 通过状态变化触发重组，不遍历 Compose 节点。

如果没有实际基准数据，面试中更适合表述为“避免主线程 IO 和页面重建”，不要虚构具体性能提升比例。

### 7.2 弱引用与内存管理

`SkinManager` 是全局单例，生命周期长于 Activity 和 View。如果直接保存 View 强引用，遗漏 detach 时可能导致页面无法回收。

因此：

- attach/detach 负责正常生命周期管理。
- `WeakReference` 避免全局观察者成为 View 回收的强引用根。
- notify 时清理已经失效的观察者。
- `SkinDelegate` 同样不强持有 View。

### 7.3 当前实现边界

- `AssetManager.addAssetPath` 属于非公开 API，需要关注 Android 版本和厂商兼容性。
- Compose 主路径当前主要是皮肤名称到 Light/Dark `SkinColors` 的映射。
- 可换肤 View 只处理已经采集和实现的属性，并不是任意属性都能自动替换。
- `getIdentifier()` 可以增加名称到资源 ID 的缓存，减少重复查找。
- 连续快速切换皮肤时，可以使用 Mutex 或版本号避免较早请求覆盖较晚请求。
- 更完善的实现可以将 Resources、包名和皮肤名称封装为不可变 `SkinSnapshot` 一次性发布。

---

## 8. 技术与模式归类

| 分类 | 实际使用 |
|---|---|
| Android Framework | AssetManager、Resources、PackageManager、LayoutInflater.Factory2、View 生命周期 |
| AndroidX | AppCompat、withStyledAttributes |
| Compose Runtime | collectAsState、CompositionLocalProvider、staticCompositionLocalOf |
| Kotlin | Coroutines、Dispatchers、StateFlow |
| 网络与缓存 | Retrofit、MMKV、应用私有文件缓存 |
| 设计模式 | Observer、Delegate、统一状态源、Fallback |

Observer 和 Delegate 是设计模式；StateFlow 是 Kotlin 协程 Flow 体系的状态容器；CompositionLocal 是 Compose 树中的数据提供机制。

---

## 9. 最终面试回答

> 我在项目中自研了一套 Android View 和 Compose 混合架构的动态换肤框架，整体主要解决四个问题。
>
> 第一个是资源从哪里来。皮肤使用独立 APK 作为资源载体，可以由服务端下载并缓存到应用私有目录。切换时我在 IO 协程中读取皮肤文件，通过 PackageManager 获取皮肤包名，再反射创建 AssetManager 并调用 addAssetPath，把外部 APK 加入资源路径，最后构造独立的 Resources，交给 SkinManager 统一管理。
>
> 第二个是资源如何对应。因为宿主 APK 和皮肤 APK 的资源 ID 是各自编译生成的，不能直接共用，所以我把资源名称和资源类型作为两边的映射协议。换肤时先根据宿主资源 ID 得到 entryName 和 type，再通过皮肤 Resources 的 getIdentifier 查找同名资源；皮肤包没有提供对应资源时自动回退宿主资源。对于 shape Drawable，还会解析 solid、stroke 和 gradient 中引用的颜色，在保留圆角、描边等结构的基础上替换颜色。
>
> 第三个是哪些 UI 需要更新。传统 View 侧，我在 Activity 创建阶段通过 LayoutInflater.Factory2 拦截 XML 控件创建，把常见控件替换为支持换肤的实现。每个控件通过 SkinAttributeProvider 采集 textColor、background、strokeColor 等资源引用，通过 SkinSupportable 暴露统一的 applySkin 接口，具体资源查找和属性设置由 SkinDelegate 复用。Compose 侧则由 AppSkinTheme 统一包裹页面，组件通过 AppTheme.colors 获取当前主题 Token。
>
> 第四个是什么时候更新。SkinManager 是统一状态中心。皮肤资源加载完成后，View 侧通过弱引用 Observer 通知已经 attach 的控件重新执行 applySkin；Compose 侧通过 StateFlow 发布当前皮肤，AppSkinTheme 使用 collectAsState 订阅，再通过 CompositionLocalProvider 下发新的主题数据并触发重组。这样 View 和 Compose 共享同一份皮肤状态，但使用各自适合的刷新机制。
>
> 资源读取和构建放在 IO 协程，UI 更新回到主线程；皮肤文件使用本地缓存减少重复加载；Observer 和 Delegate 使用弱引用，并配合 View 的 attach/detach 生命周期降低内存泄漏风险。最终实现了不重建 Activity、不重启应用的跨技术栈实时换肤。

## 10. 简历描述

> 自主研发基于 AssetManager 反射与 Observer/CompositionLocal 协同的 Android/Compose 混合架构换肤框架，结合 Kotlin 协程与弱引用机制优化资源加载与内存管理，实现跨技术栈无需重启的实时无缝换肤体验。

> 核心总结：AssetManager 解决资源入口，名称和类型解决跨包映射，Factory2 与 SkinSupportable 确定更新对象，Observer 与 StateFlow 决定刷新时机。
