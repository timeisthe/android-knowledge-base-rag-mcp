---
category: 八股
created_at: '2026-07-23'
difficulty: advanced
source_file: Android高级开发面试八股优化整理.md
subcategory: Android高级
tags:
- Bitmap
- MVVM
- MVI
- Binder
- AIDL
- 内存泄漏
- 性能优化
- Baseline Profile
title: Android 高级八股：Bitmap、架构、Binder、内存与性能
updated_at: '2026-07-23'
verified_at: '2026-07-23'
---

# Android 高级八股：Bitmap、架构、Binder、内存与性能

> 时效性：2026-07-23 使用 Android CLI 1.0.15857036 与 Android 官方知识库复核。版本敏感内容已在正文标注；第三方旧链接仅作历史索引。

## 11. Bitmap 与图片加载

### 11.1 Bitmap 内存计算

Bitmap 内存约等于：宽 * 高 * 每像素字节数。常见格式：

- `ARGB_8888`：4 字节/像素。
- `RGB_565`：2 字节/像素，无 alpha，质量较低。

资源目录密度会影响解码尺寸。例如把 xxhdpi 图片放到 xhdpi 目录，在 xxhdpi 设备上可能被放大，内存增加。

### 11.2 加载大图

- 先用 `inJustDecodeBounds` 读取尺寸。
- 计算 `inSampleSize` 降采样。
- 超大图局部查看用 `BitmapRegionDecoder`。
- 列表图片交给 Glide/Coil 等成熟库处理。

### 11.3 LruCache

LRU 缓存通常由 HashMap + 双向链表实现，查找 O(1)，移动和淘汰 O(1)。Android `LruCache` 内部基于 `LinkedHashMap` 的访问顺序。

### 11.4 Glide 简要原理

Glide 会根据 `with(Activity/Fragment/View)` 绑定生命周期，内部通过隐藏 Fragment 或 Lifecycle 感知请求启停。缓存通常包括活动资源、内存缓存、磁盘缓存。面试重点是：生命周期绑定、缓存 key、解码变换、线程调度和列表复用。

现代补充：Kotlin/Compose 项目中 Coil 更常见，原因是 Kotlin 协程友好、Compose 支持好。

### 11.5 Bitmap 补充题

**getByteCount 和 getAllocationByteCount 区别？**

`getByteCount()` 表示当前 Bitmap 像素数据所需字节数；`getAllocationByteCount()` 表示实际分配内存大小。复用 Bitmap 或复用内存块时，allocation 可能大于 byteCount。

**图片放错 drawable 目录为什么影响内存？**

Android 会按资源目录密度和设备密度做缩放。低密度目录图片在高密度设备上可能被放大解码，导致 Bitmap 宽高和内存增加。图片应放到匹配密度目录，或使用 `drawable-nodpi` 避免缩放。

## 12. 架构：MVC、MVP、MVVM 与现代推荐

### 12.1 MVC

Android 早期常把 Activity/Fragment 写成 Controller，但实际容易变成 View + Controller + 部分 Model 的混合体，导致页面臃肿。

### 12.2 MVP

MVP 把业务逻辑放到 Presenter，View 只负责显示。优点是职责清晰、便于单测；缺点是接口多、模板代码多，Presenter 容易持有 View 导致泄漏。

如果维护老项目，Presenter 应在 View 销毁时解绑，并取消网络请求。

### 12.3 MVVM

现代 Android 更常用 MVVM 或 MVI：

- View：Activity/Fragment/Compose UI，只渲染状态和发送事件。
- ViewModel：持有 UI state，处理 UI 逻辑。
- Model/Repository：负责数据来源、缓存、网络、本地数据库。

推荐组合：ViewModel + StateFlow/SharedFlow + Room + Retrofit/OkHttp + Hilt/Koin + Compose 或 ViewBinding。

### 12.4 LiveData、Flow 与 StateFlow

LiveData 生命周期感知强，适合传统 View 系统；Flow 是 Kotlin 协程生态的异步流，适合复杂数据流组合；StateFlow 表示可观察状态，SharedFlow 表示事件流。

现代实践：

- UI 状态用 `StateFlow<UiState>`。
- 一次性事件用 `SharedFlow` 或 Channel。
- 在 UI 层用 `repeatOnLifecycle` 收集，避免后台仍然收集。

## 13. Binder 与 IPC

### 13.1 为什么 Android 主要使用 Binder

Binder 相比传统 socket/管道，更适合 Android 的高频系统服务调用：性能较好、支持身份传递、权限校验、死亡通知、对象引用语义，并由 ServiceManager 管理服务发现。

### 13.2 Binder 通信过程

简化流程：

1. 服务端实现 Binder，并注册到 ServiceManager 或通过 bindService 暴露。
2. 客户端拿到 Binder 代理对象。
3. 客户端调用代理方法，数据被写入 Parcel。
4. Binder 驱动完成跨进程传输并唤醒服务端 Binder 线程。
5. 服务端执行 `onTransact`，返回结果。

Binder 不是为大数据传输设计的。大对象应使用文件描述符、共享内存或 ContentProvider。

### 13.3 AIDL

AIDL 用来生成 Binder 通信模板代码。支持基本类型、String、CharSequence、List、Map、Parcelable、AIDL 接口等。

注意：

- AIDL 方法默认运行在 Binder 线程池，不在主线程。
- 服务端要考虑线程安全。
- 客户端要处理 `DeadObjectException` 和 Binder 死亡。
- 多模块共用 AIDL 时，应把接口放到公共 API 模块，避免重复定义导致包名和签名不一致。

### 13.4 多进程问题

多进程会导致：

- Application 多次创建。
- 静态变量和单例不共享。
- SharedPreferences 可靠性下降，不适合作多进程同步。
- 调试、日志和初始化逻辑复杂。

多进程应有明确收益，例如隔离 WebView、推送、播放器、稳定性保护或跨应用服务。

## 14. 内存、泄漏与 OOM

### 14.1 内存泄漏与 OOM

内存泄漏是对象不再需要却仍被引用；OOM 是可用内存不足导致分配失败。泄漏可能导致 OOM，但 OOM 也可能由一次性大对象、图片解码、Native 内存等造成。

常见泄漏：

- Handler 延迟消息持有 Activity。
- 静态集合/单例持有 Context 或 View。
- BroadcastReceiver、监听器、回调未反注册。
- Thread、Timer、协程任务生命周期过长。
- Cursor、File、Bitmap 等资源未关闭。
- Fragment ViewBinding 未在 `onDestroyView` 释放。

### 14.2 LeakCanary 原理

LeakCanary 监听 Activity/Fragment 销毁，把对象包装成弱引用并关联 ReferenceQueue。延迟后如果弱引用没有入队，说明对象可能未被回收；触发 GC 后仍未回收，则 dump hprof，并用 Shark 分析到 GC Roots 的引用路径。

## 15. 性能优化

### 15.1 启动优化

先区分冷、温、热启动，并明确 TTID（首帧）与 TTFD（可交互/内容就绪）口径。优化必须基于 Macrobenchmark、Perfetto 或 Play 指标，而不是只看单次 Log。

主要方向：减少 Application/ContentProvider 同步初始化；延迟或按需初始化；移除主线程 I/O、锁等待、反射扫描和同步 Binder；压缩首屏布局与 Compose 重组范围。

Profile 相关要区分：

- Baseline Profile 描述应用或库的常用代码路径，使 ART 在安装阶段对关键路径进行预编译，改善启动和运行时卡顿。
- Startup Profile 主要优化启动相关类的 DEX 布局，减少启动时页面读取；它与 Baseline Profile 互补，不是同义词。
- 使用 Macrobenchmark 验证 Profile 是否生效及收益，避免把“加了 Profile”直接等同于性能提升。

App Startup 可统一声明初始化依赖，但每个 Initializer 仍会占用启动关键路径；是否接入取决于依赖图与真实 trace。

### 15.2 卡顿优化

一帧在 60Hz 下约 16.6ms，在高刷设备下预算更少。卡顿通常来自主线程执行过久、布局过深、频繁 GC、锁竞争、Binder 慢调用、I/O 或 GPU 过度绘制。

排查工具：

- Perfetto/System Trace。
- Choreographer frame callback。
- Android Studio Profiler。
- Looper Printer 监控消息耗时。
- 线上使用 Matrix、BlockCanary 类方案，但要控制性能开销。

### 15.3 布局优化

- 减少层级，优先 ConstraintLayout 或 Compose 合理拆分。
- 避免 `wrap_content` 嵌套导致多次测量。
- 使用 ViewStub、include/merge。
- RecyclerView item 避免复杂嵌套。
- `onDraw` 不创建对象、不做 I/O、不做复杂计算。

### 15.4 内存优化

- 控制图片尺寸和缓存。
- 避免 Activity 泄漏。
- 按生命周期取消任务。
- 关注 Native 内存、线程数、Bitmap、WebView。
- 使用 LeakCanary、MAT、Android Studio Memory Profiler。

### 15.5 网络优化

- 连接复用、HTTP/2、合理超时。
- 缓存策略：Cache-Control、ETag、If-None-Match。
- 压缩：gzip/br、图片 WebP/AVIF。
- 请求合并、分页、避免重复请求。
- 弱网重试、降级和可观测性。

## 当前官方参考

- [Baseline Profiles](https://developer.android.com/topic/performance/baselineprofiles)
- [Startup Profiles](https://developer.android.com/topic/performance/startupprofiles/overview)
- [Macrobenchmark](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
