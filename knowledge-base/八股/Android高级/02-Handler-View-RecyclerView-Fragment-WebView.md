---
category: 八股
created_at: '2026-07-23'
difficulty: advanced
source_file: Android高级开发面试八股优化整理.md
subcategory: Android高级
tags:
- Handler
- Looper
- View
- RecyclerView
- Fragment
- ViewPager2
- Navigation
- WebView
title: Android 高级八股：Handler、View、RecyclerView、Fragment 与 WebView
updated_at: '2026-07-23'
verified_at: '2026-07-23'
---

# Android 高级八股：Handler、View、RecyclerView、Fragment 与 WebView

> 时效性：2026-07-23 使用 Android CLI 1.0.15857036 与 Android 官方知识库复核。版本敏感内容已在正文标注；第三方旧链接仅作历史索引。

## 5. Handler、Looper 与消息机制

### 5.1 核心模型

`Handler` 负责发送和处理消息，`Message` 是消息载体，`MessageQueue` 是按执行时间排序的单链表队列，`Looper` 不断从队列取消息并分发。

流程：

```text
Handler.sendMessage/post
-> MessageQueue.enqueueMessage
-> Looper.loop
-> MessageQueue.next
-> Handler.dispatchMessage
-> handleMessage 或 Runnable.run
```

一个线程最多一个 Looper 和一个 MessageQueue，但可以有多个 Handler。Looper 通过 `ThreadLocal` 与线程绑定。

### 5.2 子线程能否 new Handler

可以，但前提是当前线程已执行 `Looper.prepare()` 并开启 `Looper.loop()`。主线程可以直接创建 Handler，是因为 `ActivityThread.main()` 已经准备并启动了主线程 Looper。

子线程也可以创建指向主线程的 Handler：

```kotlin
val mainHandler = Handler(Looper.getMainLooper())
```

### 5.3 Handler 内存泄漏

非静态内部 Handler 会隐式持有外部 Activity；如果消息队列中还有延迟消息，引用链可能是：Message -> Handler -> Activity，导致 Activity 无法回收。

解决：

- 使用静态内部类 + WeakReference。
- 在 `onDestroy` 中 `removeCallbacksAndMessages(null)`。
- 现代代码优先使用 `lifecycleScope`、`viewModelScope`、`repeatOnLifecycle` 管理任务。

### 5.4 post 与 sendMessage

`post(Runnable)` 本质也是构造 Message，只是把 Runnable 放到 `Message.callback`。分发时优先执行 callback；没有 callback 时才调用 Handler 的 `handleMessage`。

### 5.5 同步屏障与异步消息

MessageQueue 支持同步屏障。插入同步屏障后，普通同步消息会被挡住，异步消息可以优先执行。Android UI 刷新链路中，`ViewRootImpl.scheduleTraversals` 会使用同步屏障，保证 VSync 到来后的遍历、绘制任务优先执行。

异步消息来源：

- 创建异步 Handler。
- `Message.setAsynchronous(true)`。

### 5.6 IdleHandler

`MessageQueue.IdleHandler` 会在消息队列空闲时回调。适合做轻量、非关键的延迟初始化，例如首帧后加载次要模块。

注意：Idle 不代表永远有机会执行；如果队列持续繁忙或有同步屏障影响，执行时机可能推迟。

### 5.7 为什么主线程 Looper 死循环不会卡死

`Looper.loop()` 是事件循环，不是持续占满 CPU 的忙等。没有消息时，`MessageQueue.next()` 会通过 native poll/epoll 阻塞等待；有消息或被唤醒后继续处理。主线程“卡死”的根因不是 loop 本身，而是某个消息执行太久、阻塞了后续事件。

### 5.8 Handler 补充题

**MessageQueue 是什么数据结构？**

Java 层 MessageQueue 不是普通队列，而是按 `when` 时间排序的单链表。延迟消息会根据触发时间插入到合适位置，`next()` 取队头，未到时间则阻塞等待。

**先 postDelay 10 秒，再 post 一个普通消息，会怎样？**

延迟消息 A 入队后，队列可能阻塞到 A 的执行时间；随后普通消息 B 入队，如果 B 成为队头，会唤醒 MessageQueue，Looper 先处理 B，再继续等待 A。

**Message.obtain 为什么比 new Message 好？**

`Message.obtain()` 会从消息池复用 Message，减少频繁分配和 GC。Message 被分发后会回收到池中，池大小有限。面试里说清“对象池 + 单链表 + 回收”即可。

**HandlerThread 是什么？**

HandlerThread 是带 Looper 的线程。启动后在子线程中准备 Looper，外部用这个 Looper 创建 Handler，把任务串行投递到该子线程。适合轻量串行后台任务，比如本地 I/O、日志写入。大量并发任务更适合线程池或协程 Dispatcher。

**quit 和 quitSafely 区别？**

`quit()` 会直接退出消息循环，队列中未处理消息会被移除；`quitSafely()` 会先处理已经到期的消息，再移除尚未到期的延迟消息，更适合平滑停止。

**Looper 如何区分多个 Handler？**

每个 Message 有 `target` 字段指向发送它的 Handler。Looper 取到 Message 后调用 `msg.target.dispatchMessage(msg)`，所以同一个 Looper 可以服务多个 Handler。

**ANR 和 Handler 的关系是什么？**

ANR 不是 Handler 直接抛出的异常，而是主线程消息处理被阻塞，导致输入、广播、服务等系统事件超时。主线程所有 UI 和生命周期回调都在消息循环里执行，所以某个消息耗时过长会拖住后续消息。

## 6. View 绘制与事件分发

### 6.1 View 绘制流程

绘制三大阶段：

- `measure`：测量 View 尺寸。
- `layout`：确定 View 在父容器中的位置。
- `draw`：绘制背景、内容、子 View、装饰。

入口通常是 `ViewRootImpl.performTraversals()`。当调用 `requestLayout`、`invalidate` 等方法时，会请求下一次 VSync，再执行遍历。

### 6.2 MeasureSpec

`MeasureSpec` 是一个 32 位 int，高 2 位表示模式，低 30 位表示尺寸。

- `EXACTLY`：父容器确定了精确尺寸，常见于固定值或 `match_parent`。
- `AT_MOST`：子 View 最大不能超过父容器给的尺寸，常见于 `wrap_content`。
- `UNSPECIFIED`：父容器不限制子 View，常见于 ScrollView 内部测量等特殊场景。

自定义 View 如果不重写 `onMeasure` 处理 `wrap_content`，通常会表现得像 `match_parent` 或占满父容器可用空间。

### 6.3 为什么 onCreate 拿不到 View 宽高

`onCreate` 时 View 只是被 inflate，还没有完成 measure/layout。获取宽高方式：

- `view.post { }`
- `ViewTreeObserver.OnGlobalLayoutListener`
- `doOnLayout` / `doOnPreDraw`
- `onWindowFocusChanged`，但会多次回调，不适合通用逻辑。

### 6.4 invalidate、postInvalidate 与 requestLayout

- `invalidate`：请求重绘，不一定重新测量布局，需在 UI 线程调用。
- `postInvalidate`：可在子线程调用，内部切到 UI 线程请求重绘。
- `requestLayout`：请求重新 measure/layout/draw，成本更高。

### 6.5 SurfaceView、TextureView、GLSurfaceView

`SurfaceView` 拥有独立 Surface，可在子线程绘制，适合视频、相机预览、高频渲染。缺点是与普通 View 层级混合、动画裁剪等历史上更复杂。

`TextureView` 在 View 层级内合成，适合需要平移、缩放、旋转等变换的视频/相机预览，但通常比 SurfaceView 更占资源。

`GLSurfaceView` 封装 EGL/OpenGL 渲染线程，适合 OpenGL 场景。

<span id="view-event-dispatch-overview" class="kb-anchor-offset"></span>

### 6.6 事件分发

事件分发真正解决的是“这次从 DOWN 开始的手势归谁”。核心方法：

- `dispatchTouchEvent`：分发事件。
- `onInterceptTouchEvent`：ViewGroup 决定是否拦截。
- `onTouchEvent`：View 自己消费事件。

入口链路可概括为：ViewRootImpl -> DecorView -> Activity -> Window -> DecorView/ViewGroup -> 子 View。DecorView 看似出现两次，是因为它先通过 Window.Callback 把事件交给 Activity，Activity 再通过 Window.superDispatchTouchEvent 进入 DecorView 父类的 ViewGroup 分发。

ViewGroup 在 DOWN 时清理上一段手势状态；未拦截时倒序命中子 View。子 View 消费 DOWN 后，会被记录为本次手势的 TouchTarget，后续 MOVE/UP 沿这个目标继续分发，而不是每次重新寻找子 View。

父容器可以在 MOVE 阶段中途拦截。此时原子 View 收到 `ACTION_CANCEL`，父容器从当前事件开始在自己的 `onTouchEvent` 中接管。若 DOWN 没有被某个 View 消费，后续 MOVE/UP 通常不会再分发给它。

滑动冲突的两种经典方案：

- 外部拦截法：父容器在 `onInterceptTouchEvent` 中根据 `touchSlop`、方向和子 View 边界统一决定是否接管。
- 内部拦截法：子 View 在 DOWN 时调用 `requestDisallowInterceptTouchEvent(true)`，先禁止祖先拦截；MOVE 判断应交给父容器时再传 false。这个标记会沿 parent 链向上传递，并在手势结束时重置。

<a class="kb-deep-link" href="/android-framework/view-system/view-event-dispatch#view-event-dispatch-deep-dive" target="_self">
  <span class="kb-deep-link__eyebrow">深入阅读 · 原理、源码与代码实现</span>
  <strong>View 事件分发、触摸目标与滑动冲突</strong>
  <span>查看 ViewRootImpl 到 ViewGroup 的完整链路、mFirstTouchTarget 状态机、ACTION_CANCEL，以及外部/内部拦截法的可运行 Kotlin 写法。</span>
</a>

### 6.7 View 绘制补充题

**getWidth 和 getMeasuredWidth 区别？**

`getMeasuredWidth()` 是 measure 阶段得到的测量宽度；`getWidth()` 是 layout 后右边界减左边界的实际宽度。大多数情况下相等，但自定义布局、动画、特殊测量时可能不同。

**View#post 和 Handler#post 区别？**

`Handler#post` 是直接把 Runnable 投递到对应 Handler 的 MessageQueue。`View#post` 会投递到 View 关联的 Handler；如果 View 还未 attach，Runnable 可能先暂存，attach 后再执行。因此 `View#post` 常用于等 View 完成 attach/布局后执行 UI 操作。

**为什么 LinearLayout 嵌套权重可能慢？**

`layout_weight` 可能导致 LinearLayout 对子 View 进行多次测量，尤其在嵌套和 `wrap_content` 场景下更明显。复杂布局更推荐 ConstraintLayout 或减少层级。

**FrameLayout、LinearLayout、RelativeLayout 谁更快？**

不能脱离布局复杂度绝对比较。FrameLayout 通常最简单；LinearLayout 简单排列性能好，但 weight 可能多测量；RelativeLayout 规则依赖较多，历史上容易多次 measure。现代项目重点是减少层级和过度测量，而不是死背某个布局一定最快。

**自定义 View 流程和注意事项？**

流程包括处理自定义属性、重写 `onMeasure`、必要时重写 `onLayout`、在 `onDraw` 绘制、处理触摸事件、保存恢复状态。注意支持 `wrap_content`、padding、RTL、无障碍、状态保存、避免 onDraw 分配对象。

**局部刷新怎么做？**

传统 View 可调用 `invalidate(Rect)` 或在绘制时只更新脏区域，但硬件加速和父子 View 合成会让实际刷新策略更复杂。业务层面更重要的是减少无意义 invalidate、缩小自定义 View 绘制范围、避免整页 requestLayout。

**setContentView 之后发生了什么？**

Activity 的 PhoneWindow 创建 DecorView，LayoutInflater 把 XML 加载成 View 树，并添加到 DecorView 的 content 区域。之后 WindowManager 将 DecorView 添加到窗口，ViewRootImpl 负责后续 measure/layout/draw 和输入事件。

### 6.8 屏幕刷新、Choreographer 与 Surface

**Android 绘制和屏幕刷新大致怎么协作？**

App 主线程收到 VSync 后执行 Choreographer 回调，完成 View 树遍历并提交渲染命令；RenderThread/GPU 完成栅格化和合成准备；SurfaceFlinger 负责把多个 Surface 合成后交给显示设备。掉帧通常是 App 主线程、RenderThread、GPU 或 SurfaceFlinger 任一环节超预算。

**双缓冲、三缓冲是什么？**

双缓冲通常一个前台 buffer 用于显示，一个后台 buffer 用于绘制，绘制完成后交换。三缓冲增加一个缓冲区，降低生产者和消费者互相等待的概率，但可能增加延迟和内存占用。

**SurfaceView 为什么可以子线程绘制？**

SurfaceView 拥有独立 Surface，绘制不完全依赖普通 View 树的 `onDraw`。开发者可以在子线程锁定 Canvas 或使用 OpenGL 绘制，然后提交到 Surface。

**TextureView 和 SurfaceView 怎么选？**

SurfaceView 更适合视频、相机、游戏等高性能场景；TextureView 作为 View 树的一部分，支持普通 View 动画、缩放、旋转、透明等，但合成成本通常更高。

### 6.9 事件分发补充题

**OnTouchListener、onTouchEvent、OnClickListener 顺序？**

View 的 `dispatchTouchEvent` 中会先调用 OnTouchListener。如果 `onTouch` 返回 true，事件被消费，`onTouchEvent` 不再执行；如果返回 false，继续走 `onTouchEvent`。点击事件是在 `onTouchEvent` 处理 UP 时触发 `performClick`，再回调 OnClickListener。

**ACTION_CANCEL 什么时候触发？**

常见于父 View 中途拦截事件、手势被系统打断、窗口失去焦点、多指或滑动冲突导致当前 View 不再继续接收事件。收到 CANCEL 后应清理按压、拖拽等临时状态。

**父子 View 都设置点击，谁优先？**

事件从父分发到子，通常子 View 如果可点击并消费 DOWN/UP，就由子响应；父 View 是否响应取决于是否拦截或子是否消费。不要简单背“子优先”或“父优先”，要看 dispatch/intercept/touch 返回值。

## 7. RecyclerView

### 7.1 多级缓存

RecyclerView 复用体系常见层次：

- `mAttachedScrap` / `mChangedScrap`：屏幕内临时分离的 ViewHolder，通常不需要重新绑定。
- `mCachedViews`：屏幕外缓存，默认大小较小，可能直接复用。
- `ViewCacheExtension`：开发者自定义缓存，少用。
- `RecycledViewPool`：按 viewType 缓存 ViewHolder，跨 RecyclerView 共享。

### 7.2 为什么要预布局

预布局用于支持动画。Adapter 数据变化后，RecyclerView 先保留变化前后的位置信息，ItemAnimator 才能知道从哪里移动到哪里、哪个 item 被删除或新增。

### 7.3 性能优化

- 使用 `DiffUtil` / `ListAdapter` / `AsyncListDiffer` 做最小刷新。
- 避免 `notifyDataSetChanged`。
- 多类型列表保持 viewType 稳定，减少不必要布局层级。
- 图片加载跟随生命周期，滑动时可暂停低优先级加载。
- 设置合适的 `setHasFixedSize`、共享 `RecycledViewPool`、预取策略。
- Compose 中对应关注 LazyColumn key 稳定性、item contentType、重组范围。

### 7.4 RecyclerView 补充题

**ListView 和 RecyclerView 区别？**

RecyclerView 把布局、动画、分割线、复用池拆成可插拔组件，支持多布局、局部刷新、ItemAnimator、LayoutManager、DiffUtil。ListView 内置能力更固定，现代新项目基本优先 RecyclerView 或 Compose LazyColumn。

**RecyclerView 局部刷新为什么更强？**

它支持 `notifyItemChanged/Inserted/Removed/Moved` 和 payload，可只重新绑定局部 item 或局部字段，配合 DiffUtil 能减少刷新范围和动画异常。

**缓存为什么分多级？**

屏幕内临时缓存避免布局过程重复创建；屏幕外小缓存避免刚滑出又滑回时重新绑定；RecycledViewPool 面向跨位置甚至跨 RecyclerView 的复用。多级缓存是在内存和绑定成本之间折中。

## 8. Fragment、ViewPager 与 Navigation

### 8.1 Fragment 生命周期：Fragment 与 View 是两个 LifecycleOwner

当前 AndroidX Fragment 的正确模型不是只背一条回调链。一个 Fragment 实例有自己的 Lifecycle；当它返回非空 View 时，还会创建独立的 View Lifecycle。Fragment 进入返回栈后实例可能仍处于 `CREATED`，但旧 View 已执行 `onDestroyView()`，之后返回时再创建新 View。

状态上限由三层共同决定：FragmentManager 当前状态、父 Fragment/Activity 状态，以及事务通过 `setMaxLifecycle()` 设置的最大状态。子 Fragment 不可能高于父级；ViewPager2 通常把离屏 Fragment 的最大状态限制在 `STARTED`。

创建方向的关键顺序：

1. `onAttach()` 在任何 Lifecycle 状态变化前发生。
2. `onCreate()`：Fragment 进入 `CREATED`，此时 View 尚不存在。
3. `onCreateView()` 返回非空 View 后创建 View LifecycleOwner，随后调用 `onViewCreated()`。
4. 旧 View 状态恢复后调用 `onViewStateRestored()`，View Lifecycle 进入 `CREATED`。
5. 进入更高状态时，先调用 Fragment 回调，再向 Fragment Lifecycle、View Lifecycle 依次发送事件。

离开方向的关键顺序与上行不同：

1. 先向 View Lifecycle 发送下降事件，再向 Fragment Lifecycle 发送事件，最后调用对应 Fragment 回调。
2. 退出动画完成且 View 脱离窗口后，View Lifecycle 先发送 `ON_DESTROY`，随后调用 `onDestroyView()`。
3. Fragment 被真正移除或 FragmentManager 销毁后才进入 `DESTROYED`、调用 `onDestroy()`；`onDetach()` 最后发生。

实践规则：

- ViewBinding 在 `onDestroyView()` 置空，任何 View、Adapter、监听器引用都不应越过 View 生命周期。
- 更新 View 的 Flow/LiveData 观察者绑定 `viewLifecycleOwner`，Flow 用 `viewLifecycleOwner.lifecycleScope + repeatOnLifecycle(STARTED)`。
- Fragment 参数放 `arguments`/Safe Args，不依赖自定义构造函数；不要复用已从 FragmentManager 移除的 Fragment 实例。
- XML 容器优先 `FragmentContainerView`，避免旧 `<fragment>` 标签让 Fragment 超过 FragmentManager 状态。

### 8.2 Fragment 通信

推荐方式：

- Activity 与 Fragment 共享 `ViewModel`。
- Fragment Result API。
- Navigation Safe Args。
- 明确接口回调。

不推荐：大量使用 EventBus 或通过 `getActivity()` 强转互相调用，耦合高且生命周期风险大。

### 8.3 ViewPager2

ViewPager2 基于 RecyclerView，使用 `FragmentStateAdapter`，支持竖向滑动、RTL、DiffUtil 等。旧的 `FragmentPagerAdapter`、`FragmentStatePagerAdapter` 已不再是新项目首选。

### 8.4 Navigation、返回栈与预测性返回

Navigation 由 `NavController` 管理目的地和返回栈。底部导航等多入口场景应使用多返回栈的状态保存/恢复能力：`saveState`、`restoreState`、`popUpToSaveState`，并配合 `launchSingleTop`，而不是手动缓存 Fragment 实例。

返回行为应接入 Navigation 或 `OnBackPressedDispatcher`。现代系统支持预测性返回动画，继续直接覆写已废弃的 `Activity.onBackPressed()` 会绕开生命周期感知和预测性返回链路。

页面实例是否重建取决于导航、返回栈、进程与 FragmentManager 状态恢复。需要保留的 UI 状态放 ViewModel/SavedStateHandle，需要持久的数据放仓库层，不应依赖 Fragment 实例永远复用。

## 9. WebView

### 9.1 加载优化

- 提前创建或复用 WebView 池，但要谨慎处理内存和 Context 泄漏。
- 静态资源缓存、离线包、HTTP 缓存。
- DNS 预解析、连接复用、首屏关键资源优先。
- 原生注入必要参数，减少 H5 首屏等待。

### 9.2 JS 交互

Android 调 JS 优先 `evaluateJavascript()`。JS 调 Android 可使用 `addJavascriptInterface`、WebMessage API 或受控 URL 路由，但“换成 WebMessage 就自动安全”是误区。

`addJavascriptInterface` 会把对象暴露给 WebView 中所有 frame，应用无法仅凭接口调用可靠判断 frame 的真实 origin。因此只应对完全可信、受控内容启用，接口最小化并仅暴露 `@JavascriptInterface` 方法；切换到不可信内容前移除接口。

`postWebMessage`/MessageChannel 必须指定可信 target origin，不能用 `*`；收到消息后继续校验来源、消息结构、身份和业务权限。

### 9.3 安全注意

- 本地内容优先 `WebViewAssetLoader` 的 HTTPS 风格地址，避免 `file://` 与宽松文件访问。
- 不加载不可信 file/content URL；关闭不必要的 JavaScript、文件访问和混合内容。
- 启用 Safe Browsing，限制可导航域名，对重定向后最终 URL 也做校验。
- JSBridge 参数必须校验来源、长度、类型、登录态和业务授权。
- WebView 独立进程只能降低崩溃影响，不能代替内容与桥接层安全校验。

### 9.4 WebView 补充题

**WebView 常见漏洞有哪些？**

包括 `addJavascriptInterface` 暴露对象过大、file 域访问导致本地文件泄露、明文 HTTP/混合内容、中间人篡改、任意 scheme 跳转、JSBridge 参数未校验。修复思路是最小暴露、限制 file access、HTTPS、域名白名单、参数签名校验。

**JSBridge 常见原理？**

JS 调 Native 常见有 URL Scheme 拦截、注入对象、prompt 拦截、WebMessagePort。Native 调 JS 常用 `evaluateJavascript`。桥接层要解决方法注册、参数序列化、回调 ID、线程切换和安全校验。

## 10. 动画

**视图动画、帧动画、属性动画区别？**

视图动画只改变 View 的显示效果，不改变真实属性和点击区域；帧动画按帧播放 drawable，图片多时内存压力大；属性动画真正改变对象属性，适用范围更广，是现代 Android 动画核心。

**ObjectAnimator 和 ValueAnimator 区别？**

`ValueAnimator` 只产生动画过程中的值，需要开发者在监听里使用这些值；`ObjectAnimator` 是 ValueAnimator 的子类，会通过属性 setter 自动修改目标对象属性。

**Interpolator 和 Evaluator 区别？**

Interpolator 决定动画进度随时间如何变化，例如加速、减速、回弹；Evaluator 决定在某个进度下，起始值和结束值之间如何计算具体值，例如颜色、Point、自定义对象。

## 当前官方参考

- [Fragment Lifecycle](https://developer.android.com/guide/fragments/lifecycle)
- [Multiple back stacks](https://developer.android.com/guide/navigation/backstack/multi-back-stacks)
- [Predictive back](https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture)
- [WebView native bridge risks](https://developer.android.com/privacy-and-security/risks/insecure-webview-native-bridges)
