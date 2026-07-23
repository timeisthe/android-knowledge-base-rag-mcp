---
category: 八股
created_at: '2026-07-23'
difficulty: advanced
source_file: Android高级开发面试八股优化整理.md
subcategory: Android高级
tags:
- Activity
- Service
- BroadcastReceiver
- ContentProvider
- 生命周期
- ANR
- App Links
title: Android 高级八股：Activity 与四大组件
updated_at: '2026-07-23'
verified_at: '2026-07-23'
---

# Android 高级八股：Activity 与四大组件

> 时效性：2026-07-23 使用 Android CLI 1.0.15857036 与 Android 官方知识库复核。版本敏感内容已在正文标注；第三方旧链接仅作历史索引。

## 0. 复习策略

Android 高级面试通常不会只问“背定义”，更喜欢沿着一条链路追问：上层 API 怎么用，Framework 怎么调度，跨进程怎么通信，主线程为什么不会卡死，出现性能问题怎么定位。因此复习时建议按下面四层组织答案：

1. 先讲结论：这个技术解决什么问题，适合什么场景。
2. 再讲关键机制：涉及哪些对象、线程、进程、队列或生命周期。
3. 补充边界条件：异常场景、版本差异、限制和坑。
4. 最后讲实践方案：项目里怎么用、怎么排查、怎么优化。

## 1. Activity

### 1.1 Activity 启动流程

**一句话回答**：Activity 启动本质是应用进程通过 Binder 请求系统进程，由 ActivityTaskManagerService/ActivityManagerService 完成任务栈、进程和生命周期调度，最后回到目标应用主线程创建 Activity 并执行生命周期。

典型冷启动流程：

1. Launcher 调用 `startActivity`，通过 Binder 向 system_server 中的 ATMS/AMS 发起请求。
2. 系统解析 Intent、权限、启动模式、任务栈和目标 Activity 信息。
3. 如果目标应用进程不存在，AMS 通过 socket 请求 Zygote fork 新进程。
4. 应用进程启动 `ActivityThread.main()`，创建主线程 `Looper`、`Handler` 和 `ApplicationThread`。
5. 应用进程通过 `attachApplication` 绑定到 AMS。
6. 系统通过 Binder 回调应用进程的 `ApplicationThread`，让主线程执行 launch transaction。
7. `ActivityThread` 通过 `Instrumentation` 反射创建 Activity，依次调用 `attach`、`onCreate`、`onStart`、`onResume`。

面试追问点：

- Android P 之后启动回调逐步走 `ClientTransaction`，不要再只背老版本的 `LAUNCH_ACTIVITY`。
- `Instrumentation` 是创建 Activity、调用生命周期、测试注入的重要钩子。
- 真正执行生命周期的是应用主线程，不是 Binder 线程。

### 1.2 Activity 生命周期：状态模型比固定顺序更重要

Activity 的核心状态仍是 `Created -> Started -> Resumed`，离开时反向经过 `Paused -> Stopped -> Destroyed`。但跨 Activity 的回调交错顺序不是所有窗口形态下都固定不变。

从完全不透明的 A 启动普通 B，常见顺序是：

```text
A.onPause()
B.onCreate()
B.onStart()
B.onResume()
A.onStop()
```

从 B 返回仍存活的 A，常见顺序是：

```text
B.onPause()
A.onRestart()
A.onStart()
A.onResume()
B.onStop()
B.onDestroy()
```

需要补充的边界：

- 半透明 Activity、Dialog 主题 Activity、多窗口场景下，底层 Activity 可能处于 `STARTED/PAUSED` 且仍可见，不一定进入 `STOPPED`。
- `onPause()` 应快速完成，不适合数据库落盘、网络请求等重工作；完全不可见后再在 `onStop()` 释放或降级 UI 相关资源，通常更符合多窗口语义。
- `onDestroy()` 不是进程终止通知。进程被系统直接杀死时，不保证收到它。
- 回调顺序受窗口是否透明、目标页面是否已存在、配置变化、进程重建等影响。面试时应先讲可见性与交互焦点，再给“常见顺序”。

Home 键通常使页面 `onPause -> onStop`；Back/预测性返回最终会 finish 当前 Activity，但返回过程应交给 `OnBackPressedDispatcher`/Navigation 管理，不应继续依赖覆写已废弃的 `Activity.onBackPressed()`。

### 1.3 onSaveInstanceState、SavedState 与 ViewModel

`onSaveInstanceState()` 用于保存“系统重建页面所需的少量临时 UI 状态”，不是业务持久化方案。系统会自动保存带 ID 的 View 层级状态；自定义状态应保持精简且可放入 Bundle。

关键边界：

- `onCreate(savedInstanceState)` 每次创建都会调用，Bundle 可能为空；`onRestoreInstanceState()` 仅在确有状态时调用，位于 `onStart()` 之后。
- 不要把某一条 `onPause/onStop/onSaveInstanceState` 顺序当成跨版本保证。Android 28 前后，`onStop()` 与保存状态的先后发生过变化：旧版本通常先保存再 stop，Android 28+ 通常先 stop 再保存。
- `ViewModel` 只能跨配置变更保留内存状态，不能抵抗进程死亡；进程恢复需要 `SavedStateHandle`、Bundle、数据库或文件。
- Bundle/`rememberSaveable` 只放恢复 UI 所需的小数据。Binder 事务缓冲区当前约 1MB，且由进程内正在进行的事务共享。
- `onSaveInstanceState()` 不是可靠的业务落盘回调；用户明确 finish、异常终止等场景不应依赖它保存关键数据。

推荐分层：短小 UI 元素状态用 View 自动保存、Bundle 或 `rememberSaveable`；页面状态用 ViewModel；可恢复业务数据放 Repository、数据库或文件。

### 1.4 启动模式与任务栈

`standard`：默认模式，每次启动都创建新实例，适合普通详情页。

`singleTop`：目标实例已在栈顶时复用，并回调 `onNewIntent`。适合通知重复点击、搜索页等。

`singleTask`：在目标任务栈中查找已有实例，存在则清理其上的页面并回调 `onNewIntent`。适合首页、主入口。

`singleInstance` / `singleInstancePerTask`：强隔离任务栈。传统 `singleInstance` 使用场景变少，现代项目中要谨慎使用，避免任务切换体验异常。

相关 Flag：

- `FLAG_ACTIVITY_NEW_TASK`：新任务启动，跨应用启动 Activity 常见。
- `FLAG_ACTIVITY_SINGLE_TOP`：效果类似 `singleTop`。
- `FLAG_ACTIVITY_CLEAR_TOP`：清掉目标 Activity 上方实例，常与 `singleTop` 或 `singleTask` 配合。

### 1.5 Intent 传递数据大小限制

Intent extras 通过 Binder 跨进程传输，Binder transaction buffer 有限制。不要简单背“1MB”，更准确的说法是：单进程 Binder 事务缓冲区通常约 1MB，且由进程内并发事务共享；超过限制可能抛 `TransactionTooLargeException`。

大数据传递方案：

- 传 ID，不传实体：目标页通过 ID 从数据库、缓存或仓库层读取。
- 进程内临时共享：`ViewModel`、单例缓存、内存 LRU，但要考虑进程死亡。
- 跨进程大数据：文件、`ContentProvider`、`ParcelFileDescriptor`、共享内存。
- 图片/二进制：传 Uri，不传 Bitmap。

不推荐：用 EventBus 或全局静态变量作为通用页面传参方案，容易造成生命周期和进程恢复问题。

### 1.6 显式启动、隐式启动、Deep Link 与 App Links

显式 Intent 直接指定组件；隐式 Intent 通过 action、category、data 匹配。Android 12 起，包含 `intent-filter` 的组件必须显式声明 `android:exported`。

普通自定义 scheme 适合应用内或可控来源跳转，但可能被其他应用抢占。对 HTTPS 网站链接，优先使用经过域名验证的 Android App Links，通过站点的 `assetlinks.json` 建立网站与签名证书之间的可信关联。

Android 15+ 的 Dynamic App Links 可在服务端 `assetlinks.json` 中动态细化路径、查询参数、片段和排除规则，无需发版；动态规则只能收窄 Manifest 中已声明的范围，不能扩大范围。

所有外部 Deep Link 都应视为不可信输入：校验 scheme/host/path、参数类型与长度、登录态和业务权限，避免开放重定向、越权跳页与 Intent 注入。

### 1.7 ANR 场景与当前超时口径

ANR 是系统在组件或输入处理超时后生成的诊断结果，不等于“某个生命周期方法超过固定秒数就直接报错”。AOSP/Pixel 的默认口径如下，OEM 可调整：

- 输入分发超时：默认 5 秒。
- 广播：Android 13 及以下，前台优先广播约 10 秒、后台约 60 秒；Android 14+ 会根据进程是否 CPU 饥饿扩展为约 10–20 秒和 60–120 秒。
- 执行 Service：前台 Service 默认约 20 秒，后台 Service 默认约 200 秒；冷启动和 `onCreate/onStartCommand/onBind` 都计入。
- ContentProvider：不应再统一背“10 秒”。远程调用方可通过 `ContentProviderClient.setDetectNotResponding()` 指定检测阈值，耗时包含目标进程冷启动与查询。

常见根因是主线程阻塞、锁竞争、同步 Binder 慢调用、I/O、慢启动、广播 `goAsync()` 未及时 `finish()`、Binder 线程池耗尽等。优先使用 Play Console ANR 集群、Perfetto、ANR trace、主线程与 Binder 线程堆栈定位。

### 1.8 Activity 补充题

**onNewIntent 什么时候执行？**

当目标 Activity 已有实例被复用时会执行 `onNewIntent`，常见于 `singleTop` 且目标在栈顶、`singleTask`/`singleInstance` 栈内已有实例，或者 Intent Flag 触发复用。注意 `onNewIntent` 不会自动替换 `getIntent()` 返回值，必要时要调用 `setIntent(intent)`。

**Activity 之间传递数据有哪些方式？**

常见方式包括 Intent extras、Bundle、Parcelable/Serializable、Activity Result API、共享 ViewModel、数据库/文件/缓存传 ID 查询、ContentProvider。现代项目里跨页面返回结果优先用 Activity Result API，Fragment 间通信优先用 Fragment Result API 或共享 ViewModel。

**跨 App 启动 Activity 注意什么？**

可以通过显式 ComponentName 或隐式 Intent + intent-filter。被启动方如果对外暴露组件，需要设置 `android:exported=true`，并通过 permission、签名校验、参数校验、防重放等方式保护入口。Android 12 后 exported 是强制要求。

**任务栈是不是严格的 Stack？**

概念上可按栈理解，但 Framework 内部是以 Task、ActivityRecord 等结构管理，支持重排、复用、移动到前台、清栈等复杂操作，所以不要把它理解成单纯的后进先出数组。

## 2. Service 与后台任务

### 2.1 Service 生命周期

`startService`：调用方启动服务后，服务可独立运行。首次启动 `onCreate -> onStartCommand`，多次启动只回调 `onStartCommand`，调用 `stopService` 或 `stopSelf` 后销毁。

`bindService`：调用方绑定服务，用于进程内或跨进程通信。首次绑定 `onCreate -> onBind`，解绑后 `onUnbind -> onDestroy`。

混合使用时，只有“启动状态”和“绑定状态”都解除，Service 才会销毁。

### 2.2 onStartCommand、后台限制与前台服务

`START_NOT_STICKY`、`START_STICKY`、`START_REDELIVER_INTENT` 只描述 Service 进程被杀后的重建意图，不承诺系统一定立即或最终重启服务。

当前版本边界：

- Android 8.0+ 对后台 Service 有执行限制；可靠延期工作优先 WorkManager。
- Android 12+ 从后台启动前台服务通常受限，必须满足系统允许的例外，否则可能抛 `ForegroundServiceStartNotAllowedException`。
- 面向 Android 14+ 时，前台服务必须声明正确的 `foregroundServiceType` 及对应权限，并在运行时满足类型前置条件。
- Android 15+ 中，应用处于后台时，`dataSync` 与 `mediaProcessing` 类型各自在滚动 24 小时内累计最多运行 6 小时；超时会回调 `Service.onTimeout()`，服务必须在数秒内停止。
- Android 15+ 进一步限制从 `BOOT_COMPLETED` 启动多种前台服务类型。

选择 API 时先按任务语义判断：可延迟且需保证完成用 WorkManager；用户主动发起的数据传输考虑用户发起的数据传输 API；必须持续且用户可感知才使用前台服务。

### 2.3 IntentService 是否还推荐

`IntentService` 内部使用 `HandlerThread` 串行处理任务，任务结束后自动停止。它的思想仍值得理解，但类本身已经不推荐作为新代码首选。

现代替代：

- 可靠延迟任务：`WorkManager`。
- 页面生命周期内并发任务：Kotlin coroutines + `viewModelScope` / `lifecycleScope`。
- 需要用户感知的长任务：Foreground Service。

### 2.4 Service 与 Activity 通信

常见方式：

- 同进程绑定：Service 返回自定义 Binder，Activity 拿到 Binder 后直接调用方法。
- 跨进程：AIDL、Messenger、ContentProvider、Broadcast 或 socket。
- 应用内状态同步：Repository + Flow/LiveData，UI 观察状态变化。

不建议把全局广播当作应用内事件总线；`LocalBroadcastManager` 也已废弃，应用内事件优先使用 Kotlin Flow、LiveData 或明确的回调接口。

### 2.5 Service 补充题

**普通 Service 能不能做耗时任务？**

Service 默认运行在主线程，不能直接做耗时任务。耗时逻辑要切到线程池、协程、HandlerThread，或者用 WorkManager/Foreground Service。Service 只是“没有界面的组件”，不是“后台线程”。

**bindService 和 startService 混用怎么销毁？**

start 后 Service 进入 started 状态，bind 后进入 bound 状态。只 `unbindService` 不会销毁 started Service；只 `stopService` 也不会销毁仍被绑定的 Service。必须 started 和 bound 两种关系都解除，才会走 `onDestroy`。

**系统服务和 bindService 启动的服务有什么区别？**

系统服务通常运行在 system_server 或独立系统进程，通过 ServiceManager 注册并暴露 Binder；应用 Service 是四大组件之一，由 AMS 管理生命周期，通过 bindService 返回 Binder 给客户端。两者都可走 Binder，但注册、权限、生命周期、进程身份不同。

## 3. BroadcastReceiver

### 3.1 广播分类

- 普通广播：`sendBroadcast`，接收者无确定顺序。
- 有序广播：`sendOrderedBroadcast`，接收者按优先级顺序处理，可中断。
- 系统广播：系统发送，如电量、时区、开机、网络变化等。
- 应用内事件：现代项目不建议依赖广播，可用 Flow/LiveData/回调替代。

过时点：粘性广播在 Android 5.0 后基本不推荐；`LocalBroadcastManager` 已废弃。

### 3.2 Manifest Receiver 与 Context Receiver

Manifest 注册适合应用未运行时仍需接收的少数广播，但 Android 8.0+ 面向 API 26 的应用不能在 Manifest 中声明大多数隐式广播，豁免项除外。动态注册只在注册 Context 有效期间接收。

导出边界：

- API 33 引入 `RECEIVER_EXPORTED` / `RECEIVER_NOT_EXPORTED`。
- 面向 Android 14+ 时，动态注册非纯系统广播的 Receiver 必须明确导出行为。
- 只接收本应用广播用 `RECEIVER_NOT_EXPORTED`；需要接收其他应用或部分高权限系统应用广播时用 `RECEIVER_EXPORTED` 并加权限与数据校验。
- 若一组 IntentFilter 中既有仅应用内广播又有外部广播，应拆成不同 Receiver。

注册范围要与生命周期对称，及时 `unregisterReceiver()`；若 Receiver 可能活得比 Activity 长，应使用 Application Context，避免泄漏。

### 3.3 广播分发原理

动态注册时，应用把 `IIntentReceiver` Binder 对象和 `IntentFilter` 注册到 AMS。广播发送后，AMS 根据 Intent 匹配接收者，通过 Binder 回调目标进程，再由 `ActivityThread` 的 Handler 切到主线程执行 `onReceive`。

静态广播需要 PMS 参与解析 Manifest 中的 Receiver 信息，必要时拉起目标进程。

`onReceive` 运行在主线程，必须快速返回。耗时任务用 `goAsync`、WorkManager 或前台服务承接。

### 3.4 BroadcastReceiver 补充题

**有序广播还能不能用？**

可以用，但场景变少。它允许接收者按优先级处理并中断广播，适合强顺序的系统/平台能力。普通业务事件不建议滥用有序广播，因为耦合高、链路难追踪。

**onReceive 里能不能开线程？**

可以启动短任务，但 `onReceive` 返回后进程优先级可能降低，后台任务不可靠。需要异步处理时可用 `goAsync()` 获取 `PendingResult`，并尽快 `finish()`；可靠任务优先交给 WorkManager 或前台服务。

## 4. ContentProvider

### 4.1 作用

ContentProvider 为跨应用数据访问提供统一接口，通过 Uri 标识数据，外部使用 `ContentResolver` 调用 `query/insert/update/delete`。

三者关系：

- `ContentProvider`：真正管理数据。
- `ContentResolver`：调用方访问 Provider 的入口。
- `ContentObserver`：观察数据变化。

### 4.2 原理

Provider 启动时会安装到应用进程，并向 AMS 注册。调用方通过 AMS 获取目标 Provider 的 Binder 代理，再通过 Binder 调用 Provider 方法。查询结果通常通过 `Cursor` 返回，大数据查询会涉及跨进程游标窗口。

实践注意：

- 对外 Provider 必须做好权限控制。
- 查询不要在主线程执行。
- 文件共享优先使用 `FileProvider`，不要直接暴露 file path。

### 4.3 ContentProvider 补充题

**为什么 ContentProvider 适合跨进程数据共享？**

它统一了 Uri 寻址、权限控制、跨进程调用和数据变更通知。调用方不需要知道数据实际来自 SQLite、文件还是网络，只通过 ContentResolver 操作。

**ContentObserver 怎么工作？**

观察者通过 ContentResolver 注册到指定 Uri。当 Provider 数据变化时调用 `notifyChange(uri)`，系统再通知相关观察者。通知回调在哪个线程执行取决于注册时传入的 Handler。

## 当前官方参考

- [Activity lifecycle](https://developer.android.com/guide/components/activities/activity-lifecycle)
- [ANR diagnosis](https://developer.android.com/topic/performance/anrs/diagnose-and-fix-anrs)
- [Foreground services](https://developer.android.com/develop/background-work/services/fgs/changes)
- [Broadcasts](https://developer.android.com/develop/background-work/background-tasks/broadcasts)
- [Android App Links](https://developer.android.com/training/app-links/about)
