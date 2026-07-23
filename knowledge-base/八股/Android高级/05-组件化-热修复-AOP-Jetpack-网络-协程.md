---
category: 八股
created_at: '2026-07-23'
difficulty: advanced
source_file: Android高级开发面试八股优化整理.md
subcategory: Android高级
tags:
- 组件化
- 插件化
- 热修复
- ASM
- KSP
- Jetpack
- Compose
- OkHttp
- Retrofit
- 协程
- Flow
title: Android 高级八股：组件化、热修复、AOP、Jetpack、网络与协程
updated_at: '2026-07-23'
verified_at: '2026-07-23'
---

# Android 高级八股：组件化、热修复、AOP、Jetpack、网络与协程

> 时效性：2026-07-23 使用 Android CLI 1.0.15857036 与 Android 官方知识库复核。版本敏感内容已在正文标注；第三方旧链接仅作历史索引。

## 21. 组件化、路由与模块化

### 21.1 模块化与组件化

模块化是按代码职责拆分 Gradle module；组件化强调业务模块可独立开发、独立调试、低耦合集成。

常见结构：

- app 壳工程。
- common/base/core 基础模块。
- feature 业务模块。
- api/bridge 模块定义跨模块接口。

### 21.2 组件通信

- 路由：ARouter、Jetpack Navigation、多模块 Deep Link。
- 接口下沉：公共 api 模块定义接口，业务模块实现。
- 依赖注入：Hilt/Koin 管理实现绑定。
- 事件流：Flow/LiveData 做状态通知。

### 21.3 ARouter 原理

ARouter 编译期通过注解处理器扫描 `@Route`，生成路由表类。运行时加载路由表，按 path 找到目标 Activity/Provider，再构造 Intent 或服务实例完成跳转。

注意：运行时扫描 dex 的方案会影响启动性能，通常需要编译期索引或 Gradle 插件优化。

### 21.4 模块化、组件化、插件化补充题

**组件独立调试怎么做？**

常见做法是通过 Gradle 配置控制业务模块在 application 和 library 之间切换，独立调试时提供壳 Activity、Mock 数据和独立 Manifest；集成打包时作为 library 被 app 壳依赖。

**组件 Application 初始化怎么处理？**

可以定义组件初始化接口，由壳工程统一调用；也可以通过注解处理器或 Gradle 插件生成初始化表，避免运行时全 dex 扫描。现代项目还可用 AndroidX App Startup，但要注意启动链路成本。

**插件 Activity 为什么需要占坑？**

未在宿主 Manifest 注册的 Activity 无法通过系统校验。传统插件化会先用已注册的 StubActivity 通过 AMS 校验，再在应用进程启动阶段把 Intent/ClassLoader 替换为插件 Activity，实现生命周期接管。

## 22. 热修复与插件化

### 22.1 热修复

热修复常见方向：

- 类修复：调整 ClassLoader/DexPathList，让补丁 dex 优先加载。
- 资源修复：替换或追加 AssetManager 资源路径。
- Native 修复：替换 so。
- 方法级修复：运行时 hook 或 inline 替换。

现代注意：Android 版本、厂商 ROM、hidden API、签名校验、应用商店政策都会影响热修复可行性。新项目不要把热修复当作常规发版替代。

### 22.2 插件化

插件化解决动态加载 APK、资源和组件生命周期问题。核心难点：

- 类加载：PathClassLoader/DexClassLoader。
- 资源加载：AssetManager addAssetPath。
- 四大组件：Manifest 注册校验、生命周期调度、占坑 Activity、Hook Instrumentation/AMS。

过时提醒：原资料中 VirtualApk、Small 等被称为主流，但现在多数业务已经转向 App Bundle、动态特性模块、组件化和服务端配置。插件化仍可作为 Framework 能力考点，但工程上要谨慎。

## 23. AOP、APT、ASM

APT/KAPT/KSP：编译期处理注解，生成代码。典型场景：路由表、DI、数据库 DAO。Kotlin 新项目更推荐 KSP，性能和 Kotlin 兼容性更好。

AspectJ：基于切点织入代码，曾常用于埋点、权限、日志，但与现代 Gradle/AGP 兼容成本较高。

ASM：直接操作字节码，常用于 Gradle 插件、无侵入埋点、性能监控插桩。Transform API 已从 AGP 8.0 移除；字节码转换应使用 `androidComponents {}` 下的 Instrumentation API。它按 class 独立、可增量并行处理，不能继续把旧 Transform 的全量输入模型原样搬过去。

动态代理：运行时代理接口，Retrofit 就大量使用动态代理解析接口注解。

### 23.1 AOP 与字节码插桩补充题

**APT、AspectJ、ASM 怎么区分？**

APT/KSP 是编译期生成新代码，不修改已有字节码；AspectJ 通过切点把逻辑织入目标位置；ASM 直接读写 class 字节码，灵活但门槛高。埋点、耗时统计、权限防抖等常用 ASM 或 Gradle instrumentation。

**动态代理和静态代理区别？**

静态代理在编译期写好代理类；动态代理运行时生成代理对象，Java 动态代理要求目标是接口。Retrofit 使用动态代理把接口方法调用转成 HTTP 请求描述。

## 24. Jetpack 与现代 Android

### 24.1 ViewModel

ViewModel 保存 UI 状态并跨配置变更复用，但不应持有 Activity、Fragment View 或短生命周期 Context。宿主正常 finish、导航图/Fragment 作用域真正移除时，ViewModelStore 清空并调用 `onCleared()`。

重要边界：进程被系统杀死时，不保证执行 `onCleared()`；ViewModel 也不会自动恢复内存字段。需要恢复的小状态放 `SavedStateHandle`，业务数据放数据库、文件或 Repository。

### 24.2 Lifecycle

Lifecycle 把组件生命周期抽象成可观察状态。现代用法包括：

- `DefaultLifecycleObserver`
- `lifecycleScope`
- `repeatOnLifecycle`

旧的 `@OnLifecycleEvent` 已废弃。

### 24.3 Room

Room 是 SQLite 抽象层，提供编译期 SQL 校验、DAO、迁移、Flow 支持。面试重点：事务、迁移、索引、线程、Flow 查询自动更新。

### 24.4 DataBinding 与 ViewBinding

DataBinding 支持表达式和双向绑定，但编译和可读性成本较高。ViewBinding 更轻量，只负责类型安全地访问 View。现代 XML 项目通常优先 ViewBinding；Compose 项目则直接声明式 UI。

### 24.5 Compose 状态、保存与生命周期

Compose 是声明式 UI：状态变化触发相关读取点重组。`remember` 只跨重组保存，组合离开后丢失；`rememberSaveable` 通过 SavedState 机制跨配置变更和系统进程重建恢复，但仅适合 Bundle 兼容的小型 UI 状态。

业务状态应由状态持有者/ViewModel 管理；需要进程恢复时使用 `SavedStateHandle` 保存最小恢复参数，再从数据层重建。不要把大列表、Bitmap 或完整业务对象塞进 `rememberSaveable`。

Flow 在 Compose 中优先使用生命周期感知的 `collectAsStateWithLifecycle()`；副作用使用 `LaunchedEffect`、`DisposableEffect`、`SideEffect`，并理解 key 变化会取消和重启 effect。

性能重点是稳定性、状态下沉、重组作用域、Lazy 列表稳定 key，以及用 Layout Inspector/Compose tracing/benchmark 证实问题。

### 24.6 Jetpack 补充题

**DataBinding 如何刷新 View？**

DataBinding 编译期生成 Binding 类，布局表达式关联 Observable/LiveData。当数据变化时标记 dirty flag，并在下一帧或合适时机执行 `executeBindings` 更新 View。

**View 如何反向刷新 Model？**

双向绑定会给 View 设置监听器，例如 EditText 的 TextWatcher。用户输入变化后回写到绑定变量，再触发后续数据流更新。

**ViewModel 为什么能跨配置变更？**

ComponentActivity/Fragment 持有 ViewModelStore，配置变更时通过 NonConfigurationInstances 保留 ViewModelStore。真正 finish 时才清空，触发 ViewModel `onCleared()`。

**Navigation Fragment 会不会重复创建？**

可能。Fragment 实例和 View 都可能因返回栈、配置变化、进程重建而重建；多返回栈场景使用 Navigation 的 `saveState/restoreState`，状态用 ViewModel、SavedStateHandle 和数据层恢复。不要把正确性建立在 Fragment 实例永久复用上。

## 25. OkHttp、Retrofit、缓存与网络框架

### 25.1 OkHttp

OkHttp 核心：Dispatcher 调度请求，连接池复用连接，拦截器链处理请求和响应。

拦截器顺序大致包括：

- 应用拦截器。
- RetryAndFollowUpInterceptor。
- BridgeInterceptor。
- CacheInterceptor。
- ConnectInterceptor。
- 网络拦截器。
- CallServerInterceptor。

应用拦截器只执行一次，适合统一 header、日志、业务处理；网络拦截器能观察重定向、重试后的网络层请求。

### 25.2 Retrofit

Retrofit 通过动态代理创建接口实现，调用接口方法时解析注解，构造 OkHttp Request，并通过 Converter 转换请求/响应，通过 CallAdapter 适配返回类型，如 Call、RxJava、suspend 函数。

### 25.3 HTTP 缓存

HTTP 缓存由响应头控制：`Cache-Control`、`ETag`、`Last-Modified` 等。OkHttp 配置 Cache 后可按协议自动缓存；业务也可自定义拦截器处理离线缓存。

### 25.4 OkHttp、Retrofit、Glide、LeakCanary 补充题

**OkHttp Dispatcher 做什么？**

Dispatcher 负责同步/异步请求调度，维护 ready/running 队列，并限制最大并发数和单 host 并发数。异步请求通过线程池执行。

**OkHttp 连接池复用条件？**

连接复用需要地址、协议、TLS 配置、证书等条件满足。HTTP/2 支持多路复用，同一个连接可承载多个并发流，减少握手成本。

**Retrofit 注解什么时候解析？**

调用接口方法时，动态代理进入 InvocationHandler，Retrofit 会解析方法注解和参数注解，构建 ServiceMethod，并把调用适配成 OkHttp Call 或 suspend/RxJava 等返回形式。解析结果会缓存。

**Glide 内存缓存包含哪些层？**

常见有 ActiveResources、MemoryCache、BitmapPool、DiskCache。活动资源避免正在使用的图片被重复加载；内存缓存复用已解码资源；BitmapPool 复用 Bitmap 内存；磁盘缓存存原始数据或变换后的资源。

**LeakCanary 为什么延迟检测？**

对象销毁后不会立刻 GC，延迟检测可减少误报。延迟后如果弱引用仍未进入 ReferenceQueue，再主动触发 GC 并 dump hprof 分析引用链。

## 26. Kotlin 与协程高频补充

原 PDF 对 Kotlin 和协程覆盖不足，但现在 Android 面试几乎必问。

### 26.1 协程是什么

协程是轻量级并发抽象，不等于线程。协程运行在线程之上，可以挂起和恢复。挂起不会阻塞线程，线程可以去执行其他任务。

### 26.2 Dispatchers

- `Dispatchers.Main`：主线程，更新 UI。
- `Dispatchers.IO`：I/O 密集任务。
- `Dispatchers.Default`：CPU 密集任务。
- `Dispatchers.Unconfined`：不推荐常规业务使用。

### 26.3 Job、作用域与结构化并发

协程应运行在明确作用域中。`viewModelScope` 跟随 ViewModel 清理，`lifecycleScope` 跟随 Lifecycle 清理。结构化并发要求子协程生命周期受父协程管理，避免任务泄漏。

### 26.4 Flow、StateFlow、SharedFlow

Flow 是冷流；StateFlow 是持有最新值的热状态流；SharedFlow 是可配置 replay/buffer 的热广播流。一次性 UI 事件是否用 SharedFlow、Channel 或直接建模为状态，要根据丢失、重放和消费语义决定，不能只背固定搭配。

View 系统收集 Flow 应绑定 View 生命周期：

```kotlin
viewLifecycleOwner.lifecycleScope.launch {
    viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.uiState.collect(::render)
    }
}
```

Compose 优先 `collectAsStateWithLifecycle()`。仅使用 `lifecycleScope.launch { flow.collect {} }` 会一直运行到 DESTROY，在 STOPPED 后仍可能继续收集。

## 当前官方参考

- [AGP API updates](https://developer.android.com/build/releases/gradle-plugin-api-updates)
- [Save UI state in Compose](https://developer.android.com/develop/ui/compose/state-saving)
- [Lifecycle-aware coroutines](https://developer.android.com/topic/libraries/architecture/coroutines)
- [Background work](https://developer.android.com/develop/background-work)
