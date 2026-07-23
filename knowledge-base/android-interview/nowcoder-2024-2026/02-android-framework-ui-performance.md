---
category: android-interview
created_at: '2026-07-22'
difficulty: advanced
source_count: 19
subcategory: nowcoder-2024-2026
tags:
- Android
- Framework
- Activity
- Fragment
- Handler
- Binder
- RecyclerView
- 内存泄漏
- 启动优化
title: Android Framework、UI 与性能：面经高频机制内化
updated_at: '2026-07-22'
---

# 1. 生命周期与状态：不要把回调表当成答案

Activity 和 Fragment 生命周期的本质，是系统根据“可见性、交互焦点、宿主状态、配置变化和进程存活”推进组件状态。

## Activity 切换

从 A 启动 B，常见顺序是：

A.onPause → B.onCreate → B.onStart → B.onResume → A.onStop。

真正顺序会受 B 是否透明、主题、窗口展示时机等影响。只背固定序列容易在“Dialog、透明 Activity、分屏”场景出错。

## 配置变化与进程重建

- 横竖屏等配置变化默认会销毁并重建 Activity。
- ViewModel 可跨配置重建保留内存状态，因为它挂在 ViewModelStore 上，而不是旧 Activity 实例上。
- ViewModel 不能抵抗进程死亡；需要 SavedStateHandle、Bundle、数据库或文件。
- Bundle 适合体积小、可序列化、重建所需的关键状态，不适合大对象、Bitmap、复杂业务缓存。

## Fragment 常见问题

Fragment 同时具有“Fragment 生命周期”和“View 生命周期”。把 ViewBinding、订阅或请求绑定到 Fragment 本体，而不是 viewLifecycleOwner，容易造成：

- View 已销毁但订阅仍回调；
- 返回栈恢复后重复订阅；
- 请求重复发起；
- 持有旧 View 引用导致泄漏。

# 2. Handler、Looper 与 MessageQueue

## 角色关系

- Looper：把当前线程与一个消息循环绑定。
- MessageQueue：按时间管理待执行消息，必要时阻塞线程。
- Handler：把消息或 Runnable 投递到指定 Looper，并负责分发处理。
- Message：承载任务和参数，使用对象池降低高频分配与 GC 压力。

一个线程可以有多个 Handler，但通常只有一个 Looper 和一个 MessageQueue。不同 Handler 的消息进入同一个队列，取出后根据 Message.target 回到对应 Handler。

## 为什么主线程不会退出

应用主线程进入 Looper.loop 后持续从 MessageQueue 取消息。队列暂无可执行消息时，不是忙等，而是进入 native 层等待；新消息到来或定时消息到期时再被唤醒。因此“无限循环”不等于持续占用 CPU。

## post 与 sendMessage

Handler.post(Runnable) 最终也是把任务包装到 Message 中。它与 sendMessage 的核心传输路径相同，区别主要是消息携带的是 callback 还是 what/obj 等字段。

## 常见边界

- 子线程直接 new Handler 报错，是因为该线程没有准备 Looper。
- 可以在线程中 Looper.prepare、创建 Handler、Looper.loop，但更常用 HandlerThread 或协程。
- 匿名内部类 Handler 可能隐式持有 Activity；如果队列中的延迟消息活得更久，就形成泄漏链。
- Handler 不是线程；它只是向某个线程的队列投递工作。

# 3. Binder 与 IPC

## 为什么 Android 主要使用 Binder

Linux 已有管道、Socket、共享内存等 IPC。Binder 额外提供了更适合 Android 系统服务模型的能力：

- 面向对象的远程调用接口；
- 内核可识别调用方身份，便于权限校验；
- 引用计数和死亡通知；
- 相比多次拷贝的传统方案，常规调用数据路径更高效；
- 与 ServiceManager 和系统服务体系紧密结合。

这不代表 Binder 在任何情况下都最快。大块数据仍应考虑共享内存、文件或流式传输；Binder 事务有大小限制。

## 一次调用的基本路径

客户端代理对象发起调用 → 参数序列化到 Parcel → Binder 驱动把事务交给服务端进程 → Binder 线程池取出事务 → Stub 反序列化并调用真实实现 → 返回结果。

AIDL 的本质是生成 Proxy/Stub、事务码和 Parcel 编解码样板。

## 主线程 Binder 风险

Binder 调用在语法上像本地方法，但服务端可能排队、锁等待、访问磁盘或网络。主线程同步调用仍可能卡顿或触发 ANR，所以必须根据远端成本选择线程和超时策略。

# 4. View 绘制、事件分发与自定义 View

## 绘制流程

ViewRootImpl 发起遍历，核心阶段是 measure、layout、draw。

- measure：父节点通过 MeasureSpec 约束子节点，子节点计算 measuredWidth/Height。
- layout：确定每个 View 在父容器中的实际位置。
- draw：背景、内容、子 View、装饰等按顺序绘制。

“create → measure → layout → draw”不是准确流程；create 是对象构造，不属于每帧遍历阶段。

## 事件分发

触摸事件经 ViewRootImpl、DecorView、Activity/Window 进入 ViewGroup，再通过 dispatchTouchEvent、onInterceptTouchEvent、onTouchEvent 决定目标、拦截和消费。子 View 消费 DOWN 后会成为本次手势的 TouchTarget；父容器如果在 MOVE 中途拦截，子 View 会收到 ACTION_CANCEL，后续事件由父容器处理。

滑动冲突的根本是父子容器都可能解释同一手势。解决方案不是机械调用 requestDisallowInterceptTouchEvent，而是明确：

- 哪个方向或阶段由谁拥有手势；
- 何时从点击判定切换为滑动判定；
- ACTION_DOWN 到后续事件必须保持一致的目标链。

<a class="kb-deep-link" href="/android-framework/view-system/view-event-dispatch#view-event-dispatch-deep-dive" target="_self">
  <span class="kb-deep-link__eyebrow">深入阅读 · 源码链路</span>
  <strong>View 事件分发、触摸目标与滑动冲突</strong>
  <span>从 TouchTarget、DISALLOW_INTERCEPT、ACTION_CANCEL 展开，并给出外部拦截法和内部拦截法的具体实现。</span>
</a>

## 自定义 View

圆角图片、图表、特殊布局等题目应说明：

- 属性读取和默认值；
- 测量策略；
- 绘制方案：clipPath、BitmapShader、Outline 或离屏层；
- 图片缩放模式和边界；
- 对象复用，避免 onDraw 中频繁分配；
- 无障碍、点击区域和状态保存。

# 5. RecyclerView 与复杂列表

RecyclerView 的核心不是“有缓存”，而是把 ViewHolder 创建、绑定和复用拆开，并通过多层缓存与 RecycledViewPool 降低重复创建成本。

回答复杂列表题时至少覆盖：

- item type 与稳定 id；
- ViewHolder 绑定必须完整覆盖旧状态，避免错位；
- 局部刷新 payload 与 DiffUtil；
- 图片/视频生命周期，进入和离开屏幕时释放；
- 预取、嵌套列表、共享 RecycledViewPool；
- 曝光埋点不能只以绑定回调代替真实可见；
- 异步结果必须校验 item 身份，防止复用后回写错位。

notifyDataSetChanged 会让框架失去精确变化信息，容易造成无效重绑和动画闪动；DiffUtil 能计算差异，但比较函数昂贵或数据频繁变化时也要控制成本。

# 6. 内存泄漏、GC 与 LeakCanary

## 根本逻辑

GC 依据从 GC Roots 出发的可达性判断对象是否存活。内存泄漏不是“对象没有释放函数”，而是本应结束生命周期的对象仍被一条强引用链连接到 GC Roots。

典型 GC Roots 包括活跃线程栈、静态字段、JNI 全局引用和系统运行时持有对象。

## Android 高频泄漏链

- 单例或静态集合持有 Activity/View。
- 非静态内部类、匿名类、Handler、Runnable 隐式持有外部类。
- 长生命周期线程、协程或回调未取消。
- Fragment 销毁 View 后仍持有 ViewBinding。
- 监听器、广播、观察者、WebView、Cursor、流未解绑或关闭。
- 缓存没有容量与淘汰边界。

“A 持有 B、B 持有 A”本身不一定泄漏；如果这个环没有被 GC Roots 连接，整个环仍可回收。

## LeakCanary 的思路

在 Activity/Fragment View 等生命周期结束后，把对象放入弱引用观察集合；等待 GC 后若对象仍存活，再触发堆转储并分析从 GC Roots 到目标对象的最短强引用路径。

弱引用不是通用修复方案。真正修复应消除错误的生命周期关系、取消任务、解绑监听或改变所有权。

# 7. 启动、列表、包体和线上性能

## 启动优化

完整回答顺序：

1. 定义冷、温、热启动。
2. 建立指标：进程启动、Application、首 Activity、首帧、可交互。
3. 用 trace 找关键路径，而不是凭感觉异步。
4. 初始化分类：首屏必需、可延后、可懒加载、后台预热。
5. 建立依赖图，避免异步后出现竞态。
6. 验证功能、线程安全、低端机、弱网和回退。
7. 灰度并监控 P50/P90/P99，而不只看平均值。

IdleHandler 只能在消息队列空闲时执行，不保证立刻，也不适合无界耗时任务。用它预加载 WebView 要考虑内存上涨、内核版本、Cookie/进程隔离和复用安全。

## 复杂首页偶现问题

首帧慢、模块乱序、旧角标、错跳和埋点不一致同时出现时，应怀疑共享状态、异步竞态、item 身份和事件时序，而不是分别打补丁。

推荐诊断路径：

- 为启动会话、请求、模块和实验分桶建立统一 trace id。
- 记录数据版本、提交顺序、主线程任务和首帧时间。
- 检查列表 diff、稳定 id、点击时读取的位置或对象是否过期。
- 区分“数据已返回、已绑定、已布局、实际可见”四个状态。
- 用线上采样、回放、灰度和对照实验验证根因。

## 包体优化

从资源、代码、Native 库和打包格式拆分：

- R8/ProGuard 移除无用代码和优化字节码；
- 资源 shrink、图片格式和多密度策略；
- ABI 精简、Native 符号与重复库分析；
- 动态特性、按需下载；
- 用 APK Analyzer 建立模块级体积预算。
