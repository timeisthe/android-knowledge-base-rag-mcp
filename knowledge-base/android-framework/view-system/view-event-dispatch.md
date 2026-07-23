---
category: android-framework
content_level: deep-dive
created_at: '2026-07-23'
difficulty: advanced
description: 从 ViewRootImpl、DecorView、Activity 到 ViewGroup TouchTarget，完整解释 View 事件分发、拦截、消费、ACTION_CANCEL，以及滑动冲突的外部拦截法和内部拦截法。
related_overview: /八股/Android高级/02-Handler-View-RecyclerView-Fragment-WebView#view-event-dispatch-overview
subcategory: view-system
tags:
- Android
- View
- ViewGroup
- MotionEvent
- dispatchTouchEvent
- onInterceptTouchEvent
- onTouchEvent
- TouchTarget
- 滑动冲突
- 源码链路
title: View 事件分发、触摸目标与滑动冲突：从源码链路到两种拦截法
updated_at: '2026-07-23'
verified_at: '2026-07-23'
---

<span id="view-event-dispatch-deep-dive" class="kb-anchor-offset"></span>

# View 事件分发、触摸目标与滑动冲突：从源码链路到两种拦截法

> 本文是事件分发的深挖层，适合在忘记细节、排查滑动冲突或准备源码追问时查阅。只想快速复习时，可返回 <a href="/八股/Android高级/02-Handler-View-RecyclerView-Fragment-WebView#view-event-dispatch-overview" target="_self">Android 高级八股中的事件分发速览</a>。

## 1. 先建立正确模型：系统在决定“这次手势归谁”

事件分发不是简单地从父 View 调用到子 View。它真正解决的是三个问题：

1. 当前坐标命中了哪个子 View？
2. 哪个 View 愿意接管从 `ACTION_DOWN` 开始的整段手势？
3. 手势进行到一半时，父容器能否从子 View 手里夺回控制权？

一次完整触摸手势通常从 `ACTION_DOWN` 开始，以 `ACTION_UP` 或 `ACTION_CANCEL` 结束。中间可能包含多个 `ACTION_MOVE`，多指场景还会出现 `ACTION_POINTER_DOWN` 和 `ACTION_POINTER_UP`。

最重要的不变量是：

> `ACTION_DOWN` 不只是一次普通回调，它用于建立后续事件的触摸目标。没有 View 接受 DOWN，就不会凭空在后续 MOVE 中重新选择一个普通子 View。

这也是为什么“某个方法返回 true”不能只理解为“这一行代码处理完了”：对 DOWN 返回 true，通常还表示“我愿意继续接收这次手势的后续事件”。

## 2. 关键类分别负责什么

### 2.1 MotionEvent：一次输入采样的数据载体

`MotionEvent` 保存动作类型、事件时间、按下时间、坐标、压力、工具类型和一个或多个 pointer。常用字段与方法：

- `actionMasked`：忽略 pointer index 后的动作类型。
- `actionIndex`：`POINTER_DOWN/POINTER_UP` 对应的是哪个 pointer index。
- `pointerCount`：当前事件里包含几个 pointer。
- `getPointerId(index)`：取得稳定的 pointer ID。
- `findPointerIndex(id)`：在本次事件中重新找到该 ID 的 index。
- `x/y`：相对当前接收 View 的坐标；事件向子 View 分发时会进行坐标转换。
- `rawX/rawY`：相对屏幕的坐标，不应直接代替局部坐标完成所有手势计算。

pointer index 在不同事件之间可能变化，pointer ID 在手指抬起前保持稳定。多指手势必须按 ID 跟踪，不能长期缓存 index。

### 2.2 ViewRootImpl：窗口输入与 View 树之间的桥

系统输入通过窗口的 `InputChannel` 进入应用进程，`ViewRootImpl.WindowInputEventReceiver` 接收 `InputEvent`，放入 ViewRootImpl 的输入阶段链。触摸事件到达 `ViewPostImeInputStage` 后，最终调用根 View 的：

```text
mView.dispatchPointerEvent(event)
```

`View.dispatchPointerEvent` 会判断它是不是触摸事件：

```text
touch event    -> dispatchTouchEvent
other pointer -> dispatchGenericMotionEvent
```

这里的 `mView` 通常是窗口的 `DecorView`。

### 2.3 Activity、Window 与 DecorView：窗口级入口和回调转发

应用常见的触摸调用链是：

```text
InputDispatcher / InputChannel
-> ViewRootImpl.WindowInputEventReceiver
-> ViewRootImpl 输入阶段链
-> DecorView.dispatchPointerEvent
-> DecorView.dispatchTouchEvent
-> Activity.dispatchTouchEvent
-> PhoneWindow.superDispatchTouchEvent
-> DecorView.superDispatchTouchEvent
-> ViewGroup.dispatchTouchEvent
-> 子 ViewGroup / View.dispatchTouchEvent
-> onTouchEvent
```

看起来 DecorView 出现了两次，但不是无限递归：

- `DecorView.dispatchTouchEvent` 先通过 `Window.Callback` 把事件交给 Activity。
- `Activity.dispatchTouchEvent` 再调用 `Window.superDispatchTouchEvent`。
- `DecorView.superDispatchTouchEvent` 调用的是父类 `FrameLayout/ViewGroup` 的实现，真正进入 View 树分发。

如果整棵 View 树都没有消费，`Activity.dispatchTouchEvent` 最后才会回退到 `Activity.onTouchEvent`。

### 2.4 ViewGroup：路由器，也是手势所有权管理器

`ViewGroup` 不只是“有 onInterceptTouchEvent 的 View”。它还维护本次手势已经交给了哪些子 View。

AOSP 中最关键的状态包括：

- `mFirstTouchTarget`：`TouchTarget` 链表头，记录正在接收事件的子 View。
- `TouchTarget.child`：实际触摸目标。
- `TouchTarget.pointerIdBits`：该目标接收哪些 pointer。
- `FLAG_DISALLOW_INTERCEPT`：子 View 是否要求祖先暂时不要拦截。
- `mLastTouchDownX/Y`：最近一次命中子 View 时的 DOWN 坐标。

单指场景通常只有一个 TouchTarget；启用事件拆分的多指场景中，不同 pointer 可以分配给不同子 View，因此源码使用链表和 pointer bitset，而不是只保存一个 `targetView`。

### 2.5 View：最终消费和点击状态机

普通 `View` 没有 `onInterceptTouchEvent`。它主要通过：

- `dispatchTouchEvent`：先执行安全过滤和 `OnTouchListener`，再决定是否进入 `onTouchEvent`。
- `onTouchEvent`：维护 pressed、long press、click、tooltip、TouchDelegate 等状态。
- `performClick`：触发点击语义、声音、无障碍事件和 `OnClickListener`。

因此 `OnTouchListener`、`onTouchEvent`、`OnClickListener` 不是三个平级回调。实际顺序是：

```text
View.dispatchTouchEvent
-> OnTouchListener.onTouch（View enabled 且监听器存在）
-> 若未消费，再调用 View.onTouchEvent
-> ACTION_UP 满足点击条件时 performClick
-> OnClickListener.onClick
```

## 3. ViewGroup.dispatchTouchEvent 的具体执行流程

下面按一次手势的状态变化拆开，而不是逐行翻译源码。

### 3.1 ACTION_DOWN：清理旧状态

收到新的 DOWN 时，ViewGroup 会先：

```text
cancelAndClearTouchTargets(ev)
resetTouchState()
```

这样做是为了防御上一段手势因为切应用、ANR、窗口变化等原因没有正常收到 UP/CANCEL。`resetTouchState` 会清空 TouchTarget、取消相关标记，并清除 `FLAG_DISALLOW_INTERCEPT`。

所以 `requestDisallowInterceptTouchEvent(true)` 只对当前手势有效，不会永久禁止父容器拦截。

### 3.2 判断父容器是否拦截

源码判断条件可以概括为：

```text
如果是 ACTION_DOWN，或者已经存在子 TouchTarget：
    如果没有 DISALLOW_INTERCEPT：调用 onInterceptTouchEvent
    否则：跳过父容器拦截，intercepted = false
否则：
    没有子目标，且又不是 DOWN，父容器继续按自己处理
```

为什么只有“DOWN 或已有子目标”时才值得继续询问 `onInterceptTouchEvent`？

- DOWN 要决定初始目标。
- 已有子目标时，父容器可能在 MOVE 阶段夺回手势。
- 如果没有子目标，说明之前没有子 View 接住这段手势；后续事件不需要重新扫描普通子 View，ViewGroup 直接按自身逻辑处理。

### 3.3 没被拦截时，倒序寻找命中的子 View

只有事件未取消、父容器也未拦截时，ViewGroup 才会为 DOWN 或 POINTER_DOWN 寻找新目标。

核心步骤：

1. 按绘制顺序从前到后扫描；源码循环通常表现为从子数组末尾向前，因为视觉上更靠上的 View 应优先命中。
2. 跳过不可见、不能接收 pointer 或坐标不在范围内的子 View。
3. 把 MotionEvent 坐标从父容器坐标系转换到子 View 坐标系。
4. 调用子 View 的 `dispatchTouchEvent`。
5. 子 View 返回 true 时，通过 `addTouchTarget` 把它加入 `mFirstTouchTarget`，停止继续寻找普通目标。

这就是“消费 DOWN 后才能持续收到后续事件”的源码基础：不是系统每次 MOVE 都重新命中测试，而是 DOWN 时建立了 TouchTarget。

### 3.4 后续 MOVE/UP：沿 TouchTarget 分发

已有 TouchTarget 后，MOVE/UP 主要沿目标链表分发，不再对所有子 View 做一次普通命中扫描。

分发前会通过 `dispatchTransformedTouchEvent`：

- 过滤不属于该目标的 pointer。
- 把坐标偏移到子 View 的局部坐标系。
- 考虑子 View 的变换矩阵。
- 必要时把 action 临时替换为 `ACTION_CANCEL`。
- 调用 `child.dispatchTouchEvent(event)`。
- 恢复原事件坐标和 action，避免影响其他目标。

### 3.5 父容器中途拦截：给子 View 发 CANCEL

假设子 View 已经消费 DOWN，父容器在 MOVE 时 `onInterceptTouchEvent` 返回 true：

1. 当前 TouchTarget 被标记为需要取消。
2. 同一个 MOVE 在发给子 View 前，被转换为 `ACTION_CANCEL`。
3. 子 View 清理 pressed、长按、拖拽等临时状态。
4. ViewGroup 从 TouchTarget 链表移除该子 View。
5. 当前事件和后续事件改由父容器自己的 `onTouchEvent` 处理。

因此父容器不是把 MOVE 同时交给自己和子 View 正常处理。所有权发生变化时，子 View 收到的是 CANCEL。

### 3.6 ACTION_UP / ACTION_CANCEL：结束并清理

手势结束时，ViewGroup 会调用 `resetTouchState`：

- 清空 TouchTarget。
- 清除 cancel 标记。
- 清除 `FLAG_DISALLOW_INTERCEPT`。
- 重置嵌套滚动轴等状态。

下一次 DOWN 会重新开始完整目标选择。

## 4. 三个核心方法的返回值到底表示什么

| 方法 | 返回 true 的实际含义 | 常见误解 |
|---|---|---|
| `View.dispatchTouchEvent` | 这个 View 对当前事件返回已处理；DOWN 返回 true 通常让它成为后续目标 | 等同于“拦截” |
| `ViewGroup.dispatchTouchEvent` | 可能是自己处理，也可能是某个子 View 处理 | 返回 true 就是父容器消费 |
| `ViewGroup.onInterceptTouchEvent` | 父容器要从子 View 分发链中拿走当前手势 | 只是观察事件，不影响子 View |
| `View.onTouchEvent` | 当前 View 的默认触摸处理消费了事件 | false 后仍会继续收到同一手势 |
| `OnTouchListener.onTouch` | 监听器先于 `onTouchEvent` 消费，true 会阻止默认 onTouchEvent | 只是一条旁路通知 |

再强调两个边界：

- `onInterceptTouchEvent(true)` 只说明父容器要拦截，父容器仍应正确实现 `onTouchEvent`。如果自身最终不消费，事件不会神奇地回到原子 View。
- `requestDisallowInterceptTouchEvent(true)` 只影响祖先是否调用拦截逻辑，不代表当前子 View 一定能消费事件。

## 5. 三条典型时间线

### 5.1 子 View 正常拥有整段手势

```text
DOWN
父 onIntercept = false
子 dispatch/onTouchEvent = true
父记录 TouchTarget = 子

MOVE
父 onIntercept = false
沿 TouchTarget 交给子

UP
交给子
清空 TouchTarget
```

### 5.2 父容器在 MOVE 阶段夺回手势

```text
DOWN
父不拦截 -> 子消费 -> 建立 TouchTarget

MOVE 1
位移未超过 touchSlop -> 父不拦截 -> 子继续收到 MOVE

MOVE 2
判断为父容器方向 -> 父拦截
子收到 ACTION_CANCEL
父 onTouchEvent 收到当前 MOVE

后续 MOVE / UP
只交给父容器
```

### 5.3 子 View 暂时禁止父容器拦截

```text
DOWN
子调用 requestDisallowInterceptTouchEvent(true)
标记沿 parent 链向上传递

MOVE
祖先 ViewGroup 看到 DISALLOW_INTERCEPT，跳过 onInterceptTouchEvent

子判断应该交给父容器
调用 requestDisallowInterceptTouchEvent(false)

下一次 MOVE
父容器重新获得 onInterceptTouchEvent 机会，可返回 true
子收到 CANCEL，父容器接管
```

注意：子 View 在处理某个 MOVE 时才解除禁止，父容器对这个 MOVE 的拦截阶段已经过去，因此通常从下一次事件开始接管，而不是时间倒流后重新处理当前 MOVE。

## 6. 滑动冲突的根本判断

所谓滑动冲突，通常是父子容器都能解释同一串 MotionEvent，例如：

- 横向 ViewPager2 + 纵向 RecyclerView。
- 可横向滑动的父容器 + 横向列表子容器。
- ScrollView + RecyclerView。
- 地图、图表或 WebView 嵌套在可滑动容器中。

处理前先回答四个问题：

1. 父子手势方向是否正交？
2. 如果方向相同，子 View 是否已经滚到边界？
3. 从点击切换到滑动的阈值是什么？通常应使用 `touchSlop`。
4. 手势一旦判定归属，是否在 UP/CANCEL 前保持稳定，避免来回抢夺？

外部拦截法与内部拦截法的区别不是算法不同，而是“由谁做所有权判断”。

## 7. 外部拦截法：父容器统一决定是否拦截

### 7.1 适用场景

- 父容器知道完整布局关系。
- 父子滑动方向清晰，例如父横向、子纵向。
- 希望冲突规则集中在父容器，子 View 保持通用。

### 7.2 核心逻辑

父容器在 `onInterceptTouchEvent` 中记录 DOWN，MOVE 超过 `touchSlop` 后判断方向：

- 更像父容器的手势：返回 true，父容器接管。
- 更像子 View 的手势：返回 false，继续交给子 View。
- UP/CANCEL：重置状态，通常不在此时突然拦截。

以下示例是“父容器横向拖动、子 View 纵向滚动”的核心实现：

```kotlin
import kotlin.math.abs
import kotlin.math.roundToInt

class HorizontalDragLayout @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : FrameLayout(context, attrs) {

    private val touchSlop = ViewConfiguration.get(context).scaledTouchSlop

    private var downX = 0f
    private var downY = 0f
    private var lastX = 0f
    private var dragging = false

    override fun onInterceptTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = event.x
                downY = event.y
                lastX = event.x
                dragging = false
                return false
            }

            MotionEvent.ACTION_MOVE -> {
                if (!dragging) {
                    val dx = event.x - downX
                    val dy = event.y - downY
                    val horizontalGesture =
                        abs(dx) > touchSlop && abs(dx) > abs(dy)

                    if (horizontalGesture) {
                        dragging = true
                        // 当前 MOVE 接下来会进入 onTouchEvent，避免第一次滚动突然跳过整段距离。
                        lastX = event.x
                    }
                }
                return dragging
            }

            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_CANCEL -> {
                dragging = false
                return false
            }
        }

        return false
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                lastX = event.x
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                val deltaX = event.x - lastX
                lastX = event.x
                scrollBy((-deltaX).roundToInt(), 0)
                return true
            }

            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_CANCEL -> {
                dragging = false
                return true
            }
        }

        return true
    }
}
```

真实组件还要补充滚动边界、速度跟踪、fling、pointer ID 切换，以及 `performClick`/无障碍语义。示例只展示冲突所有权的关键部分。

### 7.3 同方向嵌套时不能只比较 dx/dy

父子都是横向列表时，仅判断“横向”无法决定归属。还要判断子 View 是否能继续滚动，例如：

```kotlin
val fingerMovesRight = dx > 0
val childScrollDirection = if (fingerMovesRight) -1 else 1
val childCanContinue = child.canScrollHorizontally(childScrollDirection)

val parentShouldIntercept = horizontalGesture && !childCanContinue
```

这里的方向容易写反：手指向右移动时，内容通常要向左侧历史区域滚动，因此应结合具体组件验证 `canScrollHorizontally(direction)` 的方向语义。

## 8. 内部拦截法：子 View 决定何时让父容器接管

### 8.1 适用场景

- 子 View 更了解自己的滚动方向、缩放状态或边界。
- 父容器规则简单，但无法准确知道子组件内部能否继续滚动。
- 子组件需要在某些阶段独占手势，例如地图缩放、WebView 内部手势、图表拖动。

### 8.2 requestDisallowInterceptTouchEvent 做了什么

调用：

```kotlin
parent.requestDisallowInterceptTouchEvent(true)
```

会让直接父 ViewGroup 设置 `FLAG_DISALLOW_INTERCEPT`，然后继续向它的 parent 传递，所以影响的是整条祖先链，而不只是直接父容器。

ViewGroup 分发后续事件时，如果该标记存在，会跳过 `onInterceptTouchEvent`。传 false 会清除标记并继续向上传递。手势结束或新的 DOWN 到来时，系统也会清理这个标记。

### 8.3 父容器实现

经典内部拦截法中，父容器对 DOWN 不拦截，让子 View 先建立触摸目标；如果子 View 后续解除禁止，父容器再在 MOVE 阶段接管：

```kotlin
override fun onInterceptTouchEvent(event: MotionEvent): Boolean {
    return when (event.actionMasked) {
        MotionEvent.ACTION_DOWN -> false
        MotionEvent.ACTION_MOVE -> true
        MotionEvent.ACTION_UP,
        MotionEvent.ACTION_CANCEL -> false
        else -> false
    }
}
```

这段代码单独看会觉得“父容器总拦截 MOVE”，但正常情况下子 View 已经调用了 `requestDisallowInterceptTouchEvent(true)`，父容器的 MOVE 拦截方法会被框架直接跳过。只有子 View 解除禁止后，父容器才真正获得调用机会。

父容器仍然必须在 `onTouchEvent` 中实现实际滚动逻辑。

### 8.4 子 View 实现

下面以纵向 RecyclerView 嵌套在横向父容器为例：

```kotlin
import kotlin.math.abs

class ConflictAwareRecyclerView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : RecyclerView(context, attrs) {

    private val touchSlop = ViewConfiguration.get(context).scaledTouchSlop
    private var downX = 0f
    private var downY = 0f

    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = event.x
                downY = event.y
                // 先保证自己能看到后续 MOVE，再根据方向决定是否交还给父容器。
                parent.requestDisallowInterceptTouchEvent(true)
            }

            MotionEvent.ACTION_MOVE -> {
                val dx = event.x - downX
                val dy = event.y - downY

                if (abs(dx) > touchSlop || abs(dy) > touchSlop) {
                    val childShouldHandle = abs(dy) >= abs(dx)
                    parent.requestDisallowInterceptTouchEvent(childShouldHandle)
                }
            }

            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_CANCEL -> {
                parent.requestDisallowInterceptTouchEvent(false)
            }
        }

        return super.dispatchTouchEvent(event)
    }
}
```

流程是：

1. DOWN 时子 View 禁止祖先拦截。
2. MOVE 超过 touchSlop 后判断方向。
3. 纵向手势继续禁止拦截，由 RecyclerView 处理。
4. 横向手势解除禁止，父容器从下一次可拦截的事件开始接管。
5. 子 View 随后收到 CANCEL，清理自己的滑动状态。

### 8.5 内部拦截法的限制

- 子 View 必须先收到 DOWN，才能执行禁止拦截。如果它和自己的子节点都没有消费 DOWN，后续方案无法按预期工作。
- `requestDisallowInterceptTouchEvent` 不是立即把当前事件重新发给父容器；解除禁止通常影响后续事件。
- 多层嵌套时标记会向所有祖先传播，可能同时影响外层 AppBar、ViewPager2 等组件。
- 系统返回手势等特殊输入可能有额外优先级，不能把它当成绝对不可拦截锁。

## 9. 外部拦截法和内部拦截法怎么选

| 对比项 | 外部拦截法 | 内部拦截法 |
|---|---|---|
| 谁决定归属 | 父容器 | 子 View |
| 核心入口 | `onInterceptTouchEvent` | `requestDisallowInterceptTouchEvent` |
| 规则位置 | 集中在父容器 | 分散到了解业务的子 View |
| 子 View 是否要定制 | 通常不用 | 通常需要自定义或包装 |
| 适合场景 | 父容器知道方向和布局关系 | 子 View 更了解边界、缩放或内部状态 |
| 常见风险 | 父容器过早拦截，点击和纵向滚动失效 | 忘记在 UP/CANCEL 清理，或多层祖先都被禁止拦截 |

如果组件本身支持 Nested Scrolling，例如 RecyclerView、NestedScrollView、CoordinatorLayout，父子同方向协作通常应优先使用嵌套滚动协议。外部/内部拦截法解决的是原始 MotionEvent 所有权；Nested Scrolling 解决的是滚动距离、预滚动、剩余距离和 fling 如何在父子之间协作，两者不是同一个层次。

## 10. 容易答错或写错的边界情况

### 10.1 dispatchTouchEvent 返回 true，不等于父容器拦截

ViewGroup 返回 true 可能只是某个子 View 消费了事件。是否拦截要看 `onInterceptTouchEvent` 以及 TouchTarget 状态。

### 10.2 DOWN 返回 false，后续 MOVE 通常不会再给这个 View

无论是 `OnTouchListener` 还是 `onTouchEvent`，如果 DOWN 最终没有被当前 View 的分发链处理，系统不会因为后来发生了 MOVE 就重新把完整手势交给它。

### 10.3 父容器中途拦截后，子 View 收到的是 CANCEL

不是先给子 View 一个普通 MOVE 再同时给父容器。CANCEL 是子 View 清理 pressed、长按、拖拽和动画状态的信号。

### 10.4 onInterceptTouchEvent 不是实际滚动代码的位置

它只做“是否接管”的决策。实际消费、位移、速度跟踪和 fling 应在父容器的 `onTouchEvent` 或专门手势处理器中完成。

### 10.5 不要在 MOVE 中反复改变归属

如果没有方向锁定和 touchSlop，细小抖动会让父子容器来回争抢。通常一旦判定为横向或纵向，在 UP/CANCEL 前保持稳定。

### 10.6 clickable 的 disabled View 也可能消费事件

AOSP 的 `View.onTouchEvent` 中，disabled 但 clickable 的 View 可以返回 true，只是不执行正常点击响应。因此“控件禁用就一定不消费事件”并不准确。

### 10.7 自定义触摸必须保留点击和无障碍语义

如果自定义 View 在 `onTouchEvent` 中识别点击，应调用 `performClick()`，并重写 `performClick` 调用 `super.performClick()`。只在 UP 时直接执行业务代码，会遗漏无障碍、键盘触发、点击声音等语义。

### 10.8 ACTION_OUTSIDE 默认不会分发给 ViewGroup 子节点

需要在 Window.Callback 或 ViewGroup 的 `dispatchTouchEvent` 中自行处理，不能把它当成普通越界 MOVE。

## 11. 排查事件分发时怎么打日志

建议同时在父容器和目标子 View 记录：

```kotlin
private fun MotionEvent.debugAction(): String = MotionEvent.actionToString(actionMasked)

override fun dispatchTouchEvent(event: MotionEvent): Boolean {
    Log.d("TouchTrace", "parent dispatch ${event.debugAction()}")
    val handled = super.dispatchTouchEvent(event)
    Log.d("TouchTrace", "parent dispatch result=$handled")
    return handled
}

override fun onInterceptTouchEvent(event: MotionEvent): Boolean {
    val intercepted = shouldIntercept(event)
    Log.d("TouchTrace", "parent intercept ${event.debugAction()} -> $intercepted")
    return intercepted
}
```

排查时关注的不是单个 true/false，而是完整序列：

- DOWN 最终由谁返回 true？
- MOVE 时父容器是否被 `DISALLOW_INTERCEPT` 跳过？
- 子 View 是否收到了 CANCEL？
- UP/CANCEL 后状态是否清理？
- 多指时当前跟踪的是 pointer ID 还是易变化的 index？

## 12. 面试回答模板

可以先用 30 秒回答主链路：

> 触摸事件从 ViewRootImpl 进入 DecorView，经 Activity 和 Window 回到 DecorView 的 ViewGroup 分发。ViewGroup 在 DOWN 时清理旧状态，通过 onInterceptTouchEvent 判断是否拦截；未拦截时倒序命中子 View，子 View 消费 DOWN 后会被记录为 TouchTarget。后续 MOVE/UP 沿 TouchTarget 分发。父容器如果中途拦截，子 View 会收到 ACTION_CANCEL，之后事件交给父容器 onTouchEvent。滑动冲突可用外部拦截法让父容器按方向决定，或内部拦截法让子 View 用 requestDisallowInterceptTouchEvent 控制祖先是否有拦截机会。

继续追问时再展开：

- `mFirstTouchTarget` 为什么决定后续分发。
- DISALLOW_INTERCEPT 如何沿 parent 链传播和重置。
- 外部/内部拦截的代码、touchSlop 和方向锁定。
- 同方向嵌套为什么还要看 `canScrollHorizontally/Vertically` 或 Nested Scrolling。
- CANCEL、OnTouchListener、performClick、多指 pointer ID 等边界。

## 13. 当前官方与源码参考

- [Handling touch events in a ViewGroup](https://developer.android.com/develop/ui/views/touch-and-input/gestures/viewgroup)
- [Handling Input Events in Android Views](https://developer.android.com/develop/ui/views/touch-and-input/input-events)
- [Handle multi-touch gestures](https://developer.android.com/develop/ui/views/touch-and-input/gestures/multi)
- [AOSP ViewRootImpl.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/view/ViewRootImpl.java)
- [AOSP DecorView.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/com/android/internal/policy/DecorView.java)
- [AOSP Activity.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/app/Activity.java)
- [AOSP ViewGroup.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/view/ViewGroup.java)
- [AOSP View.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/view/View.java)

> 源码核对日期：2026-07-23，基于 AOSP `refs/heads/main`。`mFirstTouchTarget`、`FLAG_DISALLOW_INTERCEPT` 等属于实现细节，未来版本可能调整；DOWN 建立手势、父容器可拦截、子 View 收到 CANCEL 等公开行为契约更稳定。
